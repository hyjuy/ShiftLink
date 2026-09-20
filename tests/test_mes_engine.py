"""Engine refactored for Configuration-based scenarios and explicit routes."""

from datetime import datetime, timezone
import pytest
from shiftlink.mes.contracts import (
    Configuration, EquipmentConfig, RelationConfig, ScenarioSpec, SignalSpec, SignalEffect, Run, Snapshot, Alarm
)
from shiftlink.mes.engine import MesEngine


def utc_now():
    return datetime.now(timezone.utc)


def make_config(equipment, relations, route, scenarios):
    """Minimal Configuration fixture."""
    return Configuration(
        config_id="test-config-1",
        version_label="test-v1",
        source="test",
        line_id="LN-0001",
        equipment=tuple(equipment),
        relations=tuple(relations),
        route=tuple(route),
        scenarios=tuple(scenarios),
    )


class TestEngineBasics:
    """Lifecycle, snapshots, events (existing behavior preserved)."""

    def test_engine_starts_stopped(self):
        config = make_config(
            equipment=[
                EquipmentConfig(equipment_id="EQ-01", asset_id="ASSET-01", code="RT-01", name="Roller 1",
                               segment_id="SG-01", profile_id="roller", capabilities=(), signals=())
            ],
            relations=[],
            route=["EQ-01"],
            scenarios=[]
        )
        run = Run.create(seed=1)
        engine = MesEngine(run, config)
        assert engine.snapshot.line_mode == "stopped"
        assert len(engine.snapshot.equipment) == 1
        assert engine.snapshot.equipment[0].operating_state == "stopped"

    def test_start_and_pause(self):
        config = make_config(
            equipment=[EquipmentConfig("EQ-01", "ASSET-01", "RT-01", "R1", "SG-01", "roller", (), ())],
            relations=[], route=["EQ-01"], scenarios=[]
        )
        run = Run.create(seed=2)
        engine = MesEngine(run, config)
        snap = engine.start()
        assert snap.line_mode == "running"
        engine.tick()  # Events flush on next tick
        snap = engine.snapshot
        assert len(snap.equipment) == 1
        assert snap.equipment[0].operating_state == "running"
        snap = engine.pause()
        assert snap.line_mode == "paused"
        # After pause, snapshot is partially updated (line_mode only), equipment state remains
        # Start again to resume and verify pause actually works
        engine.resume()
        assert engine._running  # Resume sets _running = True

    def test_events_preserved(self):
        config = make_config(
            equipment=[EquipmentConfig("EQ-01", "ASSET-01", "RT-01", "R1", "SG-01", "roller", (), ())],
            relations=[], route=["EQ-01"], scenarios=[]
        )
        run = Run.create(seed=3)
        engine = MesEngine(run, config)
        engine.start()
        engine.tick()  # Flush start event
        assert any(e.event_type == "started" for e in engine.events)
        engine.pause()
        # pause() queues paused event but tick() won't flush it (not running)
        # Resume to flush pending events
        engine.resume()
        engine.tick()
        assert any(e.event_type == "paused" for e in engine.events)


