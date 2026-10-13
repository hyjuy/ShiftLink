"""현장 해결 기록 → 지식카드 초안 (규칙 기반, LLM 없음).

초안은 status=draft, grade=L0 이고 검수 전까지 검색(kb_cards.json·질의 파이프라인)에 나가지 않는다.
상태 조건(`{signal}_state`)은 본문이 아니라 활성 구성의 정상 범위로 서버가 다시 계산한다.
"""

from __future__ import annotations

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


def _text(value: object, limit: int, name: str, *, required: bool = True) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if required and not text:
        raise ValueError(f"{name} must be a nonblank string")
    if len(text) > limit:
        raise ValueError(f"{name} is longer than {limit} chars")
    return text


def check_resolution(resolution: object) -> dict[str, Any]:
    """PDA 본문 검사. 잘못되면 ValueError(인계 저장 전에 거절한다)."""
    if not isinstance(resolution, dict):
        raise ValueError("resolution must be an object")
    result = resolution.get("result")
    if result not in RESULTS:
        raise ValueError("result must be resolved, temporary or failed")
    actions = resolution.get("actions")
    if not isinstance(actions, list) or len(actions) > 20 or not all(isinstance(a, str) for a in actions):
        raise ValueError("actions must be a list of up to 20 strings")
    actions = [_text(a, 500, "action", required=False) for a in actions]
    actions = [a for a in actions if a]
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
        if spec.normal_min is not None and value < spec.normal_min:
            found.setdefault(spec.signal, (spec, "low"))
        elif spec.normal_max is not None and value > spec.normal_max:
            found.setdefault(spec.signal, (spec, "high"))
    return list(found.values())


def build_draft(handover_id: str, raw: object, config: Configuration, equipment_id: object,
                card_id: str, now: datetime) -> dict[str, Any]:
    """해결 기록 1건 → 저장할 초안. 시도 실패(failed)는 초안을 만들지 않고 status=attempt_only."""
    resolution = check_resolution(raw)
    if resolution["result"] == "failed":
        return {"status": "attempt_only"}
    eq = _equipment(config, equipment_id)
    states = _states(eq, resolution["evidence"])
    actions, symptom = resolution["actions"], resolution["symptom"]
    verification = resolution["verification"]
    # 조치 없는 해결은 검사에서 막는다. 그래서 초안은 항상 T3(단계형)다.

    if states:
        spec, state = states[0]
        direction = {"high": "높음", "low": "낮음"}[state]
        head = f"{eq.code} {spec.name} {direction}"
    else:
        head = eq.code
    title = f"{head} — {(actions[0] if actions else symptom)[:60]}"
    know_how = "\n".join(actions)
    card: dict[str, Any] = {
        "card_id": card_id, "version": "1", "grade": "L0", "status": "draft",
        "tacit_type": "T3", "equipment": eq.code.split("-")[0], "component": eq.name,
        "mes_equipment_id": eq.equipment_id, "scenario": "S1",
        "title": title, "symptom": symptom, "know_how": know_how,
        "rationale": f"현장 작업자 기록({handover_id}): 결과 {RESULT_LABELS[resolution['result']]}. "
                     + (f"해결로 본 근거: {verification}" if verification else "해결 근거 기록 없음 — 검수 보완"),
        "conditions": [{"signal": f"{spec.signal}_state", "op": "==", "value": state, "unit": None}
                       for spec, state in states],
        "safety_flag": False, "confidence": 0.0,
        "provenance": {"seed_ids": [], "persona_id": "field-resolution", "event_ids": [],
                       "generator": GENERATOR, "generated_at": now.isoformat(),
                       "sources": [{"source_id": handover_id, "locator": "handover"}],
                       "extraction_method": "rule", "schema_version": SCHEMA_VERSION},
        "split": "dev",
    }
    placeholder_steps = []
    steps = []
    for order, action in enumerate(actions, start=1):
        expected = verification if order == len(actions) and verification else PLACEHOLDER
        if expected == PLACEHOLDER:
            placeholder_steps.append(f"ST-{order:02d}")
        steps.append({"step_id": f"ST-{order:02d}", "order": order, "action": action, "expected_result": expected})
    card["type_payload"] = {"steps": steps}

    text = " ".join([symptom, know_how, verification])
    flags: dict[str, Any] = {"placeholder_steps": placeholder_steps}
    if hits := [word for word in SAFETY_WORDS if word in text]:
        flags["needs_safety_review"] = hits
    if not states:
        flags["no_out_of_range_signal"] = True
    flags["scenario_default"] = "S1 고정. 현장 기록에서 시나리오를 알 수 없어 검수에서 정한다."

    try:
        KnowledgeCard.model_validate(card)
    except ValidationError as error:
        flags["validation_errors"] = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors()]
        status = "invalid"
    else:
        status = "pending_review"
    flags["lint"] = lint_card(card, known_fields=set(KnowledgeCard.model_fields))
    return {"status": status, "card": card, "review_flags": flags}
