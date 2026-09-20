"""Explicit safe views from MES records to ShiftLink-facing observations."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from .storage import MesStorage


class ObserverAdapter:
    """Expose only observations available at ``as_of``; never ground truth."""

    def __init__(self, storage: MesStorage) -> None:
        self.storage = storage

    def observations(self, run_id: str, *, as_of: datetime | None = None, after_sequence: int = -1) -> dict[str, object]:
        snapshots, events = self.storage.replay(run_id, after_sequence=after_sequence, as_of=as_of)
        latest = snapshots[-1] if snapshots else None
        return {
            "run_id": run_id,
            "as_of": as_of.isoformat() if as_of else None,
            "snapshot": asdict(latest) if latest else None,
            "events": [asdict(event) for event in events],
        }


ShiftLinkObserver = ObserverAdapter
