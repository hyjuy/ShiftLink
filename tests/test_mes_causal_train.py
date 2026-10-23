import unittest
import numpy as np

from scripts import mes_causal_data as data
from scripts import mes_causal_train as train


class CausalTrainingTests(unittest.TestCase):
    def test_stats_use_only_fit_current_good_channels(self):
        session = data.Session('A', 19, 'fit-only', [])
        frames = [session.advance() for _ in range(150)]
        channels, stats = train.fit_statistics({'fit-only': frames})
        self.assertEqual(len(channels), 63)
        self.assertNotIn(('EQ-0007', 'rt_lift_delay'), channels)
        self.assertNotIn(('EQ-0001', 'fluid_viscosity'), channels)
        self.assertTrue(all(stats[c][1] > 0 for c in channels))

    def test_quantile_calibration_does_not_use_fault_labels(self):
        values = np.arange(200, dtype=float).reshape(100, 2)
        limits = train.calibrate(values)
        np.testing.assert_array_equal(limits, [198, 199])
        with self.assertRaises(ValueError):
            train.calibrate(np.full((10, 2), np.nan))

    def test_predict_batch_shape_and_future_exclusion(self):
        import torch
        from tests.test_mes_timestral_finetune import tiny
        torch.set_num_threads(1)
        model = tiny()
        x = np.random.default_rng(4).normal(2, .1, (3, 2, 64)).astype('float32')
        q, timing = train.forecast(model, x, batch=2)
        self.assertEqual(q.shape, (3, 2, 3))
        self.assertTrue(np.isfinite(q).all())
        self.assertEqual(timing['windows'], 3)

    def test_disjoint_roles_reject_seed_or_run_overlap(self):
        train.check_disjoint([{'runs': [{'run_id': 'a', 'seed': 1, 'nonce': 'n1'}]},
                              {'runs': [{'run_id': 'b', 'seed': 2, 'nonce': 'n2'}]}])
        for field in ('run_id', 'seed', 'nonce'):
            a = {'run_id': 'a', 'seed': 1, 'nonce': 'n1'}
            b = {'run_id': 'b', 'seed': 2, 'nonce': 'n2'}
            b[field] = a[field]
            with self.assertRaises(ValueError):
                train.check_disjoint([{'runs': [a]}, {'runs': [b]}])


if __name__ == '__main__':
    unittest.main()
