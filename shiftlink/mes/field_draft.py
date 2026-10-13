"""현장 해결 기록 → 지식카드 초안 (규칙 기반, LLM 없음).

초안은 status=draft, grade=L0 이고 검수 전까지 검색(kb_cards.json·질의 파이프라인)에 나가지 않는다.
상태 조건(`{signal}_state`)은 본문이 아니라 활성 구성의 정상 범위로 서버가 다시 계산한다.
같은 설비·같은 이상 조건·겹치는 조치의 기록은 새 초안을 만들지 않고 기존 초안의 근거로 붙어 빈칸을 채운다.
"""

from __future__ import annotations

import re
from datetime import datetime
from math import isfinite
from typing import Any

from pydantic import ValidationError

from shiftlink.agent.schemas import SCHEMA_VERSION, KnowledgeCard
from shiftlink.data.card_lint import lint_card

from .contracts import Configuration, EquipmentConfig

GENERATOR = "field-resolution-v1"
# naming_registry: 현장 초안 전용 K-#### 범위. kb 카드와 겹치지 않는다.
ID_RANGE = (7000, 7999)
RESULTS = ("resolved", "temporary", "failed")
RESULT_LABELS = {"resolved": "해결", "temporary": "임시조치", "failed": "효과 없음"}
PLACEHOLDER = "현장 기록에 결과 없음 — 검수 보완"
# 안전 표현은 판단하지 않고 검수 대상으로만 표시한다. 근거(safety_basis)는 만들지 않는다.
SAFETY_WORDS = ("재기동", "재가동", "재투입", "차단기", "개방", "커버", "충전", "바이패스", "분해", "전원 투입", "인터록", "잠금", "격리")
# 이보다 짧은 증상·조치·근거는 '기록 빈약'으로 표시한다(글자 수). 막지는 않는다.
# ponytail: 글자 수만 본다. 짧아도 정확한 기록("팬 정지")이 표시될 수 있다. 오표시가 잦으면 낱말 수·사전으로 바꾼다.
THIN_MIN = {"symptom": 8, "action": 4, "verification": 6}
# 같은 초안으로 묶는 조치 겹침 비율(두 글자 어간 + 한 글자 낱말, 작은 쪽 대비).
# 10/13 같은 상황 실측: 같은 원인을 다르게 적은 기록 0.43, 다른 원인 0.25 이하.
# ponytail: 낱말 겹침이라 표현이 더 갈리면 따로 쌓인다. 묶음이 자주 갈라지면 검수 화면에서 수동 병합을 둔다.
OVERLAP_MIN = 0.4


def _text(value: object, limit: int, name: str, *, required: bool = True) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if required and not text:
        raise ValueError(f"{name} must be a nonblank string")
    if len(text) > limit:
        raise ValueError(f"{name} is longer than {limit} chars")
    return text


def check_resolution(resolution: object) -> dict[str, Any]:
    """PDA 본문 검사. 잘못되면 ValueError(인계 저장 전에 거절한다).

    actions 항목은 문자열 또는 {action, result}. result는 그 조치 직후 본 결과(선택)다.
    """
    if not isinstance(resolution, dict):
        raise ValueError("resolution must be an object")
    result = resolution.get("result")
    if result not in RESULTS:
        raise ValueError("result must be resolved, temporary or failed")
    raw_actions = resolution.get("actions")
    if not isinstance(raw_actions, list) or len(raw_actions) > 20:
        raise ValueError("actions must be a list of up to 20 items")
    actions = []
    for item in raw_actions:
        if isinstance(item, str):
            item = {"action": item}
        if not isinstance(item, dict) or set(item) - {"action", "result"}:
            raise ValueError("each action must be a string or {action, result}")
        action = _text(item.get("action"), 500, "action", required=False)
        if action:
            actions.append({"action": action,
                            "result": _text(item.get("result"), 500, "action result", required=False)})
    if result != "failed" and not actions:
        raise ValueError("resolved or temporary needs at least one action")
    evidence = resolution.get("evidence")
    if evidence is not None and not isinstance(evidence, dict):
        raise ValueError("evidence must be an object or null")
    return {
        "question": _text(resolution.get("question"), 4000, "question", required=False),
        "symptom": _text(resolution.get("symptom"), 1000, "symptom"),
        "actions": actions,
        "result": result,
        "verification": _text(resolution.get("verification"), 1000, "verification",
                              required=result == "resolved"),
        "evidence": evidence,
    }