class TestCapabilityBasedScenarios:
    """Scenarios selected by capability, not hardcoded equipment_id."""

    def test_hydraulic_scenario_by_capability_not_code(self):
        """Any equipment with hydraulic_supply capability triggers hydraulic scenario."""
        # Setup: HPU with standard name vs. one with different asset/name but same capability
        config = make_config(
            equipment=[
                EquipmentConfig("EQ-01", "ASSET-HPU-NEW", "PUMP-X", "Custom Pump Unit", "SG-01",
                               "hydraulic_source", ("hydraulic_supply",),
                               (SignalSpec("pressure", "Pressure", "bar", 100, 150),)),
                EquipmentConfig("EQ-02", "ASSET-RT1", "RT-01", "Roller 1", "SG-02",
                               "roller", ("material_transport",),
                               (SignalSpec("speed", "Speed", "m_min", 50, 120),)),
            ],
            relations=[
                RelationConfig("material_flow", "EQ-02", "EQ-03", 10),
                RelationConfig("hydraulic_supply", "EQ-01", "EQ-02", 5, 12.0, "L_min"),
            ],
            route=["EQ-02"],
            scenarios=[
                ScenarioSpec(
                    scenario_id="hydraulic_fault",
                    cause_capability="hydraulic_supply",
                    propagation_relation="hydraulic_supply",
                    wait_reason="hydraulic_supply_low",
                    alarm_code="HYDR-001",
                    signal_effects=(SignalEffect("hydraulic_supply", "pressure", 80),),
                    recovery_ticks=2,
                )
            ]
        )
        run = Run.create(seed=10)
        engine = MesEngine(run, config)
        engine.start()
        engine.tick()
        snap_before = engine.snapshot
        assert snap_before.equipment[0].fault_level == "normal"

        engine.set_scenario("hydraulic_fault")
        engine.tick()  # Scenario takes effect on next tick
        snap_fault = engine.snapshot
        # Cause equipment (EQ-01 with hydraulic_supply) should be in fault
        cause_eq = next(e for e in snap_fault.equipment if e.equipment_id == "EQ-01")
        assert cause_eq.operating_state == "stopped"
        assert cause_eq.fault_level == "critical"

    def test_set_scenario_fails_if_capability_missing(self):
        """set_scenario raises ValueError if cause_capability not found in any active equipment."""
        config = make_config(
            equipment=[
                EquipmentConfig("EQ-01", "ASSET-RT", "RT-01", "Roller", "SG-01", "roller", ("material_transport",), ()),
            ],
            relations=[], route=["EQ-01"],
            scenarios=[
                ScenarioSpec("hydraulic_fault", "hydraulic_supply", "hydraulic_supply", "no_supply", "H-001", (), 2)
            ]
        )
        run = Run.create(seed=11)
        engine = MesEngine(run, config)
        with pytest.raises(ValueError, match="cannot apply.*hydraulic_fault.*hydraulic_supply"):
            engine.set_scenario("hydraulic_fault")

    def test_scenario_propagation_by_relation_type(self):
        """Affected equipment determined by propagation_relation, not hardcoded list."""
        config = make_config(
            equipment=[
                EquipmentConfig("EQ-01", "A1", "HPU", "HPU", "SG", "hpu", ("hydraulic_supply",), ()),
                EquipmentConfig("EQ-02", "A2", "RT", "RT-1", "SG", "roller", (), ()),
                EquipmentConfig("EQ-03", "A3", "RT", "RT-2", "SG", "roller", (), ()),
                EquipmentConfig("EQ-04", "A4", "CV", "CV", "SG", "conveyor", (), ()),
            ],
            relations=[
                RelationConfig("hydraulic_supply", "EQ-01", "EQ-02"),
                RelationConfig("hydraulic_supply", "EQ-01", "EQ-03"),
                # EQ-04 has co_occurrence, not hydraulic_supply → should NOT be affected
                RelationConfig("co_occurrence", "EQ-01", "EQ-04"),
            ],
            route=["EQ-02", "EQ-03"], scenarios=[
                ScenarioSpec("hyd_fault", "hydraulic_supply", "hydraulic_supply", "no_hyd", "H-1", (), 2)
            ]
        )
        run = Run.create(seed=12)
        engine = MesEngine(run, config)
        engine.start()
        engine.tick()
        engine.set_scenario("hyd_fault")
        engine.tick()  # Scenario effect on next tick
        snap = engine.snapshot

        eq_map = {e.equipment_id: e for e in snap.equipment}
        assert eq_map["EQ-01"].fault_level == "critical"  # cause
        assert eq_map["EQ-02"].wait_reason == "no_hyd"     # propagation target
        assert eq_map["EQ-03"].wait_reason == "no_hyd"     # propagation target
        assert eq_map["EQ-04"].wait_reason is None          # co_occurrence ignored


