"""Manual stops retain existing evidence, never new decisions or alarms."""
import copy,json
from pathlib import Path
from unittest import TestCase
from tests import test_pda_fault_stop as baseline
from scripts import mes_causal_pda_service as m
from shiftlink.pda.ai_insights import read_insights

class ManualStopTests(TestCase):
    setUp=baseline.FaultStopTests.setUp
    detected=baseline.FaultStopTests.detected
    stopped=baseline.FaultStopTests.stopped

    def test_manual_pause_same_sequence_preserves_identity_restart_and_reader(self):
        for mode in ('paused','stopped'):
            with self.subTest(mode=mode):
                self.path.unlink(missing_ok=True);a=self.detected()
                before=a.report(self.data[111])['items'][0];state=copy.deepcopy(self.data[111]);state.update(line_mode=mode,is_synthetic=True)
                # MesEngine.pause changes line_mode without rewriting equipment states.
                original=copy.deepcopy(state);first=m.poll(a,'http://unused',state)
                self.assertEqual(first['status'],'stopped');self.assertEqual(len(first['items']),1)
                row=first['items'][0];self.assertEqual(row['event_id'],before['event_id']);self.assertEqual(row['observed_at'],before['observed_at']);self.assertEqual(row['state'],'before_stop')
                self.assertEqual(a.detector.warm,0);self.assertEqual(state,original)
                restored=m.AdvisorySession(self.binding,self.path)
                for _ in range(3):self.assertEqual(m.poll(restored,'http://unused',state)['items'],first['items'])
                output=Path(self.tmp.name)/'manual-latest.json';output.write_text(json.dumps(restored.report(state)))
                shown=read_insights(output,state,self.binding.config_id);self.assertEqual(shown['items'],first['items']);self.assertFalse(shown['operational_notifications'])
                self.assertEqual(m.poll(restored,'http://unused',self.data[111]|dict(is_synthetic=True))['items'],[])

    def test_manual_stop_advanced_frames_do_not_analyze_or_repeat(self):
        a=self.detected();before=a.report(self.data[111])['items'][0]
        for i in range(112,175):
            f=self.stopped(i,mode='stopped')
            for row in f['measurements']:row['value']=999999.
            self.assertFalse(a.feed(f,self.binding.config_id))
            self.assertEqual(a.detector.warm,0)
        value=a.report(f);self.assertEqual(value['status'],'stopped');self.assertEqual(len(value['items']),1)
        self.assertEqual(value['items'][0]['event_id'],before['event_id']);self.assertEqual(value['items'][0]['stop_sequence'],112)
        a.flush();self.assertEqual(m.AdvisorySession(self.binding,self.path).report(f)['items'],value['items'])

    def test_individual_manual_stop_retains_without_mes_alarm(self):
        a=self.detected();before=a.report(self.data[111])['items'][0];f=self.stopped(mode='running',alarm=False)
        self.assertEqual(f['active_alarms'],[]);original=copy.deepcopy(f)
        self.assertFalse(a.feed(f,self.binding.config_id));value=a.report(f)
        self.assertEqual(len(value['items']),1);self.assertEqual(value['items'][0]['event_id'],before['event_id']);self.assertEqual(value['items'][0]['state'],'before_stop');self.assertEqual(f,original)
        output=Path(self.tmp.name)/'individual.json';output.write_text(json.dumps(value));self.assertEqual(read_insights(output,f,self.binding.config_id)['items'],value['items'])
