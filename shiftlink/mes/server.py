"""One-process localhost server for the synthetic MES demonstration."""

from __future__ import annotations

import json
import csv
from io import StringIO
import threading
from dataclasses import asdict, is_dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .catalog import Catalog
from .contracts import Run
from .engine import MesEngine
from .storage import MesStorage


def _json(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


class MesService:
    """Owns the single engine instance; HTTP reads never advance it."""

    def __init__(self, catalog_path: Path, storage: MesStorage | None = None, seed: int = 0) -> None:
        self.catalog = Catalog.load(catalog_path)
        self.storage = storage or MesStorage()
        self.engine = MesEngine(Run.create(seed=seed), self.catalog)
        self.storage.create_run(self.engine.run)
        self.speed = 1.0
        self._saved_sequences: set[tuple[str, int]] = set()
        self._lock = threading.RLock()

    def state(self) -> dict[str, object]:
        with self._lock:
            return json.loads(json.dumps(asdict(self.engine.snapshot), default=_json)) | {"speed": self.speed}

    def events(self, after_sequence: int) -> dict[str, object]:
        with self._lock:
            return {"run_id": self.engine.run.run_id, "events": json.loads(json.dumps([asdict(event) for event in self.engine.events if event.sequence > after_sequence], default=_json)), "is_synthetic": True}

    def replay(self, run_id: str, after_sequence: int) -> dict[str, object]:
        with self._lock:
            snapshots, events = self.storage.replay(run_id, after_sequence=after_sequence)
            if not snapshots and self.storage.get_run(run_id) is None:
                raise KeyError("run not found")
        return {"snapshots": json.loads(json.dumps(snapshots, default=_json)), "events": json.loads(json.dumps(events, default=_json)), "is_synthetic": True}

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
        self.send_response(status); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/state": self._send(200, self.service.state()); return
            if parsed.path == "/api/catalog": self._send(200, {"data": self.service.catalog.data, "is_synthetic": True}); return
            if parsed.path == "/api/events": self._send(200, self.service.events(int(parse_qs(parsed.query).get("after_sequence", ["-1"])[0]))); return
            if parsed.path == "/api/runs": self._send(200, self.service.runs()); return
            if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/replay"):
                run_id = parsed.path.split("/")[3]; sequence = int(parse_qs(parsed.query).get("sequence", ["-1"])[0])
                self._send(200, self.service.replay(run_id, sequence)); return
            if parsed.path == "/api/export":
                query = parse_qs(parsed.query); run_id = query.get("run_id", [self.service.engine.run.run_id])[0]; format_name = query.get("format", ["jsonl"])[0]
                content_type = "text/csv; charset=utf-8" if format_name == "csv" else "application/x-ndjson; charset=utf-8"
                self._send(200, self.service.export(run_id, format_name).encode(), content_type); return
            if parsed.path == "/": self._send(200, (self.web_root / "index.html").read_bytes(), "text/html; charset=utf-8"); return
            if parsed.path.startswith("/static/") and Path(parsed.path).name in {"app.js", "style.css"}:
                name = Path(parsed.path).name; kind = "text/javascript" if name.endswith("js") else "text/css"
                self._send(200, (self.web_root / name).read_bytes(), f"{kind}; charset=utf-8"); return
            self._send(404, {"error": "not found", "is_synthetic": True})
        except KeyError as error: self._send(404, {"error": str(error), "is_synthetic": True})
        except ValueError as error: self._send(400, {"error": str(error), "is_synthetic": True})

    def do_POST(self) -> None:  # noqa: N802
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 <= size <= 8192:
                raise ValueError("request too large")
            payload = json.loads(self.rfile.read(size) or b"{}")
            if self.path != "/api/control": self._send(404, {"error": "not found", "is_synthetic": True}); return
            self._send(200, self.service.control(payload))
        except (ValueError, KeyError, json.JSONDecodeError) as error: self._send(400, {"error": str(error), "is_synthetic": True})


def serve(host: str = "127.0.0.1", port: int = 8000, *, catalog_path: Path | None = None, db_path: Path | None = None) -> None:
    root = Path(__file__).resolve().parents[2]
    database = db_path or root / "data" / "mock-mes.sqlite3"
    database.parent.mkdir(parents=True, exist_ok=True)
    service = MesService(catalog_path or root / "docs" / "00_plant_and_relations.json", MesStorage(database))
    handler = type("MesHandler", (_Handler,), {"service": service, "web_root": Path(__file__).with_name("web")})
    server = ThreadingHTTPServer((host, port), handler)
    stopped = threading.Event()
    worker = threading.Thread(target=_run_ticks, args=(service, stopped), daemon=True); worker.start()
    print(f"Synthetic MES: http://{host}:{port} | database: {database}", flush=True)
    try: server.serve_forever()
    finally:
        stopped.set()
        worker.join()
        server.server_close()
        service.storage.close()


def _run_ticks(service: MesService, stopped: threading.Event) -> None:
    while not stopped.wait(1 / service.speed):
        service.tick()