def _equipment(config: Configuration, equipment_id: object) -> EquipmentConfig:
    found = [e for e in config.equipment if e.active and e.equipment_id == equipment_id]
    if len(found) != 1:
        raise ValueError("equipment_id must name an active equipment in the configuration")
    return found[0]


def _states(eq: EquipmentConfig, evidence: dict[str, Any] | None) -> list[tuple[Any, str]]:
    """정상 범위 밖 신호만 (spec, high|low). 값과 범위는 서버 구성에서 읽는다."""
    specs = {spec.signal: spec for spec in eq.signals}
    if evidence and evidence.get("equipment_id") not in (None, eq.equipment_id):
        raise ValueError("evidence belongs to another equipment")
    found: dict[str, tuple[Any, str]] = {}
    for item in (evidence or {}).get("measurements") or []:
        if not isinstance(item, dict) or item.get("equipment_id") != eq.equipment_id:
            raise ValueError("evidence measurement belongs to another equipment")
        spec = specs.get(item.get("signal"))
        if spec is None:
            raise ValueError(f"unknown signal in evidence: {item.get('signal')!r}")
        value = item.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
            raise ValueError(f"evidence value must be a finite number: {spec.signal}")
        if item.get("quality") != "good":
            continue
        # 정지 중이라 0인 유량·전류는 증상이 아니라 멈춘 결과다(고장 시나리오는 라인을 세운다).
        # ponytail: 운전 중 실제로 0이 된 경우도 빠진다. 설비 운전 상태를 근거에 실으면 그것으로 가른다.
        if spec.zero_when_stopped and value == 0:
            continue
        if spec.normal_min is not None and value < spec.normal_min:
            found.setdefault(spec.signal, (spec, "low"))
        elif spec.normal_max is not None and value > spec.normal_max:
            found.setdefault(spec.signal, (spec, "high"))
    return list(found.values())


def prepare(raw: object, config: Configuration, equipment_id: object) -> dict[str, Any]:
    """검사를 마친 해결 기록 + 설비 + 서버가 계산한 이상 상태. 인계 저장 전에 부른다."""
    resolution = check_resolution(raw)
    eq = _equipment(config, equipment_id)
    return {"resolution": resolution, "eq": eq, "states": _states(eq, resolution["evidence"])}


def check_with_mes(prepared: dict[str, Any], measurements: list[dict[str, Any]],
                   active_alarms: list[str], checked_at: str) -> dict[str, Any]:
    """저장 시점의 MES로 '해결'을 확인한다. 질의 때 벗어났던 신호가 모두 정상 범위로 돌아오고 그 설비 경보가 없으면 recovered.

    작업자 표기(result)와 별개로 남긴다. 값은 서버 스냅샷에서 읽는다(PDA가 보낸 값이 아니다).
    """
    eq = prepared["eq"]
    still = {spec.signal for spec, _ in _states(eq, {"equipment_id": eq.equipment_id, "measurements": [
        m for m in measurements if m.get("equipment_id") == eq.equipment_id]})}
    before = {m.get("signal"): m.get("value") for m in (prepared["resolution"]["evidence"] or {}).get("measurements") or []}
    now = {m.get("signal"): m.get("value") for m in measurements if m.get("equipment_id") == eq.equipment_id}
    signals = [{"signal": spec.signal, "name": spec.name, "before": before.get(spec.signal), "now": now.get(spec.signal),
                "back_to_normal": spec.signal not in still} for spec, _ in prepared["states"]]
    check = {"checked_at": checked_at, "signals": signals, "active_alarms": sorted(active_alarms),
             "recovered": bool(signals) and all(s["back_to_normal"] for s in signals) and not active_alarms}
    prepared["mes_check"] = check
    return check


