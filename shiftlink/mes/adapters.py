"""Explicit safe views from MES records to ShiftLink-facing observations.

Boundary rules (see docs/mock-mes-modularization.md):
- Only event types in OBSERVABLE_EVENT_TYPES reach model-facing observations.
  ``scenario_selected`` and ``recovery_started`` carry injected-cause context and are excluded.
- ``scenario_id`` is stripped from snapshots; it names the injected cause.
- ``wait_reason`` and alarm codes stay: they model plant-observable annunciations, not ground truth.
- Ground truth is never exposed here.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from .storage import MesStorage

OBSERVABLE_EVENT_TYPES = frozenset({
    "started", "paused", "coil_entered", "coil_exited",
    "alarm_raised", "alarm_cleared", "recovered", "run_closed",
})

_SNAPSHOT_FIELDS = (
    "run_id", "sequence", "simulated_at", "line_id", "line_mode", "support_scenario",
    "equipment", "coils", "measurements", "active_alarms", "is_synthetic",
)


def _observable_snapshot(snapshot) -> dict[str, object]:
    payload = asdict(snapshot)
    return {key: payload[key] for key in _SNAPSHOT_FIELDS}


class ObserverAdapter:
    """Expose only observations available at ``as_of``; never ground truth."""

    def __init__(self, storage: MesStorage) -> None:
        self.storage = storage

    def observations(self, run_id: str, *, as_of: datetime | None = None, after_sequence: int = -1) -> dict[str, object]:
        snapshots, events = self.storage.replay(run_id, after_sequence=after_sequence, as_of=as_of)
        latest = snapshots[-1] if snapshots else None
        run = self.storage.get_run(run_id)
        return {
            "run_id": run_id,
            "as_of": as_of.isoformat() if as_of else None,
            "config_id": run.config_id if run else None,
            "snapshot": _observable_snapshot(latest) if latest else None,
            "events": [asdict(event) for event in events if event.event_type in OBSERVABLE_EVENT_TYPES],
        }


ShiftLinkObserver = ObserverAdapter
