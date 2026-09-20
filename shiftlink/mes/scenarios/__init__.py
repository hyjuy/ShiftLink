"""The small, explicit set of synthetic runtime scenarios."""

SCENARIOS = frozenset({"normal", "drive_fault", "downstream_block", "hydraulic_fault"})


def validate(scenario_id: str) -> str:
    if scenario_id not in SCENARIOS:
        raise ValueError(f"unknown scenario: {scenario_id}")
    return scenario_id