def _mes_line(check: dict[str, Any] | None) -> str:
    if not check:
        return "MES 확인 없음"
    values = ", ".join(f"{s['name']} {s['before']}→{s['now']}{'' if s['back_to_normal'] else '(아직 이상)'}" for s in check["signals"])
    alarms = "경보 " + ", ".join(check["active_alarms"]) if check["active_alarms"] else "경보 없음"
    return f"MES 확인: {'정상 복귀' if check['recovered'] else '아직 이상'} ({values or '이상 신호 없음'}; {alarms})"


def _record(handover_id: str, relation: str, prepared: dict[str, Any]) -> dict[str, Any]:
    check = prepared.get("mes_check")
    return {"handover_id": handover_id, "relation": relation, "result": prepared["resolution"]["result"],
            "mes_recovered": bool(check and check["recovered"])}


def _conditions(states: list[tuple[Any, str]]) -> list[dict[str, Any]]:
    return [{"signal": f"{spec.signal}_state", "op": "==", "value": state, "unit": None} for spec, state in states]


# 어느 조치에나 붙는 말. 이것만 겹쳐서 다른 조치로 묶이거나 다른 단계 결과가 들어가지 않게 뺀다.
# 재가동·완료는 MES 복귀 절차라 거의 모든 기록에 들어간다. 후·전 같은 한 글자 말도 뺀다('팬'·'핀'은 남긴다).
GENERIC_STEMS = {"확인", "재확", "점검", "상태", "조치", "작업", "실시", "재가", "완료", "후", "전", "및", "등"}


def _stems(text: str) -> set[str]:
    tokens = re.findall(r"\w+", text)
    return ({token[:2] for token in tokens if len(token) >= 2} | {token for token in tokens if len(token) == 1}) - GENERIC_STEMS


def _overlap(a: str, b: str) -> float:
    left, right = _stems(a), _stems(b)
    return len(left & right) / min(len(left), len(right)) if left and right else 0.0


def _overlaps(a: str, b: str) -> bool:
    return _overlap(a, b) >= OVERLAP_MIN


def _step_results(resolution: dict[str, Any]) -> list[str]:
    """조치별 결과: 직접 적은 결과, 없으면 마지막 조치에만 해결 근거."""
    actions, verification = resolution["actions"], resolution["verification"]
    return [item["result"] or (verification if i == len(actions) - 1 else "") for i, item in enumerate(actions)]


def _thin(resolution: dict[str, Any]) -> list[str]:
    reasons = []
    if len(resolution["symptom"]) < THIN_MIN["symptom"]:
        reasons.append("증상이 짧음")
    if resolution["actions"] and all(len(a["action"]) < THIN_MIN["action"] for a in resolution["actions"]):
        reasons.append("조치가 짧음")
    if resolution["result"] == "resolved" and len(resolution["verification"]) < THIN_MIN["verification"]:
        reasons.append("해결 근거가 짧음")
    return reasons


def _record_line(handover_id: str, prepared: dict[str, Any]) -> str:
    resolution = prepared["resolution"]
    verification = resolution["verification"]
    return (f"현장 작업자 기록({handover_id}): 결과 {RESULT_LABELS[resolution['result']]}. "
            + (f"해결로 본 근거: {verification}" if verification else "해결 근거 기록 없음 — 검수 보완")
            + ". " + _mes_line(prepared.get("mes_check")))


def completeness(card: dict[str, Any], flags: dict[str, Any]) -> dict[str, Any]:
    """승격 전에 채워야 할 빈칸. 기록이 쌓이면 줄어드는 것(missing)과 운영자만 채우는 것(operator)을 나눈다.

    ready는 '승격 권장' 표시일 뿐이다. 승격은 언제나 운영자가 확인한다(자동 승격 없음).
    """
    records = flags.get("records", [])
    resolved = [r for r in records if r["relation"] != "contradicting" and r["result"] == "resolved"
                and r.get("mes_recovered")]
    mismatch = [r["handover_id"] for r in records if r["result"] == "resolved" and not r.get("mes_recovered")]
    contradicting = [r for r in records if r["relation"] == "contradicting"]
    missing = []
    if not card["conditions"]:
        missing.append("MES 이상 조건")
    missing += [f"단계 결과 {step_id}" for step_id in flags.get("placeholder_steps", [])]
    if not resolved:
        missing.append("MES로 확인된 해결 기록")
    if flags.get("thin_record"):
        missing.append("기록 빈약: " + ", ".join(flags["thin_record"]))
    operator = ["부품 확인", "시나리오 확인"]
    if len(card["conditions"]) > 2:
        operator.append("조건 확인(우연히 함께 벗어난 신호 정리)")
    if flags.get("needs_safety_review"):
        operator.append("안전 근거")
    if mismatch:
        operator.append("해결 표기와 MES 불일치 " + ", ".join(mismatch))
    return {"missing": missing, "operator": operator, "resolved_records": len(resolved),
            "contradicting_records": len(contradicting),
            "ready": not missing and len(resolved) >= 2 and not contradicting}


