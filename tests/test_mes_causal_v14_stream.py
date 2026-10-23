"""Device-run regressions: frozen batch equivalence and bounded online state."""
import copy
from datetime import datetime, timedelta, timezone
import json
import math
import sys
import unittest
import numpy as np
from scripts.mes_causal_schema import signals, units, metadata, MANUAL
from scripts.mes_causal_v14_stream import OnlineDetector


def config():
    specs = signals(); channels = sorted(specs)
    stats = [[e, s, units(specs[e, s])[0], units(specs[e, s])[1] / 10] for e, s in channels]
    variable = [specs[c]['unit'] != 'bool' and c[1] not in MANUAL and c[1] != 'rt_lift_delay' for c in channels]
    return dict(base=dict(channels=channels, stats=stats, variable=variable,
                         tolerance=[1e-8] * len(channels), selected={'no_timestral': {
                             'params': dict(width=5, patience=4, q=.98),
                             'limits': {'level': [3.] * len(channels)}}}),
                limits=[3.] * len(channels), thermal_rise_limits=[.7] * len({e for e, s in channels}))


def frames(n=280, run='stream-fixture'):
    settings = config(); stats = {(e, s): (m, scale) for e, s, m, scale in settings['base']['stats']}
    output = []
    for tick in range(n):
        at = (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=tick)).isoformat()
        measurements = []
        for j, (key, spec) in enumerate(signals().items()):
            center, scale = stats[key]
            value = 0. if spec['unit'] == 'bool' else center + scale * .05 * math.sin(tick * .7 + j)
            measurements.append(dict(equipment_id=key[0], signal=key[1], unit=spec['unit'],
                                     value=value, quality='good', observed_at=at))
        output.append(dict(run_id=run, sequence=tick, config_id=metadata()['config_id'],
                           simulated_at=at, line_mode='running', measurements=measurements))
    return output


def channel_choices():
    channels = config()['base']['channels']
    temperatures = {}
    for e, s in channels:
        if 'temp' in s: temperatures.setdefault(e, []).append((e, s))
    eq = next(e for e, cs in temperatures.items() if len(cs) >= 2)
    current = next(c for c in channels if c[0] == eq and 'current' in c[1])
    return temperatures[eq][:2], current


def modify(rows, keys, start, end, z=None, flat=False):
    stats = {(e, s): (m, a) for e, s, m, a in config()['base']['stats']}
    previous = {(m['equipment_id'], m['signal']): m['value'] for m in rows[start-1]['measurements']}
    for row in rows[start:end]:
        for m in row['measurements']:
            key = m['equipment_id'], m['signal']
            if key in keys:
                m['value'] = previous[key] if flat else stats[key][0] + stats[key][1] * z


def oracle(rows, settings=None):
    from scripts import mes_causal_v11_run as prepare
    from scripts import mes_causal_v14 as frozen
    settings = settings or config(); runs = {}
    for row in rows: runs.setdefault(row['run_id'], []).append(row)
    result = {}
    for run, values in runs.items():
        args = list(prepare.prepare({run: values}, settings['base']))
        args[6] = {'level': np.asarray(settings['limits'])}
        args[7] = dict(args[7], thermal_rise_limits=settings['thermal_rise_limits'])
        result.update(frozen.predict(*args))
    return result


