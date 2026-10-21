import importlib.util
import unittest
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('continuity',Path(__file__).resolve().parents[1]/'scripts/mes_timestral_continuity.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
P=dict(clean_z=0,gap=2,hold_z=3,peak_fraction=.75,early_scale=None,early_z=None)


class ContinuityTests(unittest.TestCase):
    def run_case(self,wanted,z=None,ratio=None,ewma=None,resets=None,keys=None,params=None):
        n=len(wanted);keys=keys or [('r',i+1) for i in range(n)]
        result=m.continuity_alerts(keys,np.array(z if z is not None else [4]*n)[:,None],
            np.array(ratio if ratio is not None else [.05]*n)[:,None],
            {k:{'e'} if yes else set() for k,yes in zip(keys,ewma if ewma is not None else [True]*n)},['e'],
            resets or [False]*n,{k:{'e'} if yes else set() for k,yes in zip(keys,wanted)},params or P)
        return [bool(result[k]) for k in keys]

    def test_clean_zero_preserves_current_even_if_missing(self):
        self.assertEqual(self.run_case([1,1,1],z=[1,np.nan,4],ratio=[0,np.nan,.05]),[1,1,1])
        self.assertEqual(self.run_case([1,1,1],params=dict(P,control=True)),[1,1,1])

    def test_bridge_is_bounded_and_does_not_refresh_anchor(self):
        self.assertEqual(self.run_case([1,0,0,0,0]),[1,1,1,0,0])
        self.assertEqual(self.run_case([1,0,0,0],z=[4,3.2,2,4]),[1,1,0,0])
        self.assertEqual(self.run_case([1,0,0],ratio=[.05,.01,.05]),[1,0,0])

    def test_peak_of_cleaned_segment_rejects_decline_then_resets(self):
        self.assertEqual(self.run_case([1,1,0],z=[8,4,4]),[1,1,0])
        self.assertEqual(self.run_case([1,0,1,0],z=[8,6,4,3.2]),[1,1,1,1])

    def test_early_does_not_create_or_refresh_bridge_anchor(self):
        p=dict(P,early_scale=.25,early_z=2.5)
        self.assertEqual(self.run_case([0,0],ratio=[.3,.05],params=p),[1,0])
        self.assertEqual(self.run_case([1,0,0,0],ratio=[.05,.3,.05,.05],params=p),[1,1,1,0])

    def test_cleaning_reset_missing_and_prefix_causality(self):
        self.assertEqual(self.run_case([1,1],z=[1,4],params=dict(P,clean_z=2)),[0,1])
        self.assertEqual(self.run_case([1,0,0],z=[4,np.nan,4]),[1,0,0])
        self.assertEqual(self.run_case([1,0,0],resets=[False,True,False]),[1,0,0])
        self.assertEqual(self.run_case([1,0],keys=[('r',1),('r',3)]),[1,0])
        self.assertEqual(self.run_case([1,0]),self.run_case([1,0,1])[:2])
        with self.assertRaises(ValueError):self.run_case([1],params=dict(P,peak_fraction=2))
        with self.assertRaises(ValueError):self.run_case([1,1],keys=[('r',1),('r',1)])

    def test_coverage_cannot_be_offset_by_other_positive_frames(self):
        keys=[('r',1),('r',2)];positive={k:{'e'} for k in keys}
        before={keys[0]:{'e'},keys[1]:set()};after={keys[0]:set(),keys[1]:{'e'}}
        self.assertEqual(m.coverage_loss(keys,positive,before,after),1)
        self.assertEqual(m.coverage_loss(keys,{k:set() for k in keys},before,after),0)

    def test_selection_rejects_coverage_loss_and_diagnostic_preserves_primary_metrics(self):
        b=dict(detected_events=10,wrong_alert_equipment_seconds=2,duplicate_alert_episodes=50,p95_onset_delay_seconds=9)
        e=dict(b,duplicate_alert_episodes=10);good=dict(b,duplicate_alert_episodes=10,p95_onset_delay_seconds=8)
        row=dict(params=P,metrics=[good]*4,lost=[0]*4,delayed=[0]*4,removed_active=[0]*4)
        bad=dict(row,removed_active=[1,0,0,0])
        chosen,passed=m.choose([bad,row],[b]*4,[e]*4)
        self.assertTrue(passed);self.assertEqual(chosen,row)
        self.assertFalse(m.choose([bad],[b]*4,[e]*4)[1])
        control=dict(row,params=dict(P,control=True),metrics=[b]*4)
        chosen,passed=m.choose([bad,control],[b]*4,[e]*4)
        self.assertFalse(passed);self.assertEqual(chosen,control)


if __name__=='__main__':unittest.main()
