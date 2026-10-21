import importlib.util
import unittest
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('stateful',Path(__file__).resolve().parents[1]/'scripts/mes_timestral_stateful.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
P=dict(gate=.1,on_scale=1,on_z=3,off_z=2,release=1)

class StatefulTests(unittest.TestCase):
    def test_hold_requires_current_evidence_after_ewma_turns_off(self):
        got=m.hold_evidence(np.array([4,4,4,1,np.nan]),np.array([0,.05,.2,2,2]),np.array([True,False,False,True,True]),2.5,.1)
        np.testing.assert_equal(got,[True,False,True,False,False])

    def run_case(self,z,ratio,*,baseline=True,resets=None,params=None,use_timestral=True):
        keys=[('a',i) for i in range(len(z))]
        alerts=m.stateful_alerts(keys,np.array(z)[:,None],np.array(ratio)[:,None],
            {key:{'e'} if baseline else set() for key in keys},['e'],resets or [False]*len(keys),params or P,use_timestral=use_timestral)
        return [bool(alerts[key]) for key in keys]

    def test_hold_survives_ts_dips_and_releases_current_frame(self):
        self.assertEqual(self.run_case([4,4,4,1,1],[.2,0,.05,.2,.2]),[True,True,True,False,False])

    def test_stale_ewma_cannot_reopen_when_raw_is_normal(self):
        self.assertEqual(self.run_case([4,1,1,1],[.2,.8,.8,.8]),[True,False,False,False])

    def test_extra_start_is_immediate_and_requires_current_raw(self):
        self.assertEqual(self.run_case([1,3.5,3.5],[2,2,0],baseline=False),[False,True,True])

    def test_release_counter_missing_and_resets(self):
        self.assertEqual(self.run_case([4,1,4,1,1,4,np.nan],[.2]*7,params=dict(P,release=2)),[True,True,True,True,False,True,False])
        self.assertEqual(self.run_case([4,4,4],[.2,0,0],resets=[False,True,False]),[True,False,False])

    def test_causal_and_ablation(self):
        self.assertEqual(self.run_case([4,4],[2,0],baseline=False,use_timestral=False),[False,False])
        self.assertEqual(self.run_case([4,4],[0,0],use_timestral=False),[True,True])
        self.assertEqual(self.run_case([4,4],[.2,0]),self.run_case([4,4,10],[.2,0,10])[:2])

    def test_selection_checks_all_four_metrics_on_each_dataset(self):
        base=dict(detected_events=10,wrong_alert_equipment_seconds=5,duplicate_alert_episodes=3,p95_onset_delay_seconds=4)
        good=dict(base,detected_events=11,wrong_alert_equipment_seconds=4)
        bad=dict(good,duplicate_alert_episodes=30)
        rows=[{'params':dict(P,on_scale=1.5),'metrics':[good,bad]}, {'params':P,'metrics':[good,good]}]
        chosen,passed=m.choose(rows,[base,base])
        self.assertTrue(passed);self.assertEqual(chosen['params'],P)
        self.assertFalse(m.choose(rows[:1],[base,base])[1])

if __name__=='__main__':unittest.main()
