"""사건 이력 → PDA 대시보드 분석(정지 손실·반복 증상·조치 효과·지식 공백).

사건 = 경보(alarm_at) → 조치 시작(action_at) → 복구(recovered_at). 저장된 4주 이력(docs/data/analytics)과
지금 실행의 사건(경보 이벤트 + 조치 기록 세션 + 인계)을 같은 형식으로 합쳐 같은 함수로 계산한다.
지표 정의는 docs/design/pda_ui/dashboard_analytics_20261014.md.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

HISTORY = Path(__file__).resolve().parents[2] / "docs" / "data" / "analytics" / "line_history.json"
RECUR_WITHIN = timedelta(days=7)   # 복구 뒤 이 안에 같은 설비·같은 경보가 다시 나면 재발
WEEK = timedelta(days=7)
KST = timezone(timedelta(hours=9))


def calendar_weeks(now: datetime, weeks: int) -> tuple[datetime, datetime]:
    """달력 주(월~일, 한국 시각) 기준 구간 [시작, 끝). 이번 주를 포함해 weeks주 — 시작점이 '지금'에 따라 흔들리지 않는다."""
    local = now.astimezone(KST) if now.tzinfo else now
    monday = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return monday - WEEK * (weeks - 1), monday + WEEK
# 원인 설비가 멈추면 이 관계로 이어진 설비가 같이 선다. 라인 경로(route)까지 이어지면 출측 코일 생산이 멈춘다.
# ponytail: 같은 시간으로 본다(전달 지연 lag_seconds 무시).
PROPAGATES = {"drive", "hydraulic_supply", "interlock", "power_supply", "pneumatic_supply"}


def coils_per_hour(standard: dict[str, Any]) -> float:
    """표준 생산 속도 = 연간 능력(t) ÷ 연간 유효 가동 시간(h) ÷ 평균 코일 중량(t). 값과 근거는 카탈로그 production_standard."""
    return standard["annual_capacity_t"] / standard["effective_hours_per_year"] / standard["avg_coil_weight_t"]


def _halts_line(equipment_id: str, edges: dict[str, list[str]], route: set[str]) -> bool:
    """이 설비가 서면 관계를 따라(여러 단계) 라인 경로 설비가 서는가."""
    seen, todo = set(), [equipment_id]
    while todo:
        eq = todo.pop()
        if eq in route:
            return True
        if eq not in seen:
            seen.add(eq)
            todo.extend(edges.get(eq, []))
    return False
SKIP_CODES = {"AL-SYMPTOM"}   # 증상 패턴 알림은 설비를 세우지 않는다


def _dt(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _norm(raw: dict[str, Any]) -> dict[str, Any]:
    return {**raw, **{k: _dt(raw.get(k)) for k in ("alarm_at", "action_at", "recovered_at")}}


def load_history(end: datetime, path: Path = HISTORY) -> list[dict[str, Any]]:
    """저장 이력을 지금 실행 시작(end)에 이어 붙도록 옮긴다."""
    data = json.loads(path.read_text(encoding="utf-8"))
    shift = end - _dt(data["_meta"]["end"])
    out = []
    for raw in data["incidents"]:
        row = _norm(raw)
        # 저장 이력의 카드 ID는 그 카드 방법으로 고친 기록이다. 단계별 센서 결과는 없다.
        row.update(card_method=bool(row.get("card_id")), no_change=False)
        out.append({**row, **{k: row[k] + shift for k in ("alarm_at", "action_at", "recovered_at") if row[k]}})
    return out


def _action_name(steps: list[dict[str, Any]]) -> str | None:
    """카드 단계로 한 조치가 있으면 '카드 방법' — 이름을 카드와 단계 번호로(K-1025 1·2·4단계). 없으면 첫 조치."""
    cards = [s["card_step"] for s in steps if s.get("card_step")]
    if not cards:
        return steps[0]["action"] if steps else None
    nums = "·".join(str(c["n"]) for c in cards if c["n"])
    return f'{cards[0]["card_id"]} {nums + "단계" if nums else "방법대로"}'


def live_incidents(events: Iterable[dict[str, Any]], sessions: list[dict[str, Any]],
                   handovers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """지금 실행의 사건. 조치 시작 = 그 설비 조치 기록 세션의 첫 조치, 복구 = 같은 경보 해제."""
    events = [{**e, "occurred_at": _dt(e["occurred_at"])} for e in events]
    by_session = {(h.get("resolution") or {}).get("session_id"): h for h in handovers if isinstance(h.get("resolution"), dict)}
    out = []
    for e in events:
        if e["event_type"] != "alarm_raised" or e["observation"] in SKIP_CODES:
            continue
        eq, code, at = e["equipment_id"], e["observation"], e["occurred_at"]
        cleared = next((x["occurred_at"] for x in events if x["event_type"] == "alarm_cleared"
                        and x["equipment_id"] == eq and x["observation"] == code and x["occurred_at"] >= at), None)
        steps = [(s, _dt(s["data"]["steps"][0]["simulated_at"])) for s in sessions
                 if s["equipment_id"] == eq and s["data"].get("steps")]
        session, action_at = next(((s, t) for s, t in sorted(steps, key=lambda p: p[1])
                                   if t >= at and (cleared is None or t <= cleared)), (None, None))
        resolution = ((by_session.get(session["session_id"]) or {}).get("resolution") or {}) if session else {}
        done = session["data"]["steps"] if session else []
        out.append({"incident_id": f"LIVE-{e['sequence']}-{eq}", "equipment_id": eq, "alarm_code": code,
                    "alarm_at": at, "action_at": action_at, "recovered_at": cleared,
                    "action": _action_name(done), "card_method": any(s.get("card_step") for s in done),
                    # 모든 조치가 센서를 움직이지 못했는데 닫은 기록 — 엉뚱한 시도인지 가르는 객관 신호
                    "no_change": bool(done) and not any("→" in s["result_text"] for s in done),
                    "cause": resolution.get("cause"), "result": resolution.get("result"),
                    # 근무일지 항목과 같은 이름: 본 것 → 상황·증상, 조치마다 센서 변화 → 조치 결과. 확신도는 받지 않으므로 비운다.
                    "story": resolution.get("symptom"),
                    "causes": [{"certainty": None, "note": resolution["cause"], "evidence": ""}] if resolution.get("cause") else [],
                    "action_steps": [{"action": s["action"], "observed_result": s.get("result_text", "")} for s in done],
                    "handover_id": (by_session.get(session["session_id"]) or {}).get("handover_id") if session else None,
                    "card_id": (session["data"].get("card_ids") or [None])[0] if session else None})
    return out


def _minutes(a: datetime, b: datetime) -> float:
    return max(0.0, (b - a).total_seconds() / 60)


def _link_recurrence(incidents: list[dict[str, Any]]) -> None:
    last: dict[tuple[str, str], dict[str, Any]] = {}
    for inc in sorted(incidents, key=lambda i: i["alarm_at"]):
        key = (inc["equipment_id"], inc["alarm_code"])
        prev = last.get(key)
        if prev and prev["recovered_at"] and inc["alarm_at"] - prev["recovered_at"] <= RECUR_WITHIN:
            prev["recurred_after_days"] = round((inc["alarm_at"] - prev["recovered_at"]).total_seconds() / 86400, 1)
            inc["recurrence_of"] = prev["incident_id"]
        last[key] = inc


def knowledge_gap(queries: list[dict[str, Any]], drafts: list[dict[str, Any]], kb_ids: set[str]) -> dict[str, Any]:
    """지식 공백 — 합성 이력 없이 이 MES DB에 쌓인 실제 기록만: 지식 없음 질의 → 카드 초안 → 검수 대기 → 승인
    → 카드로 답(승인된 현장 카드를 근거로 답한 질의 = 공백이 닫힘).
    승인 = 초안의 카드 ID가 카드 묶음(kb_cards.json)에 들어감(승격 도구는 초안 상태를 바꾸지 않는다)."""
    approved = [d["card"]["card_id"] for d in drafts if d["card"].get("card_id") in kb_ids]
    return {"no_knowledge": sum(q.get("no_knowledge") is True for q in queries),
            "drafts": len(drafts),
            "pending": sum(d["status"] == "pending_review" and d["card"].get("card_id") not in kb_ids for d in drafts),
            "approved": len(approved), "approved_ids": approved,
            "answered": sum(any(c in approved for c in q.get("cited_card_ids") or []) for q in queries)}


def _method_split(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """카드 방법 대 카드 밖 방법 — 조치 기록이 있는 사건만. 건수·재발·센서 변화 없이 닫음."""
    out = {}
    for name, flag in (("card", True), ("other", False)):
        items = [i for i in rows if i["action"] and i["card_method"] == flag]
        out[name] = {"count": len(items), "recurred": sum("recurred_after_days" in i for i in items),
                     "no_change": sum(i["no_change"] for i in items)}
    return out


def _outcome(inc: dict[str, Any], now: datetime) -> str:
    if "recurred_after_days" in inc:
        return "recurred"
    if not inc["recovered_at"]:
        return "open"
    return "watching" if now - inc["recovered_at"] < RECUR_WITHIN else "held"


def summary(incidents: list[dict[str, Any]], relations: Iterable[Any], now: datetime,
            labels: dict[str, str] | None = None, *, route: Iterable[str] = (),
            standard: dict[str, Any] | None = None) -> dict[str, Any]:
    labels = labels or {}
    relations = list(relations)
    # 반복 증상·신뢰성은 이번 주 포함 달력 4주(월~일), 정지 손실·생산은 이번 주(월~일).
    window_start, window_end = calendar_weeks(now, 4)
    week_start, week_end = calendar_weeks(now, 1)
    incidents = [dict(i) for i in incidents if window_start <= i["alarm_at"] <= now]
    _link_recurrence(incidents)
    affected = defaultdict(list)
    for r in relations:
        if r.relation_type in PROPAGATES:
            affected[r.from_id].append(r.to_id)

    for inc in incidents:
        end = inc["recovered_at"] or now
        inc["down_min"] = round(_minutes(inc["alarm_at"], end), 1)
        inc["affected"] = affected.get(inc["equipment_id"], [])
        inc["outcome"] = _outcome(inc, now)
        inc["label"] = labels.get(inc["alarm_code"], inc["alarm_code"])

    # 정지 손실 — 이번 주(월요일 0시부터 지금까지). 원인 설비가 라인을 세운 시간 × 표준 생산 속도 = 못 만든 코일.
    # 직렬 라인이라 몇 대가 같이 기다려도 출측이 멈춘 시간은 한 번이다(대기 설비 수를 곱하지 않는다).
    # ponytail: 서로 다른 원인이 같은 시간에 겹치면 두 번 센다. 겹침이 생기면 라인 정지 구간을 합집합으로 바꾼다.
    rate = coils_per_hour(standard) if standard else 0.0
    route_set = set(route)
    loss: dict[str, dict[str, Any]] = {}
    for inc in incidents:
        start, end = max(inc["alarm_at"], week_start), inc["recovered_at"] or now
        if end <= start:
            continue
        m = _minutes(start, end)
        row = loss.setdefault(inc["equipment_id"], {"equipment_id": inc["equipment_id"], "stop_min": 0.0,
                                                    "halts_line": _halts_line(inc["equipment_id"], affected, route_set),
                                                    "incidents": []})
        row["stop_min"] += m
        row["incidents"].append(inc["incident_id"])
    for row in loss.values():
        row["coils_exact"] = row["stop_min"] / 60 * rate if row["halts_line"] else 0.0
    loss_rows = sorted(({**{k: v for k, v in r.items() if k != "coils_exact"}, "stop_min": round(r["stop_min"]),
                         "coils": round(r["coils_exact"])} for r in loss.values()),
                       key=lambda r: (-loss[r["equipment_id"]]["coils_exact"], -r["stop_min"]))
    lost = round(sum(r["coils_exact"] for r in loss.values()))
    planned = round(standard["planned_hours_per_week"] * rate) if standard else 0
    production = {"planned": planned, "lost": lost, "produced": planned - lost,
                  "coils_per_hour": round(rate, 1)}

    # 설비 신뢰성(4주, 설비 단위 — 증상 구분 없이 그 설비의 고장 전부):
    #   MTTR(평균 수리 시간) = 정지 시간 합 ÷ 고장 수,  MTBF(평균 고장 간격) = (4주 구간 시작부터 지금까지 − 정지 시간 합) ÷ 고장 수.
    by_eq: dict[str, list[float]] = defaultdict(list)
    for inc in incidents:
        by_eq[inc["equipment_id"]].append(inc["down_min"])
    window_h = (now - window_start).total_seconds() / 3600
    reliability = {eq: {"failures": len(d), "mttr_min": round(sum(d) / len(d)),
                        "mtbf_h": round((window_h - sum(d) / 60) / len(d))} for eq, d in by_eq.items()}
    for r in loss_rows:   # 정지 손실 줄에 그 설비의 MTBF·MTTR
        r["reliability"] = reliability.get(r["equipment_id"])

    # 반복 증상 — 달력 4주 안에 같은 설비·같은 경보 2회 이상. 원인·결과 분포와 조치별 재발.
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for inc in incidents:
        groups[(inc["equipment_id"], inc["alarm_code"])].append(inc)
    repeats = []
    for (eq, code), rows in groups.items():
        if len(rows) < 2:
            continue
        by_action: dict[tuple[bool, str], list[dict[str, Any]]] = defaultdict(list)
        for inc in rows:
            by_action[(inc["card_method"], inc["action"] or "기록 없음")].append(inc)
        actions = []
        for (card_method, action), items in by_action.items():
            gaps = [i["recurred_after_days"] for i in items if "recurred_after_days" in i]
            actions.append({"action": action, "method": "card" if card_method else "other",
                            "no_change": sum(i["no_change"] for i in items),
                            "count": len(items), "recurred": len(gaps),
                            "watching": sum(i["outcome"] in ("watching", "open") for i in items),
                            "held": sum(i["outcome"] == "held" for i in items),
                            "avg_recur_days": round(sum(gaps) / len(gaps), 1) if gaps else None,
                            "card_ids": sorted({i["card_id"] for i in items if i["card_id"]}),
                            "incidents": [i["incident_id"] for i in items]})
        repeats.append({"equipment_id": eq, "alarm_code": code, "label": labels.get(code, code), "count": len(rows),
                        "recurred": sum("recurred_after_days" in i for i in rows),
                        # '해결'로 닫았는데 재발 — 적힌 원인을 고쳐도 안 끝났다 = 근본 원인 미확인
                        "resolved_recurred": sum(i["result"] == "resolved" and "recurred_after_days" in i for i in rows),
                        "causes": Counter(i["cause"] or "기록 없음" for i in rows).most_common(),
                        "temporary": sum(i["result"] == "temporary" for i in rows),
                        "actions": sorted(actions, key=lambda a: (a["recurred"] == 0, -a["count"])),
                        "methods": _method_split(rows),   # 같은 증상 안에서 카드 방법 대 카드 밖 방법
                        "incidents": [i["incident_id"] for i in rows]})
    repeats.sort(key=lambda g: (-g["recurred"], -g["count"]))

    def view(inc: dict[str, Any]) -> dict[str, Any]:
        return {**{k: v.isoformat() if isinstance(v, datetime) else v for k, v in inc.items()}}

    return {"now": now.isoformat(), "week_start": week_start.isoformat(), "week_end": week_end.isoformat(),
            "window_start": window_start.isoformat(), "window_end": window_end.isoformat(), "loss": loss_rows, "production": production,
            "repeats": repeats,
            "incidents": [view(i) for i in sorted(incidents, key=lambda i: i["alarm_at"], reverse=True)]}


if __name__ == "__main__":   # 저장 이력만으로 한 번 계산해 본다
    from shiftlink.mes.configuration import from_catalog
    from shiftlink.mes.engine import MesEngine
    catalog = json.loads((HISTORY.parents[1] / "reference" / "00_plant_and_relations.json").read_text(encoding="utf-8"))
    end = _dt(json.loads(HISTORY.read_text(encoding="utf-8"))["_meta"]["end"])
    config = from_catalog(catalog)
    out = summary(load_history(end), config.relations, end, MesEngine.ALARM_LABELS, route=config.route,
                  standard=catalog["production_lines"][0]["production_standard"])
    print(json.dumps({k: out[k] for k in ("production", "loss")}, ensure_ascii=False, indent=1))