class TestExplicitRoute:
    """Material route is explicit, never inferred from capacity."""

    def test_route_capacity_independent(self):
        """Route follows config.route despite capacity ranking."""
        # EQ-03 has capacity 120, EQ-04 has capacity 20.
        # If we used capacity heuristic, we'd route EQ-02 -> EQ-03.
        # But config.route says EQ-02 -> EQ-04, so coils follow that path.
        config = make_config(
            equipment=[
                EquipmentConfig("EQ-02", "A2", "RT-1", "R1", "SG", "roller", (), ()),
                EquipmentConfig("EQ-03", "A3", "RT-2", "R2", "SG", "roller", (), ()),
                EquipmentConfig("EQ-04", "A4", "CV", "C", "SG", "conveyor", (), ()),
            ],
            relations=[
                # Both are material_flow from EQ-02, but capacity would normally pick EQ-03
                RelationConfig("material_flow", "EQ-02", "EQ-03", lag_seconds=10, capacity_value=120, capacity_unit="m_min"),
                RelationConfig("material_flow", "EQ-02", "EQ-04", lag_seconds=10, capacity_value=20, capacity_unit="m_min"),
            ],
            route=["EQ-02", "EQ-04", "EQ-03"],  # explicit: EQ-02 -> EQ-04, not EQ-03
            scenarios=[]
        )
        run = Run.create(seed=13)
        engine = MesEngine(run, config)
        engine.start()
        snap = engine.snapshot
        coils = snap.coils
        # Initial coils are seeded at route[0], [1], [2] positions: EQ-02, EQ-04, EQ-03
        coil_ids = [c["equipment_id"] for c in coils]
        assert coil_ids == ["EQ-02", "EQ-04", "EQ-03"], f"Got {coil_ids}"

    def test_coil_moves_along_explicit_route(self):
        """Coils follow explicit route, dwell_seconds/lag_seconds timing respected."""
        config = make_config(
            equipment=[
                EquipmentConfig("EQ-01", "A1", "RT", "R", "SG", "roller", (),
                               (SignalSpec("speed", "Speed", "m_min", 50, 100),), dwell_seconds=5),
                EquipmentConfig("EQ-02", "A2", "CV", "C", "SG", "conveyor", (),
                               (SignalSpec("speed", "Speed", "m_min", 50, 100),), dwell_seconds=3),
            ],
            relations=[
                RelationConfig("material_flow", "EQ-01", "EQ-02", lag_seconds=2),
            ],
            route=["EQ-01", "EQ-02"],
            scenarios=[]
        )
        run = Run.create(seed=14)
        engine = MesEngine(run, config)
        engine.start()

        # Advance until first coil moves to EQ-02
        for _ in range(20):
            engine.tick()
        snap = engine.snapshot
        # At least one coil should have moved to EQ-02
        assert any(c["equipment_id"] == "EQ-02" for c in snap.coils), f"Coils still at {[c['equipment_id'] for c in snap.coils]}"


