"""KB-20260930-T4 검증. 저장소 루트에서 `python docs/.../verify.py` 로 돌린다.

단계 A(events/artifacts)와 단계 B(cards)를 모두 본다. cards.json이 아직 없으면
단계 A만 검사하고 넘어간다.

검사 항목은 `t4-handover-cards-assignment-20260930.md` 의 완료 기준을 그대로 옮긴 것이다.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))

from shiftlink.agent.schemas import Artifact, Event, KnowledgeCard  # noqa: E402

# 인계 메모 5요소. 페르소나마다 머리말 표현이 달라 동의어를 함께 본다.
ELEMENT_MARKERS = {
    "current_state": ["[현재 상태]"],
    "prior_action": ["[앞 근무자 조치]", "[확인 완료]"],
    "failed_attempt": ["[시도했으나", "[안 된 것]"],
    "unresolved": ["[미해결]", "[미확인]"],
    "next_check": ["[다음 조 확인]"],
}

# true_cause 와 기록 텍스트가 이 길이 이상 연속으로 겹치면 원인 누수로 본다.
LEAK_NGRAM = 12

failures: list[str] = []
notes: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    if ok:
        print(f"  OK   {label}")
    else:
        print(f"  FAIL {label}" + (f" — {detail}" if detail else ""))
        failures.append(label)


def longest_common_substring(a: str, b: str) -> str:
    """겹치는 가장 긴 연속 문자열. 원인 문장이 통째로 옮겨졌는지 보는 용도라
    O(len(a)*len(b))로 충분하다(문서 한 건당 수천 자 규모).
    # ponytail: DP 없이 슬라이딩. 건수가 수만으로 늘면 suffix automaton으로 바꾼다."""
    best = ""
    for i in range(len(a)):
        # 이미 찾은 것보다 긴 후보만 본다.
        for j in range(i + len(best) + 1, len(a) + 1):
            if a[i:j] in b:
                best = a[i:j]
            else:
                break
    return best


