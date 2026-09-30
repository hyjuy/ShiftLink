"""cards.json에서 review.md(검수표)와 README.md(추적표)를 만든다.

카드를 고치면 다시 돌려 두 문서를 맞춘다. 사람이 review.md 판정 칸에 적은 값은
기존 파일에서 읽어 그대로 옮긴다 — 재생성이 검수 결과를 지우면 안 된다.
"""

import json
import re
from pathlib import Path

HERE = Path(__file__).parent
BATCH = "KB-20260930-T4"
SEED = 20260930


def load_existing_verdicts(path: Path) -> dict[str, str]:
    """기존 review.md에서 카드별 판정 값을 걷어 온다."""
    if not path.exists():
        return {}
    verdicts, current = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^## (K-\d{4}) ", line)
        if m:
            current = m.group(1)
        elif current and line.startswith("- **판정**:"):
            verdicts[current] = line.split(":", 1)[1].strip()
            current = None
    return verdicts


def slot_of(card: dict) -> str:
    """카드에 기록된 슬롯을 그대로 쓴다.

    목록 인덱스로 매기면 검수에서 카드가 빠졌을 때 남은 카드의 슬롯이 밀려
    provenance.seed_ids와 어긋난다(K-1111 흡수 때 실제로 발생). 슬롯은 생성 시점의
    식별자이므로 재배치하지 않는다.
    """
    for s in card["provenance"]["seed_ids"]:
        if s.startswith("slot:"):
            return s.split(":", 1)[1]
    return "-"


def event_ref(cards_sources: list[dict]) -> str:
    """근거 사건만 골라 'EV-0301(AR-0302)' 형태로 줄인다."""
    out = []
    for s in cards_sources:
        sid = s["source_id"]
        if not sid.startswith("EV-"):
            continue
        loc = s.get("locator", "")
        m = re.search(r"AR-\d{4}", loc)
        out.append(f"{sid}({m.group(0)})" if m else sid)
    return ", ".join(out)


def doc_ref(cards_sources: list[dict]) -> str:
    """사건이 아닌 문헌 출처."""
    out = []
    for s in cards_sources:
        if s["source_id"].startswith("EV-"):
            continue
        loc = s.get("locator", "")
        out.append(f'{s["source_id"]} {loc}'.strip())
    return "; ".join(out)


def build_review(cards: list[dict], verdicts: dict[str, str]) -> str:
    lines = [
        f"# {BATCH} 검수표",
        "",
        "판정 칸에 `accepted` / `rejected` / `수정` 중 하나를 적는다. accepted면 grade를 L1로 올린다.",
        "",
        "생성자 본인 검수 금지. 검수는 최재영이 맡는다.",
        "",
    ]
    for c in cards:
        slot = slot_of(c)
        safety_mark = " · ⚠ 안전" if c.get("safety_flag") else ""
        lines.append(f'## {c["card_id"]} · {c["equipment"]} · {c["tacit_type"]}{safety_mark} — {c["title"]}')
        lines.append("")
        lines.append(f'- **부품**: {c["component"]}')
        lines.append(f'- **노하우**: {c["know_how"]}')
        lines.append(f'- **근거 설명**: {c["rationale"]}')

        hm = c["type_payload"]["handover_method"]
        lines.append("- **인계 방법**:")
        for ctx in hm["required_context"]:
            lines.append(f"  - 필요한 맥락: {ctx}")
        lines.append(f'  - 받는 사람: {hm["recipient_role"]}')
        lines.append(f'  - 시점: {hm["timing"]}')
        lines.append(f'  - 경로: {hm["channel"]}')
        lines.append(f'  - 확인 방법: {hm["acknowledgement"]}')

        if c.get("safety_basis"):
            lines.append(f'- **안전 근거**: {c["safety_basis"]}')

        ge = c["generalization_evidence"]
        lines.append(f'- **근거 사건**: {event_ref(c["provenance"]["sources"])}')
        lines.append(f'- **일반화 범위**: {ge["generalization_scope"]}')
        lines.append(f'- **근거 강도**: {ge["confidence_basis"]}')
        docs = doc_ref(c["provenance"]["sources"])
        if docs:
            lines.append(f"- **문헌 출처**: {docs}")

        note = f'| {slot} | {c["card_id"]} | T4 | {c["title"]} | {len(ge["supporting_event_ids"])}건 | {c["component"]} | ok |'
        lines.append(f"- **작성 노트**: {note}")
        lines.append(f'- **판정**: {verdicts.get(c["card_id"], "")}'.rstrip())
        lines.append("")
    return "\n".join(lines) + "\n"