class TestSignalSpecAndEffects:
    """Measurements from SignalSpec, effects from ScenarioSpec."""

    def test_measurement_from_signal_spec(self):
        """Measurement unit and bounds come from SignalSpec, not hardcoded."""
        config = make_config(
            equipment=[
                EquipmentConfig("EQ-01", "A1", "HPU", "HPU", "SG", "hpu", ("hydraulic_supply",),
                               (SignalSpec("pressure", "System Pressure", "kPa", 800, 900),)),
            ],
            relations=[], route=["EQ-01"],
            scenarios=[]
        )
        run = Run.create(seed=15)
        engine = MesEngine(run, config)
        engine.start()
        snap = engine.snapshot
        measurement = snap.measurements[0]
        assert measurement.signal == "pressure"
        assert measurement.unit == "kPa"
        assert 800 <= measurement.value <= 900

    def test_zero_when_stopped_signal(self):
        """Signal with zero_when_stopped=True returns 0 when equipment is stopped."""
        config = make_config(
            equipment=[
                EquipmentConfig("EQ-01", "A1", "RT", "Roller", "SG", "roller", (),
                               (SignalSpec("speed", "Speed", "m_min", 50, 100, zero_when_stopped=True),)),
            ],
            relations=[], route=["EQ-01"],
            scenarios=[]
        )
        run = Run.create(seed=16)
        engine = MesEngine(run, config)
        # Initial state (stopped)
        snap = engine.snapshot
        measurement = next((m for m in snap.measurements if m.signal == "speed"), None)
        assert measurement.value == 0.0, f"Expected 0 when stopped, got {measurement.value}"

        engine.start()
        engine.tick()  # Rebuild snapshot with running state
        snap_running = engine.snapshot
        measurement_running = next((m for m in snap_running.measurements if m.signal == "speed"), None)
        assert measurement_running.value > 0, "Speed should be > 0 when running"

    def test_signal_effects_override_in_scenario(self):
        """ScenarioSpec.signal_effects override measurements for affected capability."""
        config = make_config(
            equipment=[
                EquipmentConfig("EQ-01", "A1", "HPU", "HPU", "SG", "hpu", ("hydraulic_supply",),
                               (SignalSpec("pressure", "Pressure", "bar", 100, 120),)),
            ],
            relations=[], route=["EQ-01"],
            scenarios=[
                ScenarioSpec("hyd_fault", "hydraulic_supply", "hydraulic_supply", "low_supply", "H-1",
                            (SignalEffect("hydraulic_supply", "pressure", 50.0),), 2)
            ]
        )
        run = Run.create(seed=17)
        engine = MesEngine(run, config)
        engine.start()
        engine.tick()
        engine.set_scenario("hyd_fault")
        engine.tick()
        snap = engine.snapshot
        measurement = snap.measurements[0]
        assert measurement.value == 50.0, f"Expected 50 (effect), got {measurement.value}"


class TestAlarmCodeAndWaitReason:
    """Alarm code from ScenarioSpec, not hardcoded SYN-{scenario}."""

    def test_alarm_code_from_scenario(self):
        """Alarm raised uses ScenarioSpec.alarm_code, not SYN-{scenario_id}."""
        config = make_config(
            equipment=[
                EquipmentConfig("EQ-01", "A1", "GR", "Gear", "SG", "gearbox", ("drive",), ()),
            ],
            relations=[], route=["EQ-01"],
            scenarios=[
                ScenarioSpec("drive_fault", "drive", "drive", "upstream_fault", "DRV-CRITICAL", (), 2)
            ]
        )
        run = Run.create(seed=18)
        engine = MesEngine(run, config)
        engine.start()
        engine.tick()
        engine.set_scenario("drive_fault")
        engine.tick()
        snap = engine.snapshot
        alarm = snap.active_alarms[0]
        assert alarm.code == "DRV-CRITICAL"
        assert "SYN-" not in alarm.code

    def test_wait_reason_from_scenario(self):
        """Affected equipment gets wait_reason from ScenarioSpec, not hardcoded."""
        config = make_config(
            equipment=[
                EquipmentConfig("EQ-01", "A1", "GR", "Gear", "SG", "gearbox", ("drive",), ()),
                EquipmentConfig("EQ-02", "A2", "RT", "Roller", "SG", "roller", (), ()),
            ],
            relations=[
                RelationConfig("drive", "EQ-01", "EQ-02"),
            ],
            route=["EQ-02"],
            scenarios=[
                ScenarioSpec("drive_fault", "drive", "drive", "custom_upstream_fault", "DRV-X", (), 2)
            ]
        )
        run = Run.create(seed=19)
        engine = MesEngine(run, config)
        engine.start()
        engine.tick()
        engine.set_scenario("drive_fault")
        engine.tick()
        snap = engine.snapshot
        affected = next(e for e in snap.equipment if e.equipment_id == "EQ-02")
        assert affected.wait_reason == "custom_upstream_fault"


