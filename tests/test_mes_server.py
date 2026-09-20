from datetime import datetime, timezone
from pathlib import Path
import threading
import unittest


class MesServerTests(unittest.TestCase):
    def test_events_identify_run_and_speed_is_reported(self):
        from shiftlink.mes.server import MesService
        service = MesService(Path("docs/00_plant_and_relations.json"))
        self.addCleanup(service.storage.close)
        service.control({"command": "speed", "speed": 2})
        self.assertEqual(service.state()["speed"], 2)
        self.assertEqual(service.events(-1)["run_id"], service.state()["run_id"])

    def test_invalid_payloads_are_rejected(self):
        from shiftlink.mes.server import MesService
        service = MesService(Path("docs/00_plant_and_relations.json"))
        self.addCleanup(service.storage.close)
        for payload in ([], None, {"command": "speed", "speed": None}, {"command": "speed", "speed": True}):
            with self.assertRaises(ValueError):
                service.control(payload)

    def test_control_advances_a_single_persisted_engine(self) -> None:
        from shiftlink.mes.server import MesService

        service = MesService(Path("docs/00_plant_and_relations.json"))
        before = service.state()["sequence"]
        service.control({"command": "start"})
        service.engine.tick()
        after = service.state()

        self.assertEqual(after["sequence"], before + 1)
        self.assertTrue(after["is_synthetic"])
        self.assertEqual(service.events(-1)["events"][-1]["event_type"], "started")

    def test_control_rejects_unknown_command(self) -> None:
        from shiftlink.mes.server import MesService

        service = MesService(Path("docs/00_plant_and_relations.json"))
        with self.assertRaises(ValueError):
            service.control({"command": "delete"})

    def test_replay_and_exports_use_only_public_records(self) -> None:
        from shiftlink.mes.server import MesService

        service = MesService(Path("docs/00_plant_and_relations.json"))
        service.control({"command": "start"})
        service.tick()
        run_id = service.engine.run.run_id

        self.assertEqual(service.replay(run_id, -1)["snapshots"][0]["run_id"], run_id)
        self.assertIn('"kind": "snapshot"', service.export(run_id, "jsonl"))
        self.assertTrue(service.export(run_id, "csv").startswith("kind,run_id"))

    def test_background_tick_can_persist_sqlite_state(self) -> None:
        from shiftlink.mes.server import MesService

        service = MesService(Path("docs/00_plant_and_relations.json"))
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


if __name__ == "__main__":
    unittest.main()
