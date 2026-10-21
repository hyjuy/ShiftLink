import importlib.util
import unittest
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('followup',Path(__file__).resolve().parents[1]/'scripts/mes_timestral_pi_followup.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class AlarmTests(unittest.TestCase):
    def test_hybrid_gates_baseline_and_adds_only_current_confirmed_evidence(self):
        keys=[('a',i) for i in range(1,5)]
        baseline={key:{'e'} for key in keys}
        x=np.array([[.1],[1],[5],[5.]])
        got=m.hybrid_alerts(keys,x,['e'],{'e':2},baseline,2,2,3,.25)
        self.assertEqual([got[key] for key in keys],[set(),{'e'},{'e'},{'e'}])
        got=m.hybrid_alerts(keys,x,['e'],{'e':2},{key:set() for key in keys},2,2,3,.25)
        self.assertEqual([got[key] for key in keys],[set(),set(),set(),{'e'}])

    def test_strict_threshold_and_current_exceedance(self):
        keys=[('a',i) for i in range(1,6)]
        out=m.causal_alerts(keys,np.array([[2],[3],[3],[1],[3]]),['e'],{'e':2},1,2,3)
        self.assertEqual([out[key] for key in keys],[set(),set(),{'e'},set(),{'e'}])

    def test_run_and_missing_sequence_reset(self):
        keys=[('a',1),('a',2),('a',4),('b',1),('b',2)]
        out=m.causal_alerts(keys,np.full((5,1),3.),['e'],{'e':2},1,2,3)
        self.assertEqual([out[key] for key in keys],[set(),{'e'},set(),set(),{'e'}])

    def test_future_values_do_not_change_past(self):
        keys=[('a',i) for i in range(5)]
        x=np.ones((5,2))*3
        old=m.causal_alerts(keys,x,['a','b'],{'a':2,'b':2},1,3,5)
        x[3:]=100
        new=m.causal_alerts(keys,x,['a','b'],{'a':2,'b':2},1,3,5)
        self.assertEqual([old[k] for k in keys[:3]],[new[k] for k in keys[:3]])

    def test_nan_is_not_an_exceedance_and_invalid_contract_refused(self):
        self.assertEqual(m.causal_alerts([('a',1)],np.array([[np.nan]]),['e'],{'e':2},1,1,1),{('a',1):set()})
        for scale,k,n in ((0,1,1),(1,4,3),(1,0,3)):
            with self.assertRaises(ValueError):m.causal_alerts([('a',1)],np.array([[3]]),['e'],{'e':2},scale,k,n)

    def test_selection_requires_both_strict_improvements(self):
        baseline={'detected_events':29,'wrong_alert_equipment_seconds':19}
        def row(count,wrong,scale):
            return {'scale':scale,'k':1,'n':1,'metrics':dict(detected_events=count,wrong_alert_equipment_seconds=wrong,p95_onset_delay_seconds=10)}
        rows=[row(35,19,1),row(32,18,2),row(33,17,1.5),row(29,0,.5)]
        selected,passed=m.choose(rows,baseline)
        self.assertTrue(passed)
        self.assertEqual(selected['scale'],1.5)
        self.assertFalse(m.choose([rows[0],rows[3]],baseline)[1])


if __name__=='__main__':unittest.main()
