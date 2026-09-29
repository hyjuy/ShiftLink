"""New synthetic MES observations remain available for every demo device."""

import unittest
from pathlib import Path

from shiftlink.mes.catalog import Catalog
from shiftlink.mes.configuration import from_catalog, from_payload, to_payload, validate
from shiftlink.mes.contracts import Run
from shiftlink.mes.engine import MesEngine
from shiftlink.mes.scenarios.priority import expand


CATALOG = Path(__file__).parents[1] / "docs/data/reference/00_plant_and_relations.json"


class SensorCoverageTests(unittest.TestCase):
    @staticmethod
    def baseline():
        return from_catalog(Catalog.load(CATALOG).data)

    def test_every_device_has_anomaly_observations_in_config_and_snapshot(self):
        config = self.baseline()
        expected = {
            "HPU-01": {"hpu_pressure", "hpu_flow", "hpu_oil_level", "hpu_pump_current"},
            "PDP-01": {"bus_voltage", "bus_current", "breaker_trip"},
            "CAU-01": {"air_pressure", "air_flow", "compressor_current"},
            "GR-01": {"gr_vib_rms", "gr_brg_temp", "gr_oil_level", "gr_rpm"},
            "GR-02": {"gr_vib_rms", "gr_brg_temp", "gr_oil_level", "gr_rpm"},
            "RT-01": {"rt_speed", "rt_motor_current", "rt_vib_rms"},
            "RT-02": {"rt_speed", "rt_motor_current", "rt_vib_rms"},
            "RT-03": {"rt_speed", "rt_motor_current", "rt_vib_rms"},
            "CV-01": {"cv_speed", "cv_motor_current", "cv_vib_rms"},
            "CV-02": {"cv_speed", "cv_motor_current", "cv_vib_rms"},
        }
        self.assertEqual(validate(config), [])
        self.assertEqual(expand(config).config_id, config.config_id)
        snapshot = MesEngine(Run.create(seed=3, config_id=config.config_id), config).snapshot
        for equipment in config.equipment:
            with self.subTest(equipment=equipment.code):
                configured = {signal.signal for signal in equipment.signals}
                observed = {m.signal for m in snapshot.measurements if m.equipment_id == equipment.equipment_id}
                self.assertTrue(expected[equipment.code] <= configured)
                self.assertEqual(observed, configured)

    def test_expansion_is_idempotent_and_persisted_config_retains_sensors(self):
        config = self.baseline()
        expanded = expand(config)
        restored = from_payload(to_payload(config))

        self.assertEqual(expanded, config)
        self.assertEqual(restored, config)
        self.assertEqual(expand(restored), restored)

    def test_drive_and_transport_speed_are_zero_only_while_stopped(self):
        config = self.baseline()
        engine = MesEngine(Run.create(seed=3, config_id=config.config_id), config)
        speed_signals = {"gr_rpm", "rt_speed", "cv_speed"}
        stopped = [m for m in engine.snapshot.measurements if m.signal in speed_signals]
        self.assertTrue(stopped)
        self.assertTrue(all(m.value == 0 for m in stopped))

        engine.start()
        engine.tick()
        running = [m for m in engine.snapshot.measurements if m.signal in speed_signals]
        self.assertEqual({(m.equipment_id, m.signal) for m in running},
                         {(m.equipment_id, m.signal) for m in stopped})
        self.assertTrue(all(m.value > 0 for m in running))

    def test_motion_dependent_signals_are_zero_while_stopped(self):
        config = self.baseline()
        engine = MesEngine(Run.create(seed=3, config_id=config.config_id), config)
        stopped_signals = {
            "hpu_flow", "hpu_pump_current", "air_flow", "compressor_current",
            "gr_vib_rms", "gr_current", "rt_motor_current", "rt_vib_rms",
            "cv_motor_current", "cv_vib_rms",
        }
        observations = [m for m in engine.snapshot.measurements if m.signal in stopped_signals]
        self.assertTrue(observations)
        self.assertTrue(all(m.value == 0 for m in observations))

        engine.start()
        engine.tick()
        running = [m for m in engine.snapshot.measurements if m.signal in stopped_signals]
        self.assertEqual({(m.equipment_id, m.signal) for m in running},
                         {(m.equipment_id, m.signal) for m in observations})
        self.assertTrue(all(m.value > 0 for m in running))

    def test_manual_based_gearbox_overheat_changes_observed_temperature(self):
        config = self.baseline()
        scenario = next(s for s in config.scenarios if s.scenario_id == "gearbox_overheat")
        self.assertTrue(scenario.source_url)
        engine = MesEngine(Run.create(seed=3, config_id=config.config_id), config)
        engine.start()
        engine.tick()
        cause = next(eq for eq in config.equipment if "drive" in eq.capabilities)
        key = (cause.equipment_id, "gr_brg_temp")
        before = {(m.equipment_id, m.signal): m.value for m in engine.snapshot.measurements}
        engine.set_scenario(scenario.scenario_id)
        after = {(m.equipment_id, m.signal): m.value for m in engine.snapshot.measurements}

        self.assertNotEqual(before[key], after[key])
        self.assertEqual(after[key], 85)


if __name__ == "__main__":
    unittest.main()
