"""Pi regression for three consumed duplicate cases; original input stays intact."""
import gzip,json,os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from scripts.mes_causal_pda_service import AdvisorySession,BoundSource
from scripts.mes_causal_episode import EpisodeSource as Source,RECOVERY_FRAMES
import copy,numpy as np
ROOT=Path(__file__).resolve().parents[1]
FIXTURES=Path(os.environ.get('SHIFTLINK_RANDOM_INJECTION_ROOT','/home/pi/shiftlink/analytics/validation/random-injection-20261024'))

@unittest.skipUnless((FIXTURES/'plan.json').exists(),'consumed Pi random-injection fixtures required')
class ConsumedDuplicates(unittest.TestCase):
    def check_case(self,name):
        plan=json.loads((FIXTURES/'plan.json').read_text());case=next(c for c in plan['cases'] if c['id']==name)
        settings=json.loads((ROOT/'docs/research/evidence/mes-causal-v14c-20261023/settings.json').read_text())
        config=json.loads((ROOT/'deploy/analytics/source-config.json').read_text());profile=json.loads((ROOT/'deploy/analytics/normal-profile.json').read_text())
        binding=Source(settings,config,normal_profile=profile)
        with gzip.open(FIXTURES/'cases'/(name+'.json.gz'),'rt') as f:frames=json.load(f)
        with TemporaryDirectory() as tmp:
            session=AdvisorySession(binding,Path(tmp)/'checkpoint.json');events=[]
            for frame in frames:
                if case['event']['equipment_id'] in session.feed(frame,binding.config_id):events.append(frame['sequence'])
        self.assertEqual(events[0],{'friction-02':149,'friction-03':133,'variance-01':136}[name],'first notice changed')
        self.assertEqual(len(events),1,'same injected incident produced multiple first notices: '+str(events))
    def first_session(self,tmp):
        settings=json.loads((ROOT/'docs/research/evidence/mes-causal-v14c-20261023/settings.json').read_text())
        config=json.loads((ROOT/'deploy/analytics/source-config.json').read_text());profile=json.loads((ROOT/'deploy/analytics/normal-profile.json').read_text())
        binding=Source(settings,config,profile)
        with gzip.open(FIXTURES/'cases/friction-02.json.gz','rt') as f:frames=json.load(f)
        path=Path(tmp)/'checkpoint.json';session=AdvisorySession(binding,path)
        for f in frames[:149]:session.feed(f,binding.config_id)
        self.assertTrue(session.detector.episode_on[session.detector.equipment.index('EQ-0004')])
        return binding,session,path,frames
    def test_session_checkpoint_and_duplicate_frame_preserve_first_notice(self):
        with TemporaryDirectory() as tmp:
            binding,session,path,frames=self.first_session(tmp);session.flush();restored=AdvisorySession(binding,path)
            state=restored.detector.context_state();self.assertEqual(restored.feed(frames[148],binding.config_id),set());self.assertEqual(restored.detector.context_state(),state)
            for f in frames[149:]:self.assertEqual(restored.feed(f,binding.config_id),set())
    def test_manual_stop_history_and_hold_do_not_reissue_existing_notice(self):
        from scripts import mes_causal_pda_service as service
        from shiftlink.pda.ai_insights import read_insights
        with TemporaryDirectory() as tmp:
            binding,session,path,frames=self.first_session(tmp);identity=session.notices['EQ-0004']['event_id']
            held=copy.deepcopy(frames[149]);previous={(m['equipment_id'],m['signal']):m for m in frames[148]['measurements']}
            for m in held['measurements']:m['value']=previous[m['equipment_id'],m['signal']]['value']
            self.assertEqual(session.feed(held,binding.config_id),set());self.assertTrue(session.detector.last_status['hold'])
            stopped=copy.deepcopy(held);stopped['line_mode']='paused';value=service.poll(session,'http://unused',stopped)
            self.assertEqual(value['items'][0]['event_id'],identity);self.assertEqual(value['items'][0]['state'],'before_stop')
            output=Path(tmp)/'latest.json';output.write_text(json.dumps(value));self.assertEqual(read_insights(output,stopped,binding.config_id)['items'],value['items'])
            restored=AdvisorySession(binding,path);self.assertEqual(service.poll(restored,'http://unused',stopped)['items'],value['items'])
    def test_friction_thermal_then_level_is_one_notice(self):self.check_case('friction-02')
    def test_second_friction_thermal_then_level_is_one_notice(self):self.check_case('friction-03')
    def test_variance_dip_is_not_complete_recovery(self):self.check_case('variance-01')