def build_readme(cards: list[dict], index: dict, plan: dict) -> str:
    stage_b = index["prompts"]["stage-b-cards"]
    stage_a = index["prompts"]["stage-a-records"]
    kb = [e for e in plan["events"] if e["split"] == "kb"]
    dev = [e for e in plan["events"] if e["split"] == "dev"]
    omitted = [e for e in plan["events"] if e["omitted_handover_element"]]

    lines = [
        f"# T4 인계 카드 배치 {BATCH}",
        "",
        f"근무일지·인계 메모를 먼저 합성하고, 그 기록에서 반복된 인계 요령만 뽑아 T4 카드로 만든 배치다. 카드 {len(cards)}장.",
        "",
        f"- 시드: `{SEED}` — [`plan.py`](plan.py)가 사건 30건의 설비·시나리오·페르소나·누락 항목을 정한다. 같은 시드면 [`plan.json`](plan.json)이 바이트 단위로 같다.",
        f'- 생성: {stage_b["model"]}, {stage_b["run_at"][:10]}.',
        "- 지시문: [`prompts/stage-a-records.md`](prompts/stage-a-records.md)(기록 합성), [`prompts/stage-b-cards.md`](prompts/stage-b-cards.md)(카드 추출). 해시는 [`prompts/index.json`](prompts/index.json).",
        f'- 원 지시서: [`{index["source_instruction"]["path"]}`](../../../../{index["source_instruction"]["path"].replace("docs/", "")}) `sha256:{index["source_instruction"]["sha256"][:12]}`',
        "- **재현성 한계**: 시드는 사건 배정만 고정한다. 사건 서술과 카드 문장은 같은 지시문으로 다시 돌려도 똑같이 나오지 않는다. 그래서 지시문 원문과 해시, 카드별 근거 사건을 남긴다.",
        "- 모든 카드는 `status=draft`, `grade=L0`, `confidence=0.0`, `split=kb`이다. accepted 여부는 사람이 검수해 정한다([`review.md`](review.md)).",
        "",
        "## 두 층 구분",
        "",
        "| 층 | 파일 | 내용 |",
        "|---|---|---|",
        f'| 기록(사실) | [`events.json`](events.json), [`artifacts.json`](artifacts.json) | 사건 {len(plan["events"])}건과 사건별 근무일지·인계 메모 {len(plan["events"]) * 2}건. 교대마다 1건씩 일어난 일 |',
        f"| 카드(요령) | [`cards.json`](cards.json) | 여러 기록에서 2건 이상 반복된 인계 요령 {len(cards)}장. 다음에도 재사용할 수 있는 형태 |",
        "",
        "## 데이터 분할",
        "",
        "| split | 사건 | 용도 |",
        "|---|---|---|",
        f'| `kb` | {kb[0]["event_id"]}~{kb[-1]["event_id"]} ({len(kb)}건) | T4 카드의 근거. 유현준 MES 연결 시험 입력 |',
        f'| `dev` | {dev[0]["event_id"]}~{dev[-1]["event_id"]} ({len(dev)}건) | 평가셋 재료. **카드 근거로 쓰지 않는다** |',
        "",
        f"인계 메모 5요소(현재 상태·앞 근무자 조치·실패한 시도·미해결·다음 조 확인) 중 하나를 일부러 뺀 누락 사례가 {len(omitted)}건 있다({len(omitted) / len(plan['events']):.0%}). 어느 사건에서 무엇을 뺐는지는 `plan.json`의 `omitted_handover_element`에 있다.",
        "",
        "## 카드 → 근거 사건 → 지시문 추적표",
        "",
        f'각 카드의 `provenance.prompt_version` = `{stage_b["path"]}@sha256:{stage_b["sha256"][:12]}…`, `provenance.seed_ids` = `["{BATCH}:seed={SEED}", "slot:<Sxx>"]`.',
        "",
        "| 카드 | 슬롯 | 설비 | 안전 | 제목 | 근거 사건 | 근거 건수 |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in cards:
        ge = c["generalization_evidence"]
        safety = "⚠" if c.get("safety_flag") else ""
        sup = ", ".join(ge["supporting_event_ids"])
        lines.append(
            f'| {c["card_id"]} | {slot_of(c)} | {c["equipment"]} | {safety} | {c["title"]} | {sup} | {len(ge["supporting_event_ids"])} |'
        )

    lines += [
        "",
        "## 해시",
        "",
        "| 파일 | sha256 |",
        "|---|---|",
        f'| [`prompts/stage-a-records.md`](prompts/stage-a-records.md) | `{stage_a["sha256"]}` |',
        f'| [`prompts/stage-b-cards.md`](prompts/stage-b-cards.md) | `{stage_b["sha256"]}` |',
        f'| 원 지시서 `{index["source_instruction"]["path"]}` | `{index["source_instruction"]["sha256"]}` |',
        f'| 분장 문서 `{index["assignment"]["path"]}` | `{index["assignment"]["sha256"]}` |',
        "",
        "## 검증",
        "",
        "```bash",
        "uv run --with pydantic==2.9.2 python docs/data/knowledge_cards/kb/20260930-T4/verify.py",
        "# 또는 .venv가 있으면: .venv/Scripts/python.exe docs/data/knowledge_cards/kb/20260930-T4/verify.py",
        "```",
        "",
        "[`verify.py`](verify.py)가 보는 것: 스키마 통과, `plan.json` 배정 일치, 인계 메모 5요소(계획된 누락 포함), `true_cause` 누수, `measurements` 키가 MES 신호명인지, 기존 ID 충돌, 카드의 평가용 사건 인용 0건, 근거 사건 2건 이상.",
        "",
        "## 안전 근거에 대하여",
        "",
        "안전 인계 카드(K-1103·K-1110)는 OSHA 29 CFR 1910.147(f)(4)를 절차 구조 참고로 인용한다. 국내 법적 의무의 대체물이 아니다.",
        "",
        "KOSHA GUIDE M-101-2012는 이번 배치의 `safety_basis`에 쓰지 않았다. [`S-02`](../../../../sources/safety/S-02_KOSHA_GUIDE_M-101-2012.md)가 조항 단위 검토 미완 상태이고, 확정 근거로 쓰기 전에 적용 조항 검토와 카드별 매핑이 필요하다고 명시하기 때문이다.",
        "",
        "## 재생성",
        "",
        "```bash",
        "python docs/data/knowledge_cards/kb/20260930-T4/plan.py              # plan.json",
        "python docs/data/knowledge_cards/kb/20260930-T4/prompts/build_index.py  # prompts/index.json",
        "python docs/data/knowledge_cards/kb/20260930-T4/build_docs.py        # review.md, README.md",
        "```",
        "",
        "`build_docs.py`는 `review.md`의 기존 판정 칸을 읽어 그대로 옮긴다. 검수 결과는 재생성으로 지워지지 않는다.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    cards = json.loads((HERE / "cards.json").read_text(encoding="utf-8"))
    index = json.loads((HERE / "prompts/index.json").read_text(encoding="utf-8"))
    plan = json.loads((HERE / "plan.json").read_text(encoding="utf-8"))

    review_path = HERE / "review.md"
    verdicts = load_existing_verdicts(review_path)
    # 줄바꿈 LF 고정 — 기본값은 Windows에서 CRLF가 되어 git 저장본과 어긋난다.
    review_path.write_text(build_review(cards, verdicts), encoding="utf-8", newline="\n")
    (HERE / "README.md").write_text(build_readme(cards, index, plan), encoding="utf-8", newline="\n")

    filled = sum(1 for v in verdicts.values() if v)
    print(f"review.md: 카드 {len(cards)}장 (기존 판정 {filled}건 보존)")
    print(f"README.md: 추적표 {len(cards)}행")


if __name__ == "__main__":
    main()