class OnlineTests(unittest.TestCase):
    def equivalent(self, rows):
        expected = oracle(rows); detector = OnlineDetector(config()); actual = {}
        for row in rows: actual[row['run_id'], row['sequence']] = detector.step(row)
        self.assertEqual(actual, expected)
        return detector, actual

    def test_normal_and_coherent_temperature_match_every_batch_row(self):
        rows = frames(); temp, current = channel_choices(); modify(rows, temp, 110, 150, 2.)
        detector, actual = self.equivalent(rows)
        self.assertTrue(any(actual.values()))
        self.assertFalse(any(actual[rows[0]['run_id'], t] for t in range(64)))

    def test_bad_sample_does_not_rearm_flat_notification(self):
        rows = frames(); temp, current = channel_choices(); modify(rows, [current], 100, 220, flat=True)
        for m in rows[125]['measurements']:
            if (m['equipment_id'], m['signal']) == current: m['quality'] = 'bad'
        detector, actual = self.equivalent(rows)
        self.assertEqual(sum(current[0] in v for v in actual.values()), 1)

    def test_global_acquisition_hold_preserves_active_source(self):
        rows = frames(); temp, current = channel_choices(); modify(rows, [current], 100, 210, 6.)
        modify(rows, list(signals()), 125, 135, flat=True)
        self.equivalent(rows)

    def test_temperature_must_not_hide_independent_current(self):
        rows = frames(); temp, current = channel_choices()
        modify(rows, temp, 100, 160, 2.); modify(rows, [current], 140, 190, 6.)
        detector, actual = self.equivalent(rows)
        self.assertGreaterEqual(sum(current[0] in v for v in actual.values()), 2)

    def test_bad_missing_stale_and_nonfinite_measurements_match_batch(self):
        rows = frames(); temp, current = channel_choices(); modify(rows, temp, 110, 155, 2.)
        for tick, field, value in [(112, 'quality', 'bad'), (114, 'value', None),
                                   (117, 'value', float('nan')), (130, 'observed_at', rows[0]['simulated_at'])]:
            for m in rows[tick]['measurements']:
                if (m['equipment_id'], m['signal']) == temp[0]: m[field] = value
        self.equivalent(rows)

    def test_pause_and_resume_match_batch(self):
        rows = frames(); temp, current = channel_choices(); modify(rows, [current], 100, 220, 6.)
        for row in rows[130:135]: row['line_mode'] = 'paused'
        self.equivalent(rows)

    def test_sequence_gap_matches_batch_rewarm(self):
        rows = frames()
        for row in rows[120:]: row['sequence'] += 4
        self.equivalent(rows)

    def test_run_boundary_has_no_old_state(self):
        self.equivalent(frames(140, 'one') + frames(140, 'two'))

    def test_duplicate_and_old_frame_are_ignored_without_rewarming(self):
        rows = frames(180); expected = oracle(rows); detector = OnlineDetector(config())
        for row in rows[:140]: detector.step(row)
        self.assertEqual(detector.step(rows[139]), set()); self.assertFalse(detector.last_status['accepted'])
        self.assertEqual(detector.step(rows[100]), set())
        for row in rows[140:]: self.assertEqual(detector.step(row), expected[row['run_id'], row['sequence']])

    def test_wrong_contract_is_rejected_before_state_mutation(self):
        rows = frames(145); detector = OnlineDetector(config()); expected = oracle(rows)
        for row in rows[:140]: detector.step(row)
        bad = copy.deepcopy(rows[140]); bad['config_id'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'config'): detector.step(bad)
        bad = copy.deepcopy(rows[140]); bad['measurements'][0], bad['measurements'][1] = bad['measurements'][1], bad['measurements'][0]
        with self.assertRaisesRegex(ValueError, 'order'): detector.step(bad)
        bad = copy.deepcopy(rows[140]); bad['measurements'][0]['unit'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'unit'): detector.step(bad)
        self.assertEqual(detector.step(rows[140]), expected[rows[140]['run_id'], 140])

    def test_stale_clock_is_ignored_and_clock_gap_rewarms(self):
        rows = frames(145); detector = OnlineDetector(config())
        for row in rows[:140]: detector.step(row)
        bad = copy.deepcopy(rows[140]); bad['simulated_at'] = rows[139]['simulated_at']
        self.assertEqual(detector.step(bad), set()); self.assertFalse(detector.last_status['accepted'])
        gap = copy.deepcopy(rows[140]); gap['simulated_at'] = rows[142]['simulated_at']
        self.assertEqual(detector.step(gap), set()); self.assertFalse(detector.last_status['ready'])

    def test_invalid_settings_fail_without_loading_models(self):
        for field, value in [('thermal_rise_limits', [0.] * len(config()['thermal_rise_limits'])), ('limits', [1.])]:
            bad = copy.deepcopy(config()); bad[field] = value
            with self.assertRaises(ValueError): OnlineDetector(bad)
        self.assertNotIn('torch', sys.modules); self.assertNotIn('timestral', sys.modules)

    def test_history_is_bounded_and_input_is_not_mutated(self):
        detector = OnlineDetector(config()); rows = frames(1500)
        before = json.dumps(rows[100])
        for row in rows: detector.step(row)
        self.assertEqual(json.dumps(rows[100]), before)
        sizes = detector.history_sizes
        self.assertLessEqual(sizes['median'], 5); self.assertLessEqual(sizes['flat'], 16); self.assertLessEqual(sizes['thermal'], 37)


if __name__ == '__main__': unittest.main()