class EpisodeUnits(unittest.TestCase):
    def setUp(self):
        self.settings=json.loads((ROOT/'docs/research/evidence/mes-causal-v14c-20261023/settings.json').read_text())
        self.config=json.loads((ROOT/'deploy/analytics/source-config.json').read_text())
        self.profile=json.loads((ROOT/'deploy/analytics/normal-profile.json').read_text())
        self.binding=Source(self.settings,self.config,self.profile);self.d=self.binding.new_detector()
        self.eq=self.d.equipment[3];self.k=3;self.j=int(self.d.indexes[self.k][0]);self.n=len(self.d.aug_limits)
    def evidence(self,high=False):
        level=np.zeros(self.n);level[self.j]=self.d.aug_limits[self.j]*2 if high else 0
        return level,np.zeros(self.n,bool),np.ones(self.n,bool)
    def test_routes_share_first_notice_and_new_equipment_stays_independent(self):
        x=self.evidence(True);self.assertEqual(self.d._merge({self.eq},*x),{self.eq})
        self.assertEqual(self.d._merge({self.eq},*x),set())
        other=self.d.equipment[4];x[0][int(self.d.indexes[4][0])]=self.d.aug_limits[int(self.d.indexes[4][0])]*2
        self.assertEqual(self.d._merge({other},*x),{other})
    def test_five_valid_healthy_frames_allow_a_nearby_new_first_notice(self):
        self.d._merge({self.eq},*self.evidence(True))
        for _ in range(RECOVERY_FRAMES-1):self.d._merge(set(),*self.evidence())
        self.assertTrue(self.d.episode_on[self.k]);self.d._merge(set(),*self.evidence());self.assertFalse(self.d.episode_on[self.k])
        self.assertEqual(self.d._merge({self.eq},*self.evidence(True)),{self.eq})
    def test_unknown_source_does_not_count_as_recovery(self):
        self.d._merge({self.eq},*self.evidence(True));x=self.evidence();x[0][self.j]=np.nan
        for _ in range(10):self.d._merge(set(),*x)
        self.assertTrue(self.d.episode_on[self.k]);self.assertEqual(self.d.episode_quiet[self.k],0)
    def test_hysteresis_rejects_shallow_dips(self):
        self.d._merge({self.eq},*self.evidence(True));x=self.evidence();x[0][self.j]=self.d.aug_limits[self.j]*.8
        for _ in range(10):self.d._merge(set(),*x)
        self.assertTrue(self.d.episode_on[self.k])
    def test_flat_history_reconstruction_is_not_recovery(self):
        x=self.evidence();x[1][self.j]=True;self.d._merge({self.eq},*x)
        x=self.evidence();x[2][self.j]=False
        for _ in range(10):self.d._merge(set(),*x)
        self.assertTrue(self.d.episode_on[self.k]);self.assertEqual(self.d.episode_quiet[self.k],0)
    def test_checkpoint_roundtrip_preserves_episode_and_quiet_count(self):
        self.d._merge({self.eq},*self.evidence(True));self.d._merge(set(),*self.evidence());state=self.d.context_state();other=self.binding.new_detector();other.load_context(state)
        self.assertEqual(other.context_state(),state);self.assertEqual(other._merge({self.eq},*self.evidence(True)),set())
    def test_checkpoint_rejects_corrupt_or_cross_equipment_evidence(self):
        original=self.d.context_state();cases=[]
        for key in ['on','quiet','process','flat']:
            state=copy.deepcopy(original);state['episode'][key]=[];cases.append(state)
        state=copy.deepcopy(original);state['episode']['quiet'][0]=RECOVERY_FRAMES;cases.append(state)
        state=copy.deepcopy(original);state['episode']['on'][0]=1;cases.append(state)
        state=copy.deepcopy(original);state['episode']['process'][0][int(self.d.indexes[1][0])]=True;cases.append(state)
        state=copy.deepcopy(original);state['episode']['process'][0][int(self.d.indexes[0][0])]=True;cases.append(state)
        cases.extend([None,{},dict(original,episode={})])
        for state in cases:
            with self.subTest(state=state),self.assertRaises(ValueError):self.d.load_context(state)
        self.assertEqual(self.d.context_state(),original)
    def test_binding_cannot_silently_restore_an_operating_checkpoint(self):
        original=BoundSource(self.settings,self.config,self.profile);self.assertNotEqual(original.fingerprint,self.binding.fingerprint)
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'state.json';AdvisorySession(original,p).flush()
            with self.assertRaisesRegex(ValueError,'binding mismatch'):AdvisorySession(self.binding,p)
        with self.assertRaises(ValueError):Source(self.settings,self.config)
if __name__=='__main__':unittest.main()
