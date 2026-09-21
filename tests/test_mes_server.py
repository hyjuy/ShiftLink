from datetime import datetime, timezone
from pathlib import Path
import threading
import unittest


class MesServerTests(unittest.TestCase):
    def test_events_identify_run_and_speed_is_reported(self):
        from shiftlink.mes.server import MesService
        service = MesService(Path("docs/data/00_plant_and_relations.json"))
        self.addCleanup(service.storage.close)
        service.control({"command": "speed", "speed": 2})
        self.assertEqual(service.state()["speed"], 2)
        self.assertEqual(service.events(-1)["run_id"], service.state()["run_id"])

    def test_invalid_payloads_are_rejected(self):
        from shiftlink.mes.server import MesService
        service = MesService(Path("docs/data/00_plant_and_relations.json"))
        self.addCleanup(service.storage.close)
        for payload in ([], None, {"command": "speed", "speed": None}, {"command": "speed", "speed": True}):
            with self.assertRaises(ValueError):
                service.control(payload)

    def test_control_advances_a_single_persisted_engine(self) -> None:
        from shiftlink.mes.server import MesService

        service = MesService(Path("docs/data/00_plant_and_relations.json"))
        before = service.state()["sequence"]
        service.control({"command": "start"})
        service.engine.tick()
        after = service.state()

        self.assertEqual(after["sequence"], before + 1)
        self.assertTrue(after["is_synthetic"])
        self.assertEqual(service.events(-1)["events"][-1]["event_type"], "started")

    def test_control_rejects_unknown_command(self) -> None:
        from shiftlink.mes.server import MesService

        service = MesService(Path("docs/data/00_plant_and_relations.json"))
        with self.assertRaises(ValueError):
            service.control({"command": "delete"})

    def test_replay_and_exports_use_only_public_records(self) -> None:
        from shiftlink.mes.server import MesService

        service = MesService(Path("docs/data/00_plant_and_relations.json"))
        service.control({"command": "start"})
        service.tick()
        run_id = service.engine.run.run_id

        self.assertEqual(service.replay(run_id, -1)["snapshots"][0]["run_id"], run_id)
        self.assertIn('"kind": "snapshot"', service.export(run_id, "jsonl"))
        self.assertTrue(service.export(run_id, "csv").startswith("kind,run_id"))

    def test_background_tick_can_persist_sqlite_state(self) -> None:
        from shiftlink.mes.server import MesService

        service = MesService(Path("docs/data/00_plant_and_relations.json"))
        service.control({"command": "start"})
        errors: list[Exception] = []
        worker = threading.Thread(target=lambda: self._tick(service, errors))
        worker.start(); worker.join()

        self.assertEqual(errors, [])
        self.assertEqual(service.replay(service.engine.run.run_id, -1)["snapshots"][0]["sequence"], 1)

    @staticmethod
    def _tick(service, errors: list[Exception]) -> None:
        try:
            service.tick()
        except Exception as error:
            errors.append(error)


class MesServerConfigTests(unittest.TestCase):
    def _service(self):
        from shiftlink.mes.server import MesService
        service = MesService(Path("docs/data/00_plant_and_relations.json"))
        self.addCleanup(service.storage.close)
        return service

    def _draft(self, service, mutate=None):
        from shiftlink.mes import configuration
        payload = configuration.to_payload(service.active_config)
        if mutate:
            mutate(payload)
        return payload

    def test_state_and_replay_expose_config_linkage(self):
        service = self._service()
        state = service.state()
        self.assertEqual(state["config_id"], service.active_config.config_id)
        service.control({"command": "start"})
        service.tick()
        replay = service.replay(service.engine.run.run_id, -1)
        self.assertEqual(replay["config_id"], service.active_config.config_id)
        self.assertTrue(replay["config_preserved"])

    def test_apply_rejected_while_running_and_on_stale_base(self):
        from shiftlink.mes.server import ConflictError
        service = self._service()
        draft = self._draft(service)
        service.control({"command": "start"})
        service.tick()
        with self.assertRaises(ConflictError):
            service.apply_config({"base_config_id": service.active_config.config_id, "draft": draft})
        service.control({"command": "pause"})
        with self.assertRaises(ConflictError):
            service.apply_config({"base_config_id": "stale", "draft": draft})
        # active configuration and run remain untouched after both refusals
        self.assertEqual(service.state()["config_id"], service.active_config.config_id)

    def test_apply_swap_creates_new_run_and_preserves_old_one(self):
        service = self._service()
        service.control({"command": "start"})
        service.tick()
        old_run = service.engine.run.run_id
        old_config = service.active_config.config_id
        old_replay = service.replay(old_run, -1)
        service.control({"command": "pause"})

        def swap_hpu(payload):
            for item in payload["equipment"]:
                if item["code"].startswith("HPU"):
                    item["asset_id"] = "AS-EQ-0001-002"
                    item["name"] = item["name"] + " (교체)"
            payload["version_label"] = "B-hpu-swap"

        result = service.apply_config({
            "base_config_id": old_config, "draft": self._draft(service, swap_hpu),
            "reason": "HPU 자산 교체", "actor": "테스트(자기기입)",
        })
        self.assertNotEqual(result["run_id"], old_run)
        self.assertNotEqual(result["config_id"], old_config)
        self.assertEqual(result["previous_run_id"], old_run)
        # old run replays exactly as before, with its original config linkage
        replay_again = service.replay(old_run, -1)
        self.assertEqual(replay_again["snapshots"], old_replay["snapshots"])
        self.assertEqual(replay_again["config_id"], old_config)
        # both configurations are retrievable for replay rendering
        self.assertIsNotNone(service.storage.get_configuration(old_config))
        self.assertIsNotNone(service.storage.get_configuration(result["config_id"]))
        # change history recorded
        changes = service.storage.list_config_changes()
        self.assertEqual(changes[-1]["status"], "applied")
        self.assertEqual(changes[-1]["new_config_id"], result["config_id"])

    def test_apply_validation_failure_keeps_active_config_and_history(self):
        from shiftlink.mes.server import ConfigValidationError
        service = self._service()
        before_runs = len(service.runs()["runs"])

        def break_route(payload):
            payload["route"] = ["EQ-MISSING"]
            payload["version_label"] = "broken"

        with self.assertRaises(ConfigValidationError) as caught:
            service.apply_config({"base_config_id": service.active_config.config_id,
                                  "draft": self._draft(service, break_route)})
        self.assertTrue(caught.exception.errors)
        self.assertEqual(len(service.runs()["runs"]), before_runs)
        self.assertEqual(service.storage.list_config_changes()[-1]["status"], "rejected")

    def test_rollback_is_a_new_run_referencing_the_previous_config(self):
        service = self._service()
        config_a = service.active_config.config_id
        draft_b = self._draft(service, lambda p: p.update(version_label="B"))
        result_b = service.apply_config({"base_config_id": config_a, "draft": draft_b})
        draft_a_again = self._draft(service)  # payload of B
        # roll back by applying A's stored payload as a new configuration
        stored_a = service.storage.get_configuration(config_a)
        result_back = service.apply_config({"base_config_id": result_b["config_id"], "draft": stored_a})
        self.assertEqual(result_back["config_id"], config_a)
        self.assertNotEqual(result_back["run_id"], result_b["run_id"])
        del draft_a_again


if __name__ == "__main__":
    unittest.main()
