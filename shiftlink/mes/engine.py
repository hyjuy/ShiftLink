"""Deterministic, in-memory synthetic MES state engine."""

from __future__ import annotations

from datetime import timedelta
from collections import deque
from dataclasses import replace
from random import Random
from typing import Any

from .contracts import (
    Alarm, Configuration, EquipmentConfig, EquipmentState, Measurement, RecoveryAction, RelationConfig,
    Run, RuntimeEvent, ScenarioSpec, SignalEffect, SignalSpec, Snapshot
)
from .scenarios.priority import COMPONENTS
from .signal_semantics import MODEL, SAMPLES


class MesEngine:
    """Advance one synthetic line without UI, storage, or wall-clock dependencies."""

    def __init__(self, run: Run, config: Configuration) -> None:
        self.run = run
        self.config = config
        self._equipment_by_id = config.equipment_by_id()
        self._scenario_by_id = {s.scenario_id: s for s in config.scenarios}
        self._relations_by_type = {}
        for rel in config.relations:
            if rel.relation_type not in self._relations_by_type:
                self._relations_by_type[rel.relation_type] = []
            self._relations_by_type[rel.relation_type].append(rel)
        self._sequence = 0
        self._running = False
        self._resume_mode = "running"
        self._scenario = "normal"
        self._recovery_ticks = 0
        self._recovery_spec = None
        self._completed_actions: list[str] = []
        self._components = self._new_components()
        self.events: list[RuntimeEvent] = []
        self._pending_events: list[tuple[str, str | None, str]] = []
        self._active_alarms: dict[str, Alarm] = {}
        self._next_coil = 1
        self._symptom_frames = deque(maxlen=3)
        self._coils = [self._new_coil(equipment_id, position) for equipment_id, position in zip(config.route, (0.2, 0.5, 0.8))]
        self._snapshot = self._build_snapshot()

    @property
    def snapshot(self) -> Snapshot:
        return self._snapshot

    def symptom_diagnostics(self):
        from .symptoms import screen_symptoms
        frames = list(self._symptom_frames)
        if frames:
            frames[-1] = self.snapshot
        return screen_symptoms(frames, self.config)

    def start(self) -> Snapshot:
        if self._running:
            return self.snapshot
        self._running = True
        self._queue_event("started", None, "synthetic line started")
        self._snapshot = replace(self._snapshot, line_mode=self._resume_mode)
        return self.snapshot

    def pause(self) -> Snapshot:
        self._symptom_frames.clear()
        if self._running:
            self._resume_mode = self._snapshot.line_mode
        self._running = False
        self._queue_event("paused", None, "synthetic line paused")
        self._snapshot = replace(self._snapshot, line_mode="paused")
        return self.snapshot

    def resume(self) -> Snapshot:
        return self.start()

    def set_scenario(self, scenario_id: str) -> Snapshot:
        if self._scenario != "normal" and self._recovery_required():
            raise ValueError("현재 시나리오의 조치·복귀를 완료하거나 새 실행을 시작하세요.")
        if scenario_id not in self._scenario_by_id:
            raise ValueError(f"unknown scenario: {scenario_id}")
        spec = self._scenario_by_id[scenario_id]
        if scenario_id != "normal":
            cause_eq = self._cause_equipment_id(spec)
            if not cause_eq:
                raise ValueError(f"cannot apply {scenario_id} (requires {spec.cause_capability} capability) to this configuration")
        self._scenario = scenario_id
        self._recovery_ticks = 0
        self._recovery_spec = None if scenario_id == "normal" else self._recovery_plan(spec)
        self._completed_actions = []
        if spec.product_hold:
            for coil in self._coils:
                coil["quality_status"] = "hold"
                self._queue_event("coil_held", coil["equipment_id"], str(coil["coil_id"]))
        for component in self._components:
            if component["equipment_id"] == self._cause_equipment_id(spec) and component["component_id"] == spec.component_id:
                component["health_percent"] = min(component["health_percent"], 25.0 if spec.component_id == "seal" else 35.0)
        self._queue_event("scenario_selected", None, scenario_id)
        self._refresh_snapshot()
        return self.snapshot

    def perform_action(self, action_id: str) -> Snapshot:
        spec = self._recovery_spec
        if not spec or self._scenario == "normal" or self._recovery_ticks:
            raise ValueError("진행 중인 조치 단계가 없습니다.")
        if action_id in self._completed_actions:
            return self.snapshot
        if len(self._completed_actions) >= len(spec.recovery_actions) or spec.recovery_actions[len(self._completed_actions)].action_id != action_id:
            raise ValueError("화면에 표시된 다음 조치부터 순서대로 완료하세요.")
        action = spec.recovery_actions[len(self._completed_actions)]
        self._completed_actions.append(action_id)
        cause = self._cause_equipment_id(spec)
        if action_id == "repair":
            for component in self._components:
                if component["equipment_id"] == cause and component["component_id"] == spec.component_id:
                    component["health_percent"] = 95.0
                    component["maintenance_count"] += 1
                    component["last_maintenance_at"] = self._at().isoformat()
        self._queue_event("recovery_action_completed", cause, action.title + " (모의 확인)")
        self._refresh_snapshot()
        return self.snapshot

    def recover(self) -> Snapshot:
        if self._scenario == "normal":
            return self.snapshot
        if self._recovery_required() and len(self._completed_actions) < len(self._recovery_spec.recovery_actions):
            raise ValueError("필수 점검·조치·정상 확인을 모두 완료해야 복귀할 수 있습니다.")
        if self._recovery_ticks:
            return self.snapshot
        self._recovery_ticks = self._scenario_by_id[self._scenario].recovery_ticks
        self._queue_event("recovery_started", None, "recovery in progress")
        self._refresh_snapshot()
        return self.snapshot

    def tick(self, count: int = 1) -> Snapshot:
        if count < 0:
            raise ValueError("count must be non-negative")
        for _ in range(count):
            if not self._running:
                break
            self._sequence += 1
            self._flush_events()
            self._wear_components()
            if self._recovery_ticks:
                self._recovery_ticks -= 1
                if not self._recovery_ticks:
                    self._scenario = "normal"
                    for coil in self._coils:
                        if coil.get("quality_status") == "hold":
                            coil["quality_status"] = "released"
                            self._event("coil_released", coil["equipment_id"], str(coil["coil_id"]))
                    self._event("recovered", None, "synthetic line stabilized")
            if not self._recovery_ticks:
                self._move_coils()
            self._snapshot = self._build_snapshot()
        return self.snapshot

    def reset(self) -> Run:
        self._symptom_frames.clear()
        self.run = Run.create(seed=self.run.seed, started_at=self.run.started_at, config_id=self.run.config_id)
        self._sequence = 0
        self._running = False
        self._resume_mode = "running"
        self._scenario = "normal"
        self._recovery_ticks = 0
        self._recovery_spec = None
        self._completed_actions = []
        self._components = self._new_components()
        self.events = []
        self._pending_events = []
        self._active_alarms = {}
        self._next_coil = 1
        self._coils = [self._new_coil(equipment_id, position) for equipment_id, position in zip(self.config.route, (0.2, 0.5, 0.8))]
        self._snapshot = self._build_snapshot()
        return self.run

    def _new_components(self):
        return [{"equipment_id": eq.equipment_id, "component_id": key, "name": name,
                 "health_percent": 100.0, "operating_seconds": 0, "maintenance_count": 0,
                 "last_maintenance_at": None}
                for eq in self.config.equipment if eq.active
                for key, name in COMPONENTS.get(eq.profile_id, ())]

    def _wear_components(self):
        states, _ = self._states()
        for component in self._components:
            if states[component["equipment_id"]][0] == "running":
                component["operating_seconds"] += self.run.tick_seconds
                component["health_percent"] = round(max(0, component["health_percent"] - 0.001 * self.run.tick_seconds), 3)

    def _recovery_status(self):
        spec = self._recovery_spec
        if not spec:
            return None
        stage = ("completed" if self._scenario == "normal" else "stabilizing" if self._recovery_ticks
                 else "ready" if len(self._completed_actions) == len(spec.recovery_actions) else "actions")
        return {"title": spec.title, "source_url": spec.source_url, "stage": stage,
                "remaining_ticks": self._recovery_ticks, "product_hold": spec.product_hold,
                "required": self._recovery_required(),
                "equipment_id": self._cause_equipment_id(spec),
                "actions": [{"action_id": a.action_id, "title": a.title, "detail": a.detail,
                             "completed": a.action_id in self._completed_actions} for a in spec.recovery_actions]}

    def _refresh_snapshot(self):
        paused = self._snapshot.line_mode == "paused"
        event_count = len(self.events)
        self._snapshot = self._build_snapshot()
        # Control changes belong to the next persisted tick, like other commands.
        for event in self.events[event_count:]:
            self._queue_event(event.event_type, event.equipment_id, event.observation)
        del self.events[event_count:]
        if paused:
            self._snapshot = replace(self._snapshot, line_mode="paused")

    def _find_equipment_with_capability(self, capability: str) -> str | None:
        for eq in self.config.equipment:
            if eq.active and capability in eq.capabilities:
                return eq.equipment_id
        return None

    def _cause_equipment_id(self, spec: ScenarioSpec) -> str | None:
        if spec.cause_equipment_id is None:
            return self._find_equipment_with_capability(spec.cause_capability)
        eq = self._equipment_by_id.get(spec.cause_equipment_id)
        return eq.equipment_id if eq and eq.active and spec.cause_capability in eq.capabilities else None

    def _at(self):
        return self.run.started_at + timedelta(seconds=self._sequence * self.run.tick_seconds)

    def _event(self, event_type: str, equipment_id: str | None, observation: str) -> None:
        self.events.append(RuntimeEvent(self.run.run_id, self._sequence, self._at(), event_type, equipment_id, observation))

    def _queue_event(self, event_type: str, equipment_id: str | None, observation: str) -> None:
        self._pending_events.append((event_type, equipment_id, observation))

    def _flush_events(self) -> None:
        for event_type, equipment_id, observation in self._pending_events:
            self._event(event_type, equipment_id, observation)
        self._pending_events.clear()

    def _new_coil(self, equipment_id, position=0.0):
        coil = {"coil_id": f"COIL-{self._next_coil:03d}", "equipment_id": equipment_id,
                "segment_id": self._equipment_by_id[equipment_id].segment_id, "position": position}
        self._next_coil += 1
        return coil

    def _travel_time(self, equipment_id: str) -> float:
        """Get lag_seconds from material_flow relation, or dwell_seconds default."""
        for rel in self.config.relations:
            if rel.relation_type == "material_flow" and rel.from_id == equipment_id and rel.lag_seconds:
                return rel.lag_seconds
        eq = self._equipment_by_id.get(equipment_id)
        return eq.dwell_seconds if eq else 10.0

    def _move_coils(self) -> None:
        states, _ = self._states()
        occupied = {coil["equipment_id"]: 0 for coil in self._coils}
        for coil in self._coils:
            occupied[coil["equipment_id"]] = occupied.get(coil["equipment_id"], 0) + 1

        for coil in sorted(self._coils, key=lambda item: self.config.route.index(item["equipment_id"]) if item["equipment_id"] in self.config.route else 1000, reverse=True):
            current = coil["equipment_id"]
            if states[current][0] != "running" or coil.get("quality_status") == "hold":
                continue

            travel_time = self._travel_time(current)
            coil["position"] = min(1.0, round(coil["position"] + self.run.tick_seconds / travel_time, 6))

            if coil["position"] < 1:
                continue

            # Try to move to next equipment in route
            route_index = self.config.route.index(current) if current in self.config.route else -1
            if route_index == -1 or route_index == len(self.config.route) - 1:
                self._coils.remove(coil)
                self._event("coil_exited", current, f"{coil['coil_id']} discharged")
            else:
                following = self.config.route[route_index + 1]
                following_eq = self._equipment_by_id[following]
                occupied_count = occupied.get(following, 0)
                if occupied_count < following_eq.coil_capacity and states[following][0] == "running":
                    occupied[current] -= 1
                    occupied[following] = occupied_count + 1
                    coil.update(equipment_id=following, segment_id=following_eq.segment_id, position=0.0)

        # Add new coil to first position if empty
        if self.config.route and self.config.route[0] not in occupied and states[self.config.route[0]][0] == "running":
            coil = self._new_coil(self.config.route[0])
            self._coils.append(coil)
            occupied[self.config.route[0]] = 1
            self._event("coil_entered", self.config.route[0], f"{coil['coil_id']} entered")

    def _states(self) -> tuple[dict[str, tuple[str, str, str | None]], str]:
        states = {}
        for eq in self.config.equipment:
            if not eq.active:
                states[eq.equipment_id] = ("stopped", "normal", None)
            else:
                states[eq.equipment_id] = ("running" if (self._running and not self._recovery_ticks) else "stopped", "normal", None)

        if not self._running:
            return states, "stopped"
        if self._recovery_ticks:
            return {key: ("waiting", "normal", "recovery") for key in states}, "recovering"
        if self._scenario == "normal":
            return states, "running"

        spec = self._scenario_by_id.get(self._scenario)
        if not spec:
            return states, "running"

        if spec.product_hold:
            for coil in self._coils:
                if coil.get("quality_status") == "hold":
                    states[coil["equipment_id"]] = ("waiting", "normal", "quality_hold")
            return states, "quality_hold"

        # Find cause equipment by capability
        cause_eq_id = self._cause_equipment_id(spec)
        if spec.scenario_id == 'hpu_accumulator_precharge':
            if cause_eq_id in states:
                states[cause_eq_id] = ('stopped', 'normal', 'precharge_measurement')
                for relation in self.config.relations:
                    if relation.from_id == cause_eq_id and relation.relation_type == 'hydraulic_supply':
                        states[relation.to_id] = ('waiting', 'normal', 'precharge_measurement')
            return states, 'running'
        if cause_eq_id and cause_eq_id in states:
            states[cause_eq_id] = (("stopped", "critical", "self_fault") if spec.stop_on_fault
                                   else ("running", "warning", "observed_deviation"))

        # Find affected equipment via propagation_relation
        affected_ids = []
        if spec.propagation_relation in self._relations_by_type:
            for rel in self._relations_by_type[spec.propagation_relation]:
                if rel.from_id == cause_eq_id:
                    affected_ids.append(rel.to_id)

        for equipment_id in affected_ids:
            if equipment_id in states:
                states[equipment_id] = ("waiting", "normal", spec.wait_reason)

        return states, "fault"

    def _recovery_required(self) -> bool:
        # Generic plans guide the demo but never block recovery or switching scenarios.
        authored = self._scenario_by_id.get(self._scenario)
        return bool(self._recovery_spec and authored and authored.recovery_actions)

    def _recovery_plan(self, spec: ScenarioSpec) -> ScenarioSpec:
        """Scenarios without authored steps get a generic synthetic check-repair-verify plan."""
        if spec.recovery_actions:
            return spec
        eq = self._equipment_by_id.get(self._cause_equipment_id(spec))
        names = {s.signal: s.name for s in (eq.signals if eq else ())}
        signals = ", ".join(names.get(e.signal, e.signal) for e in spec.signal_effects) or "관측 신호"
        code = eq.code if eq else "원인 설비"
        return replace(spec, recovery_actions=(
            RecoveryAction("inspect", "이상 신호 위치 확인", f"정지·에너지 차단 확인 후 {code}의 {signals} 측정 위치와 계측 상태를 점검한 것으로 기록합니다."),
            RecoveryAction("repair", "원인 조치 기록", "이 시나리오에는 원인별 정비 절차가 정의되어 있지 않습니다. 확인된 원인에 대한 조치 완료를 모의 기록합니다."),
            RecoveryAction("verify", "정상 범위 회복 확인", "주입한 모의 신호를 구성의 정상 범위로 되돌리고 재가동 전 확인을 기록합니다.")))

    def _signal_effect(self, equipment, signal):
        spec = self._scenario_by_id.get(self._scenario)
        plan = self._recovery_spec
        if not spec or (plan and len(self._completed_actions) == len(plan.recovery_actions)):
            return None
        return next((effect for effect in spec.signal_effects
                     if equipment.equipment_id == self._cause_equipment_id(spec)
                     and effect.capability in equipment.capabilities and effect.signal == signal), None)

    def _measurement_value(self, equipment: EquipmentConfig, signal_spec: SignalSpec) -> float:
        effect = self._signal_effect(equipment, signal_spec.signal)
        if effect is not None:
            return round(effect.value, 3)

        if signal_spec.zero_when_stopped and self._states()[0][equipment.equipment_id][0] != "running":
            return 0.0

        if signal_spec.semantics.get('model') == MODEL:
            signals = {s.signal: s for s in equipment.signals}
            def related(name):
                return self._measurement_value(equipment, signals[name]) if name in signals else None
            dependencies = {
                'hpu_cooler_oil_in_temp': ('hpu_oil_temp', 0),
                'hpu_cooler_oil_out_temp': ('hpu_cooler_oil_in_temp', -5),
                'hpu_cooler_water_out_temp': ('hpu_cooler_water_in_temp', 5),
                'hpu_cooler_oil_flow': ('hpu_flow', 0),
                'hpu_accumulator_gas_pressure': ('hpu_accumulator_fluid_pressure', 0),
            }
            if signal_spec.signal in dependencies:
                source, offset = dependencies[signal_spec.signal]
                value = related(source)
                if value is not None:
                    return round(value + offset, 3)
            if signal_spec.signal == 'cv_queue_len':
                count = sum(coil['equipment_id'] == equipment.equipment_id for coil in self._coils)
                return round(min(100, 100 * count / equipment.coil_capacity), 3)
            if signal_spec.semantics.get('acquisition') == 'event':
                return 0.0  # No lift command/completion pair exists in this transport model.

        low, high = signal_spec.normal_min, signal_spec.normal_max
        if low is None and high is None:
            low = high = 0.0
        elif low is None:
            low = float(high) * 0.9
        elif high is None:
            high = float(low) * 1.1

        sequence = self._sequence
        if signal_spec.semantics.get('model') == MODEL and signal_spec.signal in SAMPLES:
            sequence = int(sequence * self.run.tick_seconds // 60)
        random = Random(f"{self.run.seed}:{sequence}:{equipment.equipment_id}:{signal_spec.signal}")
        value = (float(low) + float(high)) / 2 + (random.random() - 0.5) * (float(high) - float(low)) * 0.08

        return round(value, 3)

    def _build_snapshot(self) -> Snapshot:
        state_map, line_mode = self._states()
        at = self._at()
        equipment = tuple(
            EquipmentState(eq.equipment_id, *state_map.get(eq.equipment_id, ("stopped", "normal", None)))
            for eq in self.config.equipment if eq.active
        )
        measurements = []
        for eq in self.config.equipment:
            if not eq.active:
                continue
            for signal_spec in eq.signals:
                quality, observed_at = 'good', at
                if signal_spec.semantics.get('model') == MODEL and self._signal_effect(eq, signal_spec.signal) is None:
                    if signal_spec.semantics.get('acquisition') == 'event':
                        quality = 'unavailable'
                    elif signal_spec.signal in SAMPLES:
                        elapsed = self._sequence * self.run.tick_seconds
                        observed_at = self.run.started_at + timedelta(seconds=elapsed // 60 * 60)
                measurements.append(Measurement(
                    eq.equipment_id, signal_spec.signal, self._measurement_value(eq, signal_spec),
                    signal_spec.unit, observed_at, quality
                ))
        active = self._update_alarms(state_map, at)
        snapshot = Snapshot(
            self.run.run_id, self._sequence, at, self.config.line_id, line_mode, self._scenario,
            equipment=equipment, coils=tuple(dict(coil) for coil in self._coils),
            measurements=tuple(measurements), active_alarms=active,
            recovery=self._recovery_status(), components=tuple(dict(c) for c in self._components)
        )
        if self._symptom_frames and self._symptom_frames[-1].sequence == snapshot.sequence:
            self._symptom_frames[-1] = snapshot
        else:
            self._symptom_frames.append(snapshot)
        return snapshot

    # 경보 코드의 화면 이름. 없는 코드는 코드 그대로 보인다.
    ALARM_LABELS = {
        "AL-SENSOR-ANOMALY": "센서값 범위 이탈", "AL-HYD-HOT": "유압유 과열", "AL-HYD-LOW": "유압 공급 저하",
        "AL-GR-HOT": "감속기 과열", "AL-GR-LEAK": "감속기 누유", "AL-AIR-LOW": "공압 공급 저하",
        "AL-PDP-TRIP": "배전반 차단기 트립", "AL-DRV-VIB": "구동부 진동 이상", "AL-DSB-QUE": "출측 코일 정체",
        "AL-SYMPTOM": "증상 패턴 감지",
    }

    def _update_alarms(self, state_map: dict[str, tuple[str, str, str | None]], at) -> tuple[Alarm, ...]:
        fault_ids = {equipment_id for equipment_id, (_, level, _) in state_map.items() if level != "normal"}
        for equipment_id in fault_ids:
            spec = self._scenario_by_id.get(self._scenario)
            code = spec.alarm_code if spec else "UNKNOWN"
            previous = self._active_alarms.get(equipment_id)
            if previous and (previous.code != code or previous.severity != state_map[equipment_id][1]):
                self._event("alarm_cleared", equipment_id, previous.code)
                del self._active_alarms[equipment_id]
            if equipment_id not in self._active_alarms:
                self._active_alarms[equipment_id] = Alarm(f"AL-{equipment_id}", code, equipment_id, state_map[equipment_id][1], at,
                                                          label=self.ALARM_LABELS.get(code, code))
                self._event("alarm_raised", equipment_id, code)
        for equipment_id in tuple(self._active_alarms):
            if equipment_id not in fault_ids:
                self._event("alarm_cleared", equipment_id, self._active_alarms[equipment_id].code)
                del self._active_alarms[equipment_id]
        return tuple(self._active_alarms.values())
