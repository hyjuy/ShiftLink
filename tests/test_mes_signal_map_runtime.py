"""Check the synthetic MES output promised by the KB MES signal map."""

import json
from pathlib import Path
import unittest

from shiftlink.mes.adapters import ObserverAdapter
from shiftlink.mes.catalog import Catalog
from shiftlink.mes.configuration import from_catalog
from shiftlink.mes.contracts import Run
from shiftlink.mes.engine import MesEngine
from shiftlink.mes.storage import MesStorage


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs/data/reference/00_plant_and_relations.json"
SIGNAL_MAP = ROOT / "docs/data/knowledge_cards/kb/20260929-A/mes_signal_map.json"

# scenario, cause equipment, affected signal/value, alarm, downstream wait IDs
EXPECTED = (
    ("drive_fault", "EQ-0004", "gr_vib_rms", 5.0, "AL-DRV-VIB", ("EQ-0006", "EQ-0007")),
    ("hydraulic_fault", "EQ-0001", "hpu_pressure", 120.0, "AL-HYD-LOW", ("EQ-0006", "EQ-0007", "EQ-0008", "EQ-0009")),
    ("downstream_block", "EQ-0009", "cv_queue_len", 95.0, "AL-DSB-QUE", ("EQ-0008",)),
    ("gearbox_overheat", "EQ-0004", "gr_brg_temp", 85.0, "AL-GR-HOT", ("EQ-0006", "EQ-0007")),
    ("hydraulic_overheat", "EQ-0001", "hpu_oil_temp", 78.0, "AL-HYD-HOT", ("EQ-0006", "EQ-0007", "EQ-0008", "EQ-0009")),
    ("gearbox_leak", "EQ-0004", "gr_oil_leak", 1.0, "AL-GR-LEAK", ("EQ-0006", "EQ-0007")),
    ("cau_supply_fault", "EQ-0003", "air_pressure", 450.0, "AL-AIR-LOW", ("EQ-0009",)),
    ("pdp_trip", "EQ-0002", "breaker_trip", 1.0, "AL-PDP-TRIP", ("EQ-0004", "EQ-0005", "EQ-0001")),
)


class MesSignalMapRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = from_catalog(Catalog.load(CATALOG).data)
        cls.signal_map = json.loads(SIGNAL_MAP.read_text(encoding="utf-8"))

    def test_map_covers_current_runtime_signals(self):
        configured = {signal.signal for eq in self.config.equipment for signal in eq.signals}
        mapped = {signal["signal"] for card in self.signal_map["cards"] for signal in card["signals"]}
        mapped.update(self.signal_map["unlinked"]["signals"])
        self.assertEqual(mapped, configured)
        snapshot = MesEngine(Run.create(seed=23, config_id=self.config.config_id), self.config).snapshot
        self.assertEqual({(item.equipment_id, item.signal) for item in snapshot.measurements},
                         {(eq.equipment_id, signal.signal) for eq in self.config.equipment
                          for signal in eq.signals if eq.active})
        self.assertEqual(len(snapshot.measurements), 46)

    def test_mapped_signal_units_and_equipment_match_configuration(self):
        equipment = {eq.code: eq for eq in self.config.equipment}
        for card in self.signal_map["cards"]:
            for mapped in card["signals"]:
                for code in mapped["equipment"].split("/"):
                    with self.subTest(card=card["card_id"], signal=mapped["signal"], equipment=code):
                        spec = next(signal for signal in equipment[code].signals
                                    if signal.signal == mapped["signal"])
                        self.assertEqual(spec.unit, mapped["unit"])
                        if mapped["direction"] != "any":
                            self.assertIsNotNone(spec.normal_min)
                            self.assertIsNotNone(spec.normal_max)

    def test_scenario_measurements_and_alarms_match_map(self):
        mapped_scenarios = {scenario for card in self.signal_map["cards"] for scenario in card["scenarios"]}
        mapped_scenarios.update(self.signal_map["unlinked"]["scenarios"])
        self.assertEqual(mapped_scenarios, {scenario.scenario_id for scenario in self.config.scenarios})

        for scenario, cause_id, signal, value, alarm, wait_ids in EXPECTED:
            with self.subTest(scenario=scenario):
                run = Run.create(seed=23, config_id=self.config.config_id)
                engine = MesEngine(run, self.config)
                store = MesStorage()
                try:
                    store.create_run(run)
                    engine.start()
                    store.save_tick(engine.tick())
                    engine.set_scenario(scenario)
                    store.save_tick(engine.tick())
                    observed = ObserverAdapter(store).observations(run.run_id)["snapshot"]
                    measurement = next(item for item in observed["measurements"]
                                       if item["equipment_id"] == cause_id and item["signal"] == signal)
                    self.assertEqual(measurement["value"], value)
                    point = next(spec for eq in self.config.equipment if eq.equipment_id == cause_id
                                 for spec in eq.signals if spec.signal == signal)
                    self.assertEqual(measurement["unit"], point.unit)
                    self.assertEqual(measurement["quality"], "good")
                    self.assertTrue(value > point.normal_max or value < point.normal_min)
                    if scenario == "hydraulic_fault":
                        flow = next(item for item in observed["measurements"]
                                    if item["equipment_id"] == cause_id and item["signal"] == "hpu_flow")
                        self.assertEqual(flow["value"], 0.0)
                    alarms = {(item["equipment_id"], item["code"]) for item in observed["active_alarms"]}
                    self.assertIn((cause_id, alarm), alarms)
                    states = {item["equipment_id"]: item for item in observed["equipment"]}
                    self.assertEqual(states[cause_id]["fault_level"], "critical")
                    for affected in wait_ids:
                        self.assertEqual(states[affected]["wait_reason"],
                                         next(spec.wait_reason for spec in self.config.scenarios
                                              if spec.scenario_id == scenario))
                finally:
                    store.close()

    def test_quality_hold_has_no_signal_effect_or_alarm(self):
        run = Run.create(seed=23, config_id=self.config.config_id)
        engine = MesEngine(run, self.config)
        engine.start()
        engine.tick()
        before = {(item.equipment_id, item.signal): item.value for item in engine.snapshot.measurements}
        engine.set_scenario("coil_quality_hold")
        engine.tick()
        after = {(item.equipment_id, item.signal): item.value for item in engine.snapshot.measurements}
        self.assertEqual(before.keys(), after.keys())
        self.assertFalse(engine.snapshot.active_alarms)
        self.assertTrue(all(coil["quality_status"] == "hold" for coil in engine.snapshot.coils))


if __name__ == "__main__":
    unittest.main()
