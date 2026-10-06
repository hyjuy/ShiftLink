"""Answer composition (10/6 design, docs/planning/답변_보정_설계_20261006.md).

The model keeps a short summary; code writes the facts. Post-processing only, so no extra model call or retry.
    L1  measurement fact lines from observation_facts
    L2  drop summary sentences that assert a direction/state about a reading nobody measured
    L3  put the cited card's own prohibition / stop sentences first
Layers are switched per pipeline (`compose_layers`) or by env SHIFTLINK_COMPOSE="L1,L2,L3". Default: none.
"""

import os
import re
from typing import Any, Iterable

from shiftlink.agent.response import (
    DIRECTION_FALLBACK_ANSWER, GUARD_FALLBACK_ANSWER, NO_MEASURE_ANSWER, NO_READING_NOTE, REFERENCE_NOTE,
    _CARD_ID, _sentences,
)
from shiftlink.rag.retrieval import _SIGNAL_LABELS

LAYERS = ("L1", "L2", "L3")
_STATES = ("low", "normal", "high")
_DIRECTION = re.compile("초과|넘|벗어|미만|높|낮")
# Criteria and hedges are not assertions about a reading ("38 미만이면 …", "그럴 수 있다").
_HEDGE = re.compile(r"이면|라면|하면|으면|경우|때|인지|거나|수 있|가능성|여부")
_PROHIBIT = re.compile(r"않는다|않는|않도록|말 것|말고|금지|하지 않|안 된다|해서는 안")
_SOURCE_MARK = re.compile(r"\.pdf|PDF p|§|인쇄 p|/US|CAUTION|DANGER|WARNING", re.I)
_HANGUL = re.compile("[가-힣]")
_NUMBER = re.compile(r"\d")


def layers_from_env() -> frozenset[str]:
    return frozenset(x for x in (p.strip().upper() for p in os.environ.get("SHIFTLINK_COMPOSE", "").split(",")) if x in LAYERS)


def _shown(value: Any) -> str:
    return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)


def _fact_line(fact: dict[str, Any]) -> str:
    """Same range wording as edge/ollama.observation_fact_block, as a sentence."""
    lo, hi, state = fact.get("normal_min"), fact.get("normal_max"), fact["state"]
    span = f"{_shown(lo)}–{_shown(hi)}" if lo is not None and hi is not None else (
        f"{_shown(lo)} 이상" if lo is not None else (f"{_shown(hi)} 이하" if hi is not None else ""))
    where = {"normal": "안", "low": "보다 낮음", "high": "보다 높음"}[state]
    unit = f" {fact['unit']}" if fact.get("unit") else ""
    gap = " " if state == "normal" and span else ""
    return f"현재 {fact['label']}({fact['signal']}) {_shown(fact.get('value'))}{unit} — 정상 범위 {span}{gap}{where}."


def _cited_cards(cited_ids: list[str], tool_results: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = {c.get("card_id"): c for key in ("ranked_cards", "cards") for c in tool_results.get(key) or []}
    return [by_id[i] for i in cited_ids if i in by_id]


def _is_reference(cited: list[dict[str, Any]]) -> bool:
    return any(c.get("condition_status") == "reference" for c in cited)


def l1_lines(cited: list[dict[str, Any]], tool_results: dict[str, Any]) -> list[str]:
    if _is_reference(cited):
        return [REFERENCE_NOTE]
    all_facts = [f for f in tool_results.get("observation_facts") or [] if isinstance(f, dict)]
    if not all_facts:
        return [NO_READING_NOTE]
    facts = [f for f in all_facts if f.get("state") in _STATES]
    wanted = {str(cond.get("signal", "")).removesuffix("_state") for c in cited for cond in c.get("conditions") or []}
    picked = [f for f in facts if f["signal"] in wanted] if wanted else [f for f in facts if f["state"] != "normal"]
    return [_fact_line(f) for f in picked[:3]]


def _first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0]


def l2_filter(answer: str, cited: list[dict[str, Any]], tool_results: dict[str, Any]) -> str:
    if _is_reference(cited):
        return answer  # a criterion question: the card's thresholds are the answer
    grounded = {f.get("label") for f in tool_results.get("observation_facts") or []
                if isinstance(f, dict) and f.get("state") in _STATES}
    labels = {label for _, label in _SIGNAL_LABELS}
    sentences = _sentences(answer)
    kept = []
    for sentence in sentences:
        text = _CARD_ID.sub(" ", sentence)
        if not _DIRECTION.search(text) or _HEDGE.search(text):
            kept.append(sentence)
            continue
        mentioned = {label for label in labels if label in text}
        if grounded:  # readings exist: only a mentioned signal nobody measured is unsupported
            unsupported = bool(mentioned - grounded)
        else:
            unsupported = bool(mentioned) or bool(_NUMBER.search(text))
        if not unsupported:
            kept.append(sentence)
    if len(kept) == len(sentences):
        return answer
    if kept:
        return " ".join(kept)
    base = _first_sentence(cited[0].get("know_how") or "") if cited else ""
    return f"{NO_MEASURE_ANSWER} 카드 기준: {base}" if base else NO_MEASURE_ANSWER


def _card_prohibitions(card: dict[str, Any]) -> list[str]:
    """The card's own words: prohibition-like preconditions/stop conditions in step order, then the first stop condition."""
    steps = (card.get("type_payload") or {}).get("steps") or []
    texts = [t for s in steps for key in ("preconditions", "stop_conditions") for t in s.get(key) or []]
    out = [_first_sentence(t) for t in texts if _PROHIBIT.search(t)]
    stops = [_first_sentence(t) for s in steps for t in s.get("stop_conditions") or []]
    out += [t for t in stops[:1] if t not in out]
    if not out and card.get("safety_flag"):
        basis = re.sub(r"^.*?(?:CAUTION|DANGER|WARNING)[^:]*:\s*", "", card.get("safety_basis") or "", flags=re.S)
        basis = re.sub(r'"[^"]*"', " ", basis)
        parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\(|\)", basis) if p.strip()]
        out = [p for p in parts if _HANGUL.search(p) and not _SOURCE_MARK.search(p)][:1]
    return out


def l3_line(answer: str, cited: list[dict[str, Any]], tool_results: dict[str, Any]) -> str:
    sentences, ids = [], []
    extra = [c for c in tool_results.get("ranked_cards") or []
             if c.get("safety_flag") and c.get("condition_status") == "verified" and c not in cited][:1]
    for card in cited + extra:
        for text in _card_prohibitions(card):
            if len(sentences) < 2 and text not in sentences and text not in answer:
                sentences.append(text)
                ids.append(card["card_id"])
    return f"먼저: {' '.join(sentences)} ({', '.join(dict.fromkeys(ids))})" if sentences else ""


def compose_answer(answer: str, cited_ids: list[str], tool_results: dict[str, Any], layers: Iterable[str],
                   errors: Iterable[str] = ()) -> str:
    layers = set(layers)
    cited = _cited_cards(cited_ids, tool_results)
    summary = l2_filter(answer, cited, tool_results) if "L2" in layers else answer
    if answer == GUARD_FALLBACK_ANSWER and any("답이" in e or "정상 범위인데" in e for e in errors):
        summary = DIRECTION_FALLBACK_ANSWER  # the stock sentence blames a missing number; this block was a direction error
    head = l1_lines(cited, tool_results) if "L1" in layers else []
    if "L3" in layers and (line := l3_line(summary, cited, tool_results)):
        head.append(line)
    return "\n".join([*head, summary])
