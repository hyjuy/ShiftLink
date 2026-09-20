"""End-to-end component guarantees for the dependency-free synthetic MES."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from shiftlink.mes import configuration
from shiftlink.mes.adapters import ObserverAdapter
from shiftlink.mes.contracts import GroundTruth, Run
from shiftlink.mes.engine import MesEngine
from shiftlink.mes.storage import MesStorage


UTC = timezone.utc
STARTED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _relation(rel_type, from_id, to_id, lag=10):
    return {"relation_type": rel_type, "from_id": from_id, "to_id": to_id,
            "from_kind": "equipment", "to_kind": "equipment", "lag_seconds": lag}


CATALOG = {
    "production_lines": [{"line_id": "LN-0001"}],
    "equipment": [
        {"equipment_id": "EQ-0001", "code": "HPU-01", "measurement_points": [{"signal": "hpu_pressure", "unit": "bar", "normal_min": 145, "normal_max": 165}]},
        {"equipment_id": "EQ-0004", "code": "GR-01", "measurement_points": [{"signal": "gr_vib_rms", "unit": "mm_s", "normal_min": 0.5, "normal_max": 2.8}]},
        {"equipment_id": "EQ-0006", "code": "RT-01", "measurement_points": [{"signal": "rt_speed", "unit": "m_min", "normal_min": 20, "normal_max": 120}]},
        {"equipment_id": "EQ-0007", "code": "RT-02", "measurement_points": [{"signal": "rt_speed", "unit": "m_min", "normal_min": 20, "normal_max": 120}]},
        {"equipment_id": "EQ-0008", "code": "RT-03", "measurement_points": [{"signal": "rt_speed", "unit": "m_min", "normal_min": 20, "normal_max": 120}]},
        {"equipment_id": "EQ-0009", "code": "CV-01", "measurement_points": [{"signal": "cv_queue_len", "unit": "pct", "normal_min": 0, "normal_max": 70}]},
    ],
    "relations": [
        _relation("material_flow", "EQ-0006", "EQ-0007", 12),
        _relation("material_flow", "EQ-0007", "EQ-0008", 15),
        _relation("material_flow", "EQ-0008", "EQ-0009", 10),
        _relation("drive", "EQ-0004", "EQ-0006", 1),
        _relation("hydraulic_supply", "EQ-0001", "EQ-0007", 5),
        _relation("interlock", "EQ-0009", "EQ-0008", 2),
    ],
}
CONFIG = configuration.from_catalog(CATALOG)


def engine(run_id: str = "integration-run", seed: int = 23) -> MesEngine:
    return MesEngine(Run(run_id, seed, STARTED_AT, config_id=CONFIG.config_id), CONFIG)


def events_for_tick(subject: MesEngine) -> list[object]:
    """Storage requires each event to be saved with its own snapshot sequence."""
    return [event for event in subject.events if event.sequence == subject.snapshot.sequence]


class MesIntegrationTests(unittest.TestCase):
    def test_normal_all_incidents_and_recovery_are_consistent(self) -> None:
        subject = engine()
        subject.start()
        normal = subject.tick()
        self.assertEqual((normal.line_mode, normal.scenario_id), ("running", "normal"))

        cases = {
            "drive_fault": ("EQ-0004", "EQ-0006"),
            "downstream_block": ("EQ-0009", "EQ-0008"),
            "hydraulic_fault": ("EQ-0001", "EQ-0007"),
        }
        for scenario, (cause_id, affected_id) in cases.items():
            with self.subTest(scenario=scenario):
                subject.set_scenario(scenario)
                fault = subject.tick()
                states = {state.equipment_id: state for state in fault.equipment}

                self.assertEqual(fault.line_mode, "fault")
                self.assertEqual(states[cause_id].fault_level, "critical")
                self.assertEqual(states[affected_id].operating_state, "waiting")
                self.assertEqual(states[affected_id].fault_level, "normal")
                self.assertTrue(fault.active_alarms)

                subject.recover()
                recovered = subject.tick(2)
                self.assertEqual((recovered.line_mode, recovered.scenario_id), ("running", "normal"))
                self.assertFalse(recovered.active_alarms)

    def test_fixed_run_inputs_reproduce_after_engine_restart(self) -> None:
        first, restarted = engine("reproducible"), engine("reproducible")
        for subject in (first, restarted):
            subject.start()
            subject.tick(2)
            subject.set_scenario("drive_fault")
            subject.tick(1)
            subject.recover()
            subject.tick(2)

        self.assertEqual(first.snapshot, restarted.snapshot)
        self.assertEqual(first.events, restarted.events)

    def test_service_state_reads_do_not_advance_the_shared_engine(self) -> None:
        """Two dashboard/API clients must observe one engine, not advance two copies."""
        from shiftlink.mes.server import MesService

        service = MesService(Path("docs/00_plant_and_relations.json"), seed=23)
        self.addCleanup(service.storage.close)
        service.control({"command": "start"})
        first_client = service.state()
        second_client = service.state()
        service.tick()

        self.assertEqual(first_client["sequence"], second_client["sequence"])
        self.assertEqual(service.state()["sequence"], first_client["sequence"] + 1)
        self.assertTrue(service.events(-1)["is_synthetic"])

    def test_persisted_replay_and_exports_match_public_runtime_history(self) -> None:
        with TemporaryDirectory() as temporary:
            store = MesStorage(Path(temporary) / "mes.sqlite")
            try:
                subject = engine()
                store.create_run(subject.run)
                subject.start()
                store.save_tick(subject.snapshot, events_for_tick(subject))
                subject.tick()
                store.save_tick(subject.snapshot, events_for_tick(subject))
                subject.set_scenario("hydraulic_fault")
                subject.tick()
                fault = subject.snapshot
                store.save_tick(fault, events_for_tick(subject))

                replayed_snapshots, replayed_events = store.replay(subject.run.run_id)
                jsonl_path = store.export_jsonl(subject.run.run_id, Path(temporary) / "history.jsonl")
                csv_path = store.export_csv(subject.run.run_id, Path(temporary) / "history.csv")

                self.assertEqual(replayed_snapshots[-1], fault)
                self.assertTrue(any(event.event_type == "alarm_raised" for event in replayed_events))
                records = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
                self.assertEqual(len(records), len(replayed_snapshots) + len(replayed_events))
                with csv_path.open(encoding="utf-8") as source:
                    self.assertEqual(sum(1 for _ in csv.DictReader(source)), len(records))
            finally:
                store.close()

    def test_observer_and_exports_exclude_ground_truth_and_future_records(self) -> None:
        with TemporaryDirectory() as temporary:
            store = MesStorage(Path(temporary) / "mes.sqlite")
            try:
                subject = engine()
                store.create_run(subject.run)
                subject.start()
                store.save_tick(subject.snapshot, events_for_tick(subject))
                subject.tick()
                as_of_snapshot = subject.snapshot
                store.save_tick(as_of_snapshot, events_for_tick(subject))
                subject.set_scenario("drive_fault")
                subject.tick()
                store.save_tick(subject.snapshot, events_for_tick(subject))
                store.save_ground_truth(GroundTruth(subject.run.run_id, "SECRET injected cause", STARTED_AT, "future impact", "secret action"))

                public = ObserverAdapter(store).observations(subject.run.run_id, as_of=as_of_snapshot.simulated_at)
                store.export_jsonl(subject.run.run_id, Path(temporary) / "public.jsonl")
                store.export_csv(subject.run.run_id, Path(temporary) / "public.csv")
                public_text = json.dumps(public, default=str)
                exported = (Path(temporary) / "public.jsonl").read_text(encoding="utf-8") + (Path(temporary) / "public.csv").read_text(encoding="utf-8")

                self.assertEqual(public["snapshot"]["sequence"], as_of_snapshot.sequence)
                self.assertTrue(all(event["occurred_at"] <= as_of_snapshot.simulated_at for event in public["events"]))
                self.assertNotIn("SECRET injected cause", public_text + exported)
                self.assertNotIn("ground_truth", public_text + exported)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
