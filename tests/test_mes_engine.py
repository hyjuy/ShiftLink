from datetime import datetime, timezone
import unittest
from pathlib import Path

from shiftlink.mes.contracts import Run


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
}


def make_engine(seed: int = 7):
    from shiftlink.mes.engine import MesEngine

    run = Run.create(seed=seed, started_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    return MesEngine(run, CATALOG)


class MesEngineTests(unittest.TestCase):
    def test_pause_resume_preserve_fault_alarm_without_same_tick_events(self):
        engine = make_engine()
        engine.start()
        engine.set_scenario("hydraulic_fault")
        before = engine.tick()
        events = list(engine.events)
        paused = engine.pause()
        self.assertEqual(paused.active_alarms, before.active_alarms)
        self.assertEqual(paused.equipment, before.equipment)
        self.assertEqual(paused.line_mode, "paused")
        resumed = engine.resume()
        self.assertEqual(resumed.active_alarms, before.active_alarms)
        self.assertEqual(resumed.line_mode, "fault")
        self.assertEqual(engine.events, events)
        self.assertEqual(resumed.sequence, before.sequence)

    def test_pending_scenario_does_not_raise_alarm_on_resume(self):
        engine = make_engine()
        engine.start()
        engine.tick()
        engine.pause()
        engine.set_scenario("hydraulic_fault")
        events = list(engine.events)
        engine.resume()
        self.assertEqual(engine.events, events)
        self.assertFalse(engine.snapshot.active_alarms)
        self.assertTrue(engine.tick().active_alarms)

    def test_initial_plus_entered_minus_exited_equals_current_coil_count(self):
        engine = self.real_engine()
        initial_count = len(engine.snapshot.coils)
        engine.start()
        for _ in range(100):
            snapshot = engine.tick()
            entered = sum(event.event_type == "coil_entered" for event in engine.events)
            exited = sum(event.event_type == "coil_exited" for event in engine.events)
            self.assertEqual(initial_count + entered - exited, len(snapshot.coils))
        self.assertGreater(entered, 0)

    def real_engine(self):
        from shiftlink.mes.catalog import Catalog
        from shiftlink.mes.engine import MesEngine
        return MesEngine(Run.create(seed=7), Catalog.load(Path(__file__).resolve().parents[1] / "docs/00_plant_and_relations.json"))

    def test_coils_use_catalog_ids_and_move_forward_without_wrapping(self):
        engine = self.real_engine()
        initial_ids = {coil["coil_id"] for coil in engine.snapshot.coils}
        for coil in engine.snapshot.coils:
            self.assertTrue(str(coil["equipment_id"]).startswith("EQ-"))
            self.assertTrue(str(coil["segment_id"]).startswith("SG-"))
        engine.start()
        for _ in range(100):
            snapshot = engine.tick()
            occupied = [coil["equipment_id"] for coil in snapshot.coils]
            self.assertEqual(len(occupied), len(set(occupied)))
            self.assertNotIn("EQ-0010", occupied)
            self.assertTrue(all(0 <= coil["position"] <= 1 for coil in snapshot.coils))
        self.assertFalse(initial_ids & {coil["coil_id"] for coil in snapshot.coils})
        self.assertTrue(any(event.event_type == "coil_exited" for event in engine.events))

    def test_drive_fault_stops_both_consumers_but_downstream_coil_moves(self):
        engine = self.real_engine()
        engine.start()
        before = {coil["coil_id"]: coil for coil in engine.snapshot.coils}
        engine.set_scenario("drive_fault")
        snapshot = engine.tick()
        states = {item.equipment_id: item for item in snapshot.equipment}
        self.assertEqual(states["EQ-0007"].operating_state, "waiting")
        after = {coil["coil_id"]: coil for coil in snapshot.coils}
        self.assertEqual(before["COIL-001"], after["COIL-001"])
        self.assertNotEqual(before["COIL-003"], after["COIL-003"])
        speeds = {point.equipment_id: point.value for point in snapshot.measurements if point.signal == "rt_speed"}
        self.assertEqual(speeds["EQ-0007"], 0)
        self.assertGreater(speeds["EQ-0008"], 0)

    def test_hydraulic_fault_reaches_conveyor_tensioner(self):
        engine = self.real_engine()
        engine.start()
        engine.set_scenario("hydraulic_fault")
        snapshot = engine.tick()
        states = {item.equipment_id: item for item in snapshot.equipment}
        self.assertEqual(states["EQ-0009"].wait_reason, "hydraulic_supply_low")
        self.assertEqual(states["EQ-0009"].fault_level, "normal")
        self.assertEqual(states["EQ-0010"].operating_state, "running")

    def test_blocked_exit_never_overfills_and_recovery_releases_material(self):
        engine = self.real_engine()
        engine.start()
        engine.set_scenario("downstream_block")
        engine.tick(50)
        stopped = engine.snapshot.coils
        self.assertEqual(stopped, engine.tick(10).coils)
        self.assertEqual(len({coil["equipment_id"] for coil in stopped}), len(stopped))
        self.assertFalse(any(event.event_type == "coil_exited" for event in engine.events))
        engine.recover()
        engine.tick(50)
        self.assertTrue(any(event.event_type == "coil_exited" for event in engine.events))

    def test_reset_restores_initial_coil_identifiers_and_positions(self):
        engine = self.real_engine()
        initial = engine.snapshot.coils
        engine.start()
        engine.tick(50)
        engine.reset()
        self.assertEqual(engine.snapshot.coils, initial)

    def test_seed_and_start_time_produce_identical_observations(self) -> None:
        first, second = make_engine(), make_engine()
        second.run = first.run
        first.start()
        second.start()
        first.tick(3)
        second.tick(3)

        self.assertEqual(first.snapshot, second.snapshot)

    def test_pause_keeps_sequence_and_coils_unchanged(self) -> None:
        engine = make_engine()
        engine.start()
        engine.tick()
        before = engine.snapshot
        engine.pause()
        engine.tick(3)

        self.assertEqual(engine.snapshot.sequence, before.sequence)
        self.assertEqual(engine.snapshot.coils, before.coils)

    def test_each_fault_marks_cause_and_preserves_affected_equipment_normality(self) -> None:
        expectations = {
            "drive_fault": ("EQ-0004", "EQ-0006"),
            "downstream_block": ("EQ-0009", "EQ-0008"),
            "hydraulic_fault": ("EQ-0001", "EQ-0007"),
        }
        for scenario, (cause, affected) in expectations.items():
            with self.subTest(scenario=scenario):
                engine = make_engine()
                engine.start()
                engine.set_scenario(scenario)
                snapshot = engine.tick()
                states = {item.equipment_id: item for item in snapshot.equipment}

                self.assertNotEqual(states[cause].fault_level, "normal")
                self.assertEqual(states[affected].fault_level, "normal")
                self.assertEqual(states[affected].operating_state, "waiting")

    def test_recovery_clears_fault_and_returns_to_normal_running(self) -> None:
        engine = make_engine()
        engine.start()
        engine.set_scenario("hydraulic_fault")
        engine.tick()
        engine.recover()
        engine.tick(2)

        self.assertEqual(engine.snapshot.scenario_id, "normal")
        self.assertEqual(engine.snapshot.line_mode, "running")
        self.assertFalse(engine.snapshot.active_alarms)

    def test_reset_creates_new_run_and_initial_snapshot(self) -> None:
        engine = make_engine()
        engine.start()
        engine.tick()
        old_run = engine.run
        new_run = engine.reset()

        self.assertNotEqual(new_run.run_id, old_run.run_id)
        self.assertEqual(engine.snapshot.sequence, 0)
        self.assertEqual(engine.snapshot.line_mode, "paused")

    def test_accepts_the_catalog_loader_object(self) -> None:
        from shiftlink.mes.catalog import Catalog
        from shiftlink.mes.engine import MesEngine

        engine = MesEngine(Run.create(seed=3, started_at=datetime(2026, 1, 1, tzinfo=timezone.utc)), Catalog(CATALOG))

        self.assertEqual(engine.snapshot.line_id, "LN-0001")

    def test_scenario_alarm_transition_is_emitted_with_its_next_snapshot(self) -> None:
        engine = make_engine()
        engine.start()
        engine.tick()
        recorded_sequence = engine.snapshot.sequence
        event_count = len(engine.events)

        engine.set_scenario("hydraulic_fault")

        self.assertEqual(engine.snapshot.sequence, recorded_sequence)
        self.assertEqual(len(engine.events), event_count)
        snapshot = engine.tick()
        new_events = engine.events[event_count:]
        self.assertEqual(snapshot.sequence, recorded_sequence + 1)
        self.assertTrue(snapshot.active_alarms)
        self.assertTrue(all(event.sequence == snapshot.sequence for event in new_events))


if __name__ == "__main__":
    unittest.main()
