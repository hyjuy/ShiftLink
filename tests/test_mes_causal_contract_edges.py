"""Post-freeze regression checks: no candidate parameters are changed here."""
import unittest

from scripts import mes_causal_data as data
from scripts import mes_causal_score as score


class CausalContractEdges(unittest.TestCase):
    def test_pristine_rate_excludes_common_warmup(self):
        frames = [dict(sequence=t, line_mode='running') for t in range(100)]
        alerts = {('r', t): {'E'} if t in (10, 70) else set() for t in range(100)}
        metrics = score.evaluate({'r': frames}, {'r': []}, alerts, {('r', t) for t in range(64, 100)})
        self.assertEqual(metrics['pristine_normal_run_seconds'], 36)
        self.assertEqual(metrics['pristine_normal_false_starts'], 1)
        self.assertIsNone(metrics['p95_injection_delay_seconds'])
        self.assertEqual(metrics['events'], 0)

    def test_bad_stale_nonfinite_and_wrong_units_are_excluded(self):
        base = dict(equipment_id='E', signal='x', unit='u', quality='good', observed_at='now', value=2.)
        specs = {('E', 'x'): {'unit': 'u'}}
        for change in (dict(quality='bad'), dict(observed_at='old'), dict(value=float('nan')), dict(unit='wrong')):
            frame = dict(simulated_at='now', measurements=[dict(base, **change)])
            self.assertEqual(data.valid_values(frame, specs), {})
        with self.assertRaises(ValueError):
            data.valid_values(dict(simulated_at='now', measurements=[base, base]), specs)

    def test_pause_and_sequence_gap_require_64_new_past_frames(self):
        def frame(t, mode='running'):
            return dict(sequence=t, simulated_at=str(t), line_mode=mode,
                        measurements=[dict(equipment_id='E', signal='x', unit='u', quality='good', observed_at=str(t), value=t)])
        for prefix, restart in (([frame(t) for t in range(66)], 80),
                                ([frame(t) for t in range(66)] + [frame(66, 'paused')], 67)):
            frames = prefix + [frame(t) for t in range(restart, restart + 66)]
            x, keys, targets = data.windows({'r': frames}, [('E', 'x')])
            self.assertEqual(keys, [('r', 64), ('r', 65), ('r', restart + 64), ('r', restart + 65)])
            self.assertEqual(x[2, 0, 0], restart)
            self.assertEqual(targets[2, 0], restart + 64)


if __name__ == '__main__':
    unittest.main()
