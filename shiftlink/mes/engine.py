"""Deterministic, in-memory synthetic MES state engine."""

from __future__ import annotations

from datetime import timedelta
from dataclasses import replace
from random import Random
from typing import Any

from .contracts import Alarm, EquipmentState, Measurement, Run, RuntimeEvent, Snapshot
from .scenarios import validate


class MesEngine:
    """Advance one synthetic line without UI, storage, or wall-clock dependencies."""

    def __init__(self, run: Run, catalog: dict[str, Any] | Any) -> None:
        self.run = run
        self.catalog = catalog
        data = getattr(catalog, "data", catalog)
        self._equipment = tuple(data.get("equipment", ()))
        self._equipment_by_id = {item["equipment_id"]: item for item in self._equipment}
        self._relations = tuple(data.get("relations", ()))
        self._route, self._travel_ticks = self._material_route()
        self._line_id = (data.get("production_lines") or [{"line_id": "LN-0001"}])[0]["line_id"]
        self._sequence = 0
        self._running = False
        self._resume_mode = "running"
        self._scenario = "normal"
        self._recovery_ticks = 0
        self.events: list[RuntimeEvent] = []
        self._pending_events: list[tuple[str, str | None, str]] = []
        self._active_alarms: dict[str, Alarm] = {}
        self._next_coil = 1
        self._coils = [self._new_coil(equipment_id, position) for equipment_id, position in zip(self._route, (0.2, 0.5, 0.8))]
        self._snapshot = self._build_snapshot()

    @property
    def snapshot(self) -> Snapshot:
        return self._snapshot

    def start(self) -> Snapshot:
        if self._running:
            return self.snapshot
        self._running = True
        self._queue_event("started", None, "synthetic line started")
        self._snapshot = replace(self._snapshot, line_mode=self._resume_mode)
        return self.snapshot

    def pause(self) -> Snapshot:
        if self._running:
            self._resume_mode = self._snapshot.line_mode
        self._running = False
        self._queue_event("paused", None, "synthetic line paused")
        # Pausing freezes simulated observations; it is not a plant fault reset.
        self._snapshot = replace(self._snapshot, line_mode="paused")
        return self.snapshot

    def resume(self) -> Snapshot:
        return self.start()

    def set_scenario(self, scenario_id: str) -> Snapshot:
        self._scenario = validate(scenario_id)
        self._recovery_ticks = 0
        self._queue_event("scenario_selected", None, scenario_id)
        return self.snapshot

    def recover(self) -> Snapshot:
        if self._scenario == "normal":
            return self.snapshot
        self._recovery_ticks = 2
        self._queue_event("recovery_started", None, f"recovering {self._scenario}")
        return self.snapshot

    def tick(self, count: int = 1) -> Snapshot:
        if count < 0:
            raise ValueError("count must be non-negative")
        for _ in range(count):
            if not self._running:
                break
            self._sequence += 1
            self._flush_events()
            if self._recovery_ticks:
                self._recovery_ticks -= 1
                if not self._recovery_ticks:
                    self._scenario = "normal"
                    self._event("recovered", None, "synthetic line stabilized")
            if not self._recovery_ticks:
                self._move_coils()
            self._snapshot = self._build_snapshot()
        return self.snapshot

    def reset(self) -> Run:
        self.run = Run.create(seed=self.run.seed, started_at=self.run.started_at)
        self._sequence = 0
        self._running = False
        self._resume_mode = "running"
        self._scenario = "normal"
        self._recovery_ticks = 0
        self.events = []
        self._pending_events = []
        self._active_alarms = {}
        self._next_coil = 1
        self._coils = [self._new_coil(equipment_id, position) for equipment_id, position in zip(self._route, (0.2, 0.5, 0.8))]
        self._snapshot = self._build_snapshot()
        return self.run

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

    def _material_route(self):
        links = [link for link in self._relations if link.get("relation_type") == "material_flow"
                 and link.get("from_id") in self._equipment_by_id and link.get("to_id") in self._equipment_by_id]
        if not links:
            return [item["equipment_id"] for item in self._equipment if item.get("code") in ("RT-01", "RT-02", "RT-03", "CV-01")], {}
        targets = {link["to_id"] for link in links}
        start = next((link["from_id"] for link in links if link["from_id"] not in targets), links[0]["from_id"])
        route, travel = [start], {}
        while True:
            outgoing = [link for link in links if link["from_id"] == route[-1] and link["to_id"] not in route]
            if not outgoing:
                break
            # ponytail: one product route; select the largest-capacity branch, no scrap scheduling.
            link = max(outgoing, key=lambda item: (item.get("capacity") or {}).get("value", 0))
            travel[route[-1]] = max(1, float(link.get("lag_seconds") or 10))
            route.append(link["to_id"])
        return route, travel

    def _new_coil(self, equipment_id, position=0.0):
        coil = {"coil_id": f"COIL-{self._next_coil:03d}", "equipment_id": equipment_id,
                "segment_id": self._equipment_by_id[equipment_id].get("segment_id"), "position": position}
        self._next_coil += 1
        return coil

    def _move_coils(self) -> None:
        states, _ = self._states()
        occupied = {coil["equipment_id"] for coil in self._coils}
        for coil in sorted(self._coils, key=lambda item: self._route.index(item["equipment_id"]), reverse=True):
            current = coil["equipment_id"]
            if states[current][0] != "running":
                continue
            coil["position"] = min(1.0, round(coil["position"] + self.run.tick_seconds / self._travel_ticks.get(current, 10), 6))
            if coil["position"] < 1:
                continue
            index = self._route.index(current)
            if index == len(self._route) - 1:
                self._coils.remove(coil)
                occupied.remove(current)
                self._event("coil_exited", current, f"{coil['coil_id']} discharged")
            else:
                following = self._route[index + 1]
                if following not in occupied and states[following][0] == "running":
                    occupied.remove(current)
                    occupied.add(following)
                    coil.update(equipment_id=following, segment_id=self._equipment_by_id[following].get("segment_id"), position=0.0)
        if self._route and self._route[0] not in occupied and states[self._route[0]][0] == "running":
            coil = self._new_coil(self._route[0])
            self._coils.append(coil)
            self._event("coil_entered", self._route[0], f"{coil['coil_id']} entered")

    def _id_for(self, code: str) -> str | None:
        return next((str(item["equipment_id"]) for item in self._equipment if item.get("code") == code), None)

    def _states(self) -> tuple[dict[str, tuple[str, str, str | None]], str]:
        states = {str(item["equipment_id"]): ("running" if self._running else "stopped", "normal", None) for item in self._equipment}
        if not self._running:
            return states, "paused"
        if self._recovery_ticks:
            return {key: ("waiting", "normal", "recovery") for key in states}, "recovering"
        if self._scenario == "normal":
            return states, "running"
        cause, affected, reason = {
            "drive_fault": ("GR-01", ("RT-01",), "upstream_drive_fault"),
            "downstream_block": ("CV-01", ("RT-03", "RT-02"), "downstream_block"),
            "hydraulic_fault": ("HPU-01", ("RT-01", "RT-02", "RT-03"), "hydraulic_supply_low"),
        }[self._scenario]
        cause_id = self._id_for(cause)
        if cause_id in states:
            states[cause_id] = ("stopped", "critical", "self_fault")
        relation_type = {"drive_fault": "drive", "hydraulic_fault": "hydraulic_supply", "downstream_block": "interlock"}[self._scenario]
        affected_ids = [link["to_id"] for link in self._relations if link.get("from_id") == cause_id and link.get("relation_type") == relation_type]
        if not self._relations:
            affected_ids = [self._id_for(code) for code in affected]
        for equipment_id in affected_ids:
            if equipment_id in states:
                states[equipment_id] = ("waiting", "normal", reason)
        return states, "fault"

    def _measurement_value(self, equipment: dict[str, Any], point: dict[str, Any]) -> float:
        low, high = point.get("normal_min"), point.get("normal_max")
        if low is None and high is None:
            low = high = 0.0
        elif low is None:
            low = float(high) * 0.9
        elif high is None:
            high = float(low) * 1.1
        random = Random(f"{self.run.seed}:{self._sequence}:{equipment['equipment_id']}:{point['signal']}")
        value = (float(low) + float(high)) / 2 + (random.random() - 0.5) * (float(high) - float(low)) * 0.08
        code, signal = equipment.get("code"), point.get("signal")
        if signal in ("rt_speed", "cv_speed") and self._states()[0][equipment["equipment_id"]][0] != "running":
            return 0.0
        if self._scenario == "hydraulic_fault" and code == "HPU-01" and signal == "hpu_pressure":
            value = 120.0
        if self._scenario == "drive_fault" and code == "GR-01" and signal == "gr_vib_rms":
            value = 5.0
        if self._scenario == "downstream_block" and code == "CV-01" and signal == "cv_queue_len":
            value = 95.0
        return round(value, 3)

    def _build_snapshot(self) -> Snapshot:
        state_map, line_mode = self._states()
        at = self._at()
        equipment = tuple(EquipmentState(item["equipment_id"], *state_map[str(item["equipment_id"])]) for item in self._equipment)
        measurements = tuple(
            Measurement(item["equipment_id"], point["signal"], self._measurement_value(item, point), point.get("unit", ""), at)
            for item in self._equipment for point in item.get("measurement_points", ())
        )
        active = self._update_alarms(state_map, at)
        return Snapshot(self.run.run_id, self._sequence, at, self._line_id, line_mode, self._scenario,
                        equipment=equipment, coils=tuple(dict(coil) for coil in self._coils), measurements=measurements,
                        active_alarms=active)

    def _update_alarms(self, state_map: dict[str, tuple[str, str, str | None]], at) -> tuple[Alarm, ...]:
        fault_ids = {equipment_id for equipment_id, (_, level, _) in state_map.items() if level != "normal"}
        for equipment_id in fault_ids:
            if equipment_id not in self._active_alarms:
                code = f"SYN-{self._scenario.upper()}"
                self._active_alarms[equipment_id] = Alarm(f"AL-{equipment_id}", code, equipment_id, "critical", at)
                self._event("alarm_raised", equipment_id, code)
        for equipment_id in tuple(self._active_alarms):
            if equipment_id not in fault_ids:
                self._event("alarm_cleared", equipment_id, self._active_alarms[equipment_id].code)
                del self._active_alarms[equipment_id]
        return tuple(self._active_alarms.values())
