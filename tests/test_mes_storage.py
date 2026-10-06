from datetime import datetime, timedelta, timezone
import multiprocessing
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from shiftlink.mes.adapters import ObserverAdapter
from shiftlink.mes.catalog import Catalog
from shiftlink.mes.contracts import (
    EquipmentState,
    GroundTruth,
    Measurement,
    Run,
    RuntimeEvent,
    Snapshot,
)
from shiftlink.mes.storage import MesStorage


UTC = timezone.utc


def _concurrent_store(path, role, channel, query_id):
    store = MesStorage(path)
    try:
        channel.send("ready")
        channel.recv()
        if role == "writer":
            store.connection.execute("BEGIN EXCLUSIVE")
            store.save_configuration("concurrent", '{"written": true}', commit=False)
            channel.send("locked")
            channel.recv()
            store.connection.commit()
            store.save_handover({"handover_id": "new-note", "memo_text": "retained"})
            store.save_query({"answer": "retained"})
        else:
            channel.send((len(store.pending_handovers()), len(store.pending_queries())))
            channel.send("marking")
            store.mark_handover("old-note", "uploaded")
            store.mark_query(query_id, "uploaded")
        channel.send("done")
    except Exception as error:
        channel.send((type(error).__name__, str(error)))
    finally:
        store.close()
        channel.close()


class MesStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.started_at = datetime(2026, 1, 1, tzinfo=UTC)
        self.run = Run("run-1", 7, self.started_at)
        self.snapshot = Snapshot(
            run_id=self.run.run_id,
            sequence=1,
            simulated_at=self.started_at + timedelta(seconds=1),
            line_id="LN-0001",
            line_mode="running",
            scenario_id="normal",
            equipment=(EquipmentState("EQ-0001", "running"),),
            measurements=(Measurement("EQ-0001", "hpu_pressure", 150, "bar", self.started_at),),
        )
        self.event = RuntimeEvent("run-1", 1, self.snapshot.simulated_at, "tick", "EQ-0001", "normal")

    def test_catalog_preserves_reference_ids_and_signal_units(self) -> None:
        catalog = Catalog.load(Path("docs/data/reference/00_plant_and_relations.json"))

        self.assertEqual(catalog.equipment["EQ-0001"]["code"], "HPU-01")
        self.assertEqual(catalog.measurement_point("EQ-0001", "hpu_pressure")["unit"], "bar")
        self.assertEqual(catalog.relations[0]["relation_id"], "REL-0001")

    def test_separate_processes_read_pending_and_preserve_concurrent_writes(self) -> None:
        path = Path(self.temp.name) / "shared.sqlite"
        store = MesStorage(path)
        store.save_handover({"handover_id": "old-note", "memo_text": "original"})
        query_id = store.save_query({"answer": "original"})
        self.assertEqual(store.connection.execute("PRAGMA busy_timeout").fetchone()[0], 5000)
        store.close()

        context = multiprocessing.get_context("spawn")
        processes, channels = [], []
        try:
            for role in ("writer", "uploader"):
                parent, child = context.Pipe()
                process = context.Process(target=_concurrent_store, args=(path, role, child, query_id))
                process.start()
                child.close()
                processes.append(process)
                channels.append(parent)
                self.assertTrue(parent.poll(10), "store initialization timed out")
                self.assertEqual(parent.recv(), "ready")
            writer, uploader = channels
            writer.send("write")
            self.assertTrue(writer.poll(10))
            self.assertEqual(writer.recv(), "locked")
            uploader.send("upload")
            self.assertTrue(uploader.poll(10), "pending read blocked by writer")
            self.assertEqual(uploader.recv(), (1, 1))
            self.assertTrue(uploader.poll(10))
            self.assertEqual(uploader.recv(), "marking")
            self.assertFalse(uploader.poll(0.1), "upload marker bypassed the active writer")
            writer.send("release")
            for channel in channels:
                self.assertTrue(channel.poll(10), "concurrent write timed out")
                self.assertEqual(channel.recv(), "done")
            for process in processes:
                process.join(10)
                self.assertEqual(process.exitcode, 0)
        finally:
            if channels:
                try:
                    channels[0].send("release")
                except (BrokenPipeError, OSError):
                    pass
            for process in processes:
                process.join(3)
                if process.is_alive():
                    process.terminate()
                    process.join(3)
            for channel in channels:
                channel.close()

        reopened = MesStorage(path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.get_handover("old-note")["status"], "uploaded")
        self.assertEqual(reopened.get_handover("old-note")["payload"]["memo_text"], "original")
        self.assertEqual(reopened.get_handover("new-note")["payload"]["memo_text"], "retained")
        self.assertEqual(reopened.get_configuration("concurrent"), {"written": True})
        self.assertEqual(reopened.outbox_counts()["handover"], {"pending": 1, "uploaded": 1, "conflict": 0})
        self.assertEqual(reopened.outbox_counts()["query"], {"pending": 1, "uploaded": 1, "conflict": 0})
        self.assertEqual(reopened.connection.execute(
            "SELECT status, payload FROM query_log WHERE query_id = ?", (query_id,)
        ).fetchone(), ("uploaded", '{"answer": "original"}'))
        self.assertEqual(reopened.pending_queries()[0][2], '{"answer": "retained"}')

    def test_tick_is_atomic_replayable_and_duplicate_is_rejected(self) -> None:
        store = MesStorage(Path(self.temp.name) / "mes.sqlite")
        self.addCleanup(store.close)
        store.create_run(self.run)
        store.save_tick(self.snapshot, [self.event])

        self.assertEqual(store.snapshots("run-1"), [self.snapshot])
        self.assertEqual(store.events("run-1"), [self.event])
        with self.assertRaises(ValueError):
            store.save_tick(self.snapshot, [self.event])

    def test_exports_are_re_readable_and_never_include_ground_truth(self) -> None:
        store = MesStorage(Path(self.temp.name) / "mes.sqlite")
        self.addCleanup(store.close)
        store.create_run(self.run)
        store.save_tick(self.snapshot, [self.event])
        store.save_ground_truth(GroundTruth("run-1", "secret cause", self.started_at, "impact", "action"))
        jsonl = Path(self.temp.name) / "record.jsonl"
        csv = Path(self.temp.name) / "record.csv"

        store.export_jsonl("run-1", jsonl)
        store.export_csv("run-1", csv)

        self.assertIn('"kind": "snapshot"', jsonl.read_text(encoding="utf-8"))
        self.assertNotIn("secret cause", jsonl.read_text(encoding="utf-8"))
        self.assertIn("snapshot", csv.read_text(encoding="utf-8"))
        self.assertNotIn("secret cause", csv.read_text(encoding="utf-8"))

    def test_observer_excludes_ground_truth_and_future_observations(self) -> None:
        store = MesStorage(Path(self.temp.name) / "mes.sqlite")
        self.addCleanup(store.close)
        store.create_run(self.run)
        allowed = RuntimeEvent("run-1", 1, self.snapshot.simulated_at, "alarm_raised", "EQ-0001", "AL-HYD-LOW")
        store.save_tick(self.snapshot, [allowed])
        store.save_ground_truth(GroundTruth("run-1", "secret cause", self.started_at, "impact", "action"))

        observed = ObserverAdapter(store).observations("run-1", as_of=self.snapshot.simulated_at)

        self.assertEqual(observed["snapshot"]["sequence"], 1)
        self.assertEqual(observed["events"][0]["event_type"], "alarm_raised")
        self.assertNotIn("ground_truth", observed)

    def test_observer_allowlist_blocks_injected_cause_markers(self) -> None:
        store = MesStorage(Path(self.temp.name) / "mes.sqlite")
        self.addCleanup(store.close)
        run = Run("run-2", 7, self.started_at, config_id="cfg-hash")
        store.create_run(run)
        snapshot = Snapshot(
            run_id="run-2", sequence=1, simulated_at=self.started_at + timedelta(seconds=1),
            line_id="LN-0001", line_mode="fault", scenario_id="hydraulic_fault",
        )
        events = [
            RuntimeEvent("run-2", 1, snapshot.simulated_at, "scenario_selected", None, "hydraulic_fault"),
            RuntimeEvent("run-2", 1, snapshot.simulated_at, "recovery_started", None, "recovery in progress"),
            RuntimeEvent("run-2", 1, snapshot.simulated_at, "alarm_raised", "EQ-0001", "AL-HYD-LOW"),
        ]
        store.save_tick(snapshot, events)

        observed = ObserverAdapter(store).observations("run-2", as_of=snapshot.simulated_at)

        self.assertEqual([e["event_type"] for e in observed["events"]], ["alarm_raised"])
        self.assertNotIn("scenario_id", observed["snapshot"])
        self.assertEqual(observed["config_id"], "cfg-hash")
        self.assertNotIn("hydraulic_fault", str(observed))

    def test_configuration_history_is_persisted_and_legacy_runs_stay_loadable(self) -> None:
        store = MesStorage(Path(self.temp.name) / "mes.sqlite")
        self.addCleanup(store.close)
        store.save_configuration("cfg-a", '{"version_label": "A"}')
        store.save_configuration("cfg-a", '{"version_label": "A"}')  # idempotent
        self.assertEqual(store.get_configuration("cfg-a"), {"version_label": "A"})
        self.assertIsNone(store.get_configuration("missing"))

        store.record_config_change({
            "change_id": "chg-1", "requested_at": "2026-09-20T00:00:00+00:00",
            "base_config_id": "cfg-a", "new_config_id": "cfg-b", "status": "applied",
            "reason": "HPU 교체", "actor": "작업자(자기기입)",
        })
        changes = store.list_config_changes()
        self.assertEqual(changes[0]["change_id"], "chg-1")
        self.assertEqual(changes[0]["status"], "applied")
        self.assertEqual(changes[0]["actor_self_reported"], 1)

        # legacy run (no config_id in payload) still loads, reported as unpreserved
        store.create_run(self.run)
        loaded = store.get_run("run-1")
        self.assertIsNotNone(loaded)
        self.assertIsNone(loaded.config_id)


if __name__ == "__main__":
    unittest.main()
