"""Explicit synthetic rejection follows the configured scrap branch, never normal production."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from shiftlink.mes.contracts import Configuration, EquipmentConfig, RelationConfig, Run, ScenarioSpec, SignalSpec
from shiftlink.mes.engine import MesEngine
from shiftlink.mes.scenarios.priority import expand


def configuration():
    equipment = tuple(EquipmentConfig(identifier, identifier, code, code, identifier, profile, ("transport",),
                                      (SignalSpec(signal, signal, "m_min", 60, 60),))
                      for identifier, code, profile, signal in (("source", "RT-03", "rt", "rt_speed"),
                                                               ("finished", "CV-01", "cv", "cv_speed"),
                                                               ("scrap", "CV-02", "cv", "cv_speed")))
    return Configuration("scrap-test", "test", "test", "line", equipment,
                         (RelationConfig("material_flow", "source", "finished"),),
                         ("source", "finished"), (RelationConfig("material_flow", "source", "scrap"),),
                         (ScenarioSpec("normal", "", "", "", ""),
                          ScenarioSpec("scrap_discharge", "transport", "", "", "", stop_on_fault=False)))


def engine(config=None):
    result = MesEngine(Run.create(seed=7), config or configuration())
    result._coils = [result._new_coil("source", 1)]
    result.start()
    return result


class ScrapDischargeTests(unittest.TestCase):
    def test_explicit_rejection_transfers_and_exits_scrap_branch(self):
        result = engine()
        identifier = result._coils[0]["coil_id"]
        result.set_scenario("scrap_discharge")
        snapshot = result.tick()
        rejected = next(coil for coil in snapshot.coils if coil["coil_id"] == identifier)
        self.assertEqual((rejected["equipment_id"], rejected["quality_status"]), ("scrap", "rejected"))
        self.assertEqual(snapshot.line_mode, "running")
        result.pause()
        paused = tuple(dict(coil) for coil in result.snapshot.coils)
        result.tick()
        self.assertEqual(result.snapshot.coils, paused)
        result.resume()
        for _ in range(8):
            result.tick()
        self.assertFalse(any(coil["coil_id"] == identifier for coil in result.snapshot.coils))
        self.assertTrue(any(event.event_type == "coil_exited" and event.equipment_id == "scrap" and identifier in event.observation for event in result.events))
        self.assertEqual(sum(event.event_type == "coil_rejected" and identifier in event.observation for event in result.events), 1)
        result.reset()
        self.assertEqual(result.snapshot.scenario_id, "normal")
        self.assertFalse(any(coil.get("quality_status") == "rejected" for coil in result.snapshot.coils))

    def test_full_branch_waits_and_rejection_survives_normal_selection(self):
        result = engine()
        rejected_id = result._coils[0]["coil_id"]
        blocker = result._new_coil("scrap", 0)
        blocker["quality_status"] = "hold"
        result._coils.append(blocker)
        result.set_scenario("scrap_discharge")
        result.tick()
        rejected = next(coil for coil in result.snapshot.coils if coil["coil_id"] == rejected_id)
        self.assertEqual((rejected["equipment_id"], rejected["quality_status"]), ("source", "rejected"))
        result.set_scenario("normal")
        result._coils.remove(next(coil for coil in result._coils if coil["coil_id"] == blocker["coil_id"]))
        result.tick()
        self.assertEqual(next(coil for coil in result.snapshot.coils if coil["coil_id"] == rejected_id)["equipment_id"], "scrap")

    def test_normal_and_held_loads_are_not_rejected(self):
        result = engine()
        identifier = result._coils[0]["coil_id"]
        result.tick()
        self.assertEqual(next(coil for coil in result.snapshot.coils if coil["coil_id"] == identifier)["equipment_id"], "finished")
        held = engine()
        held._coils[0]["quality_status"] = "hold"
        held.set_scenario("scrap_discharge")
        held.tick()
        self.assertEqual((held._coils[0]["equipment_id"], held._coils[0]["quality_status"]), ("source", "hold"))

    def test_nonrunning_destination_prevents_transfer(self):
        for operating_state in ("waiting", "stopped"):
            with self.subTest(operating_state=operating_state):
                result = engine()
                identifier = result._coils[0]["coil_id"]
                result.set_scenario("scrap_discharge")
                states, mode = result._states()
                states["scrap"] = (operating_state, "normal", "test")
                with patch.object(result, "_states", return_value=(states, mode)):
                    result.tick()
                self.assertEqual(next(coil for coil in result.snapshot.coils if coil["coil_id"] == identifier)["equipment_id"], "source")
                result.tick()
                self.assertEqual(next(coil for coil in result.snapshot.coils if coil["coil_id"] == identifier)["equipment_id"], "scrap")

    def test_scenario_requires_active_material_branch(self):
        config = configuration()
        for invalid in (replace(config, branches=()),
                        replace(config, branches=(RelationConfig("interlock", "source", "scrap"),)),
                        replace(config, equipment=tuple(replace(eq, active=False) if eq.equipment_id == "scrap" else eq for eq in config.equipment))):
            with self.assertRaisesRegex(ValueError, "active RT-03"):
                engine(invalid).set_scenario("scrap_discharge")
        authored = replace(config, scenarios=(config.scenarios[0],))
        self.assertTrue(any(s.scenario_id == "scrap_discharge" for s in expand(authored).scenarios))
        self.assertFalse(any(s.scenario_id == "scrap_discharge" for s in expand(replace(authored, branches=())).scenarios))


if __name__ == "__main__":
    unittest.main()
