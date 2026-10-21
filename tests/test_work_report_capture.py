"""Small work-log capture produces grounded T3/T6 drafts, never T4/T5 or published cards."""
from copy import deepcopy

import pytest

from test_work_report_reuse_harness import service, report
from shiftlink.agent.schemas import KnowledgeCard


def captured(service, **changes):
    note=report(service)
    note['work_report']['records'][0].update(capture_version=1,occurred_at='2026-10-16T09:00',
        action_steps=[{'action':'필터 오염 확인','observed_result':'오염 확인','failed':False},
                      {'action':'필터 교체','observed_result':'압력 정상 범위 복귀','failed':False}],
        restart_performed=False,restart_type='unknown',outcome='resolved',
        normal_run_status='no_recurrence',normal_run_minutes=120,normal_run_evidence='10:00~12:00 연속 운전, 정지·재발 없음',
        safety_notes='')
    note['work_report']['records'][0].update(changes)
    return note


@pytest.mark.parametrize('key,value', [('worker',42),('worker','x'*101),('performed_at','yesterday'),('performed_at',42),('performed_at','2026-02-30T09:00')])
def test_invalid_step_worker_or_time_rejected(service,key,value):
    note=captured(service)
    note['work_report']['records'][0]['action_steps'][0][key]=value
    with pytest.raises(ValueError):
        service.record_work_report(note)
    assert service.storage.get_handover(note['handover_id']) is None


def test_step_worker_and_optional_time_roundtrip(service):
    note=captured(service)
    steps=note['work_report']['records'][0]['action_steps']
    steps[0].update(worker='첫 근무자',performed_at='2026-10-16T09:20')
    steps[1].update(worker='둘째 근무자',performed_at='')
    service.record_work_report(note)
    assert service.work_report(note['handover_id'])['report']['work_report']['records'][0]['action_steps']==steps
    draft=service.storage.list_card_drafts()[0]
    assert draft['review_flags']['action_steps']==steps
    assert '첫 근무자' in draft['card']['know_how']
    assert '2026-10-16T09:20' in draft['card']['know_how']


def test_t3_candidate_uses_steps_and_observation_without_query(service):
    note=captured(service)
    saved=service.record_work_report(note)
    assert saved['candidates'][0]['reason']=='pending_review'
    draft=service.storage.list_card_drafts()[0]
    card=KnowledgeCard.model_validate(draft['card'])
    assert card.tacit_type=='T3'
    assert [step.action for step in card.type_payload.steps]==['필터 오염 확인','필터 교체']
    assert card.type_payload.steps[1].expected_result=='압력 정상 범위 복귀'
    assert (card.status,card.grade,card.split)==('draft','L0','dev')
    assert draft['review_flags']['normal_operation']['minutes']==120
    assert draft['review_flags']['normal_operation']['source']=='worker'
    assert draft['review_flags']['completeness']['ready'] is False
    assert saved['server_sensor_evidence']['scope']=='save_snapshot'
    assert all('검수 보완' not in step.expected_result for step in card.type_payload.steps)
    assert service.record_work_report(deepcopy(note))['duplicate']
    assert len(service.storage.list_card_drafts())==1


@pytest.mark.parametrize('kind',['고장·정비','PMS 정비'])
def test_restart_candidate_uses_t6_and_preserves_failed_attempt(service,kind):
    note=captured(service,type=kind,restart_performed=True,restart_type='maintenance_restart')
    note['work_report']['records'][0]['action_steps'][0].update(failed=True)
    service.record_work_report(note)
    card=KnowledgeCard.model_validate(service.storage.list_card_drafts()[0]['card'])
    assert card.tacit_type=='T6'
    assert card.type_payload.steps is None
    assert card.type_payload.restart_type=='maintenance_restart'
    assert card.type_payload.tried_and_failed[0].action=='필터 오염 확인'
    assert card.type_payload.tried_and_failed[0].observed_result=='오염 확인'
    assert card.type_payload.tried_and_failed[0].failure_reason is None


@pytest.mark.parametrize('missing',['step_result','observation','cause','unresolved','all_failed','multiple_equipment'])
def test_incomplete_candidate_still_saves_log(service,missing):
    note=captured(service);record=note['work_report']['records'][0]
    if missing=='step_result':record['action_steps'][0]['observed_result']=''
    elif missing=='observation':record.update(normal_run_status='unconfirmed',normal_run_minutes=None,normal_run_evidence='')
    elif missing=='cause':record['causes']=[]
    elif missing=='unresolved':record['outcome']='open'
    elif missing=='all_failed':
        for step in record['action_steps']:step['failed']=True
    elif missing=='multiple_equipment':
        second=service.active_config.equipment[1].equipment_id
        record['equipment'].append(second);note['equipment_ids'].append(second);note['equipment_id']=None
    saved=service.record_work_report(note)
    assert saved['candidates'][0]['reason']=='insufficient_capture'
    assert service.storage.list_card_drafts()==[]
    assert service.storage.get_handover(note['handover_id']) is not None


def test_safety_report_is_not_a_t5_rule(service):
    note=captured(service,safety_notes='차단 없이 커버를 여는 위험을 발견')
    service.record_work_report(note)
    draft=service.storage.list_card_drafts()[0]
    assert draft['card']['tacit_type']=='T3'
    assert draft['card']['safety_basis'] is None
    assert draft['review_flags']['safety_report']['status']=='needs_document_review'
    assert draft['review_flags']['safety_report']['text']=='차단 없이 커버를 여는 위험을 발견'


