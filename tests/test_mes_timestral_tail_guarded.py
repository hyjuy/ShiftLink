"""Regression contracts for the separate stage5 notification candidate."""
import copy
import unittest

import numpy as np

from scripts import mes_timestral_tail_guarded as candidate
from tests.test_mes_timestral_symptom import symptom


PARAMS = dict(cooldown=45, normal_count=8, quiet_off=1000000)


class TailGuardedTests(unittest.TestCase):
    def notices(self, values, on, *, original_on=None, params=None, data=None):
        data = symptom(values) if data is None else data
        display = {key: ({'e'} if i in on else set()) for i, key in enumerate(data['keys'])}
        original = {key: ({'e'} if i in (on if original_on is None else original_on) else set())
                    for i, key in enumerate(data['keys'])}
        output = candidate.notifications(data, display, original, params or PARAMS)
        return [i for i, key in enumerate(data['keys']) if output[key]]

    def test_five_second_other_sensor_first_notice_is_preserved(self):
        values = [[1, 0], [2.6, 0], [2.9, 0], [0, 0], [0, -2.1], [0, -3.3]]
        self.assertEqual(self.notices(values, {0, 5}), [0, 5])

    def test_first_weak_notice_learns_one_emerging_symptom(self):
        self.assertEqual(self.notices([[1, 0], [3, 0], [3, 0]], {0, 2}), [0])

    def test_same_symptom_chatter_is_suppressed(self):
        self.assertEqual(self.notices([[3, 0]] * 7, {0, 2, 4, 6}), [0])

    def test_other_sensor_stability_and_sign_reversal(self):
        self.assertEqual(self.notices([[3, 0], [0, -3], [0, -3]], {0, 2}), [0, 2])
        self.assertEqual(self.notices([[3, 0], [-3, 0], [-3, 0]], {0, 2}), [0, 2])
        self.assertEqual(self.notices([[3, 0], [3, 0], [0, -3]], {0, 2}), [0])

    def test_sensor_changes_inside_continuous_on_do_not_retrigger(self):
        self.assertEqual(self.notices([[3, 0], [0, -3], [0, -3]], {0, 1, 2}), [0])

    def test_original_floor_off_does_not_absorb_known_new_sensor(self):
        self.assertEqual(self.notices([[3, 0], [0, -3], [0, -3]], {0, 2}, original_on={0}), [0, 2])

    def test_cooldown_boundary(self):
        values = [[3, 0]] * 46
        self.assertEqual(self.notices(values, {0, 44, 45}), [0])
        self.assertEqual(self.notices(values, {0, 45}), [0, 45])

    def test_normal_rearm_boundary(self):
        self.assertEqual(self.notices([[3, 0]] + [[0, 0]] * 7 + [[3, 0]], {0, 8}), [0])
        self.assertEqual(self.notices([[3, 0]] + [[0, 0]] * 8 + [[3, 0]], {0, 9}), [0, 9])

    def test_missing_does_not_rearm_or_learn(self):
        data = symptom([[3, 0]] + [[0, -3]] * 8 + [[3, 0]])
        data['ratio'][1:9] = np.nan
        self.assertEqual(self.notices(None, {0, 9}, data=data), [0])

    def test_resets_and_inactive_boundaries(self):
        for boundary in ('reset', 'clock', 'sequence', 'run', 'inactive'):
            with self.subTest(boundary=boundary):
                data = symptom([[3, 0]] * 3)
                if boundary == 'reset':
                    data['resets'][2] = True
                elif boundary == 'clock':
                    data['observations'][2]['at'] = '2026-01-01T00:00:10+00:00'
                elif boundary in ('sequence', 'run'):
                    key = ('r', 4) if boundary == 'sequence' else ('other', 2)
                    data['keys'][2] = key
                    data['observations'][2].update(run=key[0], sequence=key[1])
                else:
                    data['observations'][1]['inactive'] = True
                self.assertEqual(self.notices(None, {0, 2}, data=data), [0, 2])

    def test_prefix_causality_and_inputs_preserved(self):
        data = symptom([[3, 0], [0, -3], [0, -3]])
        display = {key: ({'e'} if key[1] in (0, 2) else set()) for key in data['keys']}
        before = copy.deepcopy(data)
        original = copy.deepcopy(display)
        output = candidate.notifications(data, display, original, PARAMS)
        prefix = {key: data[key][:2] for key in ('keys', 'raw_z', 'ratio', 'resets', 'observations', 'signed_z')}
        prefix.update(equipment=data['equipment'], channels=data['channels'])
        alerts = {key: value for key, value in display.items() if key[1] < 2}
        self.assertEqual(candidate.notifications(prefix, alerts, alerts, PARAMS),
                         {key: value for key, value in output.items() if key[1] < 2})
        self.assertEqual(display, original)
        for key, value in data.items():
            if isinstance(value, np.ndarray):
                np.testing.assert_array_equal(value, before[key])
            else:
                self.assertEqual(value, before[key])

    def test_original_keys_and_shape_contracts(self):
        data = symptom([[3, 0]])
        with self.assertRaises(AssertionError):
            candidate.notifications(data, {('r', 0): {'e'}}, {}, PARAMS)
        data['signed_z'] = np.zeros((1, 1))
        with self.assertRaises(AssertionError):
            candidate.notifications(data, {('r', 0): {'e'}}, {('r', 0): {'e'}}, PARAMS)


if __name__ == '__main__':
    unittest.main()
