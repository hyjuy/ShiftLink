"""A worker records facts; the system proposes a review card without a type choice."""
import pytest

from test_work_report_capture import captured
from test_work_report_reuse_harness import service
from test_work_report_t4 import chain
from shiftlink.agent.schemas import KnowledgeCard
from shiftlink.rag.retrieval import _evaluate_condition


@pytest.mark.parametrize('status',['completed','partial','pending','unconfirmed'])
def test_maintenance_completion_is_not_equipment_recovery(service,status):
    note=captured(service,type='PMS 정비',candidate=False,auto_candidate=True,maintenance_status=status,
                  causes=[],outcome='open',normal_run_status='unconfirmed',normal_run_minutes=None,normal_run_evidence='')
    saved=service.record_work_report(note)
    assert saved['candidates']==[]
    record=service.work_report(note['handover_id'])['report']['work_report']['records'][0]
    assert record['maintenance_status']==status and record['outcome']=='open'
    assert service.storage.list_card_drafts()==[]


def test_maintenance_still_creates_safety_candidate_without_fault_cause(service):
    note=captured(service,type='PMS 정비',candidate=False,auto_candidate=True,maintenance_status='completed',
                  causes=[],outcome='open',normal_run_status='unconfirmed',normal_run_minutes=None,normal_run_evidence='',
                  safety_notes='잔압 접촉 위험',safety_action='전원 격리',safety_basis='HPU-M-02',
                  operating_context='기동 직후 잔압이 남아 있을 때 접근 금지')
    saved=service.record_work_report(note)
    assert [(item['kind'],item['reason']) for item in saved['candidates']]==[('T5','pending_review')]
    [draft]=service.storage.list_card_drafts()
    assert draft['review_flags']['observations']['operating_context']=='기동 직후 잔압이 남아 있을 때 접근 금지'


def test_invalid_maintenance_completion_is_rejected(service):
    with pytest.raises(ValueError,match='정비 작업 완료'):
        service.record_work_report(captured(service,type='PMS 정비',maintenance_status='invalid'))


@pytest.mark.parametrize('op,observed,expected', [('>',155,True),('>',140,False),('==',145,True)])
def test_mes_condition_threshold_is_numeric_in_saved_candidate(service,op,observed,expected):
    signal=service.active_config.equipment[0].signals[0]
    note=captured(service,candidate=False,auto_candidate=True,outcome='open',
                  normal_run_status='unconfirmed',normal_run_minutes=None,normal_run_evidence='',
                  condition_signal=signal.signal,condition_op=op,condition_value='145',condition_unit=signal.unit)
    service.record_work_report(note)
    card=KnowledgeCard.model_validate(service.storage.list_card_drafts()[0]['card'])
    assert card.conditions[0].value==145
    assert _evaluate_condition(card.conditions[0],{signal.signal:{'value':observed,'unit':signal.unit}}) is expected
    stored=service.work_report(note['handover_id'])['report']['work_report']['records'][0]
    assert stored['condition_value']=='145'


@pytest.mark.parametrize('kind,fields', [
    ('T1', {'interpretation': '평소와 다른 베어링 진동은 윤활 불량의 징후일 수 있음',
            'interpretation_basis': '동일 설비의 평소 진동과 비교'}),
    ('T2', {'condition_signal': '운전 모드', 'condition_op': '==',
            'condition_value': '기동 중', 'condition_method': '저속에서 차압을 먼저 확인',
            'condition_result': '차압 상승을 확인'}),
    ('T5', {'safety_notes': '커버가 열린 상태', 'safety_action': '접근을 중지하고 전원을 격리',
            'safety_basis': '현장 안전 절차서 4절'}),
])
def test_unresolved_observation_can_be_auto_candidate(service, kind, fields):
    note = captured(service, candidate=False, auto_candidate=True, outcome='open',
                    action_steps=[], normal_run_status='unconfirmed',
                    normal_run_minutes=None, normal_run_evidence='', **fields)
    saved = service.record_work_report(note)
    assert saved['candidates'][0]['reason'] == 'pending_review'
    [draft] = service.storage.list_card_drafts()
    card = KnowledgeCard.model_validate(draft['card'])
    assert card.tacit_type == kind
    assert (card.status, card.grade, card.split) == ('draft', 'L0', 'dev')