def _finish(card: dict[str, Any], flags: dict[str, Any]) -> dict[str, Any]:
    """스키마 검증·lint·빈칸 현황을 다시 계산한다(만들 때와 합칠 때 공통)."""
    steps = card["type_payload"]["steps"]
    flags["placeholder_steps"] = [s["step_id"] for s in steps if s["expected_result"] == PLACEHOLDER]
    text = " ".join([card["symptom"], card["know_how"], card["rationale"]])
    flags.pop("needs_safety_review", None)
    if hits := [word for word in SAFETY_WORDS if word in text]:
        flags["needs_safety_review"] = hits
    flags.pop("validation_errors", None)
    try:
        KnowledgeCard.model_validate(card)
    except ValidationError as error:
        flags["validation_errors"] = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors()]
        status = "invalid"
    else:
        status = "pending_review"
    flags["lint"] = lint_card(card, known_fields=set(KnowledgeCard.model_fields))
    flags["completeness"] = completeness(card, flags)
    return {"status": status, "card": card, "review_flags": flags}


def draft_from(prepared: dict[str, Any], handover_id: str, card_id: str, now: datetime) -> dict[str, Any]:
    """해결 기록 1건 → 새 초안. 시도 실패(failed)는 초안을 만들지 않고 status=attempt_only."""
    resolution, eq, states = prepared["resolution"], prepared["eq"], prepared["states"]
    if resolution["result"] == "failed":
        return {"status": "attempt_only"}
    actions = [a["action"] for a in resolution["actions"]]
    head = eq.code
    if states:
        spec, state = states[0]
        head += f" {spec.name} {'높음' if state == 'high' else '낮음'}" + (f" 외 {len(states) - 1}" if len(states) > 1 else "")
    temporary = resolution["result"] == "temporary"
    steps = [{"step_id": f"ST-{i:02d}", "order": i, "action": action, "expected_result": result or PLACEHOLDER}
             for i, (action, result) in enumerate(zip(actions, _step_results(resolution)), start=1)]
    card: dict[str, Any] = {
        "card_id": card_id, "version": "1", "grade": "L0", "status": "draft",
        "tacit_type": "T3", "equipment": eq.code.split("-")[0], "component": eq.name,
        "mes_equipment_id": eq.equipment_id, "scenario": "S1",
        "title": ("[임시조치] " if temporary else "") + f"{head} — {actions[0][:60]}",
        "symptom": resolution["symptom"], "know_how": "\n".join(actions),
        "rationale": _record_line(handover_id, prepared),
        "conditions": _conditions(states),
        "safety_flag": False, "confidence": 0.0,
        "provenance": {"seed_ids": [], "persona_id": "field-resolution", "event_ids": [],
                       "generator": GENERATOR, "generated_at": now.isoformat(),
                       "sources": [{"source_id": handover_id, "locator": "handover"}],
                       "extraction_method": "rule", "schema_version": SCHEMA_VERSION},
        "split": "dev",
        "type_payload": {"steps": steps},
    }
    flags: dict[str, Any] = {
        "records": [_record(handover_id, "origin", prepared)],
        "scenario_default": "S1 고정. 현장 기록에서 시나리오를 알 수 없어 검수에서 정한다."}
    if temporary:
        flags["temporary"] = True
    if thin := _thin(resolution):
        flags["thin_record"] = thin
    if not states:
        flags["no_out_of_range_signal"] = True
    return _finish(card, flags)


