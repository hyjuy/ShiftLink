"""Render traceability and the pending human review sheet from merged drafts."""
import json
import re
from pathlib import Path

HERE = Path(__file__).parent


def build():
    cards = json.loads((HERE / "cards.json").read_text(encoding="utf-8"))
    previous = (HERE / "review.md").read_text(encoding="utf-8") if (HERE / "review.md").exists() else ""
    decisions = {}
    for block in re.split(r"(?=^## K-\d{4})", previous, flags=re.M):
        card_id = re.match(r"## (K-\d{4})", block)
        if card_id:
            verdict = re.search(r"^- \*\*(?:사람 )?판정\*\*: ?([^\n]*)$", block, re.M)
            reason = re.search(r"^- \*\*(?:사람 )?판정 근거\*\*: ?([^\n]*)$", block, re.M)
            decisions[card_id[1]] = (verdict[1].strip() if verdict else "", reason[1].strip() if reason else "")
    rows, blocks = [], ["# KB-20260930-C 검수표\n\nA 배치와 같은 항목 순서로 정리했다. 판정 칸에 `accepted` / `rejected` / `수정`을 기록하고 판정 근거를 남긴다. 사람 판정은 미정이며 이 문서를 작성하거나 재생성해도 카드 상태·등급은 자동 변경하지 않는다. 출처·계보·편입 게이트는 별도 검수 대상이다.\n"]
    for c in cards:
        sources = "; ".join(f"{s['source_id']} — {s.get('locator', '')}" for s in c["provenance"]["sources"])
        rows.append(f"| {c['card_id']} | {c['equipment']} | {c['tacit_type']} | {c['title']} | {sources} |")
        ge = c.get("generalization_evidence") or {}
        payload = c.get("type_payload") or {}
        safety = " · ⚠ 안전" if c['safety_flag'] else ""
        lines = [f"## {c['card_id']} · {c['equipment']} · {c['tacit_type']}{safety} — {c['title']}", "",
                 f"- **부품**: {c['component']}"]
        if c.get('symptom'):
            lines.append(f"- **증상**: {c['symptom']}")
        lines += [f"- **노하우**: {c['know_how']}", f"- **근거 설명**: {c['rationale']}"]
        if c.get('safety_basis'):
            lines.append(f"- **안전 근거**: {c['safety_basis']}")
        for cond in c["conditions"]:
            unit = f" {cond['unit']}" if cond.get('unit') else ""
            lines.append(f"- **조건**: `{cond['signal']} {cond['op']} {cond['value']}{unit}`")
        notes = [f"근거 사건: {', '.join(ge.get('supporting_event_ids', [])) or '-'}",
                 f"재가동 유형: {payload.get('restart_type') or '-'}",
                 f"프롬프트: `{c['provenance']['prompt_version']}`",
                 f"정책 연결: `{c['provenance'].get('index_version', '-')}` · [카드별 보완 항목](policy_manifest.json)",
                 "독립 검토 근거: [1차 판정](review_round1.md) · [수정 후 재검토](review_round2.md) · [변경 전후](review_changes.json)"]
        verdict, reason = decisions.get(c['card_id'], ("", ""))
        lines += [f"- **출처**: {sources}", f"- **작성 노트**: {'; '.join(notes)}",
                  f"- **판정**: {verdict}", f"- **판정 근거**: {reason}", ""]
        blocks.append("\n".join(line.rstrip() for line in lines))
    readme = """# KB-20260930-C — T2 10장 · T6 9장

2026-09-30 생성. split=kb, confidence=0.0이며 실제 상태는 cards.json과 아래 검수표에서 확인한다.
생성자 2명과 별도 독립 검토자가 출처 대조, 판정, 수정, 재검토를 수행했다.
사람 승인 전이므로 통합 accepted KB 목록에는 아직 추가하지 않았다.

## 재현과 근거

- [plan.py](plan.py) → [plan.json](plan.json): 시드 20260930, ID K-1201~1219. 슬롯만 재현 가능하며 생성 본문은 고정되지 않는다.
- [prompts/index.json](prompts/index.json): 원본 생성 지시와 SHA256. T2 및 T6 단계 A/B를 구분한다.
- T6 원장 20건과 기록 40건은 최초 KB15/dev5 배정의 감사 기록이다. 현재 독립 평가용 dev 입력은 0건이며 중복 dev5/기록10은 `records/quarantined_dev_*.json`에 보관한다.
- 카드 추출 입력은 `records/kb_events.json`, `records/kb_artifacts.json` 관측 투영이다. 현재 split은 역사적 배정이며 계보 검토 전 활성 정책 배정으로 사용하지 않는다.
- [out/](out/): 배치 카드 원본. [merge.py](merge.py)로 [cards.json](cards.json)을 생성하고 [verify.py](verify.py)로 검사한다.
- [1차 판정](review_round1.md) → [변경 이력](review_changes.json) → [수정 후 재검토](review_round2.md). 생성 프롬프트·해시는 보존했다.
- [review.md](review.md): 사람 검수 대기. [validation.md](validation.md): 실제 실행한 검증과 환경.
- [프로젝트 충돌 검증](integration-review.md): 출처 등록·분할 계보·dev 중복 해결 전 KB 통합 보류.
- [상위 계약 반영](policy-alignment.md): 기준 출처 52개 등록, 계보 7개 후보, dev 격리, 승인·편입 게이트. 출처 승인과 계보 확정은 미완료이다.

## 가이드 예시에서 변경한 슬롯

원문에 없는 차압·유온 분기, RT 클램프 판단, 설치위치가 다른 RT 전류·승강지연 조합,
GR 전류 진단은 사용하지 않았다. HPU 표시기 확인·교체 표시/이력 판단, RT 반송·과전류,
GR 유면·온도 점검의 근거 있는 분기로 대체했다. 상세 사유는 `out/*_notes.md`에 있다.

## 한계와 남은 절차

가상 MES 상태는 검색 후보를 고르는 조건이다. 실제 표시기·부하·소음 등은 수동 확인이 필요하다.
원문 설비 모델과 가상 설치 구조의 일치는 미확정이다. T6는 합성 기록이며 동일 템플릿 반복을 실제 현장 경험으로 주장하지 않는다.
독립 검토자의 원장 정답·dev 접근 편차는 1차/2차 보고에 기록했다. 블라인드 성능평가가 아니다.
사람 검수 후에만 accepted/L1로 승격하고 상위 build_kb.py의 BATCHES에 추가한다.
사람 판정 외에 출처 승인·계보·배정·독립 근거 게이트도 해소해야 한다. `verify.py --kb-ready`가 보완 대기이면 승격·통합하지 않는다.

## 카드 추적표

| 카드 | 설비 | 유형 | 제목 | 출처 |
|---|---|---|---|---|
""" + "\n".join(rows) + "\n"
    (HERE / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    (HERE / "review.md").write_text("\n".join(blocks), encoding="utf-8", newline="\n")
    print(f"traceability and human review sheet: {len(cards)} cards")


if __name__ == "__main__":
    build()