def test_condition_card_reuses_work_steps_without_duplicate_action_fields(service):
    note = captured(service, candidate=False, auto_candidate=True, outcome='open',
                    normal_run_status='unconfirmed', normal_run_minutes=None,
                    normal_run_evidence='', condition_signal='pressure',
                    condition_op='>=', condition_value='154.845', condition_unit='bar',
                    condition_observed_at='2026-10-20T09:00:00+09:00',
                    action_steps=[{'action':'필터 교체','observed_result':'압력 회복','failed':False}])
    record=note['work_report']['records'][0]
    assert 'condition_method' not in record and 'condition_result' not in record
    saved=service.record_work_report(note)
    assert saved['candidates'][0]['reason']=='pending_review'
    [draft]=service.storage.list_card_drafts()
    assert draft['card']['tacit_type']=='T2'
    assert draft['card']['know_how']=='필터 교체'
    assert draft['card']['rationale']=='압력 회복'
    assert draft['review_flags']['observations']['condition_observed_at']=='2026-10-20T09:00:00+09:00'


def test_invalid_mes_condition_time_does_not_save(service):
    note=captured(service,condition_signal='pressure',condition_value='154.85',
                  condition_observed_at='yesterday')
    with pytest.raises(ValueError,match='운전 조건 측정시각'):
        service.record_work_report(note)


@pytest.mark.parametrize('restart,kind', [(False, 'T3'), (True, 'T6')])
def test_completed_work_auto_candidate_without_worker_check(service, restart, kind):
    note = captured(service, candidate=False, auto_candidate=True,
                    restart_performed=restart,
                    restart_type='maintenance_restart' if restart else 'unknown')
    saved = service.record_work_report(note)
    assert saved['candidates'][0]['reason'] == 'pending_review'
    assert service.storage.list_card_drafts()[0]['card']['tacit_type'] == kind


def test_completed_handover_auto_candidate_without_worker_check(service):
    _, _, final = chain(service)
    final['work_report']['records'][0].update(candidate=False, auto_candidate=True)
    saved = service.record_work_report(final)
    assert saved['candidates'][0]['reason'] == 'pending_review'
    assert service.storage.list_card_drafts()[0]['card']['tacit_type'] == 'T4'


def test_safety_without_basis_saves_report_but_not_t5(service):
    note = captured(service, candidate=False, auto_candidate=True, outcome='open',
                    action_steps=[], normal_run_status='unconfirmed',
                    normal_run_minutes=None, normal_run_evidence='',
                    safety_notes='커버가 열린 상태', safety_action='전원 격리')
    saved = service.record_work_report(note)
    assert saved['candidates'][0]['reason'] == 'insufficient_safety'
    assert service.storage.list_card_drafts() == []


def test_unstructured_observation_still_saves_without_card(service):
    note = captured(service, candidate=False, auto_candidate=True, outcome='open',
                    action_steps=[], normal_run_status='unconfirmed',
                    normal_run_minutes=None, normal_run_evidence='')
    saved = service.record_work_report(note)
    assert saved['candidates'][0]['draft_id'] is None
    assert service.storage.get_handover(note['handover_id']) is not None


def test_partial_interpretation_does_not_hide_completed_action_candidate(service):
    note = captured(service, candidate=False, auto_candidate=True,
                    interpretation='압력 저하가 평소와 다름')
    saved = service.record_work_report(note)
    assert saved['candidates'][0]['reason'] == 'pending_review'
    assert service.storage.list_card_drafts()[0]['card']['tacit_type'] == 'T3'


def test_auto_candidate_covers_maintenance_and_general_action(service):
    for index, kind in enumerate(('PMS 정비', '추가 기록')):
        note = captured(service, type=kind, candidate=False, auto_candidate=True)
        note['handover_id'] = f'HO-AUTO-ACTION-{index}'
        assert service.record_work_report(note)['candidates'][0]['reason'] == 'pending_review'
    assert [draft['card']['tacit_type'] for draft in service.storage.list_card_drafts()] == ['T3', 'T3']


