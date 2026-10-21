import importlib.util
import unittest
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('preserve',Path(__file__).resolve().parents[1]/'scripts/mes_timestral_preserve.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
P=dict(gap=2,hold_z=3,hold_ratio=.05,early_scale=None,early_z=None)

class PreserveTests(unittest.TestCase):
    def run_case(self,ratios,z=None,params=None,resets=None):
        keys=[('r',i+1) for i in range(len(ratios))]
        out=m.preserve_alerts(keys,np.array(z if z is not None else [4]*len(keys))[:,None],
            np.array(ratios)[:,None],{k:{'e'} for k in keys},['e'],resets or [False]*len(keys),params or P)
        return [bool(out[k]) for k in keys]

    def test_original_on_never_removed_and_gap_is_bounded(self):
        self.assertEqual(self.run_case([.2,.08,.08,.08,.2]),[True,True,True,False,True])
        self.assertEqual(self.run_case([.2,.08,.2],z=[np.nan,np.nan,1]),[True,False,True])

    def test_failed_evidence_cannot_restart_a_gap(self):
        self.assertEqual(self.run_case([.2,.01,.08,.08]),[True,False,False,False])
        self.assertEqual(self.run_case([.2,.08,.08],resets=[False,True,False]),[True,False,False])

    def test_no_future_backfill(self):
        self.assertEqual(self.run_case([.08,.2,.08]),[False,True,True])
        self.assertEqual(self.run_case([.2,.08]),self.run_case([.2,.08,.2])[:2])

    def test_early_does_not_refresh_original_anchor(self):
        p=dict(P,early_scale=1,early_z=2)
        self.assertEqual(self.run_case([.2,1.2,.08,.08],z=[4,2.5,4,4],params=p),[True,True,True,False])
        self.assertEqual(self.run_case([1.2,.08],z=[2.5,4],params=p),[True,False])

    def test_control_is_exact_original(self):
        self.assertEqual(self.run_case([.2,.08,1.6,0],params=dict(P,gap=0)),[True,False,True,False])

    def test_selection_preserves_events_false_alarm_and_common_delays(self):
        b=dict(detected_events=10,wrong_alert_equipment_seconds=2,duplicate_alert_episodes=10,p95_onset_delay_seconds=8)
        good=dict(b,duplicate_alert_episodes=5,p95_onset_delay_seconds=7)
        control=dict(params=dict(P,gap=0),metrics=[b]*3,lost=[0]*3,delayed=[0]*3)
        rows=[control,dict(params=P,metrics=[good]*3,lost=[0]*3,delayed=[0]*3),
            dict(params=dict(P,gap=3),metrics=[dict(good,duplicate_alert_episodes=0)]*3,lost=[1,0,0],delayed=[0]*3)]
        selected,passed=m.choose(rows,[b]*3)
        self.assertTrue(passed);self.assertEqual(selected['params'],P)
        self.assertFalse(m.choose([control],[b]*3)[1])

if __name__=='__main__':unittest.main()
