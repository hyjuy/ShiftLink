"""Small, dependency-free contracts shared by the synthetic MES components."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Run:
    run_id: str
    seed: int
    started_at: datetime
    tick_seconds: int = 1
    catalog_version: str = "DS-v1.0"
    scenario_version: str = "v1"
    split: str = "dev"
    is_synthetic: bool = True

    @classmethod
    def create(cls, seed: int, started_at: datetime | None = None) -> "Run":
        return cls(uuid4().hex, seed, started_at or utc_now())


@dataclass(frozen=True)
class EquipmentState:
    equipment_id: str
    operating_state: str
    fault_level: str = "normal"
    wait_reason: str | None = None


@dataclass(frozen=True)
class Measurement:
    equipment_id: str
    signal: str
    value: float
    unit: str
    observed_at: datetime
    quality: str = "good"


@dataclass(frozen=True)
class Alarm:
    alarm_id: str
    code: str
    equipment_id: str
    severity: str
    raised_at: datetime
    acknowledged_at: datetime | None = None
    cleared_at: datetime | None = None


@dataclass(frozen=True)
class RuntimeEvent:
    run_id: str
    sequence: int
    occurred_at: datetime
    event_type: str
    equipment_id: str | None
    observation: str


@dataclass(frozen=True)
class GroundTruth:
    run_id: str
    injected_cause: str
    injected_at: datetime
    expected_impact: str
    expected_action: str


@dataclass(frozen=True)
class Snapshot:
    run_id: str
    sequence: int
    simulated_at: datetime
    line_id: str
    line_mode: str
    scenario_id: str
    support_scenario: str = "S1"
    equipment: tuple[EquipmentState, ...] = ()
    coils: tuple[dict[str, object], ...] = ()
    measurements: tuple[Measurement, ...] = ()
    active_alarms: tuple[Alarm, ...] = ()
    is_synthetic: bool = True

    @property
    def key(self) -> tuple[str, int]:
        return self.run_id, self.sequence

    def as_dict(self) -> dict[str, object]:
        return asdict(self)
