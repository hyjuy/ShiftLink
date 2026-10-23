import unittest
import numpy as np
from scripts import mes_causal_v14 as candidate
from tests.test_mes_causal_v13 import inputs,ticks

class RiseTests(unittest.TestCase):
    def args(self):
        a=inputs();a[0]['signed_z']=np.zeros((100,3));a[4]['level'][:]=0
        a[7]['thermal_rise_limits']=[.7]
        return a

    def test_weak_coherent_warming_is_detected_before_level_threshold(self):
        a=self.args();a[0]['signed_z'][60:,0]=1.;a[0]['signed_z'][60:,2]=1.
        self.assertEqual(ticks(candidate.previous.predict(*a)),[])
        self.assertTrue(any(60<=t<70 for t in ticks(candidate.predict(*a))))

    def test_single_sensor_spike_does_not_supply_coherence(self):
        a=self.args();a[0]['signed_z'][60:,0]=3.
        self.assertEqual(ticks(candidate.predict(*a)),[])

    def test_prefix_is_unchanged_by_future_values(self):
        a=self.args();before=candidate.thermal_rise(a)
        a[0]['signed_z'][70:]=100
        np.testing.assert_equal(before[:70],candidate.thermal_rise(a)[:70])

    def test_bad_and_hold_break_contiguous_history(self):
        a=self.args();a[0]['signed_z'][60:,0]=2.;a[0]['signed_z'][60:,2]=2.
        a[5][55]=True
        self.assertTrue(np.isnan(candidate.thermal_rise(a)[60,0]))
        a=self.args();a[0]['signed_z'][60,0]=np.nan
        self.assertTrue(np.isnan(candidate.thermal_rise(a)[60,0]))

if __name__=='__main__':unittest.main()
