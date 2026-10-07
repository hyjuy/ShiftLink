"""One-process localhost server for the synthetic MES demonstration."""

from __future__ import annotations

import json
import os
import csv
from collections import deque
from io import StringIO
import threading
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from . import configuration
from .catalog import Catalog
from .contracts import Configuration, Run, utc_now
from .engine import MesEngine
from shiftlink.agent.pipeline import JudgeUnavailableError
from shiftlink.agent.response import AgentResponse, render_response

from .storage import HandoverConflictError, MesStorage

_CONTROL_BODY_LIMIT = 8192
_CONFIG_BODY_LIMIT = 256 * 1024
_ASSIST_BODY_LIMIT = 64 * 1024
_SCAN_KEEP = 50
_ROOT = Path(__file__).resolve().parents[2]
# kb split only: dev/sealed evaluation files are never opened here (C-099).
_KB_CARDS = _ROOT / "docs" / "data" / "knowledge_cards" / "kb" / "kb_cards.json"
_KB_HANDOVERS = _ROOT / "docs" / "data" / "scenarios" / "EV-0031_upstream_cause.json"


def kb_cards() -> dict[str, object]:
    """Searchable cards (C-102: accepted/kb/L1) and sample handovers for the PDA screen."""
    cards = json.loads(_KB_CARDS.read_text(encoding="utf-8"))["cards"]
    scenario = json.loads(_KB_HANDOVERS.read_text(encoding="utf-8"))
    handovers = scenario.get("handover_records", [])
    basis_ids = {basis for h in handovers for item in h.get("open_items", []) for basis in item.get("basis_ids", [])}
    basis_records = {}
    for collection, key in (("action_candidates", "action_candidate_id"), ("actions_executed", "action_executed_id"),
                            ("outcomes", "outcome_id"), ("knowledge_cards", "card_id")):
        for row in scenario.get(collection, []):
            if row.get(key) not in basis_ids:
                continue
            if collection == "knowledge_cards" and (row.get("status"), row.get("split"), row.get("grade")) != ("accepted", "kb", "L1"):
                continue
            basis_records[row[key]] = {field: row[field] for field in
                (key, "title", "detail", "executed_at", "recorded_at", "immediate_result", "observation_window_h", "post_measurements",
                 "know_how", "rationale", "safety_basis") if field in row}
    return {"cards": [c for c in cards if (c.get("status"), c.get("split"), c.get("grade")) == ("accepted", "kb", "L1")],
            "handovers": handovers, "basis_records": basis_records, "is_synthetic": True}


class ConflictError(ValueError):
    """Concurrent or stale configuration apply attempt."""


class ConfigValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("configuration validation failed")
        self.errors = errors


