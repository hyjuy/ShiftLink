import importlib.util
import unittest
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('rearm',Path(__file__).resolve().parents[1]/'scripts/mes_timestral_rearm.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
P=dict(early_scale=.75,early_z=2.5,rearm_z=2,quiet=2)


class RearmTests(unittest.TestCase):
    def run_case(self,wanted,z=None,ratio=None,ewma=None,resets=None,keys=None,params=None):
        n=len(wanted);keys=keys or [('r',i+1) for i in range(n)]
        result=m.episode_alerts(keys,np.array(z if z is not None else [4]*n)[:,None],
            np.array(ratio if ratio is not None else [.2]*n)[:,None],
            {k:{'e'} if yes else set() for k,yes in zip(keys,ewma or [False]*n)},['e'],
            resets or [False]*n,{k:{'e'} if yes else set() for k,yes in zip(keys,wanted)},params or P)
        return [bool(result[k]) for k in keys]

    def test_release_does_not_extend_and_repeated_entry_is_inhibited(self):
        self.assertEqual(self.run_case([1,1,0,1,1,0,1]),[1,1,0,0,0,0,0])

    def test_release_frame_excluded_and_entry_after_completed_quiet(self):
        self.assertEqual(self.run_case([1,0,0,0,1],z=[4,0,0,0,4],ratio=[.2,0,0,0,.2]),[1,0,0,0,1])
        self.assertEqual(self.run_case([1,0,0,1],z=[4,0,0,4],ratio=[.2,0,0,.2]),[1,0,0,0])

    def test_quiet_requires_ewma_off_and_low_timestral(self):
        p=dict(P,quiet=1)
        self.assertEqual(self.run_case([1,0,0,1],z=[4,0,0,4],ratio=[.2,0,0,.2],ewma=[0,0,1,0],params=p),[1,0,0,0])
        self.assertEqual(self.run_case([1,0,0,1],z=[4,0,0,4],ratio=[.2,0,.2,.2],params=p),[1,0,0,0])

    def test_missing_is_not_normal_but_run_or_time_reset_rearms(self):
        self.assertEqual(self.run_case([1,1,1],z=[4,np.nan,4]),[1,0,0])
        self.assertEqual(self.run_case([1,0,1],resets=[False,False,True]),[1,0,1])
        self.assertEqual(self.run_case([1,0,1],keys=[('r',1),('r',2),('r',4)]),[1,0,1])

    def test_early_entry_is_causal_and_cannot_override_inhibition(self):
        self.assertEqual(self.run_case([0,0,0],z=[3,0,3],ratio=[.8,0,.8]),[1,0,0])
        self.assertEqual(self.run_case([1,0]),self.run_case([1,0,1])[:2])

    def test_selection_uses_all_sets_and_latest_strict_delay(self):
        b=dict(detected_events=10,wrong_alert_equipment_seconds=2,duplicate_alert_episodes=50,p95_onset_delay_seconds=9)
        e=dict(b,duplicate_alert_episodes=10)
        good=dict(b,duplicate_alert_episodes=10,p95_onset_delay_seconds=8)
        row=dict(params=P,metrics=[good]*4,lost=[0]*4,delayed=[1]*4)
        bad=dict(row,metrics=[good]*3+[dict(good,p95_onset_delay_seconds=9)])
        selected,passed=m.choose([bad,row],[b]*4,[e]*4)
        self.assertTrue(passed);self.assertEqual(selected,row)
        self.assertFalse(m.choose([bad],[b]*4,[e]*4)[1])
        self.assertFalse(m.choose([dict(row,lost=[0,1,0,0])],[b]*4,[e]*4)[1])
        self.assertFalse(m.choose([dict(row,metrics=[dict(good,duplicate_alert_episodes=11)]*4)],[b]*4,[e]*4)[1])

    def test_invalid_contract_rejected(self):
        with self.assertRaises(ValueError):self.run_case([1],params=dict(P,quiet=0))
        with self.assertRaises(ValueError):self.run_case([1,1],keys=[('r',1),('r',1)])


if __name__=='__main__':unittest.main()
