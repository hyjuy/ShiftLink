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
    # None means the applied configuration was not preserved (pre-upgrade runs).
    config_id: str | None = None

    @classmethod
    def create(cls, seed: int, started_at: datetime | None = None, config_id: str | None = None) -> "Run":
        return cls(uuid4().hex, seed, started_at or utc_now(), config_id=config_id)


@dataclass(frozen=True)
class SignalSpec:
    signal: str
    name: str
    unit: str
    normal_min: float | None = None
    normal_max: float | None = None
    required: bool = True
    zero_when_stopped: bool = False


@dataclass(frozen=True)
class EquipmentConfig:
    equipment_id: str  # logical install position; meaning preserved from the legacy catalog
    asset_id: str  # synthetic asset instance; replacement issues a new id, never reused
    code: str
    name: str
    segment_id: str | None
    profile_id: str
    capabilities: tuple[str, ...]
    signals: tuple[SignalSpec, ...] = ()
    coil_capacity: int = 1
    dwell_seconds: float = 10.0
    active: bool = True


@dataclass(frozen=True)
class RelationConfig:
    relation_type: str
    from_id: str
    to_id: str
    lag_seconds: float | None = None
    capacity_value: float | None = None
    capacity_unit: str | None = None


@dataclass(frozen=True)
class SignalEffect:
    capability: str
    signal: str
    value: float


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id: str
    cause_capability: str
    propagation_relation: str
    wait_reason: str
    alarm_code: str
    signal_effects: tuple[SignalEffect, ...] = ()
    recovery_ticks: int = 2


@dataclass(frozen=True)
class LayoutGroup:
    title: str
    equipment_ids: tuple[str, ...]


@dataclass(frozen=True)
class Configuration:
    config_id: str  # sha256 of the canonical payload (configuration.config_hash)
    version_label: str
    source: str
    line_id: str
    equipment: tuple[EquipmentConfig, ...] = ()
    relations: tuple[RelationConfig, ...] = ()
    route: tuple[str, ...] = ()  # explicit main material route; never inferred from capacity
    branches: tuple[RelationConfig, ...] = ()
    scenarios: tuple[ScenarioSpec, ...] = ()
    layout: tuple[LayoutGroup, ...] = ()

    def equipment_by_id(self) -> dict[str, "EquipmentConfig"]:
        return {item.equipment_id: item for item in self.equipment}


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
