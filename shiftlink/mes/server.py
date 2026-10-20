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

from . import analytics, configuration, field_draft, work_reports
from .accounts import Accounts
from .catalog import Catalog
from .contracts import Configuration, Run, utc_now
from .engine import MesEngine
from shiftlink.agent.pipeline import JudgeUnavailableError
from shiftlink.agent.response import AgentResponse, render_response

from .storage import HandoverConflictError, MesStorage

_CONTROL_BODY_LIMIT = 8192
_CONFIG_BODY_LIMIT = 256 * 1024
_ASSIST_BODY_LIMIT = 64 * 1024
_ACCOUNT_BODY_LIMIT = 4096
_ACCOUNT_POST_ROUTES = {"/api/admin/login", "/api/admin/logout", "/api/admin/accounts", "/api/account/login"}
_SCAN_KEEP = 50
_ROOT = Path(__file__).resolve().parents[2]
# kb split only: dev/sealed evaluation files are never opened here (C-099).
_KB_CARDS = _ROOT / "docs" / "data" / "knowledge_cards" / "kb" / "kb_cards.json"
_KB_HANDOVERS = _ROOT / "docs" / "data" / "scenarios" / "EV-0031_upstream_cause.json"


def _kb_card_map() -> dict[str, dict[str, Any]]:
    return {c["card_id"]: c for c in json.loads(_KB_CARDS.read_text(encoding="utf-8"))["cards"]}


def _card_step_chips(card: dict[str, Any]) -> list[dict[str, Any]]:
    """카드 단계 → 조치 기록 칩. 칩 글자는 단계 첫 문장(길면 자름), 원문은 full. 단계가 없는 카드는 칩 하나."""
    steps = (card.get("type_payload") or {}).get("steps") or []
    if not steps:
        return [{"text": card["card_id"] + " 방법대로", "source": "card_step", "card_id": card["card_id"], "step_id": None,
                 "n": None, "full": card.get("know_how") or "",
                 "risky": any(w in (card.get("know_how") or "") for w in field_draft.SAFETY_WORDS)}]
    chips = []
    for s in steps:
        first = s["action"].split(". ")[0].rstrip(".")
        chips.append({"text": first if len(first) <= 40 else first[:38] + "…", "source": "card_step",
                      "card_id": card["card_id"], "step_id": s["step_id"], "n": s.get("order"), "full": s["action"],
                      "risky": any(w in s["action"] for w in field_draft.SAFETY_WORDS)})
    return chips


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


# 시뮬레이터 연동: PDA 조치 기록의 MES 단계 칩·재가동 칩이 모의 MES 조치를 함께 수행한다(시연에서 MES 화면을 오가지 않게).
# 실제 MES·설비에 붙일 때는 SHIFTLINK_SIM_LINK=0 으로 끈다.
SIM_LINK = os.environ.get("SHIFTLINK_SIM_LINK", "1") != "0"