def _json(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


class MesService:
    """Owns the single engine instance; HTTP reads never advance it."""

    def __init__(self, catalog_path: Path, storage: MesStorage | None = None, seed: int = 0, *, random_faults: bool = False, run_nonce: str | None = None, fault_hazard: float = .015) -> None:
        self.random_faults = random_faults
        self.run_nonce = run_nonce
        self.fault_hazard = fault_hazard
        self.catalog = Catalog.load(catalog_path)
        self.storage = storage or MesStorage()
        self.active_config: Configuration = self._restore_active_config()
        self.storage.save_configuration(self.active_config.config_id, json.dumps(configuration.to_payload(self.active_config), sort_keys=True, ensure_ascii=False))
        self.engine = self._new_engine(Run.create(seed=seed, config_id=self.active_config.config_id), self.active_config)
        self.storage.create_run(self.engine.run)
        self.speed = 1.0
        self._saved_sequences: set[tuple[str, int]] = set()
        self._lock = threading.RLock()
        # ponytail: 메모리에만 둔다(재시작하면 사라짐). 인계가 아니라 버려도 되는 값이다(작업계획 D1).
        self._scans: deque[dict[str, object]] = deque(maxlen=_SCAN_KEEP)
        self.query_pipeline = None

    def _new_engine(self, run: Run, config: Configuration) -> MesEngine:
        if self.random_faults:
            from .random_factory import RandomFactoryEngine
            return RandomFactoryEngine(run, config, run_nonce=self.run_nonce or run.run_id, hazard=self.fault_hazard)
        return MesEngine(run, config)

    def query(self, body: dict[str, Any]) -> dict[str, object]:
        from .query import query_service
        started = time.perf_counter()
        result = query_service(self, body, pipeline=self.query_pipeline)
        try:
            rendered_response = render_response(AgentResponse.model_validate(result))
        except Exception:  # Log formatting must not prevent returning the generated answer.
            rendered_response = None
        self.storage.save_query({
            "question": body.get("question"), "equipment_id": (result.get("evidence") or {}).get("equipment_id"),
            "answer": result.get("answer"), "cited_card_ids": result.get("cited_card_ids"),
            "safety_notices": result.get("safety_notices", []),
            "rendered_response": rendered_response,
            "no_knowledge": result.get("no_knowledge"), "review_queue": result.get("review_queue"),
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "model": getattr(getattr(self.query_pipeline, "model", None), "model", None),
            "answer_mode": getattr(self.query_pipeline, "answer_mode", None), "is_synthetic": True})
        return result

    def record_scan(self, body: dict[str, Any]) -> dict[str, object]:
        """웹캠 CNN 확정 결과 {class, conf, device_id, ts} → 설비 기록 (작업계획 C2)."""
        if not isinstance(body, dict):
            raise ValueError("scan body must be an object")
        label, conf, device_id, ts = body.get("class"), body.get("conf"), body.get("device_id"), body.get("ts")
        type_ids = {t["type_code"]: t["equipment_type_id"] for t in self.catalog.data.get("equipment_types", [])}
        if label not in type_ids:
            raise ValueError(f"unknown class: {label!r}")
        if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
            raise ValueError("conf must be a number in 0..1")
        if not isinstance(device_id, str) or not 0 < len(device_id) <= 64:
            raise ValueError("device_id must be a 1..64 char string")
        if ts is not None and not (isinstance(ts, str) and len(ts) <= 64):
            raise ValueError("ts must be a string")
        # ponytail: CNN은 형식만 구분하므로 GR·RT처럼 여러 대인 형식은 equipment_id가 가장 작은 설비로 고정한다.
        # 대수까지 구분하려면 설비마다 다른 객체를 정해 클래스를 늘린다.
        equipment = min((e for e in self.catalog.equipment.values() if e["equipment_type_id"] == type_ids[label]),
                        key=lambda e: e["equipment_id"])
        scan = {"scan_id": f"SC-{uuid4().hex[:12]}", "class": label, "conf": float(conf), "device_id": device_id, "ts": ts,
                "equipment_id": equipment["equipment_id"], "code": equipment["code"], "received_at": utc_now().isoformat()}
        with self._lock:
            self._scans.append(scan)
        return {"scan": scan, "is_synthetic": True}

    def recent_scans(self, limit: int) -> dict[str, object]:
        """최신 인식 결과부터 limit개 (작업계획 C3)."""
        if not 1 <= limit <= _SCAN_KEEP:
            raise ValueError(f"limit must be 1..{_SCAN_KEEP}")
        with self._lock:
            return {"scans": list(self._scans)[::-1][:limit], "is_synthetic": True}

    def record_handover(self, body: dict[str, Any]) -> dict[str, object]:
        with self._lock:
            return self.storage.save_handover(body)

    def _restore_active_config(self) -> Configuration:
        """Resume with the configuration of the newest run that preserved one; else derive from the catalog."""
        for run in reversed(self.storage.list_runs()):
            if run.config_id:
                stored = self.storage.get_configuration(run.config_id)
                if stored:
                    config = configuration.from_payload(stored)
                    if config.source == "catalog" and config.version_label == "baseline":
                        from .scenarios.priority import expand
                        return expand(config)
                    return config
        return configuration.from_catalog(self.catalog.data)

    def state(self) -> dict[str, object]:
        with self._lock:
            return json.loads(json.dumps(asdict(self.engine.snapshot), default=_json)) | {
                "speed": self.speed,
                "config_id": self.active_config.config_id,
                "symptom_diagnostics": self.engine.symptom_diagnostics(),
            }

    def events(self, after_sequence: int) -> dict[str, object]:
        with self._lock:
            return {"run_id": self.engine.run.run_id, "events": json.loads(json.dumps([asdict(event) for event in self.engine.events if event.sequence > after_sequence], default=_json)), "is_synthetic": True}

    def config(self) -> dict[str, object]:
        with self._lock:
            return {"config": configuration.to_payload(self.active_config), "is_synthetic": True}

    def stored_config(self, config_id: str) -> dict[str, object]:
        payload = self.storage.get_configuration(config_id)
        if payload is None:
            raise KeyError("configuration not found")
        return {"config": payload, "is_synthetic": True}

    def validate_config(self, body: dict[str, Any]) -> dict[str, object]:
        draft = self._load_draft(body)
        errors = configuration.validate(draft)
        with self._lock:
            delta = configuration.diff(self.active_config, draft)
        return {"valid": not errors, "errors": errors, "diff": delta, "config_id": draft.config_id, "is_synthetic": True}

    def _load_draft(self, body: dict[str, Any]) -> Configuration:
        if not isinstance(body, dict) or not isinstance(body.get("draft"), dict):
            raise ValueError("body must contain a draft object")
        return configuration.load_draft(body["draft"], source="user_upload")

    def apply_config(self, body: dict[str, Any]) -> dict[str, object]:
        draft = self._load_draft(body)
        change_id = uuid4().hex
        requested_at = utc_now().isoformat()
        base = {"change_id": change_id, "requested_at": requested_at,
                "reason": str(body.get("reason") or ""), "actor": str(body.get("actor") or ""),
                "actor_self_reported": 1}
        with self._lock:
            if self.engine.snapshot.line_mode not in ("paused", "stopped"):
                raise ConflictError("가동 중에는 구성을 적용할 수 없습니다. 일시정지 후 다시 시도하세요.")
            if body.get("base_config_id") != self.active_config.config_id:
                raise ConflictError("기준 구성이 변경되었습니다. 현재 구성을 다시 확인하세요.")
            errors = configuration.validate(draft)
            if errors:
                self._record_change_safely({**base, "base_config_id": self.active_config.config_id,
                                            "new_config_id": draft.config_id, "status": "rejected",
                                            "detail": json.dumps({"errors": errors}, ensure_ascii=False)})
                raise ConfigValidationError(errors)
            delta = configuration.diff(self.active_config, draft)
            previous_run = self.engine.run
            leftover = [dict(coil) for coil in self.engine.snapshot.coils]
            old_config_id = self.active_config.config_id
            try:
                new_run = Run.create(seed=previous_run.seed, config_id=draft.config_id)
                new_engine = self._new_engine(new_run, draft)
                self.storage.apply_configuration(draft.config_id,
                    json.dumps(configuration.to_payload(draft), sort_keys=True, ensure_ascii=False), new_run, {
                    **base, "applied_at": utc_now().isoformat(),
                    "base_config_id": old_config_id, "new_config_id": draft.config_id,
                    "status": "applied", "run_id": new_run.run_id,
                    "detail": json.dumps({"diff": delta, "previous_run_id": previous_run.run_id,
                                          "leftover_coils": leftover}, ensure_ascii=False, default=_json),
                })
            except ValueError:
                self._record_change_safely({**base, "base_config_id": old_config_id,
                                            "new_config_id": draft.config_id, "status": "failed",
                                            "detail": "storage error"})
                raise
            # Swap in-memory state only after every write succeeded.
            self.active_config = draft
            self.engine = new_engine
            self._saved_sequences = set()
            return {"run_id": new_run.run_id, "config_id": draft.config_id,
                    "previous_run_id": previous_run.run_id, "leftover_coils": leftover,
                    "diff": delta, "is_synthetic": True}

    def _record_change_safely(self, change: dict[str, Any]) -> None:
        try:
            self.storage.record_config_change(change)
        except Exception:
            pass

    def replay(self, run_id: str, after_sequence: int) -> dict[str, object]:
        with self._lock:
            snapshots, events = self.storage.replay(run_id, after_sequence=after_sequence)
            run = self.storage.get_run(run_id)
            if not snapshots and run is None:
                raise KeyError("run not found")
        config_id = run.config_id if run else None
        return {"snapshots": json.loads(json.dumps(snapshots, default=_json)),
                "events": json.loads(json.dumps(events, default=_json)),
                "config_id": config_id, "config_preserved": config_id is not None,
                "is_synthetic": True}

    def export(self, run_id: str, format_name: str) -> str:
        with self._lock:
            if self.storage.get_run(run_id) is None:
                raise KeyError("run not found")
            records = self.storage._public_records(run_id)
        if format_name == "jsonl":
            return "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
        if format_name == "csv":
            output = StringIO(); writer = csv.DictWriter(output, fieldnames=("kind", "run_id", "sequence", "occurred_at", "payload")); writer.writeheader()
            for record in records:
                payload = record["payload"]
                writer.writerow({"kind": record["kind"], "run_id": payload["run_id"], "sequence": payload["sequence"], "occurred_at": payload.get("simulated_at", payload.get("occurred_at")), "payload": json.dumps(payload, ensure_ascii=False)})
            return output.getvalue()
        raise ValueError("format must be jsonl or csv")

    def _save_current_tick(self) -> None:
        snapshot = self.engine.snapshot
        if snapshot.key in self._saved_sequences:
            return
        events = [event for event in self.engine.events if event.sequence == snapshot.sequence]
        if self.random_faults:
            labels = next((record for record in reversed(self.engine.truth) if (record['run_id'], record['sequence']) == snapshot.key), None)
            self.storage.save_tick(snapshot, events, simulation_labels=labels)
            self.engine.truth.clear()
        else:
            self.storage.save_tick(snapshot, events)
        self._saved_sequences.add(snapshot.key)

    def tick(self) -> None:
        with self._lock:
            before = self.engine.snapshot.sequence
            self.engine.tick()
            if self.engine.snapshot.sequence != before:
                self._save_current_tick()

    def control(self, payload: dict[str, Any]) -> dict[str, object]:
        if not isinstance(payload, dict):
            raise ValueError("control payload must be an object")
        command = payload.get("command")
        with self._lock:
            if command == "start":
                self.engine.start()
            elif command == "pause":
                self.engine.pause()
            elif command == "resume":
                self.engine.resume()
            elif command == "scenario":
                self.engine.set_scenario(str(payload.get("scenario_id", "")))
            elif command == "recover":
                self.engine.recover()
            elif command == "recovery_action":
                self.engine.perform_action(str(payload.get("action_id", "")))
            elif command == "speed":
                value = payload.get("speed", 1)
                if isinstance(value, bool) or not isinstance(value, (float, int)):
                    raise ValueError("speed must be a number")
                speed = float(value)
                if not 0.1 <= speed <= 20:
                    raise ValueError("speed must be between 0.1 and 20")
                self.speed = speed
            elif command == "reset":
                self.engine.reset()
                self.storage.create_run(self.engine.run)
                self._saved_sequences = set()
            else:
                raise ValueError("unknown control command")
            return self.state()

    def runs(self):
        with self._lock:
            return {"runs": self.storage.list_runs(), "is_synthetic": True}


class _Handler(BaseHTTPRequestHandler):
    service: MesService
    web_root: Path

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def _send(self, status: int, body: object, content_type: str = "application/json; charset=utf-8") -> None:
        payload = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, default=_json).encode()
        self.send_response(status); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(payload)))
        # 화면 파일 갱신이 바로 보이게 (파이 프록시와 같음)
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/state": self._send(200, self.service.state()); return
            if parsed.path == "/api/catalog": self._send(200, {"data": self.service.catalog.data, "is_synthetic": True}); return
            if parsed.path == "/api/config": self._send(200, self.service.config()); return
            if parsed.path == "/api/kb/cards": self._send(200, kb_cards()); return
            if parsed.path.startswith("/api/configs/"):
                self._send(200, self.service.stored_config(parsed.path.split("/")[3])); return
            if parsed.path == "/api/events": self._send(200, self.service.events(int(parse_qs(parsed.query).get("after_sequence", ["-1"])[0]))); return
            if parsed.path == "/api/runs": self._send(200, self.service.runs()); return
            if parsed.path == "/api/outbox": self._send(200, {**self.service.storage.outbox_counts(), "is_synthetic": True}); return
            if parsed.path == "/api/outbox/pending":
                rows = self.service.storage.pending_handovers()
                self._send(200, {"handovers": [{**json.loads(p), "created_at": c} for _, c, p in rows], "is_synthetic": True}); return
            if parsed.path == "/api/equipment/scan/recent":
                self._send(200, self.service.recent_scans(int(parse_qs(parsed.query).get("limit", ["5"])[0]))); return
            if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/replay"):
                run_id = parsed.path.split("/")[3]; sequence = int(parse_qs(parsed.query).get("sequence", ["-1"])[0])
                self._send(200, self.service.replay(run_id, sequence)); return
            if parsed.path == "/api/export":
                query = parse_qs(parsed.query); run_id = query.get("run_id", [self.service.engine.run.run_id])[0]; format_name = query.get("format", ["jsonl"])[0]
                content_type = "text/csv; charset=utf-8" if format_name == "csv" else "application/x-ndjson; charset=utf-8"
                self._send(200, self.service.export(run_id, format_name).encode(), content_type); return
            if parsed.path in ("/", "/pda.html"):
                if getattr(self, "api_only", False):
                    self._send(404, {"error": "not found", "is_synthetic": True}); return
                page = "pda.html" if parsed.path == "/pda.html" else "index.html"
                self._send(200, (self.web_root / page).read_bytes(), "text/html; charset=utf-8"); return
            if parsed.path.startswith("/static/") and Path(parsed.path).name in {"app.js", "operator.js", "style.css", "pda.js"}:
                if getattr(self, "api_only", False):
                    self._send(404, {"error": "not found", "is_synthetic": True}); return
                name = Path(parsed.path).name; kind = "text/javascript" if name.endswith("js") else "text/css"
                self._send(200, (self.web_root / name).read_bytes(), f"{kind}; charset=utf-8"); return
            self._send(404, {"error": "not found", "is_synthetic": True})
        except KeyError as error: self._send(404, {"error": str(error), "is_synthetic": True})
        except ValueError as error: self._send(400, {"error": str(error), "is_synthetic": True})
        except Exception as error:  # noqa: BLE001 — 응답 없이 끊지 않는다
            self._send(500, {"error": f"MES 서버 오류: {type(error).__name__}: {error}", "is_synthetic": True})

    def do_POST(self) -> None:  # noqa: N802
        try:
            limit = _CONFIG_BODY_LIMIT if self.path.startswith("/api/config/") else _CONTROL_BODY_LIMIT
            if self.path in ("/api/query", "/api/handover"):
                limit = _ASSIST_BODY_LIMIT
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 <= size <= limit:
                raise ValueError("request too large")
            payload = json.loads(self.rfile.read(size) or b"{}")
            if self.path == "/api/control": self._send(200, self.service.control(payload)); return
            if self.path == "/api/config/validate": self._send(200, self.service.validate_config(payload)); return
            if self.path == "/api/config/apply": self._send(200, self.service.apply_config(payload)); return
            if self.path == "/api/equipment/scan": self._send(201, self.service.record_scan(payload)); return
            if self.path == "/api/handover": self._send(200, self.service.record_handover(payload)); return
            if self.path == "/api/query": self._send(200, self.service.query(payload)); return
            self._send(404, {"error": "not found", "is_synthetic": True})
        except (ConflictError, HandoverConflictError) as error:
            self._send(409, {"error": str(error), "is_synthetic": True})
        except ConfigValidationError as error:
            self._send(400, {"error": str(error), "errors": error.errors, "is_synthetic": True})
        except JudgeUnavailableError as error:
            # The abstain judge could not run. Never show a card unjudged: tell the PDA to wait and try again.
            print(f"[판정 모델 사용 불가] {error}", flush=True)
            self._send(503, {"error": "판정 모델을 쓸 수 없습니다. 잠시 후 다시 시도해 주세요.", "retry": True, "is_synthetic": True})
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            self._send(400, {"error": str(error), "is_synthetic": True})
        except Exception as error:  # noqa: BLE001 — 모델 서버 연결 실패·의존성 누락 등도 JSON 으로 알린다
            self._send(500, {"error": f"MES 서버 오류: {type(error).__name__}: {error}", "is_synthetic": True})


