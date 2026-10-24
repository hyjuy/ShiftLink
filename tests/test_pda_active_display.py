"""Pi-only display lifecycle: replay -> durable session -> advisory reader."""
import copy,json,gzip,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from scripts import mes_causal_pda_service as worker
from scripts.mes_causal_lifecycle import LifecycleSource
try:
    from scripts.mes_causal_active_advisory import ActiveAdvisorySession as Session,ActiveAdvisorySource as Source
except ModuleNotFoundError:
    Session=worker.AdvisorySession;Source=LifecycleSource
from shiftlink.pda.ai_insights import read_insights,overlay_state
ROOT=Path(__file__).resolve().parents[1]
OLD=Path('/home/pi/shiftlink/analytics/validation/fault-lifecycle-20261024')

class ActiveDisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(OLD/'development/cases/002-hydraulic_leak-intermittent-2.json.gz','rt') as f:cls.frames=json.load(f)
        load=lambda p:json.loads((ROOT/p).read_text())
        cls.binding=Source(load('docs/research/evidence/mes-causal-v14c-20261023/settings.json'),load('deploy/analytics/source-config.json'),load('deploy/analytics/normal-profile.json'))
        cls.eq='EQ-0001'
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'checkpoint.json'
        self.s=Session(self.binding,self.path);self.s.defer_flush=True
    def feed_to(self,index):
        for frame in self.frames[max(0,self.s.cursor):index+1]:self.s.feed(frame,self.binding.config_id)
        return self.frames[index]
    def read(self,value,state):
        p=Path(self.tmp.name)/'output.json';p.write_text(json.dumps(value));return read_insights(p,state,self.binding.config_id)
    def test_long_fault_and_short_normal_gaps_stay_visible_until_observed_recovery(self):
        ids=set();notices=[];active=0
        for i,f in enumerate(self.frames):
            notices.extend(self.s.feed(f,self.binding.config_id));k=self.s.detector.equipment.index(self.eq)
            items=[r for r in self.s.report(f)['items'] if r['equipment_id']==self.eq]
            if self.s.detector.episode_on[k]:
                self.assertEqual(len(items),1,f'confirmed fault hidden at index {i}');active+=1
                ids.add(items[0]['event_id'])
                self.assertEqual(self.read(self.s.report(f),f)['items'],items)
            elif i>104:self.assertEqual(items,[],'recovered event remained visible')
        self.assertEqual(notices,[self.eq]);self.assertEqual(len(ids),1);self.assertGreater(active,200)
    def test_restart_and_duplicate_input_keep_event_identity(self):
        f=self.feed_to(160);before=self.s.report(f)['items'];self.assertEqual(len(before),1)
        self.s.flush();self.s=Session(self.binding,self.path);self.assertEqual(self.s.report(f)['items'],before)
        self.assertEqual(self.s.feed(f,self.binding.config_id),set());self.assertEqual(self.s.report(f)['items'],before)
    def stopped(self,f,mode):
        state=copy.deepcopy(f);state['line_mode']=mode;state['is_synthetic']=True
        if mode in ('running','fault'):
            for eq in state['equipment']:
                if eq['equipment_id']==self.eq:eq['operating_state']='stopped'
        return state
    def test_late_manual_pause_and_individual_stop_keep_same_event_after_restart(self):
        for mode in ('paused','stopped','fault','running'):
            with self.subTest(mode=mode):
                self.path.unlink(missing_ok=True);self.s=Session(self.binding,self.path);self.s.defer_flush=True
                f=self.feed_to(160);before=self.s.report(f)['items'];self.assertEqual(len(before),1)
                state=self.stopped(f,mode);original=copy.deepcopy(state)
                with patch.object(worker,'AdvisorySession',Session):result=worker.poll(self.s,'http://unused',state)
                self.assertEqual(len(result['items']),1);row=result['items'][0]
                self.assertEqual(row['state'],'before_stop');self.assertEqual(row['event_id'],before[0]['event_id'])
                self.assertEqual(self.read(result,state)['items'],result['items']);self.assertEqual(state,original)
                self.s.flush();self.s=Session(self.binding,self.path)
                self.assertEqual(self.s.report(state)['items'],result['items'])
    def test_resume_after_pause_keeps_identity_until_recovery_and_run_change_clears(self):
        f=self.feed_to(160);before=self.s.report(f)['items'][0]['event_id'];state=self.stopped(f,'paused')
        with patch.object(worker,'AdvisorySession',Session):worker.poll(self.s,'http://unused',state)
        self.s.flush();self.s=Session(self.binding,self.path);self.s.defer_flush=True
        emitted=[]
        for frame in self.frames[161:250]:emitted.extend(self.s.feed(frame,self.binding.config_id))
        self.assertNotIn(self.eq,emitted);self.assertEqual(self.s.report(self.frames[249])['items'][0]['event_id'],before)
        fresh=copy.deepcopy(self.frames[250]);fresh['run_id']='other';self.s.feed(fresh,self.binding.config_id)
        self.assertEqual(self.s.report(fresh)['items'],[])

    def test_stale_bad_quality_lag_and_new_run_do_not_fabricate_current_results(self):
        f=self.feed_to(160)
        for change in (dict(run_id='new'),dict(sequence=f['sequence']+4)):
            self.assertEqual(self.s.report(f|change)['items'],[])
        self.assertEqual(self.s.report(f,stalled=True)['items'],[])
        bad=copy.deepcopy(self.frames[161])
        for m in bad['measurements']:m['quality']='bad'
        self.s.feed(bad,self.binding.config_id)
        self.assertEqual(self.s.report(bad)['items'],[])
        self.assertTrue(self.s.detector.episode_on[self.s.detector.equipment.index(self.eq)])
        value=self.s.report(f);value['generated_at']=(datetime.now(timezone.utc)-timedelta(seconds=11)).isoformat()
        self.assertEqual(self.read(value,f)['items'],[])
    def test_long_stop_confirmation_must_be_valid_and_not_stale_at_stop(self):
        f=self.feed_to(160);state=self.stopped(f,'paused')
        with patch.object(worker,'AdvisorySession',Session):value=worker.poll(self.s,'http://unused',state)
        self.assertEqual(len(value['items']),1)
        for change in (dict(confirmed_sequence=True),dict(confirmed_sequence=f['sequence']+1),dict(confirmed_at=f['simulated_at'].replace('2026','2025')),dict(confirmed_sequence=105)):
            invalid=copy.deepcopy(value);invalid['items'][0].update(change)
            self.assertEqual(self.read(invalid,state)['items'],[])
    def test_overlay_preserves_legacy_alarms_and_deduplicates_equipment(self):
        f=copy.deepcopy(self.feed_to(160));f['active_alarms']=[dict(equipment_id=self.eq,code='EXISTING')]
        value=self.s.report(f);self.assertEqual(len(value['items']),1);value['items']*=2
        p=Path(self.tmp.name)/'output.json';p.write_text(json.dumps(value));original=copy.deepcopy(f)
        result=overlay_state(f,p);self.assertEqual(f,original);self.assertEqual(result['active_alarms'],original['active_alarms'])
        self.assertEqual(len(result['ai_insights']['items']),1);self.assertFalse(result['ai_insights']['operational_notifications'])

if __name__=='__main__':unittest.main()
