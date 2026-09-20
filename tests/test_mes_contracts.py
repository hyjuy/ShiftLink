from datetime import datetime, timezone
import unittest


class MesContractTests(unittest.TestCase):
    def test_snapshot_keeps_runtime_and_support_scenarios_distinct(self) -> None:
        from shiftlink.mes.contracts import Run, Snapshot

        run = Run.create(seed=7, started_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        snapshot = Snapshot(
            run_id=run.run_id,
            sequence=0,
            simulated_at=run.started_at,
            line_id="LN-0001",
            line_mode="running",
            scenario_id="normal",
            support_scenario="S1",
        )

        self.assertTrue(run.is_synthetic)
        self.assertEqual(snapshot.scenario_id, "normal")
        self.assertEqual(snapshot.support_scenario, "S1")
        self.assertEqual(snapshot.key, (run.run_id, 0))


if __name__ == "__main__":
    unittest.main()
