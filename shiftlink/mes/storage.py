"""SQLite persistence and portable exports for synthetic MES runs."""

from __future__ import annotations

import csv
import json
import sqlite3
from contextlib import nullcontext
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

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
        recovery=payload.get("recovery"), components=tuple(payload.get("components", [])),
    )


def _event(payload: dict[str, Any]) -> RuntimeEvent:
    return RuntimeEvent(**{**payload, "occurred_at": _time(payload["occurred_at"])})


class HandoverConflictError(ValueError):
    """An existing handover ID cannot silently overwrite another note."""


class MesStorage:
    """Small transactional store. Ground truth is deliberately private."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.connection = sqlite3.connect(str(path), check_same_thread=False)
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA busy_timeout = 5000")
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
            CREATE TABLE IF NOT EXISTS simulation_labels (
                run_id TEXT NOT NULL, sequence INTEGER NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY (run_id, sequence),
                FOREIGN KEY (run_id, sequence) REFERENCES snapshots(run_id, sequence));
            CREATE TABLE IF NOT EXISTS configurations (
                config_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS config_changes (
                change_id TEXT PRIMARY KEY, requested_at TEXT NOT NULL, applied_at TEXT,
                base_config_id TEXT, new_config_id TEXT, reason TEXT, actor TEXT,
                actor_self_reported INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL, detail TEXT, run_id TEXT);
            CREATE TABLE IF NOT EXISTS handover_outbox (
                handover_id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS query_log (
                query_id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS card_drafts (
                draft_id TEXT PRIMARY KEY, handover_id TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
                status TEXT NOT NULL, card TEXT NOT NULL, review_flags TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS card_draft_records (
                handover_id TEXT PRIMARY KEY, draft_id TEXT NOT NULL, relation TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS query_evidence (
                run_id TEXT NOT NULL, simulated_at TEXT NOT NULL, equipment_id TEXT NOT NULL,
                evidence TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (run_id, simulated_at, equipment_id));
            CREATE TABLE IF NOT EXISTS resolution_sessions (
                session_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, equipment_id TEXT NOT NULL,
                status TEXT NOT NULL, data TEXT NOT NULL);
        """)
        self.connection.commit()

    def save_handover(self, body: dict[str, Any]) -> dict[str, Any]:
        """Commit the original note locally; retries never overwrite it."""
        self._check_handover(body)
        with self.connection:
            return self._insert_handover(body)

    @staticmethod
    def _check_handover(body: object) -> None:
        if not isinstance(body, dict):
            raise ValueError("handover body must be an object")
        handover_id, memo = body.get("handover_id"), body.get("memo_text")
        if not isinstance(handover_id, str) or not handover_id.strip() or len(handover_id) > 64:
            raise ValueError("handover_id must be a 1..64 char string")
        if not isinstance(memo, str) or not memo.strip() or len(memo) > 4000:
            raise ValueError("memo_text must be a 1..4000 char string")

    def _insert_handover(self, body: dict[str, Any]) -> dict[str, Any]:
        """INSERT inside the caller's transaction (save_handover / save_handover_with_draft)."""
        handover_id, encoded = body["handover_id"], _dump(body)
        inserted = self.connection.execute(
            "INSERT OR IGNORE INTO handover_outbox (handover_id, created_at, payload) VALUES (?, ?, ?)",
            (handover_id, datetime.now().astimezone().isoformat(), encoded),
        ).rowcount
        row = self.connection.execute(
            "SELECT created_at, status, payload FROM handover_outbox WHERE handover_id = ?", (handover_id,)
        ).fetchone()
        if row[2] != encoded:
            raise HandoverConflictError("handover_id already exists with different content")
        return {"handover_id": handover_id, "created_at": row[0], "status": row[1],
                "duplicate": not bool(inserted), "is_synthetic": True}

    def save_handover_with_draft(self, body: dict[str, Any], op: dict[str, Any] | None,
                                 session: tuple[str, dict[str, Any]] | None = None) -> tuple[dict[str, Any], bool]:
        """인계와 초안 반영(과 조치 기록 세션 저장 완료)을 한 트랜잭션으로.

        op: None | {"kind": "new"|"merge", "draft", "draft_id"?, "relation"?}. session: (session_id, 최종 data).
        하나가 실패하면 아무것도 남지 않는다. 이미 초안에 반영된 인계(재전송)면 op를 건너뛰고 False.
        """
        self._check_handover(body)
        now = datetime.now().astimezone().isoformat()
        with self.connection:
            if session is not None and not self.connection.execute(
                    "UPDATE resolution_sessions SET status = 'saved', data = ? WHERE session_id = ? AND status = 'open'",
                    (_dump(session[1]), session[0])).rowcount:
                raise HandoverConflictError("resolution session is already saved")
            saved = self._insert_handover(body)
            if op is None or self.has_draft_record(body["handover_id"]):
                return saved, False
            draft = op["draft"]
            if op["kind"] == "new":
                self.connection.execute("INSERT INTO card_drafts VALUES (?, ?, ?, ?, ?, ?)", (
                    draft["card"]["card_id"], body["handover_id"], now,
                    draft["status"], _dump(draft["card"]), _dump(draft["review_flags"])))
                self.connection.execute("INSERT INTO card_draft_records VALUES (?, ?, 'origin', ?)",
                                        (body["handover_id"], draft["card"]["card_id"], now))
            else:
                self.connection.execute("UPDATE card_drafts SET status = ?, card = ?, review_flags = ? WHERE draft_id = ?",
                                        (draft["status"], _dump(draft["card"]), _dump(draft["review_flags"]), op["draft_id"]))
                self.connection.execute("INSERT INTO card_draft_records VALUES (?, ?, ?, ?)",
                                        (body["handover_id"], op["draft_id"], op["relation"], now))
        return saved, True

    def create_resolution_session(self, equipment_id: str, data: dict[str, Any]) -> str:
        """조치 기록 세션(조치 시작 → 조치 완료 → 마무리). 인계와 함께 저장되면 saved가 된다."""
        session_id = "RS-" + uuid4().hex
        with self.connection:
            self.connection.execute("INSERT INTO resolution_sessions VALUES (?, ?, ?, 'open', ?)",
                                    (session_id, datetime.now().astimezone().isoformat(), equipment_id, _dump(data)))
        return session_id

    def get_resolution_session(self, session_id: object) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT equipment_id, status, data FROM resolution_sessions WHERE session_id = ?", (str(session_id),)).fetchone()
        return {"session_id": session_id, "equipment_id": row[0], "status": row[1], "data": json.loads(row[2])} if row else None

    def resolution_sessions(self, run_id: str) -> list[dict[str, Any]]:
        """이 실행의 조치 기록 세션 전부(대시보드 사건 연결용)."""
        rows = self.connection.execute("SELECT session_id, equipment_id, status, data FROM resolution_sessions")
        sessions = [{"session_id": s, "equipment_id": e, "status": st, "data": json.loads(d)} for s, e, st, d in rows]
        return [s for s in sessions if s["data"].get("run_id") == run_id]

    def handover_payloads(self) -> list[dict[str, Any]]:
        return [json.loads(p) for (p,) in self.connection.execute("SELECT payload FROM handover_outbox")]

    def query_payloads(self) -> list[dict[str, Any]]:
        """이 DB에 쌓인 PDA 질의 전부(업로드 여부와 관계없이). 대시보드 지식 공백용."""
        return [json.loads(p) for (p,) in self.connection.execute("SELECT payload FROM query_log")]

    def update_resolution_session(self, session_id: str, data: dict[str, Any]) -> bool:
        """열린 세션만 고친다. False면 이미 저장된 세션이다."""
        with self.connection:
            return bool(self.connection.execute(
                "UPDATE resolution_sessions SET data = ? WHERE session_id = ? AND status = 'open'",
                (_dump(data), session_id)).rowcount)

    def save_query_evidence(self, evidence: dict[str, Any] | None) -> None:
        """질의 때 서버가 쓴 MES 근거를 보관한다. 해결 기록은 PDA가 보낸 값 대신 이것으로 판정한다(업로드 대상 아님)."""
        if not isinstance(evidence, dict) or not all(evidence.get(k) for k in ("run_id", "simulated_at", "equipment_id")):
            return
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO query_evidence VALUES (?, ?, ?, ?, ?)",
                (evidence["run_id"], str(evidence["simulated_at"]), evidence["equipment_id"], _dump(evidence),
                 datetime.now().astimezone().isoformat()))

    def get_query_evidence(self, run_id: object, simulated_at: object, equipment_id: object) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT evidence FROM query_evidence WHERE run_id = ? AND simulated_at = ? AND equipment_id = ?",
            (str(run_id), str(simulated_at), str(equipment_id))).fetchone()
        return json.loads(row[0]) if row else None

    def next_card_id(self, first: int, last: int) -> str:
        """Next unused K-#### in the field range; drafts are never retrieved, so only this table is checked."""
        row = self.connection.execute("SELECT MAX(draft_id) FROM card_drafts WHERE draft_id BETWEEN ? AND ?",
                                      (f"K-{first:04d}", f"K-{last:04d}")).fetchone()
        number = int(row[0][2:]) + 1 if row[0] else first
        if number > last:
            raise ValueError("field draft card id range is exhausted")
        return f"K-{number:04d}"

    def has_draft_record(self, handover_id: str) -> bool:
        """이 인계가 이미 어느 초안에 반영됐는지(처음 기록이든 덧붙은 근거든)."""
        return self.connection.execute("SELECT 1 FROM card_draft_records WHERE handover_id = ?",
                                       (handover_id,)).fetchone() is not None

    def list_card_drafts(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT draft_id, handover_id, created_at, status, card, review_flags FROM card_drafts ORDER BY draft_id")
        return [{"draft_id": d, "handover_id": h, "created_at": c, "status": s,
                 "card": json.loads(card), "review_flags": json.loads(flags)} for d, h, c, s, card, flags in rows]

    def get_handover(self, handover_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT created_at, status, payload FROM handover_outbox WHERE handover_id = ?", (handover_id,)
        ).fetchone()
        return {"handover_id": handover_id, "created_at": row[0], "status": row[1],
                "payload": json.loads(row[2])} if row else None

    def pending_handovers(self) -> list[tuple[str, str, str]]:
        """(handover_id, created_at, payload) not yet uploaded, oldest first."""
        return self.connection.execute(
            "SELECT handover_id, created_at, payload FROM handover_outbox WHERE status = 'pending' ORDER BY created_at"
        ).fetchall()

    def mark_handover(self, handover_id: str, status: str) -> None:
        with self.connection:
            self.connection.execute("UPDATE handover_outbox SET status = ? WHERE handover_id = ?", (status, handover_id))

    def save_query(self, record: dict[str, Any]) -> str:
        """Log one /api/query answer for upload (C5). Returns the new query_id."""
        query_id = "Q-" + uuid4().hex
        with self.connection:
            self.connection.execute("INSERT INTO query_log (query_id, created_at, payload) VALUES (?, ?, ?)",
                                    (query_id, datetime.now().astimezone().isoformat(), _dump(record)))
        return query_id

    def pending_queries(self) -> list[tuple[str, str, str]]:
        return self.connection.execute(
            "SELECT query_id, created_at, payload FROM query_log WHERE status = 'pending' ORDER BY created_at"
        ).fetchall()

    def mark_query(self, query_id: str, status: str) -> None:
        with self.connection:
            self.connection.execute("UPDATE query_log SET status = ? WHERE query_id = ?", (status, query_id))

    def outbox_counts(self) -> dict[str, dict[str, int]]:
        """Rows per upload status for the PDA 'upload pending N' badge."""
        out = {}
        for key, table in (("handover", "handover_outbox"), ("query", "query_log")):
            counts = {"pending": 0, "uploaded": 0, "conflict": 0}
            counts.update(self.connection.execute(f"SELECT status, COUNT(*) FROM {table} GROUP BY status").fetchall())
            out[key] = counts
        return out

    def create_run(self, run: Run, *, commit: bool = True) -> None:
        try:
            with self.connection if commit else nullcontext():
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

    def save_tick(self, snapshot: Snapshot, events: Iterable[RuntimeEvent] = (), *, simulation_labels: dict[str, Any] | None = None) -> None:
        events = tuple(events)
        if any(event.run_id != snapshot.run_id or event.sequence != snapshot.sequence for event in events):
            raise ValueError("events must belong to the snapshot tick")
        if simulation_labels is not None and (simulation_labels.get('run_id'), simulation_labels.get('sequence')) != snapshot.key:
            raise ValueError('simulation labels must belong to the snapshot tick')
        try:
            with self.connection:
                self.connection.execute("INSERT INTO snapshots VALUES (?, ?, ?, ?)", (snapshot.run_id, snapshot.sequence, snapshot.simulated_at.isoformat(), _dump(snapshot)))
                self.connection.executemany(
                    "INSERT INTO runtime_events VALUES (?, ?, ?, ?, ?)",
                    [(event.run_id, event.sequence, index, event.occurred_at.isoformat(), _dump(event)) for index, event in enumerate(events)],
                )
                if simulation_labels is not None:
                    self.connection.execute('INSERT INTO simulation_labels VALUES (?, ?, ?)',
                        (snapshot.run_id, snapshot.sequence, _dump(simulation_labels)))
        except sqlite3.IntegrityError as error:
            raise ValueError(f"duplicate or unknown tick: {snapshot.key}") from error

    def save_ground_truth(self, truth: GroundTruth) -> None:
        try:
            with self.connection:
                self.connection.execute("INSERT INTO ground_truth VALUES (?, ?)", (truth.run_id, _dump(truth)))
        except sqlite3.IntegrityError as error:
            raise ValueError(f"ground truth already exists or run is unknown: {truth.run_id}") from error

    def save_configuration(self, config_id: str, canonical_payload: str, created_at: datetime | None = None, *, commit: bool = True) -> None:
        """Idempotent: the same config_id always carries the same canonical payload (hash-addressed)."""
        self.connection.execute(
            "INSERT OR IGNORE INTO configurations VALUES (?, ?, ?)",
            (config_id, (created_at or datetime.now().astimezone()).isoformat(), canonical_payload),
        )
        if commit:
            self.connection.commit()

    def get_configuration(self, config_id: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT payload FROM configurations WHERE config_id = ?", (config_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def record_config_change(self, change: dict[str, Any], *, commit: bool = True) -> None:
        with self.connection if commit else nullcontext():
            self.connection.execute(
                "INSERT INTO config_changes VALUES (:change_id, :requested_at, :applied_at, :base_config_id,"
                " :new_config_id, :reason, :actor, :actor_self_reported, :status, :detail, :run_id)",
                {
                    "applied_at": None, "base_config_id": None, "new_config_id": None, "reason": None,
                    "actor": None, "actor_self_reported": 1, "detail": None, "run_id": None, **change,
                },
            )

    def apply_configuration(self, config_id: str, payload: str, run: Run, change: dict[str, Any]) -> None:
        """Commit configuration, run, and applied audit record together."""
        try:
            with self.connection:
                self.save_configuration(config_id, payload, commit=False)
                self.create_run(run, commit=False)
                self.record_config_change(change, commit=False)
        except sqlite3.Error as error:
            raise ValueError("configuration storage failed") from error

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
