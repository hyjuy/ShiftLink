"""Scenario validation now delegated to MesEngine (Configuration-aware)."""

# Legacy scenarios kept for reference; actual definitions are in Configuration.scenarios
SCENARIOS = frozenset({"normal", "drive_fault", "downstream_block", "hydraulic_fault"})


def validate(scenario_id: str) -> str:
    """Deprecated: MesEngine.set_scenario() performs configuration-aware validation."""
    if scenario_id not in SCENARIOS:
        raise ValueError(f"unknown scenario: {scenario_id}")
    return scenario_id