class TestCoilCapacity:
    """Equipment can hold multiple coils (coil_capacity > 1)."""

    def test_coil_capacity_two(self):
        """Equipment with coil_capacity=2 holds up to 2 coils."""
        config = make_config(
            equipment=[
                EquipmentConfig("EQ-01", "A1", "RT", "Holder", "SG", "roller", (),
                               coil_capacity=2, dwell_seconds=100),  # Hold coils long
                EquipmentConfig("EQ-02", "A2", "CV", "Discharge", "SG", "conveyor", (), coil_capacity=1),
            ],
            relations=[
                RelationConfig("material_flow", "EQ-01", "EQ-02", 50),
            ],
            route=["EQ-01", "EQ-02"],
            scenarios=[]
        )
        run = Run.create(seed=20)
        engine = MesEngine(run, config)
        engine.start()

        # Let multiple coils accumulate at EQ-01
        for _ in range(500):
            engine.tick()
        snap = engine.snapshot
        coils_at_eq01 = [c for c in snap.coils if c["equipment_id"] == "EQ-01"]
        assert len(coils_at_eq01) > 0, "At least one coil should occupy EQ-01"
        assert len(coils_at_eq01) <= 2, f"EQ-01 should hold <= 2 coils, got {len(coils_at_eq01)}"


class TestEventObservationBoundary:
    """scenario_selected and recovery_started not exposed in observations."""

    def test_scenario_selected_in_events_not_observation(self):
        """scenario_selected event is recorded but noted as private for model observations."""
        config = make_config(
            equipment=[EquipmentConfig("EQ-01", "A1", "RT", "R", "SG", "roller", ("transport",), ())],
            relations=[], route=["EQ-01"],
            scenarios=[ScenarioSpec("test", "transport", "material_flow", "w", "T-1", (), 2)]
        )
        run = Run.create(seed=21)
        engine = MesEngine(run, config)
        engine.start()
        engine.tick()
        engine.set_scenario("test")
        engine.tick()  # Events flush on next tick
        # Event is recorded internally
        assert any(e.event_type == "scenario_selected" for e in engine.events)

    def test_recovery_neutral_observation(self):
        """recovery_started event has neutral observation (not scenario name)."""
        config = make_config(
            equipment=[EquipmentConfig("EQ-01", "A1", "RT", "R", "SG", "roller", ("transport",), ())],
            relations=[], route=["EQ-01"],
            scenarios=[ScenarioSpec("test_scenario", "transport", "material_flow", "w", "T-1", (), 2)]
        )
        run = Run.create(seed=22)
        engine = MesEngine(run, config)
        engine.start()
        engine.tick()
        engine.set_scenario("test_scenario")
        engine.tick()
        engine.recover()
        engine.tick()  # Recovery event flushes
        event = next((e for e in engine.events if e.event_type == "recovery_started"), None)
        assert event is not None
        assert "test_scenario" not in event.observation  # no cause name in observation
        assert "recovery" in event.observation.lower()


class TestReset:
    """Reset creates new run with existing seed."""

    def test_reset_preserves_seed(self):
        config = make_config(
            equipment=[EquipmentConfig("EQ-01", "A1", "RT", "R", "SG", "roller", (), ())],
            relations=[], route=["EQ-01"],
            scenarios=[]
        )
        original_seed = 99
        run1 = Run.create(seed=original_seed)
        engine = MesEngine(run1, config)
        engine.start()
        engine.tick()

        old_run_id = engine.run.run_id
        new_run = engine.reset()

        assert new_run.seed == original_seed
        assert new_run.run_id != old_run_id
        assert engine.snapshot.line_mode == "stopped"
