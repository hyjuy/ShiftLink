"""Retain confirmed pre-stop evidence without creating a new alarm."""
import copy,json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase,main
from scripts import mes_causal_pda_service as m
from tests.test_mes_causal_pda_service import rows,source_config
from tests.test_mes_causal_v14_stream import config,channel_choices,modify
from shiftlink.pda.ai_insights import read_insights

class FaultStopTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'checkpoint.json'
        self.binding=m.BoundSource(config(),source_config());self.data=rows(180);self.key=channel_choices()[1]
    def detected(self):
        modify(self.data,[self.key],96,112,6.)
        a=m.AdvisorySession(self.binding,self.path)
        for f in self.data[:112]:a.feed(f,self.binding.config_id)
        self.assertEqual(len(a.report(self.data[111])['items']),1)
        return a
    def stopped(self,index=112,mode='fault',alarm=False):
        f=copy.deepcopy(self.data[index]);f['line_mode']=mode
        for e in f['equipment']:
            if e['equipment_id']==self.key[0]:e.update(operating_state='stopped',fault_level='critical' if alarm else 'normal')
        f['active_alarms']=[dict(equipment_id=self.key[0],code='existing')] if alarm else []
        return f
    def test_fault_retains_same_event_across_long_stop_and_restart(self):
        a=self.detected();event=a.report(self.data[111])['items'][0]['event_id']
        for i in range(112,175):self.assertFalse(a.feed(self.stopped(i),self.binding.config_id))
        value=a.report(self.stopped(174));self.assertEqual(value['status'],'stopped');self.assertEqual(value['items'][0]['event_id'],event)
        self.assertEqual(value['items'][0]['state'],'before_stop');self.assertEqual(value['items'][0]['stop_sequence'],112)
        a.flush();b=m.AdvisorySession(self.binding,self.path);self.assertEqual(b.report(self.stopped(174))['items'],value['items'])
        output=Path(self.tmp.name)/'latest.json';output.write_text(json.dumps(b.report(self.stopped(174))))
        self.assertEqual(read_insights(output,self.stopped(174),self.binding.config_id)['items'],value['items'])
    def test_same_sequence_fault_is_durable_and_does_not_reissue(self):
        a=self.detected();state=self.stopped(111)|dict(is_synthetic=True)
        first=m.poll(a,'http://unused',state);self.assertEqual(first['status'],'stopped');self.assertEqual(a.detector.warm,0)
        b=m.AdvisorySession(self.binding,self.path);self.assertEqual(m.poll(b,'http://unused',state)['items'],first['items'])
    def test_individual_fault_stop_retains_while_line_is_running(self):
        a=self.detected();f=self.stopped(mode='running',alarm=True);a.feed(f,self.binding.config_id)
        self.assertEqual(a.report(f)['items'][0]['state'],'before_stop')
    def test_normal_pause_old_evidence_resume_run_and_gap_do_not_retain(self):
        for kind in ('normal','expired','resume','run','gap'):
            with self.subTest(kind=kind):
                self.path.unlink(missing_ok=True);self.data=rows(180);a=self.detected()
                if kind=='normal':f=self.stopped(mode='paused')
                else:f=self.stopped()
                if kind=='expired':
                    for g in self.data[112:155]:a.feed(g,self.binding.config_id)
                    f=self.stopped(155)
                a.feed(f,self.binding.config_id)
                if kind=='resume':f=self.data[113];a.feed(f,self.binding.config_id)
                if kind=='run':f=self.stopped(113)|dict(run_id='new');a.feed(f,self.binding.config_id)
                if kind=='gap':f=self.stopped(115);a.feed(f,self.binding.config_id)
                self.assertEqual(a.report(f)['items'],[])
    def test_old_checkpoint_is_compatible_and_corrupt_stop_is_rejected(self):
        a=self.detected();a.flush();value=json.loads(self.path.read_text());value.pop('stopped_notices',None);self.path.write_text(json.dumps(value));m.AdvisorySession(self.binding,self.path)
        a.feed(self.stopped(),self.binding.config_id);a.flush();value=json.loads(self.path.read_text())
        value['stopped_notices'][self.key[0]]['stop_sequence']=True;self.path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):m.AdvisorySession(self.binding,self.path)
    def test_single_brief_and_small_spikes_do_not_notify_but_sustained_does(self):
        for length,z,expected in ((1,20.,False),(2,6.,False),(6,1.5,False),(12,6.,True)):
            with self.subTest(length=length,z=z):
                data=rows(130);modify(data,[self.key],96,96+length,z);a=m.AdvisorySession(self.binding,Path(self.tmp.name)/f'spike-{length}.json')
                notices=[eq for f in data for eq in a.feed(f,self.binding.config_id)]
                self.assertEqual(self.key[0] in notices,expected)

if __name__=='__main__':main()