def main() -> int:
    plan = json.loads((HERE / "plan.json").read_text(encoding="utf-8"))
    events_raw = json.loads((HERE / "events.json").read_text(encoding="utf-8"))
    artifacts_raw = json.loads((HERE / "artifacts.json").read_text(encoding="utf-8"))
    plan_by_id = {e["event_id"]: e for e in plan["events"]}

    print("== 스키마 ==")
    try:
        events = [Event.model_validate(x) for x in events_raw]
        check(True, f"Event {len(events)}건 스키마 통과")
    except Exception as exc:
        check(False, "Event 스키마", str(exc)[:300])
        return 1
    try:
        artifacts = [Artifact.model_validate(x) for x in artifacts_raw]
        check(True, f"Artifact {len(artifacts)}건 스키마 통과")
    except Exception as exc:
        check(False, "Artifact 스키마", str(exc)[:300])
        return 1

    print("\n== plan.json 일치 ==")
    check(len(events) == len(plan["events"]), "사건 수", f"{len(events)} vs {len(plan['events'])}")
    mismatched = [
        e.event_id for e in events
        if e.split != plan_by_id[e.event_id]["split"]
        or e.equipment != plan_by_id[e.event_id]["equipment"]
        or e.scenario != plan_by_id[e.event_id]["scenario"]
        or e.cards_expected != plan_by_id[e.event_id]["cards_expected"]
    ]
    check(not mismatched, "split·equipment·scenario·cards_expected 배정 일치", str(mismatched[:5]))

    art_by_event: dict[str, list[Artifact]] = {}
    for a in artifacts:
        art_by_event.setdefault(a.event_id, []).append(a)
    bad_pairs = [
        eid for eid in plan_by_id
        if sorted(a.artifact_id for a in art_by_event.get(eid, [])) != sorted(plan_by_id[eid]["artifact_ids"])
    ]
    check(not bad_pairs, "artifact_id 배정 일치", str(bad_pairs[:5]))
    bad_persona = [a.artifact_id for a in artifacts if a.persona_id != plan_by_id[a.event_id]["persona_id"]]
    check(not bad_persona, "persona_id 배정 일치", str(bad_persona[:5]))
    bad_kinds = [
        eid for eid, al in art_by_event.items()
        if sorted(a.kind for a in al) != ["handover", "work_note"]
    ]
    check(not bad_kinds, "사건마다 work_note + handover 각 1건", str(bad_kinds[:5]))
    bad_split = [a.artifact_id for a in artifacts if a.split != plan_by_id[a.event_id]["split"]]
    check(not bad_split, "artifact split 일치", str(bad_split[:5]))

    print("\n== 인계 메모 5요소 ==")
    missing_required, unexpected_present = [], []
    for a in artifacts:
        if a.kind != "handover":
            continue
        omitted = plan_by_id[a.event_id]["omitted_handover_element"]
        for elem, markers in ELEMENT_MARKERS.items():
            present = any(m in a.text for m in markers)
            if elem == omitted:
                if present:
                    unexpected_present.append(f"{a.artifact_id}/{elem}")
            elif not present:
                missing_required.append(f"{a.artifact_id}/{elem}")
    check(not missing_required, "계획에 없는 요소 누락 없음", str(missing_required[:6]))
    check(not unexpected_present, "계획된 누락 사례가 실제로 빠져 있음", str(unexpected_present[:6]))
    planned = [e for e in plan["events"] if e["omitted_handover_element"]]
    notes.append(f"계획된 누락 사례 {len(planned)}건 / 전체 {len(plan['events'])}건 ({len(planned)/len(plan['events']):.0%})")

    print("\n== true_cause 누수 ==")
    leaks = []
    for e in events:
        for a in art_by_event.get(e.event_id, []):
            if e.true_cause in a.text:
                leaks.append(f"{a.artifact_id} 원인 문장 그대로")
                continue
            common = longest_common_substring(e.true_cause, a.text)
            if len(common) >= LEAK_NGRAM:
                leaks.append(f"{a.artifact_id} {len(common)}자 겹침: {common!r}")
    check(not leaks, f"기록 텍스트에 true_cause 누수 없음(연속 {LEAK_NGRAM}자 기준)", "; ".join(leaks[:4]))

    print("\n== measurements 신호명 ==")
    ref = json.loads((ROOT / "docs/data/reference/00_plant_and_relations.json").read_text(encoding="utf-8"))
    known = {m["signal"] for eq in ref["equipment"] for m in eq.get("measurement_points", [])}
    known.add("gr_oil_leak")  # scenarios/priority.expand()가 drive 설비에 추가하는 신호
    unknown = sorted({k for e in events for k in e.measurements if k not in known})
    check(not unknown, "measurements 키가 전부 MES 신호명", str(unknown))

    print("\n== ID 충돌 ==")
    ours_ev = {e.event_id for e in events}
    ours_ar = {a.artifact_id for a in artifacts}
    clashes = []
    for path in ROOT.joinpath("docs").rglob("*.json"):
        if HERE in path.parents or path == HERE or "graphify-out" in str(path):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in data if isinstance(data, list) else []:
            if not isinstance(item, dict):
                continue
            if item.get("event_id") in ours_ev and "timeline" in item:
                clashes.append(f'{path.name}:{item["event_id"]}')
            if item.get("artifact_id") in ours_ar:
                clashes.append(f'{path.name}:{item["artifact_id"]}')
    check(not clashes, "기존 데이터와 EV/AR ID 충돌 없음", str(clashes[:5]))

    cards_path = HERE / "cards.json"
    if not cards_path.exists():
        print("\n(cards.json 없음 — 단계 B 검증 생략)")
    else:
        print("\n== 단계 B: 카드 ==")
        cards_raw = json.loads(cards_path.read_text(encoding="utf-8"))
        try:
            cards = [KnowledgeCard.model_validate(c) for c in cards_raw]
            check(True, f"KnowledgeCard {len(cards)}장 스키마 통과")
        except Exception as exc:
            check(False, "KnowledgeCard 스키마", str(exc)[:300])
            return 1

        kb_ids = {e.event_id for e in events if e.split == "kb"}
        dev_ids = {e.event_id for e in events if e.split == "dev"}
        bad_support, thin, dev_cited = [], [], []
        for c in cards:
            ge = c.generalization_evidence
            sup = list(ge.supporting_event_ids) if ge else []
            if len(sup) < 2:
                thin.append(c.card_id)
            for eid in sup + (list(ge.contradicting_event_ids) if ge else []):
                if eid in dev_ids:
                    dev_cited.append(f"{c.card_id}/{eid}")
                elif eid not in kb_ids:
                    bad_support.append(f"{c.card_id}/{eid}")
            for eid in c.provenance.event_ids:
                if eid in dev_ids:
                    dev_cited.append(f"{c.card_id}/provenance/{eid}")
        check(not dev_cited, "평가용 사건(EV-0321~0330) 인용 0건", str(dev_cited[:5]))
        check(not bad_support, "근거 사건이 전부 이 배치의 kb 사건", str(bad_support[:5]))
        check(not thin, "카드마다 근거 사건 2건 이상", str(thin[:5]))
        check(all(c.tacit_type == "T4" for c in cards), "전부 T4")
        check(all(c.type_payload and c.type_payload.handover_method for c in cards), "handover_method 존재")
        # 검수 전에는 draft/L0, 검수 통과 후에는 accepted/L1이다. 둘 중 하나여야 하고
        # 섞여 있으면 review.md 판정과 cards.json이 어긋난 상태다.
        # (accepted면 L1이라는 규칙 자체는 KnowledgeCard validator가 이미 강제한다.)
        allowed = {("draft", "L0"), ("accepted", "L1")}
        bad_state = [f"{c.card_id}:{c.status}/{c.grade}" for c in cards if (c.status, c.grade) not in allowed]
        check(not bad_state, "status/grade 조합이 draft·L0 또는 accepted·L1", str(bad_state[:5]))
        states = {(c.status, c.grade) for c in cards}
        check(len(states) == 1, "배치 안에서 status/grade가 섞이지 않음", str(sorted(states)))
        not_kb = [c.card_id for c in cards if c.split != "kb" or c.confidence != 0.0]
        check(not not_kb, "split=kb·confidence=0.0", str(not_kb[:5]))
        notes.append(f"카드 상태: {sorted(states)[0][0]}/{sorted(states)[0][1]}")
        dup = [c.card_id for c in cards if [x.card_id for x in cards].count(c.card_id) > 1]
        check(not dup, "card_id 중복 없음", str(set(dup)))

        ours_k = {c.card_id for c in cards}
        card_clashes = []
        for path in ROOT.joinpath("docs").rglob("*.json"):
            if HERE in path.parents or path.parent == HERE or "graphify-out" in str(path):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for item in data if isinstance(data, list) else []:
                # 카드 본문만 본다. manifest의 id 목록은 발급 대장이라 충돌이 아니다.
                if isinstance(item, dict) and item.get("card_id") in ours_k and "tacit_type" in item:
                    card_clashes.append(f'{path.relative_to(ROOT)}:{item["card_id"]}')
        check(not card_clashes, "기존 카드와 K- ID 충돌 없음", str(card_clashes[:5]))
        notes.append(f"카드 {len(cards)}장 (목표 10~15장)")

    print("\n== 요약 ==")
    for n in notes:
        print(f"  - {n}")
    if failures:
        print(f"\n실패 {len(failures)}건: {failures}")
        return 1
    print("\n전부 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
