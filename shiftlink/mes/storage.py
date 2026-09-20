"""SQLite persistence and portable exports for synthetic MES runs."""

from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .contracts import Alarm, EquipmentState, GroundTruth, Measurement, Run, RuntimeEvent, Snapshot


def _json_default(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _dump(value: object) -> str:
    return json.dumps(value, default=_json_default, ensure_ascii=False, sort_keys=True)


def _time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _snapshot(payload: dict[str, Any]) -> Snapshot:
    return Snapshot(
        run_id=payload["run_id"], sequence=payload["sequence"], simulated_at=_time(payload["simulated_at"]),
        line_id=payload["line_id"], line_mode=payload["line_mode"], scenario_id=payload["scenario_id"],
        support_scenario=payload.get("support_scenario", "S1"),
        equipment=tuple(EquipmentState(**item) for item in payload.get("equipment", [])),
        coils=tuple(payload.get("coils", [])),
        measurements=tuple(Measurement(**{**item, "observed_at": _time(item["observed_at"])}) for item in payload.get("measurements", [])),
        active_alarms=tuple(Alarm(**{**item, "raised_at": _time(item["raised_at"]), "acknowledged_at": _time(item.get("acknowledged_at")), "cleared_at": _time(item.get("cleared_at"))}) for item in payload.get("active_alarms", [])),
        is_synthetic=payload.get("is_synthetic", True),
    )


def _event(payload: dict[str, Any]) -> RuntimeEvent:
    return RuntimeEvent(**{**payload, "occurred_at": _time(payload["occurred_at"])})


class MesStorage:
    """Small transactional store. Ground truth is deliberately private."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.connection = sqlite3.connect(str(path), check_same_thread=False)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def close(self) -> None:
        self.connection.close()

    def _create_schema(self) -> None:
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS snapshots (
                run_id TEXT NOT NULL, sequence INTEGER NOT NULL, simulated_at TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY (run_id, sequence), FOREIGN KEY (run_id) REFERENCES runs(run_id));
            CREATE TABLE IF NOT EXISTS runtime_events (
                run_id TEXT NOT NULL, sequence INTEGER NOT NULL, event_index INTEGER NOT NULL, occurred_at TEXT NOT NULL,
                payload TEXT NOT NULL, PRIMARY KEY (run_id, sequence, event_index),
                FOREIGN KEY (run_id, sequence) REFERENCES snapshots(run_id, sequence));
            CREATE TABLE IF NOT EXISTS ground_truth (
                run_id TEXT PRIMARY KEY, payload TEXT NOT NULL, FOREIGN KEY (run_id) REFERENCES runs(run_id));
            CREATE TABLE IF NOT EXISTS configurations (
                config_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS config_changes (
                change_id TEXT PRIMARY KEY, requested_at TEXT NOT NULL, applied_at TEXT,
                base_config_id TEXT, new_config_id TEXT, reason TEXT, actor TEXT,
                actor_self_reported INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL, detail TEXT, run_id TEXT);
        """)
        self.connection.commit()

    def create_run(self, run: Run) -> None:
        try:
            with self.connection:
                self.connection.execute("INSERT INTO runs VALUES (?, ?, ?)", (run.run_id, run.started_at.isoformat(), _dump(run)))
        except sqlite3.IntegrityError as error:
            raise ValueError(f"run already exists: {run.run_id}") from error

    def get_run(self, run_id: str) -> Run | None:
        row = self.connection.execute("SELECT payload FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if not row:
            return None
        payload = json.loads(row[0]); payload["started_at"] = _time(payload["started_at"])
        return Run(**payload)

    def list_runs(self) -> list[Run]:
        return [run for run_id, in self.connection.execute("SELECT run_id FROM runs ORDER BY started_at") if (run := self.get_run(run_id))]

    def save_tick(self, snapshot: Snapshot, events: Iterable[RuntimeEvent] = ()) -> None:
        events = tuple(events)
        if any(event.run_id != snapshot.run_id or event.sequence != snapshot.sequence for event in events):
            raise ValueError("events must belong to the snapshot tick")
        try:
            with self.connection:
                self.connection.execute("INSERT INTO snapshots VALUES (?, ?, ?, ?)", (snapshot.run_id, snapshot.sequence, snapshot.simulated_at.isoformat(), _dump(snapshot)))
                self.connection.executemany(
                    "INSERT INTO runtime_events VALUES (?, ?, ?, ?, ?)",
                    [(event.run_id, event.sequence, index, event.occurred_at.isoformat(), _dump(event)) for index, event in enumerate(events)],
                )
        except sqlite3.IntegrityError as error:
            raise ValueError(f"duplicate or unknown tick: {snapshot.key}") from error

    def save_ground_truth(self, truth: GroundTruth) -> None:
        try:
            with self.connection:
                self.connection.execute("INSERT INTO ground_truth VALUES (?, ?)", (truth.run_id, _dump(truth)))
        except sqlite3.IntegrityError as error:
            raise ValueError(f"ground truth already exists or run is unknown: {truth.run_id}") from error

    def save_configuration(self, config_id: str, canonical_payload: str, created_at: datetime | None = None) -> None:
        """Idempotent: the same config_id always carries the same canonical payload (hash-addressed)."""
        self.connection.execute(
            "INSERT OR IGNORE INTO configurations VALUES (?, ?, ?)",
            (config_id, (created_at or datetime.now().astimezone()).isoformat(), canonical_payload),
        )
        self.connection.commit()

    def get_configuration(self, config_id: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT payload FROM configurations WHERE config_id = ?", (config_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def record_config_change(self, change: dict[str, Any]) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO config_changes VALUES (:change_id, :requested_at, :applied_at, :base_config_id,"
                " :new_config_id, :reason, :actor, :actor_self_reported, :status, :detail, :run_id)",
                {
                    "applied_at": None, "base_config_id": None, "new_config_id": None, "reason": None,
                    "actor": None, "actor_self_reported": 1, "detail": None, "run_id": None, **change,
                },
            )

    def list_config_changes(self) -> list[dict[str, Any]]:
        cursor = self.connection.execute("SELECT * FROM config_changes ORDER BY requested_at")
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor]

    def snapshots(self, run_id: str, *, as_of: datetime | None = None) -> list[Snapshot]:
        query = "SELECT payload FROM snapshots WHERE run_id = ?"; args: list[object] = [run_id]
        if as_of:
            query += " AND simulated_at <= ?"; args.append(as_of.isoformat())
        query += " ORDER BY sequence"
        return [_snapshot(json.loads(row[0])) for row in self.connection.execute(query, args)]

    def events(self, run_id: str, *, after_sequence: int = -1, as_of: datetime | None = None) -> list[RuntimeEvent]:
        query = "SELECT payload FROM runtime_events WHERE run_id = ? AND sequence > ?"; args: list[object] = [run_id, after_sequence]
        if as_of:
            query += " AND occurred_at <= ?"; args.append(as_of.isoformat())
        query += " ORDER BY sequence, event_index"
        return [_event(json.loads(row[0])) for row in self.connection.execute(query, args)]

    def replay(self, run_id: str, *, after_sequence: int = -1, as_of: datetime | None = None) -> tuple[list[Snapshot], list[RuntimeEvent]]:
        return ([item for item in self.snapshots(run_id, as_of=as_of) if item.sequence > after_sequence], self.events(run_id, after_sequence=after_sequence, as_of=as_of))

    def _public_records(self, run_id: str) -> list[dict[str, Any]]:
        records = [{"kind": "snapshot", "payload": json.loads(row[0])} for row in self.connection.execute("SELECT payload FROM snapshots WHERE run_id = ? ORDER BY sequence", (run_id,))]
        records += [{"kind": "event", "payload": json.loads(row[0])} for row in self.connection.execute("SELECT payload FROM runtime_events WHERE run_id = ? ORDER BY sequence, event_index", (run_id,))]
        return records

    def export_jsonl(self, run_id: str, path: str | Path) -> Path:
        destination = Path(path)
        with destination.open("w", encoding="utf-8", newline="") as output:
            for record in self._public_records(run_id):
                output.write(_dump(record) + "\n")
        return destination

    def export_csv(self, run_id: str, path: str | Path) -> Path:
        destination = Path(path)
        with destination.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=("kind", "run_id", "sequence", "occurred_at", "payload"))
            writer.writeheader()
            for record in self._public_records(run_id):
                payload = record["payload"]
                writer.writerow({"kind": record["kind"], "run_id": payload["run_id"], "sequence": payload["sequence"], "occurred_at": payload.get("simulated_at", payload.get("occurred_at")), "payload": _dump(payload)})
        return destination


SQLiteStorage = MesStorage