def build_draft(handover_id: str, raw: object, config: Configuration, equipment_id: object,
                card_id: str, now: datetime) -> dict[str, Any]:
    """검사부터 새 초안까지 한 번에(기록 1건)."""
    return draft_from(prepare(raw, config, equipment_id), handover_id, card_id, now)


def _keys(conditions: list[dict[str, Any]]) -> set[tuple[str, Any]]:
    return {(c["signal"], c["value"]) for c in conditions}


def match_score(card: dict[str, Any], prepared: dict[str, Any]) -> float:
    """같은 설비 + 겹치는 이상 조건일 때 조치 겹침 비율. OVERLAP_MIN 이상이면 한 초안으로 묶는다(0이면 묶지 않음).

    실제 스냅샷은 함께 벗어난 신호가 여럿이라 조건이 정확히 같기를 요구하지 않는다(하나 이상 공통).
    조건만 같고 조치가 다르면(예: 팬 정지 vs 핀 막힘) 다른 원인 후보라서 따로 둔다.
    """
    if card.get("mes_equipment_id") != prepared["eq"].equipment_id or not prepared["states"]:
        return 0.0
    if not _keys(card["conditions"]) & _keys(_conditions(prepared["states"])):
        return 0.0
    # 조치 전체로 비교한다. 단계 하나씩 비교하면 '온도 재확인' 같은 공통 단계 때문에 다른 원인이 묶인다.
    score = _overlap(" ".join(s["action"] for s in card["type_payload"]["steps"]),
                     " ".join(a["action"] for a in prepared["resolution"]["actions"]))
    return score if score >= OVERLAP_MIN else 0.0


def matches(card: dict[str, Any], prepared: dict[str, Any]) -> bool:
    return match_score(card, prepared) > 0


def merge(row: dict[str, Any], prepared: dict[str, Any], handover_id: str) -> tuple[dict[str, Any], str]:
    """기존 초안에 기록 1건을 근거로 붙인다. 효과 없음이면 반대 근거, 아니면 지지 근거.

    MES로 정상 복귀가 확인된 지지 근거만 빈 단계 결과를 채우고 조건을 좁힌다. 확인 안 된 기록은 붙기만 한다.
    카드 문장(증상·조치)은 처음 기록 그대로 둔다.
    """
    card, flags = row["card"], dict(row["review_flags"])
    resolution = prepared["resolution"]
    relation = "contradicting" if resolution["result"] == "failed" else "supporting"
    verified = bool(prepared.get("mes_check") and prepared["mes_check"]["recovered"])
    if relation == "supporting" and verified:
        # 해결 기록마다 함께 벗어났던 조건만 남긴다. 우연히 같이 벗어난 신호는 기록이 쌓이며 빠진다.
        common = _keys(_conditions(prepared["states"]))
        card["conditions"] = [c for c in card["conditions"] if (c["signal"], c["value"]) in common]
        # 빈 단계마다 가장 많이 겹치는 새 조치의 결과를 쓴다. 새 조치 하나는 한 단계에만 쓴다('확인' 같은 공통어 오매칭 방지).
        candidates = [(item["action"], result) for item, result in zip(resolution["actions"], _step_results(resolution)) if result]
        for step in card["type_payload"]["steps"]:
            if step["expected_result"] != PLACEHOLDER or not candidates:
                continue
            best = max(candidates, key=lambda c: _overlap(step["action"], c[0]))
            if _overlaps(step["action"], best[0]):
                step["expected_result"] = best[1]
                candidates.remove(best)
        if resolution["result"] == "resolved" and flags.pop("temporary", None):
            card["title"] = card["title"].removeprefix("[임시조치] ")
    card["rationale"] += "\n" + ("반대 근거 — " if relation == "contradicting" else "") + _record_line(handover_id, prepared)
    card["provenance"]["sources"].append({"source_id": handover_id, "locator": "handover"})
    flags["records"] = [*flags.get("records", []), _record(handover_id, relation, prepared)]
    return _finish(card, flags), relation
