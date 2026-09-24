"""Flag guide rules that the schema cannot enforce (seeds/카드_작성_가이드_초안.md).

KnowledgeCard already rejects every mechanical rule in §2 and §4 — missing symptom,
steps on a non-T3 card, T6 without restart_type, safety_flag without a basis. Do not
re-implement those here.

What it cannot decide is the §2.1 type boundary: whether a card's *purpose* is
interpreting a sign (T1), narrowing a cause (T3), or restoring state (T6). A card
misfiled as T3 still validates because it carries symptom and steps. That judgement
is a person's, so this module only raises suspicion and never rewrites a card.

Findings are advisory. An empty result is not approval.
"""

from __future__ import annotations

import re
from typing import Any, Literal

# ponytail: keyword heuristics, not semantics. Tune the lists as cards accumulate;
# swap for an entailment check only if the false-positive rate actually hurts.
RESTART_WORDS = ('재가동', '재기동', '복귀', '기동하지', '재시도')
SAFETY_WORDS = ('인터록', '잠금', '격리', '금지', '차단', '끼임', '협착', '위험',
                '해제하지', '접근하지', '중지')
PROCEDURE_MARKERS = re.compile(r'[①②③④⑤]|(?:^|\s)\d\s*[.)]\s')
SCOPE_WORDS = ('먼저', '순서', '다음으로', '확인한 뒤')

TEXT_FIELDS = ('title', 'symptom', 'know_how', 'rationale')
Severity = Literal['violation', 'review']


def _text(card: dict) -> str:
    parts = [str(card.get(f) or '') for f in TEXT_FIELDS]
    payload = card.get('type_payload') or {}
    for step in payload.get('steps') or []:
        parts += [str(step.get('action') or ''), str(step.get('expected_result') or '')]
    return ' '.join(parts)


def _finding(severity: Severity, rule: str, message: str) -> dict[str, Any]:
    return {'severity': severity, 'rule': rule, 'message': message}


def lint_card(card: dict, *, known_fields: set[str] | None = None) -> list[dict[str, Any]]:
    """Return advisory findings for one card. Never mutates it."""
    findings = []
    tacit = card.get('tacit_type')
    text = _text(card)

    if known_fields is not None:
        unknown = sorted(set(card) - known_fields)
        if unknown:
            findings.append(_finding(
                'violation', '§7 스키마 밖 임의 키',
                f'카드에 스키마 밖 키가 있다: {unknown}. 검수 메모는 별도 기록에 남긴다.'))

    # §2/§2.1: the boundary the schema cannot see.
    if tacit in ('T1', 'T2', 'T3') and any(w in text for w in RESTART_WORDS):
        findings.append(_finding(
            'review', '§2 T6 경계',
            f'{tacit} 카드에 재가동·복귀 표현이 있다. 상태 복귀가 목적이면 T6다. '
            '원인 규명이 목적이면 현재 유형을 유지한다.'))
    if tacit not in ('T3', 'T6') and PROCEDURE_MARKERS.search(text):
        findings.append(_finding(
            'review', '§2 T3 경계',
            f'{tacit} 카드의 본문이 번호 매긴 절차를 담고 있다. 무엇을 확인해 원인을 '
            '구분하는지가 핵심이면 T3다.'))
    if tacit == 'T1' and len(card.get('conditions') or []) >= 2:
        findings.append(_finding(
            'review', '§2.1 T2 경계',
            'T1 카드에 조건이 2개 이상이다. 조건에 따라 요령이 달라지는 것이 핵심이면 T2다. '
            '단순한 적용 범위라면 T1을 유지한다.'))

    # §2/§3: safety content present but not marked.
    hit = [w for w in SAFETY_WORDS if w in text]
    if hit and not card.get('safety_flag'):
        findings.append(_finding(
            'review', '§2 안전 표시',
            f'안전 관련 표현이 있으나 safety_flag가 꺼져 있다: {hit[:3]}. 금지·중지·격리 '
            '자체가 핵심이면 T5로 분리하고, 부수적이면 safety_flag와 safety_basis로 '
            '표시한다. 근거가 없으면 값을 만들지 말고 보완 대기로 남긴다.'))

    # §3: a freshly generated draft must not claim adoption.
    if card.get('status') != 'draft' or card.get('grade') != 'L0':
        findings.append(_finding(
            'review', '§3 신규 초안 상태',
            f"신규 초안은 status=draft, grade=L0다. 현재 "
            f"status={card.get('status')}, grade={card.get('grade')}."))

    # §5: generalization lists must not overlap.
    general = card.get('generalization_evidence') or {}
    overlap = set(general.get('supporting_event_ids') or []) & set(
        general.get('contradicting_event_ids') or [])
    if overlap:
        findings.append(_finding(
            'violation', '§5 일반화 근거 겹침',
            f'지지·반대 사건 목록이 겹친다: {sorted(overlap)}'))
    return findings


def lint_cards(cards: list[dict], *, known_fields: set[str] | None = None) -> dict[str, Any]:
    """Key by card_id AND version: two versions of one card are two separate cards."""
    results = {}
    for card in cards:
        found = lint_card(card, known_fields=known_fields)
        if found:
            key = f"{card.get('card_id', '<no-id>')}@{card.get('version', '<no-version>')}"
            results[key] = found
    return {'checked': len(cards), 'flagged': len(results), 'findings': results,
            'note': '자문용이다. 결과가 비어도 유형 판정이 승인된 것은 아니다.'}


def main(argv=None):
    import argparse
    import json
    import sqlite3
    from contextlib import closing
    from pathlib import Path

    from shiftlink.agent.schemas import KnowledgeCard

    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--database', type=Path,
                        default=Path('artifacts/generation/drafts.sqlite3'))
    parser.add_argument('--json', type=Path, nargs='*', default=[],
                        help='Card JSON files: a card object or a list of them')
    args = parser.parse_args(argv)
    cards = []
    if args.database.exists():
        with closing(sqlite3.connect(args.database)) as db:
            cards += [json.loads(row[0])
                      for row in db.execute('SELECT card_json FROM drafts')]
    for path in args.json:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        cards += data if isinstance(data, list) else data.get('cards', [data])
    report = lint_cards(cards, known_fields=set(KnowledgeCard.model_fields))
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 1 if any(f['severity'] == 'violation'
                    for found in report['findings'].values() for f in found) else 0


if __name__ == '__main__':
    raise SystemExit(main())