@pytest.mark.parametrize('condition_op', [None, ''])
def test_missing_condition_operator_keeps_report_without_invented_rule(service, condition_op):
    note = captured(service, candidate=False, auto_candidate=True, outcome='open',
                    action_steps=[], normal_run_status='unconfirmed',
                    normal_run_minutes=None, normal_run_evidence='',
                    condition_signal='운전 모드', condition_value='기동 중',
                    condition_method='차압 확인', condition_result='차압 상승')
    if condition_op is not None:
        note['work_report']['records'][0]['condition_op'] = condition_op
    saved = service.record_work_report(note)
    assert saved['candidates'][0]['reason'] == 'insufficient_t2'
    assert service.storage.list_card_drafts() == []
    assert service.storage.get_handover(note['handover_id']) is not None


def test_complete_interpretation_survives_partial_safety_observation(service):
    note = captured(service, candidate=False, auto_candidate=True, outcome='open',
                    action_steps=[], normal_run_status='unconfirmed',
                    normal_run_minutes=None, normal_run_evidence='',
                    interpretation='진동은 축 정렬 불량의 징후', interpretation_basis='평소 진동과 비교',
                    safety_notes='커버 개방 시 위험')
    saved = service.record_work_report(note)
    assert saved['candidates'][0]['reason'] == 'pending_review'
    [draft] = service.storage.list_card_drafts()
    assert draft['card']['tacit_type'] == 'T1'
    assert draft['review_flags']['observations']['safety_notes'] == '커버 개방 시 위험'


def test_single_observation_draft_retains_other_complete_evidence(service):
    note = captured(service, candidate=False, auto_candidate=True, outcome='open',
                    action_steps=[], normal_run_status='unconfirmed',
                    normal_run_minutes=None, normal_run_evidence='',
                    interpretation='진동은 축 정렬 불량의 징후', interpretation_basis='평소 진동과 비교',
                    condition_signal='운전 모드', condition_op='==', condition_value='기동 중',
                    condition_method='차압 확인', condition_result='차압 상승',
                    safety_notes='커버 개방 시 위험', safety_action='전원 격리', safety_basis='안전 절차 4조')
    service.record_work_report(note)
    drafts = service.storage.list_card_drafts()
    assert {item['card']['tacit_type'] for item in drafts} == {'T1', 'T2', 'T5'}
    draft = next(item for item in drafts if item['card']['tacit_type'] == 'T5')
    assert draft['review_flags']['observations']['interpretation_basis'] == '평소 진동과 비교'
    assert draft['review_flags']['observations']['condition_op'] == '=='
def test_one_record_creates_independent_observation_candidates(service):
    note = captured(service, candidate=False, auto_candidate=True, outcome='open',
                    action_steps=[], normal_run_status='unconfirmed',
                    normal_run_minutes=None, normal_run_evidence='',
                    interpretation='bearing vibration means wear', interpretation_basis='compared with baseline',
                    condition_signal='mode', condition_op='==', condition_value='start',
                    condition_method='check temperature', condition_result='temperature rose',
                    safety_notes='cover open', safety_action='isolate power', safety_basis='safety procedure')
    saved = service.record_work_report(note)
    assert {row['kind'] for row in saved['candidates'] if row['draft_id']} == {'T1', 'T2', 'T5'}
    assert {draft['card']['tacit_type'] for draft in service.storage.list_card_drafts()} == {'T1', 'T2', 'T5'}
    assert service.record_work_report(note)['candidates'] == saved['candidates']


@pytest.mark.parametrize('restart,action_kind', [(False, 'T3'), (True, 'T6')])
def test_observation_and_action_have_distinct_drafts(service, restart, action_kind):
    note = captured(service, candidate=False, auto_candidate=True,
                    restart_performed=restart,
                    restart_type='maintenance_restart' if restart else 'unknown',
                    interpretation='bearing vibration means wear', interpretation_basis='compared with baseline')
    saved = service.record_work_report(note)
    assert {row['kind'] for row in saved['candidates'] if row['draft_id']} == {'T1', action_kind}
    assert len({row['draft_id'] for row in saved['candidates'] if row['draft_id']}) == 2