class ResolutionSessionNotFound(LookupError):
    """없는 조치 기록 세션 → 404."""


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
        with self._lock:
            return self._save_query_result(body, result, started)

    def _save_query_result(self, body, result, started):
        self.storage.save_query_evidence(result.get("evidence"))
        try:
            rendered_response = render_response(AgentResponse.model_validate(result))
        except Exception:  # Log formatting must not prevent returning the generated answer.
            rendered_response = None
        query_id = self.storage.save_query({
            "question": body.get("question"), "equipment_id": (result.get("evidence") or {}).get("equipment_id"),
            "query_context": result.get("query_context"), "evidence": result.get("evidence"),
            "knowledge_status": result.get("knowledge_status"),
            "answer": result.get("answer"), "cited_card_ids": result.get("cited_card_ids"),
            "safety_notices": result.get("safety_notices", []),
            "rendered_response": rendered_response,
            "no_knowledge": result.get("no_knowledge"), "review_queue": result.get("review_queue"),
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "model": getattr(getattr(self.query_pipeline, "model", None), "model", None),
            "answer_mode": getattr(self.query_pipeline, "answer_mode", None), "is_synthetic": True,
            **({"s30h_trace": result["s30h_trace"]} if "s30h_trace" in result else {})})
        return {**result, "query_id": query_id}

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
            if isinstance(body, dict) and "work_report" in body:
                work_reports.validate(body, {eq.equipment_id for eq in self.active_config.equipment}, self.active_config)
                candidates = None if self.storage.get_handover(body.get("handover_id")) else self._plan_work_report(body)
                return self.storage.save_work_report(body,
                    {eq.equipment_id: eq.asset_id for eq in self.active_config.equipment}, self.active_config.config_id,
                    candidates=candidates, sensor_evidence=work_reports.sensor_evidence(
                        asdict(self.engine.snapshot), self.active_config, body['equipment_ids'])
                        if candidates is not None and (body['work_report'].get('form_version')==2 or
                            any(r.get('capture_version')==1 for r in body['work_report']['records'])) else None)
            # 해결 기록은 인계 저장 전에 검사하고 초안 반영까지 계산한다. 인계와 초안은 한 트랜잭션으로 남는다.
            if not (isinstance(body, dict) and body.get("resolution") is not None):
                return self.storage.save_handover(body)
            if isinstance(body["resolution"], dict) and body["resolution"].get("session_id"):
                return self._record_session_handover(body)
            prepared = field_draft.prepare(self._server_evidence(body["resolution"]), self.active_config,
                                           body.get("equipment_id"))
            snap = asdict(self.engine.snapshot)
            field_draft.check_with_mes(
                prepared, snap["measurements"],
                [a["code"] for a in snap["active_alarms"] if a.get("equipment_id") == prepared["eq"].equipment_id],
                str(snap["simulated_at"]), self.engine.run.run_id, self._events_for_check())
            self.storage._check_handover(body)
            known = self.storage.has_draft_record(body["handover_id"])
            op, reply = (None, {"created": False, "reason": "already_exists"}) if known else \
                self._plan_resolution(body["handover_id"], prepared)
            saved, applied = self.storage.save_handover_with_draft(body, op)
            if op is not None and not applied:
                reply = {"created": False, "reason": "already_exists"}
            return {**saved, "draft": {**reply, "mes_recovered": prepared["mes_check"]["recovered"]}}

    def _plan_work_report(self, body):
        plans = {}
        seen_incidents=set()
        next_number = None
        assets = {eq.equipment_id: eq.asset_id for eq in self.active_config.equipment}
        for index, record in enumerate(body["work_report"]["records"]):
            chain=None
            if not work_reports.has_incident(record):
                continue
            if source := record.get('followup_from'):
                original=self.storage.get_handover(source['handover_id'])
                links=self.storage.report_incidents(source['handover_id'])
                if original is None or original['payload'].get('kind')!='work_log' or not any(
                    link['record_index']==source['record_index'] and link['incident_id']==record['incident_id']
                    for link in links):
                    raise ValueError('Follow-up source does not belong to the incident')
                incident=self.storage.get_incident(record['incident_id'])
                latest=incident['records'][-1]
                if (latest['handover_id'],latest['record_index'])!=(source['handover_id'],source['record_index']):
                    raise ValueError('최신 인계 기록을 이어서 작성해 주세요.')
                if work_reports.handover_resolved(latest['record']) and any(c['kind']=='T4' and c['draft_id'] and c['handover_id']==latest['handover_id'] and c['record_index']==latest['record_index'] for c in incident['candidates']):
                    raise ValueError('정상 운전 확인과 후보 구성이 완료된 사건입니다. 재발은 새 사건으로 기록해 주세요.')
                if record['incident_id'] in seen_incidents:raise ValueError('같은 사건은 한 일지에서 한 번만 이어서 기록해 주세요.')
                seen_incidents.add(record['incident_id'])
                chain=work_reports.handover_chain(incident['records'],source)+[{
                    'handover_id':body['handover_id'],'record_index':index,'required_context':body['required_context'],'record':record}]
            query_id = record.get("query_id")
            query = None
            if query_id:
                stored = self.storage.get_query(query_id)
                if stored is None:
                    raise ValueError("query_id not found")
                query = {**stored["payload"], "query_id": query_id}
                context = query.get("query_context") or {}
                eq = query.get("equipment_id")
                if eq not in record["equipment"] or not context.get("asset_id") or context["asset_id"] != assets.get(eq):
                    raise ValueError("query does not match the work report equipment/asset")
                if context.get("incident_id") and context["incident_id"] != record.get("incident_id"):
                    raise ValueError("query belongs to another incident; specify its incident_id")
            ready, incomplete = [], []
            requested = record["candidate"] or record.get("auto_candidate")

            def add(kind, missing_reason, make_draft=None):
                nonlocal next_number
                draft = None
                if make_draft is not None:
                    if next_number is None:
                        next_number = int(self.storage.next_card_id(*field_draft.ID_RANGE)[2:])
                    if next_number > field_draft.ID_RANGE[1]:
                        raise ValueError('field draft card id range is exhausted')
                    draft = make_draft(f'K-{next_number:04d}')
                    next_number += 1
                decision = {'kind': kind, 'query_id': query_id, 'reason': draft['status'] if draft else missing_reason,
                            'draft': draft}
                (ready if draft else incomplete).append(decision)

            if not requested:
                add('legacy', 'not_requested')
            else:
                for kind in work_reports.observation_kinds(record):
                    missing = work_reports.observation_missing(record, kind)
                    add(kind, 'insufficient_safety' if kind == 'T5' else 'insufficient_' + kind.lower(),
                        None if missing else lambda card_id, kind=kind: work_reports.observation_candidate_from(
                            record, self.active_config, body['handover_id'], index, card_id, utc_now(), kind))
                if chain is not None:
                    add('T4', 'insufficient_handover', None if work_reports.handover_missing(chain) else
                        lambda card_id: work_reports.handover_candidate_from(chain, self.active_config, card_id, utc_now()))
                elif record.get('capture_version') == 1:
                    kind = 'T6' if record['restart_performed'] else 'T3'
                    add(kind, 'insufficient_capture', None if work_reports.capture_missing(record) else
                        lambda card_id: work_reports.capture_candidate_from(
                            record, self.active_config, body['handover_id'], index, card_id, utc_now()))
                elif query is not None or not ready and not incomplete:
                    reason = ('missing_query' if query is None else
                              'query_not_knowledge_gap' if query.get('knowledge_status') != 'no_applicable_card' else
                              'query_configuration_changed' if (query.get('query_context') or {}).get('config_id') != self.active_config.config_id else None)
                    add('T3', reason or 'pending_review', None if reason else lambda card_id: work_reports.candidate_from(
                        record, query, self.active_config, body['handover_id'], index, card_id, utc_now()))
            plans[index] = ready + incomplete
        return plans

    def record_work_report(self, body: dict[str, Any]) -> dict[str, object]:
        if not isinstance(body, dict) or body.get("kind") != "work_log" or "work_report" not in body:
            raise ValueError("work_log and work_report are required")
        return self.record_handover(body)

    def work_reports(self, limit: int = 30, offset: int = 0) -> dict[str, object]:
        with self._lock:
            return {"reports": self.storage.list_work_reports(limit,offset), "is_synthetic": True}

    def work_report(self, report_id: str) -> dict[str, object]:
        with self._lock:
            row = self.storage.get_handover(report_id)
            if row is None or row["payload"].get("kind") != "work_log":
                raise KeyError("work report not found")
            return {"report": {**row["payload"], "created_at": row["created_at"], "status": row["status"],
                               "incidents": self.storage.report_incidents(report_id),
                               "candidates": self.storage.work_report_candidates(report_id=report_id),
                               "server_sensor_evidence": self.storage.work_report_sensors(report_id)},
                    "is_synthetic": True}

    def incidents(self, limit: int = 30) -> dict[str, object]:
        with self._lock:
            return {"incidents": self.storage.list_incidents(limit), "is_synthetic": True}

    def incident(self, incident_id: str) -> dict[str, object]:
        with self._lock:
            row = self.storage.get_incident(incident_id)
            if row is None:
                raise KeyError("incident not found")
            return {"incident": row, "is_synthetic": True}

    def _events_for_check(self) -> list[dict[str, Any]]:
        """해결 확인용 이벤트: 기록된 이벤트 + 다음 틱에 기록될 대기 이벤트(pending).

        재가동 직후의 경보 해제는 다음 틱(1초)에 기록되므로, 그 사이 마무리를 눌러도 확인되게 대기분도 본다.
        대기 이벤트는 아직 일어나기 전이 아니라 '지금' 일어난 것이라 질의·조치 시작보다 뒤로 본다."""
        events = [asdict(e) for e in self.engine.events]
        run_id = self.engine.run.run_id
        return events + [{"run_id": run_id, "event_type": t, "equipment_id": eq, "pending": True}
                         for t, eq, _ in getattr(self.engine, "_pending_events", [])]

    def _server_evidence(self, resolution: object) -> object:
        """PDA가 돌려보낸 질의 근거를 서버가 질의 때 보관한 값으로 바꾼다. 없으면 근거 없음으로 둔다(값을 믿지 않는다)."""
        if not isinstance(resolution, dict) or not isinstance(resolution.get("evidence"), dict):
            return resolution
        sent = resolution["evidence"]
        stored = self.storage.get_query_evidence(sent.get("run_id"), sent.get("simulated_at"), sent.get("equipment_id"))
        if stored is None:
            return {**resolution, "evidence": None, "_evidence_note": "서버 질의 기록에 없는 근거"}
        return {**resolution, "evidence": stored}

    def _plan_resolution(self, handover_id: str, prepared: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, object]]:
        """저장하지 않고 계산만 한다: 가장 많이 겹치는 검수 대기 초안에 붙이거나 새 초안을 만든다. 예외면 아무것도 남지 않는다."""
        # MES 복구 단계 제목(시나리오별 + 일반 계획)은 누구나 하는 조치라 묶음 비교에서 뺀다.
        prepared["generic_actions"] = {a.title for spec in self.active_config.scenarios for a in spec.recovery_actions}             | {"이상 신호 위치 확인", "원인 조치 기록", "정상 범위 회복 확인"}
        scored = [(field_draft.match_score(row["card"], prepared), row) for row in self.storage.list_card_drafts()
                  if row["status"] == "pending_review" and not row["review_flags"].get("work_report")]
        score, row = max(scored, key=lambda pair: pair[0], default=(0.0, None))
        if score > 0:  # 가장 많이 겹치는 초안 하나에만 붙인다
            draft, relation = field_draft.merge(row, prepared, handover_id)
            return {"kind": "merge", "draft": draft, "draft_id": row["draft_id"], "relation": relation}, \
                {"created": False, "reason": relation}
        draft = field_draft.draft_from(prepared, handover_id, self.storage.next_card_id(*field_draft.ID_RANGE), utc_now())
        if draft["status"] == "attempt_only":
            return None, {"created": False, "reason": "attempt_only"}
        return {"kind": "new", "draft": draft}, {"created": draft["status"] == "pending_review", "reason": draft["status"]}

    # ── 조치 기록 세션: 조치 시작 → 조치마다 완료 → 마무리 → 인계와 함께 저장 ─────────────
    # 센서값은 모두 서버가 그 순간 기록한다(PDA가 보낸 값은 쓰지 않는다). 세션은 저장되면 saved로 닫힌다.

    def _eq_snapshot(self, equipment_id: str) -> dict[str, Any]:
        snap = asdict(self.engine.snapshot)
        at = snap["simulated_at"]
        return {"run_id": snap["run_id"], "equipment_id": equipment_id,
                "simulated_at": at.isoformat() if isinstance(at, datetime) else str(at),
                "measurements": [m for m in snap["measurements"] if m.get("equipment_id") == equipment_id],
                "alarms": [a["code"] for a in snap["active_alarms"] if a.get("equipment_id") == equipment_id],
                "support_scenario": snap.get("support_scenario"), "scenario_id": snap.get("scenario_id"),
                "components": [c for c in snap.get("components") or [] if c.get("equipment_id") == equipment_id],
                "recovery": snap.get("recovery")}

    def _open_session(self, session_id: object) -> dict[str, Any]:
        session = self.storage.get_resolution_session(session_id)
        if session is None:
            raise ResolutionSessionNotFound(f"unknown resolution session: {session_id}")
        if session["status"] != "open":
            raise ConflictError("resolution session is already saved")
        return session

    def _session_view(self, eq: Any, evidence: dict[str, Any]) -> dict[str, Any]:
        return {"simulated_at": evidence.get("simulated_at"), "out_of_range": field_draft.out_of_range(eq, evidence),
                "alarms": evidence.get("alarms") or []}

    def resolution_start(self, body: dict[str, Any]) -> dict[str, object]:
        with self._lock:
            if not isinstance(body, dict):
                raise ValueError("body must be an object")
            eq = field_draft._equipment(self.active_config, body.get("equipment_id"))
            question = field_draft._text(body.get("question"), 4000, "question", required=False)
            snap = self._eq_snapshot(eq.equipment_id)
            sent = body.get("evidence") if isinstance(body.get("evidence"), dict) else {}
            stored = self.storage.get_query_evidence(sent.get("run_id"), sent.get("simulated_at"), eq.equipment_id) if sent else None
            if stored is not None and stored.get("equipment_id") == eq.equipment_id:
                before = {**stored, "source": "query_evidence"}
            else:
                before = {key: snap[key] for key in ("run_id", "equipment_id", "simulated_at", "measurements", "alarms")}
                before["source"] = "snapshot"
            before["support_scenario"] = snap["support_scenario"]
            watched = [item["signal"] for item in field_draft.out_of_range(eq, before)]
            # 답에서 본 카드. 있으면 카드 효과 기록(대시보드)이고, 없으면 지식 공백 기록(카드 초안)이다.
            card_ids = body.get("card_ids") or []
            known = _kb_card_map()
            if not (isinstance(card_ids, list) and len(card_ids) <= 10 and all(c in known for c in card_ids)):
                raise ValueError("card_ids must be known card IDs")
            data = {"question": question, "run_id": before["run_id"], "before": before, "watched": watched,
                    "card_ids": card_ids, "steps": [], "after": None, "verdict": None}
            session_id = self.storage.create_resolution_session(eq.equipment_id, data)
            recovery = snap["recovery"] if (snap["recovery"] or {}).get("equipment_id") == eq.equipment_id else None
            spec = next((s for s in self.active_config.scenarios if s.scenario_id == snap["scenario_id"]), None)
            suggested = spec.component_id if spec and recovery else ""
            drafts = [row for row in self.storage.list_card_drafts() if row["card"].get("mes_equipment_id") == eq.equipment_id]
            field_actions = list(dict.fromkeys(s["action"] for row in drafts for s in row["card"]["type_payload"]["steps"]))[:5]
            causes = list(dict.fromkeys(line.removeprefix("원인: ") for row in drafts
                                        for line in (row["card"].get("know_how") or "").splitlines()
                                        if line.startswith("원인: ")))[:5]
            return {"session_id": session_id, "before": self._session_view(eq, before),
                    "components": [{"component_id": c["component_id"], "name": c["name"],
                                    "suggested": c["component_id"] == suggested} for c in snap["components"]],
                    "action_suggestions": [chip for cid in card_ids for chip in _card_step_chips(known[cid])]
                                          + [{"text": a["title"], "source": "mes_recovery", "action_id": a["action_id"]}
                                           for a in (recovery or {}).get("actions") or []]
                                          + ([{"text": field_draft.RESTART_ACTION, "source": "mes_restart"}] if recovery and SIM_LINK else [])
                                          + [{"text": a, "source": "field_record"} for a in field_actions],
                    "cause_suggestions": [*causes, field_draft.CAUSE_UNKNOWN] if field_draft.CAUSE_UNKNOWN not in causes else causes,
                    "is_synthetic": True}

    def resolution_step(self, session_id: str, body: dict[str, Any]) -> dict[str, object]:
        with self._lock:
            session = self._open_session(session_id)
            data = session["data"]
            if not isinstance(body, dict):
                raise ValueError("body must be an object")
            action = field_draft._text(body.get("action"), 500, "action")
            if len(data["steps"]) >= 20:
                raise ValueError("a session holds up to 20 steps")
            # 카드 단계 칩으로 한 조치 — 이 세션에서 본 카드의 단계만 받는다. 위험 여부는 단계 원문으로도 본다.
            card_step, full = None, ""
            if body.get("card_id") is not None:
                card_id, step_id = body.get("card_id"), body.get("step_id")
                if card_id not in data.get("card_ids", []):
                    raise ValueError("card step must come from a card seen in this session")
                chips = {c["step_id"]: c for c in _card_step_chips(_kb_card_map()[card_id])}
                if step_id not in chips:
                    raise ValueError("unknown card step")
                card_step, full = {"card_id": card_id, "step_id": step_id, "n": chips[step_id]["n"]}, chips[step_id]["full"]
            risky = any(word in action or word in full for word in field_draft.SAFETY_WORDS)
            lockout = body.get("lockout") if risky else None
            if risky and lockout not in field_draft.LOCKOUT_ANSWERS:
                raise ValueError("lockout_required")
            eq = field_draft._equipment(self.active_config, session["equipment_id"])
            linked = self._sim_link(eq.equipment_id, action) if SIM_LINK else None
            snap = self._eq_snapshot(eq.equipment_id)
            previous = data["steps"][-1]["measurements"] if data["steps"] else data["before"]["measurements"]
            step = {"order": len(data["steps"]) + 1, "action": action, "lockout": lockout,
                    "simulated_at": snap["simulated_at"], "measurements": snap["measurements"],
                    "result_text": field_draft.delta_text(eq, data["watched"], previous, snap["measurements"]),
                    "mes_linked": linked, "card_step": card_step}
            data["steps"].append(step)
            data["after"] = data["verdict"] = None  # 조치를 더 하면 마무리를 다시 한다
            self.storage.update_resolution_session(session_id, data)
            return {"order": step["order"], "result_text": step["result_text"], "simulated_at": step["simulated_at"],
                    "mes_linked": linked, "is_synthetic": True}

    def _sim_link(self, equipment_id: str, action: str) -> str | None:
        """시뮬레이터 연동(SIM_LINK): PDA에서 MES 복구 단계 칩을 완료하면 MES에도 그 조치를 수행하고,
        재가동 칩이면 라인 복구를 시작한다. 실제 설비라면 센서가 스스로 바뀌므로 이 연결이 필요 없다(끄면 기록만 한다).
        직접 적은 조치는 설비를 바꾸지 않는다. 순서가 틀리면 MES가 거절하고 단계도 남지 않는다."""
        recovery = asdict(self.engine.snapshot).get("recovery") or {}
        if recovery.get("equipment_id") != equipment_id:
            return None
        if action == field_draft.RESTART_ACTION:
            self.control({"command": "recover"})
            return "recover"
        match = next((a for a in recovery.get("actions") or [] if a["title"] == action), None)
        if match is None or match["completed"]:
            return None
        self.control({"command": "recovery_action", "action_id": match["action_id"]})
        return "recovery_action:" + match["action_id"]

    def _finish_session(self, eq: Any, data: dict[str, Any]) -> dict[str, Any]:
        """그 순간 MES로 판정한다. 기준은 기존 해결 확인과 같다(질의·조치 시작 뒤 같은 실행의 복구 기록 필수)."""
        snap = self._eq_snapshot(eq.equipment_id)
        prepared = {"resolution": {"evidence": data["before"]}, "eq": eq,
                    "states": field_draft._states(eq, data["before"])}
        check = field_draft.check_with_mes(prepared, snap["measurements"], snap["alarms"], snap["simulated_at"],
                                           self.engine.run.run_id, self._events_for_check())
        after = {key: snap[key] for key in ("run_id", "equipment_id", "simulated_at", "measurements", "alarms")}
        data["after"] = after
        data["verdict"] = {**field_draft.verdict_of(check, len(data["steps"])), "check": check}
        return data["verdict"]

    def resolution_finish(self, session_id: str) -> dict[str, object]:
        with self._lock:
            session = self._open_session(session_id)
            eq = field_draft._equipment(self.active_config, session["equipment_id"])
            verdict = self._finish_session(eq, session["data"])
            self.storage.update_resolution_session(session_id, session["data"])
            return {"verdict": verdict["verdict"], "text": verdict["text"], "suggested_result": verdict["suggested_result"],
                    "after": self._session_view(eq, session["data"]["after"]), "is_synthetic": True}

    def resolution_get(self, session_id: str) -> dict[str, object]:
        with self._lock:
            session = self.storage.get_resolution_session(session_id)
            if session is None:
                raise ResolutionSessionNotFound(f"unknown resolution session: {session_id}")
            return {**session, "is_synthetic": True}

    def _record_session_handover(self, body: dict[str, Any]) -> dict[str, object]:
        """세션에 쌓인 조치·센서 기록 + 작업자 입력(본 것·원인·부품·결과)으로 해결 기록을 만들어 기존 경로로 저장한다."""
        self.storage._check_handover(body)
        if self.storage.get_handover(body["handover_id"]) is not None:  # 재전송: 같은 본문이면 그대로, 다르면 409
            saved, _ = self.storage.save_handover_with_draft(body, None)
            return {**saved, "draft": {"created": False, "reason": "already_exists"}}
        res = body["resolution"]
        session = self._open_session(res["session_id"])
        if session["equipment_id"] != body.get("equipment_id"):
            raise ValueError("resolution session belongs to another equipment")
        eq = field_draft._equipment(self.active_config, session["equipment_id"])
        data = session["data"]
        if res.get("result") not in field_draft.RESULTS:
            raise ValueError("result must be resolved, temporary or failed")
        if res["result"] != "failed" and not data["steps"]:
            raise ValueError("complete at least one action before saving")
        cause = field_draft._text(res.get("cause"), 200, "cause")
        components = {c["component_id"]: c["name"] for c in self._eq_snapshot(eq.equipment_id)["components"]}
        if res.get("component_id") not in components:
            raise ValueError("component_id must be one of the equipment components")
        if data["verdict"] is None:
            self._finish_session(eq, data)
        scenario = data["before"].get("support_scenario")
        raw = {"question": data["question"], "symptom": res.get("symptom"), "result": res["result"],
               "actions": [{"action": s["action"], "result": s["result_text"]} for s in data["steps"]],
               "verification": data["verdict"]["text"], "evidence": data["before"], "cause": cause,
               "component_id": res["component_id"], "component_name": components[res["component_id"]],
               "scenario": scenario if scenario in field_draft.SCENARIOS else None,
               "lockout_answers": [{"action": s["action"], "lockout": s["lockout"]} for s in data["steps"] if s["lockout"]]}
        prepared = field_draft.prepare(raw, self.active_config, eq.equipment_id)
        prepared["mes_check"] = data["verdict"]["check"]  # 마무리 때의 판정을 쓴다
        if data.get("card_ids"):  # 카드를 보고 한 조치 — 새 초안이 아니라 그 카드의 효과 기록으로 남긴다
            op, reply = None, {"created": False, "reason": "card_used"}
        else:
            op, reply = self._plan_resolution(body["handover_id"], prepared)
        saved, _ = self.storage.save_handover_with_draft(body, op, session=(res["session_id"], data))
        return {**saved, "draft": {**reply, "mes_recovered": data["verdict"]["check"]["recovered"],
                                   "mes_verdict": data["verdict"]["verdict"]}}

    def card_drafts(self) -> dict[str, object]:
        """검수 대기 카드 초안 목록(읽기 전용). 검색·PDA에는 나가지 않는다.

        각 초안에 겹칠 수 있는 기존 카드(similar_kb_cards)를 붙인다. 카드 묶음은 처음 한 번만 읽는다.
        """
        with self._lock:
            if getattr(self, "_kb_provider", None) is None:
                from shiftlink.rag.loader import load_card_provider
                from .query import ROOT
                self._kb_provider = load_card_provider(ROOT / "docs/data/knowledge_cards/kb/kb_cards.json").provider
            drafts = self.storage.list_card_drafts()
            for row in drafts:
                row["similar_kb_cards"] = field_draft.similar_kb_cards(row["card"], self._kb_provider)
            return {"drafts": drafts, "is_synthetic": True}

    def admin_card_drafts(self):
        with self._lock:
            drafts=[self.storage.get_card_draft(row['draft_id']) for row in self.storage.list_card_drafts()]
            return {'drafts':drafts,'is_synthetic':True}

    def admin_card_draft(self,draft_id):
        from .candidate_review import detail
        with self._lock:return {'draft':detail(self.storage,draft_id),'is_synthetic':True}

    def review_card_draft(self,draft_id,body,actor):
        from .candidate_review import validate_decision
        action,status,reason,revision=validate_decision(body)
        with self._lock:
            self.storage.review_card_draft(draft_id,action,status,reason,revision,actor)
            return self.admin_card_draft(draft_id)

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

    def analytics(self) -> dict[str, object]:
        """대시보드 분석 — 저장 4주 이력 + 이 실행의 사건(경보·조치 기록·인계)."""
        with self._lock:
            events = [asdict(e) for e in self.engine.events]
            run, now = self.engine.run, self.engine.snapshot.simulated_at
            sessions = self.storage.resolution_sessions(run.run_id)
            handovers = self.storage.handover_payloads()
            relations, route = self.active_config.relations, self.active_config.route
            queries, drafts = self.storage.query_payloads(), self.storage.list_card_drafts()
        standard = next((line.get("production_standard") for line in self.catalog.data.get("production_lines", [])), None)
        out = analytics.summary([*analytics.load_history(run.started_at), *analytics.live_incidents(events, sessions, handovers)],
                                relations, now, MesEngine.ALARM_LABELS, route=route, standard=standard)
        return {**out, "knowledge": analytics.knowledge_gap(queries, drafts, set(_kb_card_map())), "is_synthetic": True}

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
    accounts: Accounts
    web_root: Path

    def _account_token(self) -> str:
        scheme, _, token = self.headers.get("Authorization", "").partition(" ")
        return token.strip() if scheme.lower() == "bearer" else ""

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
            if parsed.path=='/api/admin/card-drafts' or parsed.path.startswith('/api/admin/card-drafts/'):
                actor=self.accounts.administrator(self._account_token())
                if not actor:
                    self._send(401,{'error':'MES 관리자 로그인이 필요합니다.'});return
                suffix=parsed.path.removeprefix('/api/admin/card-drafts')
                result=self.service.admin_card_drafts() if not suffix else self.service.admin_card_draft(suffix[1:])
                self._send(200,{**result,'administrator':actor});return
            if parsed.path == "/api/admin/accounts":
                status, body = self.accounts.request("GET", parsed.path, token=self._account_token())
                self._send(status, body); return
            if parsed.path == "/api/incidents":
                self._send(200, self.service.incidents(int(parse_qs(parsed.query).get("limit", ["30"])[0]))); return
            if parsed.path.startswith("/api/incidents/"):
                self._send(200, self.service.incident(parsed.path.removeprefix("/api/incidents/"))); return
            if parsed.path == "/api/work-reports":
                params=parse_qs(parsed.query)
                self._send(200, self.service.work_reports(int(params.get("limit",["30"])[0]),int(params.get("offset",["0"])[0]))); return
            if parsed.path.startswith("/api/work-reports/"):
                self._send(200, self.service.work_report(parsed.path.removeprefix("/api/work-reports/"))); return
            if parsed.path == "/api/state": self._send(200, self.service.state()); return
            if parsed.path == "/api/catalog": self._send(200, {"data": self.service.catalog.data, "is_synthetic": True}); return
            if parsed.path == "/api/config": self._send(200, self.service.config()); return
            if parsed.path == "/api/kb/cards": self._send(200, kb_cards()); return
            if parsed.path == "/api/analytics": self._send(200, self.service.analytics()); return
            if parsed.path.startswith("/api/configs/"):
                self._send(200, self.service.stored_config(parsed.path.split("/")[3])); return
            if parsed.path == "/api/events": self._send(200, self.service.events(int(parse_qs(parsed.query).get("after_sequence", ["-1"])[0]))); return
            if parsed.path == "/api/runs": self._send(200, self.service.runs()); return
            if parsed.path == "/api/card-drafts": self._send(200, self.service.card_drafts()); return
            if parsed.path.startswith("/api/resolution/"):
                self._send(200, self.service.resolution_get(parsed.path.split("/")[3])); return
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
            if parsed.path in ("/", "/pda.html", "/knowledge-candidates.html"):
                if getattr(self, "api_only", False):
                    self._send(404, {"error": "not found", "is_synthetic": True}); return
                page = parsed.path[1:] if parsed.path!='/' else "index.html"
                self._send(200, (self.web_root / page).read_bytes(), "text/html; charset=utf-8"); return
            if parsed.path.startswith("/static/") and Path(parsed.path).name in {"app.js", "operator.js", "accounts.js", "style.css", "pda.js", "candidate-review.js", "candidate-review.css"}:
                if getattr(self, "api_only", False):
                    self._send(404, {"error": "not found", "is_synthetic": True}); return
                name = Path(parsed.path).name; kind = "text/javascript" if name.endswith("js") else "text/css"
                self._send(200, (self.web_root / name).read_bytes(), f"{kind}; charset=utf-8"); return
            self._send(404, {"error": "not found", "is_synthetic": True})
        except (KeyError, ResolutionSessionNotFound) as error: self._send(404, {"error": str(error), "is_synthetic": True})
        except ValueError as error: self._send(400, {"error": str(error), "is_synthetic": True})
        except Exception as error:  # noqa: BLE001 — 응답 없이 끊지 않는다
            self._send(500, {"error": f"MES 서버 오류: {type(error).__name__}: {error}", "is_synthetic": True})

    def do_POST(self) -> None:  # noqa: N802
        try:
            account_path = urlparse(self.path).path
            review_route=account_path.startswith('/api/admin/card-drafts/') and account_path.endswith('/review')
            if account_path in _ACCOUNT_POST_ROUTES or review_route:
                actor=self.accounts.administrator(self._account_token()) if review_route else None
                if review_route and not actor:
                    self._send(401,{'error':'MES 관리자 로그인이 필요합니다.'});return
                origin = self.headers.get("Origin")
                if origin is not None:
                    parsed_origin = urlparse(origin)
                    if (parsed_origin.scheme not in {"http", "https"}
                            or parsed_origin.netloc.lower() != self.headers.get("Host", "").lower()
                            or parsed_origin.path not in {"", "/"} or parsed_origin.query or parsed_origin.fragment):
                        self._send(403, {"error": "허용되지 않은 요청 출처입니다."}); return
                if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                    self._send(415, {"error": "JSON 요청이 필요합니다."}); return
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 <= size <= _ACCOUNT_BODY_LIMIT:
                    self._send(413, {"error": "요청 크기를 초과했습니다."}); return
                payload = json.loads(self.rfile.read(size) or b"{}")
                if not isinstance(payload, dict):
                    self._send(400, {"error": "JSON 객체가 필요합니다."}); return
                if review_route:
                    self._send(200,self.service.review_card_draft(account_path.split('/')[4],payload,actor));return
                status, body = self.accounts.request("POST", account_path, payload, token=self._account_token())
                self._send(status, body); return
            limit = _CONFIG_BODY_LIMIT if self.path.startswith("/api/config/") else _CONTROL_BODY_LIMIT
            if self.path in ("/api/query", "/api/handover", "/api/work-reports"):
                limit = _ASSIST_BODY_LIMIT
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 <= size <= limit:
                raise ValueError("request too large")
            payload = json.loads(self.rfile.read(size) or b"{}")
            if self.path == "/api/control": self._send(200, self.service.control(payload)); return
            if self.path == "/api/config/validate": self._send(200, self.service.validate_config(payload)); return
            if self.path == "/api/config/apply": self._send(200, self.service.apply_config(payload)); return
            if self.path == "/api/equipment/scan": self._send(201, self.service.record_scan(payload)); return
            if self.path == "/api/work-reports": self._send(200, self.service.record_work_report(payload)); return
            if self.path == "/api/handover": self._send(200, self.service.record_handover(payload)); return
            if self.path == "/api/query": self._send(200, self.service.query(payload)); return
            if self.path == "/api/resolution/start": self._send(200, self.service.resolution_start(payload)); return
            parts = self.path.split("/")
            if len(parts) == 5 and parts[1:3] == ["api", "resolution"] and parts[4] == "step":
                self._send(200, self.service.resolution_step(parts[3], payload)); return
            if len(parts) == 5 and parts[1:3] == ["api", "resolution"] and parts[4] == "finish":
                self._send(200, self.service.resolution_finish(parts[3])); return
            self._send(404, {"error": "not found", "is_synthetic": True})
        except ResolutionSessionNotFound as error:
            self._send(404, {"error": str(error), "is_synthetic": True})
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
    accounts = Accounts(database.with_name("accounts.json"))
    handler = type("MesHandler", (_Handler,), {"service": service, "accounts": accounts, "web_root": Path(__file__).with_name("web"), "api_only": api_only})
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
