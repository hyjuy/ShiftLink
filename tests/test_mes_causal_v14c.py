import unittest
import numpy as np
from scripts import mes_causal_v14c as candidate

class CalibrationTests(unittest.TestCase):
    def limits(self,scores,background=None):
        x=np.asarray(scores,float).reshape(-1,1)
        flags=np.zeros(x.shape,bool) if background is None else np.asarray(background,bool).reshape(x.shape)
        return candidate.calibrate([(x,flags)])[0]

    def test_one_frame_normal_spike_does_not_set_sustained_limit(self):
        self.assertEqual(self.limits([0,0,1,0,0]),.5)

    def test_existing_process_flags_count_towards_four_frame_run(self):
        self.assertAlmostEqual(self.limits([.1,.1,.8,.7],[True,True,False,False]),.77)

    def test_missing_and_run_boundaries_cannot_bridge_patience(self):
        self.assertEqual(self.limits([.9,.9,float('nan'),.9,.9]),1e6)
        x=np.ones((2,1));self.assertEqual(candidate.calibrate([(x,np.zeros_like(x,bool)),(x,np.zeros_like(x,bool))])[0],1e6)

    def test_floor_and_no_temperature_channels(self):
        x=np.column_stack((np.zeros(8),np.full(8,np.nan)))
        np.testing.assert_equal(candidate.calibrate([(x,np.zeros_like(x,bool))]),[.5,1e6])

    def test_existing_sustained_normal_alarm_is_not_silently_recalibrated(self):
        with self.assertRaises(ValueError):self.limits([0,0,0,0],[True]*4)

class DataTests(unittest.TestCase):
    def test_first_use_requires_lock_and_seed_groups_do_not_overlap(self):
        from scripts import mes_causal_v14c_data as data
        from scripts import mes_causal_v14_data as previous
        with self.assertRaises(ValueError):data.generate('unused','test')
        identities=[data.identity(role,family,i) for role in data.ROLES for family in ('A','B') for i in range(7)]
        self.assertEqual(len(identities),len(set(identities)))
        self.assertNotEqual(data.identity('test','A',0),previous.identity('test','A',0))

if __name__=='__main__':unittest.main()
