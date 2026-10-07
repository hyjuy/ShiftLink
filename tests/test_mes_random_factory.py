"""Opt-in random factory integration; public MES records remain observable data."""
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import unittest


CATALOG = Path(__file__).resolve().parents[1] / 'docs/data/reference/00_plant_and_relations.json'


class RandomFactoryIntegrationTests(unittest.TestCase):
    def service(self, **options):
        from shiftlink.mes.server import MesService
        service = MesService(CATALOG, seed=31, **options)
        self.addCleanup(service.storage.close)
        return service

    @staticmethod
    def observed_values(engine, ticks=20):
        engine.start()
        return [[(m.equipment_id, m.signal, m.value, m.quality) for m in engine.tick().measurements] for _ in range(ticks)]

    def test_default_service_keeps_legacy_engine(self):
        from shiftlink.mes.engine import MesEngine
        service = self.service()
        self.assertIs(type(service.engine), MesEngine)

    def test_opt_in_service_uses_random_factory(self):
        from shiftlink.mes.random_factory import RandomFactoryEngine
        service = self.service(random_faults=True, run_nonce='integration', fault_hazard=.1)
        self.assertIsInstance(service.engine, RandomFactoryEngine)
        service.control({'command': 'start'})
        for _ in range(10): service.tick()
        self.assertEqual(service.state()['sequence'], 10)
        self.assertEqual(len(service.state()['measurements']), 69)

    def test_apply_and_reset_keep_random_mode_and_change_normal_trajectory(self):
        from shiftlink.mes.configuration import to_payload
        from shiftlink.mes.random_factory import RandomFactoryEngine
        service = self.service(random_faults=True, run_nonce='integration', fault_hazard=0)
        old_values = self.observed_values(service.engine)
        old_run = service.engine.run.run_id
        service.control({'command': 'pause'})
        draft = to_payload(service.active_config)
        draft['version_label'] = 'random-integration'
        service.apply_config({'base_config_id': service.active_config.config_id, 'draft': draft})
        self.assertIsInstance(service.engine, RandomFactoryEngine)
        self.assertNotEqual(service.engine.run.run_id, old_run)
        self.assertEqual(service.engine.hazard, 0)
        applied_values = self.observed_values(service.engine)
        self.assertNotEqual(old_values, applied_values)
        applied_run = service.engine.run.run_id
        service.control({'command': 'reset'})
        self.assertIsInstance(service.engine, RandomFactoryEngine)
        self.assertNotEqual(service.engine.run.run_id, applied_run)
        self.assertEqual(service.engine.hazard, 0)
        reset_values = self.observed_values(service.engine)
        self.assertNotEqual(applied_values, reset_values)

    def test_fixed_seed_nonce_reproduces_and_new_nonce_varies(self):
        from shiftlink.mes.configuration import from_catalog
        from shiftlink.mes.contracts import Run
        from shiftlink.mes.random_factory import RandomFactoryEngine
        from shiftlink.mes.scenarios.priority import expand
        config = expand(from_catalog(json.loads(CATALOG.read_text(encoding='utf-8'))))
        started = datetime(2026, 10, 7, tzinfo=timezone.utc)
        def engine(nonce):
            return RandomFactoryEngine(Run.create(31, started, config.config_id), config, run_nonce=nonce, faults_enabled=False)
        a = self.observed_values(engine('one'))
        self.assertEqual(a, self.observed_values(engine('one')))
        self.assertNotEqual(a, self.observed_values(engine('two')))

    def test_normal_only_generator_never_injects_faults(self):
        from shiftlink.mes.configuration import from_catalog
        from shiftlink.mes.contracts import Run
        from shiftlink.mes.random_factory import RandomFactoryEngine
        from shiftlink.mes.scenarios.priority import expand
        config = expand(from_catalog(json.loads(CATALOG.read_text(encoding='utf-8'))))
        engine = RandomFactoryEngine(Run.create(31, datetime(2026,10,7,tzinfo=timezone.utc), config.config_id), config, run_nonce='normal', faults_enabled=False, hazard=1)
        engine.start()
        for _ in range(120):
            snapshot = engine.tick()
            self.assertEqual(snapshot.active_alarms, ())
            self.assertTrue(all(e.fault_level == 'normal' for e in snapshot.equipment))
        self.assertTrue(all(not row['faults'] for row in engine.truth))

    def test_partial_hpu_sensor_configuration_can_generate_observations(self):
        from shiftlink.mes.configuration import from_catalog
        from shiftlink.mes.contracts import Run
        from shiftlink.mes.random_factory import RandomFactoryEngine
        from shiftlink.mes.scenarios.priority import expand
        original = expand(from_catalog(json.loads(CATALOG.read_text(encoding='utf-8'))))
        omitted = {'hpu_flow', 'hpu_cooler_water_in_temp'}
        config = replace(original, equipment=tuple(replace(e, signals=tuple(s for s in e.signals if s.signal not in omitted)) if e.code.startswith('HPU') else e for e in original.equipment))
        engine = RandomFactoryEngine(Run.create(31, datetime(2026,10,7,tzinfo=timezone.utc), config.config_id), config, run_nonce='partial', faults_enabled=False)
        engine.start()
        measurements = engine.tick().measurements
        self.assertEqual(len(measurements), 67)
        self.assertFalse(any(m.signal in omitted for m in measurements))

    def test_unbounded_extension_preserves_observed_numeric_value(self):
        from shiftlink.mes.configuration import from_catalog
        from shiftlink.mes.contracts import Measurement, SignalSpec
        from shiftlink.mes.signal_dynamics import SignalDynamics
        from shiftlink.mes.scenarios.priority import expand
        original = expand(from_catalog(json.loads(CATALOG.read_text(encoding='utf-8'))))
        equipment = original.equipment[0]
        extension = SignalSpec('external_probe', 'External observed probe', 'mV')
        config = replace(original, equipment=(replace(equipment, signals=(*equipment.signals, extension)), *original.equipment[1:]))
        at = datetime(2026,10,7,tzinfo=timezone.utc)
        measurement = Measurement(equipment.equipment_id, extension.signal, 42.25, extension.unit, at)
        observed = SignalDynamics(config, 31, 'extension').values(1, at, [measurement])
        self.assertEqual(observed[0].value, measurement.value)
        self.assertEqual(observed[0].quality, measurement.quality)

    def test_persisted_replay_matches_live_observations_without_truth(self):
        service = self.service(random_faults=True, run_nonce='replay', fault_hazard=.1)
        service.control({'command': 'start'})
        live = []
        for _ in range(30):
            service.tick()
            live.append(service.state()['measurements'])
        run_id = service.engine.run.run_id
        replay = service.replay(run_id, -1)['snapshots']
        self.assertEqual([s['measurements'] for s in replay], live)
        exported = service.export(run_id, 'jsonl')
        self.assertNotIn('signal_targets', exported)
        self.assertNotIn('"truth"', exported)
        self.assertNotIn('"intensity"', exported)

    def test_random_ground_truth_is_saved_privately_and_memory_is_drained(self):
        service = self.service(random_faults=True, run_nonce='private-truth', fault_hazard=.1)
        service.control({'command': 'start'})
        for _ in range(30): service.tick()
        run_id = service.engine.run.run_id
        rows = service.storage.connection.execute('SELECT payload FROM simulation_labels WHERE run_id=? ORDER BY sequence', (run_id,)).fetchall()
        self.assertEqual(len(rows), 30)
        self.assertEqual(service.engine.truth, [])
        labels = [json.loads(row[0]) for row in rows]
        self.assertTrue(all(label['profile']['seed'] == 31 for label in labels))
        self.assertTrue(all('private-truth' in label['profile']['run_nonce'] for label in labels))


if __name__ == '__main__': unittest.main()
