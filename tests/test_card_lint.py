"""Guide rules the schema cannot enforce — type boundary and safety marking."""

import pytest

from shiftlink.agent.schemas import KnowledgeCard
from shiftlink.data.card_lint import lint_card, lint_cards

BASE = {'card_id': 'K-0001', 'tacit_type': 'T3', 'status': 'draft', 'grade': 'L0',
        'title': '전류가 오르면 상류부터 확인한다', 'symptom': '전류 상승',
        'know_how': '상류 감속기 진동을 확인한다', 'rationale': '구동 불균일이 전달된다'}


def rules(findings):
    return {f['rule'] for f in findings}


def test_restart_wording_on_a_t3_card_is_flagged() -> None:
    """The real miss: K-9005 validated as T3 because it carried symptom and steps."""
    card = dict(BASE, title='재가동이 안 되면 인터록 조건부터 읽는다')
    assert '§2 T6 경계' in rules(lint_card(card))


def test_t6_card_with_restart_wording_is_not_flagged() -> None:
    card = dict(BASE, tacit_type='T6', title='재가동 전 확인 순서')
    assert '§2 T6 경계' not in rules(lint_card(card))


def test_numbered_procedure_outside_t3_is_flagged() -> None:
    card = dict(BASE, tacit_type='T1', know_how='① 유면을 본다 ② 온도를 잰다')
    assert '§2 T3 경계' in rules(lint_card(card))


def test_safety_wording_without_flag_is_flagged() -> None:
    card = dict(BASE, know_how='인터록을 임의로 해제하지 않는다', safety_flag=False)
    assert '§2 안전 표시' in rules(lint_card(card))


def test_safety_wording_with_flag_is_not_flagged() -> None:
    card = dict(BASE, know_how='인터록을 임의로 해제하지 않는다', safety_flag=True,
                safety_basis='산업안전보건기준에 관한 규칙')
    assert '§2 안전 표시' not in rules(lint_card(card))


def test_t1_with_multiple_conditions_suggests_t2() -> None:
    card = dict(BASE, tacit_type='T1',
                conditions=[{'signal': 'a', 'op': '>=', 'value': 1},
                            {'signal': 'b', 'op': '<', 'value': 2}])
    assert '§2.1 T2 경계' in rules(lint_card(card))


def test_non_draft_grade_is_flagged() -> None:
    assert '§3 신규 초안 상태' in rules(lint_card(dict(BASE, grade='L1',
                                                        status='accepted')))


def test_unknown_key_is_a_violation() -> None:
    found = lint_card(dict(BASE, my_note='메모'),
                      known_fields=set(KnowledgeCard.model_fields))
    assert [f['severity'] for f in found if f['rule'] == '§7 스키마 밖 임의 키'] == [
        'violation']


def test_overlapping_generalization_lists_is_a_violation() -> None:
    card = dict(BASE, generalization_evidence={
        'supporting_event_ids': ['EV-0031'], 'contradicting_event_ids': ['EV-0031']})
    found = [f for f in lint_card(card) if f['rule'] == '§5 일반화 근거 겹침']
    assert found and found[0]['severity'] == 'violation'


def test_clean_card_produces_nothing() -> None:
    assert lint_card(BASE) == []


def test_report_counts_and_never_claims_approval() -> None:
    report = lint_cards([dict(BASE, version='1.0'),
                         dict(BASE, card_id='K-0002', version='1.0', grade='L1')])
    assert report['checked'] == 2 and report['flagged'] == 1
    assert 'K-0002@1.0' in report['findings']
    assert '승인된 것은 아니다' in report['note']


def test_two_versions_of_one_card_are_reported_separately() -> None:
    """Keying by card_id alone hid the superseded T3 version of K-9005."""
    old = dict(BASE, card_id='K-9005', version='1.0-draft-001',
               title='재가동이 안 되면 인터록 조건부터 읽는다')
    new = dict(BASE, card_id='K-9005', version='1.0-draft-002', tacit_type='T6',
               title='재가동이 안 되면 인터록 조건부터 읽는다')
    report = lint_cards([old, new])
    assert '§2 T6 경계' in rules(report['findings']['K-9005@1.0-draft-001'])
    assert '§2 T6 경계' not in rules(report['findings'].get('K-9005@1.0-draft-002', []))


@pytest.mark.parametrize('field', ['know_how', 'title', 'rationale'])
def test_every_text_field_is_scanned(field) -> None:
    assert '§2 T6 경계' in rules(lint_card(dict(BASE, **{field: '재가동 순서'})))
