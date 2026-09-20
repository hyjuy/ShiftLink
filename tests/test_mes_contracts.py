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

    def test_run_records_applied_configuration_or_none(self) -> None:
        from shiftlink.mes.contracts import Run

        legacy = Run("run-legacy", 1, datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertIsNone(legacy.config_id)

        linked = Run.create(seed=1, config_id="abc123")
        self.assertEqual(linked.config_id, "abc123")

    def test_configuration_contract_shapes(self) -> None:
        from shiftlink.mes.contracts import (
            Configuration, EquipmentConfig, LayoutGroup, RelationConfig,
            ScenarioSpec, SignalEffect, SignalSpec,
        )

        hpu = EquipmentConfig(
            equipment_id="EQ-0001", asset_id="AS-EQ-0001-001", code="HPU-01", name="유압 유닛",
            segment_id="SG-0004", profile_id="hpu", capabilities=("hydraulic_supply",),
            signals=(SignalSpec("hpu_pressure", "유압", "bar", 140.0, 180.0),),
        )
        config = Configuration(
            config_id="hash", version_label="A", source="test", line_id="LN-0001",
            equipment=(hpu,),
            relations=(RelationConfig("hydraulic_supply", "EQ-0001", "EQ-0006"),),
            route=("EQ-0006",),
            scenarios=(ScenarioSpec(
                "hydraulic_fault", "hydraulic_supply", "hydraulic_supply",
                "hydraulic_supply_low", "AL-HYD-LOW",
                signal_effects=(SignalEffect("hydraulic_supply", "hpu_pressure", 120.0),),
            ),),
            layout=(LayoutGroup("주경로", ("EQ-0006",)),),
        )

        self.assertEqual(config.equipment_by_id()["EQ-0001"].asset_id, "AS-EQ-0001-001")
        # frozen contracts: nobody mutates a configuration in place
        with self.assertRaises(Exception):
            config.equipment[0].asset_id = "other"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