def serve(host: str = "127.0.0.1", port: int = 8000, *, catalog_path: Path | None = None, db_path: Path | None = None, api_only: bool = False, random_faults: bool = False, seed: int = 0, run_nonce: str | None = None, fault_hazard: float = .015) -> None:
    root = Path(__file__).resolve().parents[2]
    database = db_path or root / "mes_data" / "mock-mes.sqlite3"
    database.parent.mkdir(parents=True, exist_ok=True)
    service = MesService(catalog_path or root / "docs" / "data" / "reference" / "00_plant_and_relations.json", MesStorage(database), seed,
                         random_faults=random_faults, run_nonce=run_nonce, fault_hazard=fault_hazard)
    handler = type("MesHandler", (_Handler,), {"service": service, "web_root": Path(__file__).with_name("web"), "api_only": api_only})
    server = ThreadingHTTPServer((host, port), handler)
    stopped = threading.Event()
    worker = threading.Thread(target=_run_ticks, args=(service, stopped), daemon=True); worker.start()
    print(f"Synthetic MES: http://{host}:{port} | database: {database}", flush=True)
    from .query import build_query_pipeline, judge_model_status, warm_models
    if (status := judge_model_status()) != "ok":  # warn only: Ollama may still be starting; queries answer 503 until it is ready
        print(f"[경고] 판정 모델을 확인하지 못했습니다({status}). 질의는 준비될 때까지 503(잠시 후 다시 시도)으로 응답합니다.", flush=True)
    if os.environ.get("SHIFTLINK_WARMUP", "1") != "0":  # load the models now so the first PDA query does not wait ~50 s
        service.query_pipeline = build_query_pipeline()
        threading.Thread(target=lambda: print(f"[예열] 모델 적재: {warm_models(service.query_pipeline)}", flush=True), daemon=True).start()
    try: server.serve_forever()
    finally:
        stopped.set()
        worker.join()
        server.server_close()
        service.storage.close()


def _run_ticks(service: MesService, stopped: threading.Event) -> None:
    while not stopped.wait(1 / service.speed):
        service.tick()
