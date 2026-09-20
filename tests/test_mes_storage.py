from datetime import datetime, timedelta, timezone
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
        catalog = Catalog.load(Path("docs/00_plant_and_relations.json"))

        self.assertEqual(catalog.equipment["EQ-0001"]["code"], "HPU-01")
        self.assertEqual(catalog.measurement_point("EQ-0001", "hpu_pressure")["unit"], "bar")
        self.assertEqual(catalog.relations[0]["relation_id"], "REL-0001")

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
        store.save_tick(self.snapshot, [self.event])
        store.save_ground_truth(GroundTruth("run-1", "secret cause", self.started_at, "impact", "action"))

        observed = ObserverAdapter(store).observations("run-1", as_of=self.snapshot.simulated_at)

        self.assertEqual(observed["snapshot"]["sequence"], 1)
        self.assertEqual(observed["events"][0]["event_type"], "tick")
        self.assertNotIn("ground_truth", observed)


if __name__ == "__main__":
    unittest.main()
