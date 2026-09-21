"""Operator recovery, product release, and synthetic component condition journeys."""
import json
from pathlib import Path
import unittest

from shiftlink.mes import configuration
from shiftlink.mes.contracts import Run
from shiftlink.mes.engine import MesEngine
from shiftlink.mes.server import MesService


SCENARIOS = ("gearbox_overheat", "hydraulic_overheat", "gearbox_leak", "coil_quality_hold")


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.service = MesService(Path("docs/data/00_plant_and_relations.json"))
        self.addCleanup(self.service.storage.close)
        self.engine = self.service.engine
        self.engine.start()

    def select(self, scenario):
        self.assertIn(scenario, {s.scenario_id for s in self.engine.config.scenarios})
        self.engine.set_scenario(scenario)
        self.service.tick()

    def actions(self):
        return self.service.state()["recovery"]["actions"]

    def finish_actions(self):
        for action in self.actions():
            self.service.control({"command": "recovery_action", "action_id": action["action_id"]})
            self.service.tick()

    def test_four_scenarios_require_ordered_actions_before_recovery(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                self.service.control({"command": "reset"}); self.engine.start()
                self.select(scenario)
                with self.assertRaises(ValueError):
                    self.engine.recover()
                actions = self.actions()
                with self.assertRaises(ValueError):
                    self.service.control({"command": "recovery_action", "action_id": actions[-1]["action_id"]})
                with self.assertRaises(ValueError):
                    self.engine.set_scenario("drive_fault")
                self.finish_actions()
                self.assertEqual(self.service.state()["recovery"]["stage"], "ready")
                self.engine.recover(); self.service.tick()
                self.assertEqual(self.engine.snapshot.line_mode, "recovering")
                self.service.tick()
                self.assertEqual(self.engine.snapshot.scenario_id, "normal")
                self.assertEqual(self.service.state()["recovery"]["stage"], "completed")

    def test_fault_signal_only_changes_after_verified_actions_and_is_targeted(self):
        self.select("gearbox_overheat")
        values = {(m.equipment_id, m.signal): m.value for m in self.engine.snapshot.measurements}
        gears = [e for e in self.engine.config.equipment if "drive" in e.capabilities]
        self.assertGreater(values[gears[0].equipment_id, "gr_brg_temp"], 62)
        self.assertLessEqual(values[gears[1].equipment_id, "gr_brg_temp"], 62)
        self.finish_actions()
        value = next(m.value for m in self.engine.snapshot.measurements if m.equipment_id == gears[0].equipment_id and m.signal == "gr_brg_temp")
        self.assertLessEqual(value, 62)

    def test_held_coils_never_move_or_exit_until_release(self):
        self.select("coil_quality_hold")
        before = self.engine.snapshot.coils
        self.engine.tick(40)
        self.assertEqual(self.engine.snapshot.coils, before)
        self.assertTrue(all(e.fault_level == "normal" for e in self.engine.snapshot.equipment))
        self.assertTrue(all(c["quality_status"] == "hold" for c in before))
        self.finish_actions()
        self.engine.recover(); self.engine.tick(2)
        self.assertTrue(all(c.get("quality_status") != "hold" for c in self.engine.snapshot.coils))
        self.engine.tick(120)
        self.assertTrue(any(e.event_type == "coil_exited" for e in self.engine.events))

    def test_component_health_changes_on_fault_and_repair_not_on_clock_alone(self):
        self.assertTrue(hasattr(self.engine.snapshot, "components"), "component condition must be visible")
        initial = self.engine.snapshot.components
        self.engine.tick(20)
        running = self.engine.snapshot.components
        self.assertGreater(running[0]["operating_seconds"], initial[0]["operating_seconds"])
        self.assertLess(running[0]["health_percent"], initial[0]["health_percent"])
        self.select("gearbox_leak")
        damaged = [c for c in self.engine.snapshot.components if c["component_id"] == "seal" and c["health_percent"] <= 25]
        self.assertEqual(len(damaged), 1)
        self.engine.pause(); paused = self.engine.snapshot.components
        self.engine.tick(20)
        self.assertEqual(self.engine.snapshot.components, paused)
        self.engine.start(); self.finish_actions()
        repaired = next(c for c in self.engine.snapshot.components if (c["equipment_id"], c["component_id"]) == (damaged[0]["equipment_id"], "seal"))
        self.assertGreaterEqual(repaired["health_percent"], 94)
        self.assertEqual(repaired["maintenance_count"], 1)

    def test_replay_preserves_recovery_condition_and_old_config_shape(self):
        self.select("hydraulic_overheat")
        self.finish_actions()
        state = self.service.state()
        recorded = self.service.replay(self.engine.run.run_id, -1)["snapshots"][-1]
        self.assertEqual(recorded["recovery"], state["recovery"])
        self.assertEqual(recorded["components"], state["components"])
        config = self.engine.config
        self.assertEqual(configuration.from_payload(configuration.to_payload(config)), config)

    def test_action_rejections_and_reset_do_not_reuse_completion(self):
        self.select("gearbox_leak")
        with self.assertRaises(ValueError):
            self.service.control({"command": "recovery_action", "action_id": "unknown"})
        action = self.actions()[0]["action_id"]
        self.service.control({"command": "recovery_action", "action_id": action})
        self.service.control({"command": "recovery_action", "action_id": action})
        self.assertEqual(sum(a["completed"] for a in self.actions()), 1)
        self.service.control({"command": "reset"}); self.engine.start(); self.select("gearbox_leak")
        self.assertFalse(any(a["completed"] for a in self.actions()))

    def test_switch_from_legacy_fault_updates_alarm_and_keeps_action_log(self):
        self.select("drive_fault")
        self.select("gearbox_overheat")
        self.assertEqual(self.engine.snapshot.active_alarms[0].code, "AL-GR-HOT")
        self.finish_actions()
        events = self.service.replay(self.engine.run.run_id, -1)["events"]
        self.assertEqual(sum(e["event_type"] == "recovery_action_completed" for e in events), 3)

    def test_baseline_restart_adds_scenarios_without_rewriting_past_config(self):
        payload = configuration.to_payload(self.engine.config)
        payload["scenarios"] = [s for s in payload["scenarios"] if s["scenario_id"] not in SCENARIOS]
        for eq in payload["equipment"]:
            eq["signals"] = [s for s in eq["signals"] if s["signal"] != "gr_oil_leak"]
        old = configuration.from_payload(payload)
        self.service.storage.save_configuration(old.config_id, json.dumps(configuration.to_payload(old)))
        old_run = Run.create(seed=1, config_id=old.config_id)
        self.service.storage.create_run(old_run)
        restored = MesService(Path("docs/data/00_plant_and_relations.json"), self.service.storage)
        self.assertTrue(set(SCENARIOS) <= {s.scenario_id for s in restored.active_config.scenarios})
        preserved = restored.stored_config(old.config_id)["config"]
        self.assertEqual(len(preserved["scenarios"]), 3)


if __name__ == "__main__":
    unittest.main()
