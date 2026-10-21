"""Causality and calibration guarantees for the offline Timestral experiment."""
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('timestral_comparison', ROOT/'scripts/mes_timestral_comparison.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def frames(n=70):
    return [{'run_id': 'r', 'sequence': i+1, 'simulated_at': f'2026-01-01T00:{i//60:02}:{i%60:02}+00:00',
             'line_mode': 'running', 'measurements': [], 'value': float(i)} for i in range(n)]


class ComparisonTests(unittest.TestCase):
    def test_causal_windows_never_include_target_or_cross_runs(self):
        rows = frames()
        x, keys = m.causal_windows({'r': rows, 's': [dict(f, run_id='s') for f in rows]},
                                 [('eq', 'x')], lambda f: {('eq', 'x'): f['value']})
        self.assertEqual(x.shape, (12, 1, 64))
        np.testing.assert_equal(x[0, 0], np.arange(64))
        self.assertEqual(keys[0], ('r', 65))
        self.assertEqual(keys[6], ('s', 65))
        rows[64]['value'] = 999
        changed, _ = m.causal_windows({'r': rows}, [('eq', 'x')], lambda f: {('eq', 'x'): f['value']})
        np.testing.assert_equal(changed[0], x[0])

    def test_mode_and_time_gap_reset_history(self):
        rows = frames(140)
        rows[65]['line_mode'] = 'stopped'
        _, keys = m.causal_windows({'r': rows}, [('eq', 'x')], lambda f: {('eq', 'x'): f['value']})
        self.assertNotIn(('r', 66), keys)
        self.assertNotIn(('r', 130), keys)
        self.assertIn(('r', 131), keys)
        rows[65]['line_mode'] = 'running'
        rows[65]['simulated_at'] = '2026-01-01T00:09:00+00:00'
        _, keys = m.causal_windows({'r': rows}, [('eq', 'x')], lambda f: {('eq', 'x'): f['value']})
        self.assertNotIn(('r', 67), keys)

    def test_missing_values_are_nan_and_labels_not_an_argument(self):
        x, _ = m.causal_windows({'r': frames()}, [('eq', 'x'), ('eq', 'missing')],
                                 lambda f: {('eq', 'x'): f['value']})
        self.assertTrue(np.isnan(x[:, 1]).all())

    def test_asymmetric_quantiles_and_scale_floor(self):
        result = m.channel_scores(np.array([[4., -4., 1.]]), np.zeros((1,3)),
            np.array([[-2., -2., 0.]]), np.array([[4., 4., 0.]]), np.array([1.,1.,10.]))
        np.testing.assert_allclose(result, [[1.,2.,1.]])
        with self.assertRaises(ValueError):
            m.channel_scores(np.array([[np.inf]]), np.array([[0.]]), np.array([[-1.]]),
                             np.array([[1.]]), np.array([1.]))
        with self.assertRaises(ValueError):
            m.channel_scores(np.array([[1.]]), np.array([[0.]]), np.array([[1.]]),
                             np.array([[-1.]]), np.array([1.]))

    def test_train_calibration_requires_entire_clean_history(self):
        runs = {'r': [(f, {'faults': []}) for f in frames(140)]}
        runs['r'][5][1]['faults'] = [{'id':'fault'}]
        mask = m.normal_window_keys(runs)
        self.assertNotIn(('r',65), mask)
        self.assertIn(('r',71), mask)
        runs['r'][100][1]['faults'] = [{'id':'new'}]
        self.assertNotIn(('r',101), m.normal_window_keys(runs))

    def test_equipment_thresholds_and_strict_comparison(self):
        keys = [('r', i) for i in range(100)]
        thresholds, counts = m.calibrate(keys, np.tile([.5,2.], (100,1)), ['a','b'], set(keys))
        self.assertEqual(thresholds, {'a':1., 'b':2.})
        self.assertEqual(counts, {'a':100, 'b':100})
        alerts = m.threshold_alerts(keys, np.tile([1.,3.],(100,1)), ['a','b'], thresholds)
        self.assertEqual(alerts[keys[0]], {'b'})
        with self.assertRaises(ValueError):
            m.calibrate(keys[:1], np.array([[1.,2.]]), ['a','b'], set(keys))

    def test_aggregate_gate_does_not_trade_recall_for_speed(self):
        baseline = dict(detected_events=35, wrong_alert_equipment_seconds=21,
                        duplicate_alert_episodes=30, p95_onset_delay_seconds=14)
        self.assertIn('detected_events', m.aggregate_failures(baseline, dict(baseline, detected_events=34,
                                                                      p95_onset_delay_seconds=1)))
        self.assertEqual(m.aggregate_failures(baseline, dict(baseline, duplicate_alert_episodes=29)), [])
        self.assertIn('no_strict_improvement', m.aggregate_failures(baseline, baseline))
        self.assertIn('p95_onset_delay_seconds', m.aggregate_failures(baseline, dict(baseline,p95_onset_delay_seconds=None)))


if __name__ == '__main__':
    unittest.main()
