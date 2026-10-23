import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from scripts import mes_causal_data as data
from scripts.mes_causal_source import SourceDynamics
from scripts.mes_causal_challenge import ChallengeDynamics
from scripts import mes_causal_score as scoring


class CausalBenchmarkTests(unittest.TestCase):
    def test_sensor_fault_cannot_propagate(self):
        for cls in (SourceDynamics, ChallengeDynamics):
            normal, faulty = cls(91), cls(91)
            changed = set()
            for t in range(120):
                event = [dict(kind='sensor_bias', equipment='EQ-0007', signal='rt_vib_rms', start=80, end=115, amplitude=2)]
                a = normal.step(t, [])
                b = faulty.step(t, event)
                changed |= {c for c in a if abs(a[c] - b[c]) > 1e-10}
                self.assertEqual(normal.process_state(), faulty.process_state())
            self.assertEqual(changed, {('EQ-0007', 'rt_vib_rms')})

    def test_process_fault_has_delayed_related_effects(self):
        for cls in (SourceDynamics, ChallengeDynamics):
            normal, faulty = cls(18), cls(18)
            changes = {}
            event = [dict(kind='leak', equipment='EQ-0001', signal=None, start=80, end=125, amplitude=2)]
            for t in range(130):
                a, b = normal.step(t, []), faulty.step(t, event)
                for key in [('EQ-0001', 'hpu_pressure'), ('EQ-0001', 'hpu_flow'), ('EQ-0007', 'rt_clamp_press')]:
                    if abs(a[key] - b[key]) > 1e-7:
                        changes.setdefault(key, t)
            self.assertEqual(len(changes), 3)
            self.assertLess(changes[('EQ-0001', 'hpu_pressure')], changes[('EQ-0007', 'rt_clamp_press')])

    def test_conditioned_sample_and_unmodeled_geometry(self):
        for cls in (SourceDynamics, ChallengeDynamics):
            normal, heated = cls(81), cls(81)
            event = [dict(kind='cooling_loss', equipment='EQ-0001', signal=None, start=50, end=130, amplitude=2)]
            for t in range(120):
                a, b = normal.step(t, []), heated.step(t, event)
            self.assertGreater(b[('EQ-0001', 'hpu_oil_temp')], a[('EQ-0001', 'hpu_oil_temp')])
            # Catalog defines viscosity as a sample conditioned at 40 degC.
            self.assertEqual(b[('EQ-0001', 'fluid_viscosity')], a[('EQ-0001', 'fluid_viscosity')])
            self.assertEqual(a[('EQ-0001', 'hpu_return_submergence')], b[('EQ-0001', 'hpu_return_submergence')])

    def test_independent_implementations_and_determinism(self):
        a, b, challenge = SourceDynamics(8), SourceDynamics(8), ChallengeDynamics(8)
        different = False
        for t in range(90):
            x, y, z = a.step(t, []), b.step(t, []), challenge.step(t, [])
            self.assertEqual(x, y)
            different |= x != z
        self.assertTrue(different)
        for module in ('mes_causal_source', 'mes_causal_challenge'):
            source = Path(importlib.util.find_spec('scripts.' + module).origin).read_text(encoding='utf-8')
            for forbidden in ('fault_schedule', 'PATTERNS', 'CHALLENGE_MECHANISMS', 'mes_causal_source import'):
                self.assertNotIn(forbidden, source)

    def test_measurement_contract_and_stale_sample(self):
        session = data.Session('A', 7, 'r', events=[])
        frames = [session.advance() for _ in range(95)]
        self.assertEqual(len(frames[-1]['measurements']), 69)
        self.assertEqual(session.state(), frames[-1])
        a = next(m for m in frames[91]['measurements'] if m['signal'] == 'fluid_viscosity')
        self.assertNotEqual(a['observed_at'], frames[91]['simulated_at'])
        self.assertNotIn(('EQ-0001', 'fluid_viscosity'), data.valid_values(frames[91]))
        self.assertTrue(all('fault' not in k for f in frames for k in f))

    def test_binary_contract_and_nontrivial_normal_noise(self):
        from scripts.mes_causal_schema import signals
        for cls in (SourceDynamics, ChallengeDynamics):
            simulator = cls(14)
            excursions = 0
            for t in range(240):
                for key, value in simulator.step(t, []).items():
                    spec = signals()[key]
                    if spec['unit'] == 'bool':
                        self.assertIn(value, (0., 1.))
                    elif spec['normal_min'] is not None:
                        excursions += value < spec['normal_min'] or value > spec['normal_max']
            self.assertGreater(excursions, 0)

    def test_test_requires_locked_candidate_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                data.generate_role(root / 'test', 'test_joint', runs=1, ticks=120)
            data.generate_role(root / 'fit', 'fit', runs=1, ticks=120)
            with self.assertRaises(FileExistsError):
                data.generate_role(root / 'fit', 'fit', runs=1, ticks=120)

    def test_prediction_window_excludes_current(self):
        frames = [dict(run_id='r', sequence=t, simulated_at=f'2026-01-01T00:{t//60:02}:{t%60:02}+00:00', line_mode='running',
                       measurements=[dict(equipment_id='E', signal='x', unit='u', quality='good', observed_at=f'2026-01-01T00:{t//60:02}:{t%60:02}+00:00', value=t)]) for t in range(66)]
        windows, keys, actual = data.windows({'r': frames}, [('E', 'x')])
        self.assertEqual(keys[0], ('r', 64))
        self.assertEqual(windows[0, 0, -1], 63)
        self.assertEqual(actual[0, 0], 64)

    def test_scoring_uses_ledger_not_generator_lags(self):
        frames = [dict(run_id='r', sequence=t, line_mode='running') for t in range(100)]
        events = [dict(event_id='one', equipment='E', start=70, end=85)]
        alerts = {('r', t): {'E'} if t in (72, 76) else set() for t in range(100)}
        metrics = scoring.evaluate({'r': frames}, {'r': events}, alerts)
        self.assertEqual(metrics['detected_events'], 1)
        self.assertEqual(metrics['duplicate_notifications'], 1)
        self.assertEqual(metrics['p95_injection_delay_seconds'], 2)
        self.assertEqual(metrics['missed_events'], 0)
        self.assertNotIn('mes_causal_source', Path(scoring.__file__).read_text(encoding='utf-8'))

    def test_local_mes_http_roundtrip(self):
        from urllib.request import urlopen, Request
        with data.local_mes() as server:
            base = 'http://127.0.0.1:' + str(server.server_address[1])
            reset = Request(base + '/benchmark/reset', json.dumps(dict(family='A', seed=5, run_id='http', events=[])).encode(), method='POST')
            with urlopen(reset) as response:
                self.assertEqual(response.status, 200)
            with urlopen(Request(base + '/benchmark/step', b'{}', method='POST')) as response:
                frame = json.load(response)
            with urlopen(base + '/api/state') as response:
                self.assertEqual(json.load(response), frame)
            self.assertEqual(len(frame['measurements']), 69)


if __name__ == '__main__':
    unittest.main()