@pytest.mark.parametrize('invalid',[False,'unknown','other_equipment','bad_shape'])
def test_cause_sensor_reference_is_validated_and_saved(service,invalid):
    eq=service.active_config.equipment[0]
    note=captured(service)
    reference={'equipment_id':eq.equipment_id,'signal':eq.signals[0].signal}
    if invalid=='unknown':reference['signal']='not-a-signal'
    elif invalid=='other_equipment':reference['equipment_id']=service.active_config.equipment[1].equipment_id
    elif invalid=='bad_shape':reference='wrong'
    note['work_report']['records'][0]['causes'][0]['sensor_ref']=reference
    if invalid:
        with pytest.raises(ValueError):service.record_work_report(note)
        assert service.storage.get_handover(note['handover_id']) is None
    else:
        service.record_work_report(note)
        restored=service.storage.get_handover(note['handover_id'])['payload']
        assert restored['work_report']['records'][0]['causes'][0]['sensor_ref']==reference
        assert service.storage.list_card_drafts()[0]['review_flags']['reported_causes'][0]['sensor_ref']==reference


@pytest.mark.parametrize('value,valid',[(154.8,True),('154.8',False)])
def test_selected_sensor_reading_is_saved_with_cause(service,value,valid):
    eq=service.active_config.equipment[0]
    note=captured(service)
    cause=note['work_report']['records'][0]['causes'][0]
    cause['sensor_ref']={'equipment_id':eq.equipment_id,'signal':eq.signals[0].signal}
    cause['sensor_reading']={'value':value,'unit':eq.signals[0].unit,'observed_at':'2026-10-20T09:00:00+09:00'}
    if not valid:
        with pytest.raises(ValueError,match='측정값'):
            service.record_work_report(note)
        return
    service.record_work_report(note)
    restored=service.storage.get_handover(note['handover_id'])['payload']
    assert restored['work_report']['records'][0]['causes'][0]['sensor_reading']==cause['sensor_reading']
    assert service.storage.list_card_drafts()[0]['review_flags']['reported_causes'][0]['sensor_reading']==cause['sensor_reading']


def test_routine_maintenance_only_becomes_candidate_when_requested(service):
    note=captured(service,type='PMS 정비',candidate=False)
    assert service.record_work_report(note)['candidates']==[]
    assert service.storage.list_card_drafts()==[]
    note['handover_id']='HO-MAINTENANCE-CANDIDATE'
    note['work_report']['records'][0]['candidate']=True
    assert service.record_work_report(note)['candidates'][0]['reason']=='pending_review'
    assert service.storage.list_card_drafts()[0]['card']['tacit_type']=='T3'


def test_capture_http_roundtrip_and_storage_restart(service,tmp_path):
    import json
    import threading
    from http.server import ThreadingHTTPServer
    from urllib.request import Request, urlopen
    from shiftlink.mes.server import _Handler
    from shiftlink.mes.storage import MesStorage

    note=captured(service,restart_performed=True,restart_type='maintenance_restart')
    handler=type('CaptureHandler',(_Handler,),{'service':service})
    server=ThreadingHTTPServer(('127.0.0.1',0),handler)
    worker=threading.Thread(target=server.serve_forever);worker.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(Request(base+'/api/work-reports',json.dumps(note).encode(),{'Content-Type':'application/json'})) as response:
            saved=json.load(response)
        assert saved['candidates'][0]['reason']=='pending_review'
        service.storage.close();service.storage=MesStorage(tmp_path/'mes.sqlite3')
        with urlopen(base+'/api/work-reports/'+note['handover_id']) as response:
            restored=json.load(response)['report']
        assert restored['work_report']==note['work_report']
        assert restored['candidates']==saved['candidates']
        assert restored['server_sensor_evidence']==saved['server_sensor_evidence']
        assert service.storage.list_card_drafts()[0]['card']['tacit_type']=='T6'
    finally:
        server.shutdown();worker.join();server.server_close()


@pytest.mark.parametrize('change',['bad_version','bad_steps','too_many','bad_action','bad_result','bad_failed','bad_restart','bad_bool'])
def test_capture_validated_at_api_boundary(service,change):
    note=captured(service);r=note['work_report']['records'][0]
    if change=='bad_version':r['capture_version']=True
    elif change=='bad_steps':r['action_steps']={}
    elif change=='too_many':r['action_steps']*=30
    elif change=='bad_action':r['action_steps'][0]['action']=123
    elif change=='bad_result':r['action_steps'][0]['observed_result']='x'*4001
    elif change=='bad_failed':r['action_steps'][0]['failed']='yes'
    elif change=='bad_restart':r.update(restart_performed=True,restart_type='fake')
    elif change=='bad_bool':r['restart_performed']='yes'
    with pytest.raises(ValueError):service.record_work_report(note)
    assert service.storage.get_handover(note['handover_id']) is None


@pytest.mark.parametrize('occurred_at',[None,''])
def test_structured_report_requires_occurrence_time(service,occurred_at):
    note=captured(service)
    if occurred_at is None:
        del note['work_report']['records'][0]['occurred_at']
    else:
        note['work_report']['records'][0]['occurred_at']=occurred_at
    with pytest.raises(ValueError,match='발생시각'):
        service.record_work_report(note)


def test_symptom_roundtrips_and_is_validated(service):
    note=captured(service,symptom='모터에서 소음이 남')
    service.record_work_report(note)
    assert service.work_report(note['handover_id'])['report']['work_report']['records'][0]['symptom']=='모터에서 소음이 남'
    for bad in (42,'x'*4001):
        other=captured(service,symptom=bad);other['handover_id']='HO-SYMPTOM-BAD'
        with pytest.raises(ValueError):service.record_work_report(other)
    assert service.storage.get_handover('HO-SYMPTOM-BAD') is None
