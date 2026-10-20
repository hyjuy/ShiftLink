"""One incident across shifts becomes a grounded T4 review draft after recovery."""
from copy import deepcopy
import sqlite3

import pytest

from test_work_report_capture import captured
from test_work_report_reuse_harness import service
from shiftlink.agent.schemas import KnowledgeCard


def chain(service,causes_missing=False,origin_notes=None):
    origin=captured(service,candidate=False,outcome='open',normal_run_status='unconfirmed',normal_run_minutes=None,normal_run_evidence='')
    origin['handover_id']='HO-T4-ORIGIN'
    origin['required_context'].update(author='첫 근무자',start_at='2026-10-15T08:00',end_at='2026-10-15T16:00')
    origin['work_report']['records'][0]['follow_up']='다음 근무에서 필터 차압 확인'
    origin['work_report']['records'][0]['safety_notes']='커버 개방 중 위험 발견'
    origin['work_report']['records'][0].update(origin_notes or {})
    if causes_missing:origin['work_report']['records'][0]['causes']=[]
    incident_id=service.record_work_report(origin)['incidents'][0]['incident_id']
    middle=captured(service,candidate=False,outcome='temporary',normal_run_status='observing',normal_run_minutes=None,normal_run_evidence='',
        incident_id=incident_id,followup_from={'handover_id':origin['handover_id'],'record_index':0})
    middle['handover_id']='HO-T4-MIDDLE'
    middle['required_context'].update(author='둘째 근무자',start_at='2026-10-15T16:00',end_at='2026-10-16T00:00')
    middle['work_report']['records'][0]['action_steps']=[{'action':'차압 확인','observed_result':'차압 상승 확인','failed':False}]
    if causes_missing:middle['work_report']['records'][0]['causes']=[]
    service.record_work_report(middle)
    final=captured(service,causes=[],incident_id=incident_id,followup_from={'handover_id':middle['handover_id'],'record_index':0})
    final['handover_id']='HO-T4-FINAL'
    final['required_context'].update(author='셋째 근무자',start_at='2026-10-16T00:00',end_at='2026-10-16T08:00')
    return origin,middle,final


def test_resolved_chain_creates_one_t4_with_all_sources(service):
    origin,middle,final=chain(service)
    result=service.record_work_report(final)
    assert result['candidates'][0]['reason']=='pending_review'
    [draft]=service.storage.list_card_drafts()
    card=KnowledgeCard.model_validate(draft['card'])
    assert card.tacit_type=='T4'
    assert card.type_payload.steps is None
    assert card.type_payload.handover_method.recipient_role
    assert '첫 근무자' in card.know_how and '셋째 근무자' in card.know_how
    assert '차압 상승 확인' in card.know_how
    assert '다음 근무에서 필터 차압 확인' in card.know_how
    assert (card.status,card.grade,card.split)==('draft','L0','dev')
    assert {origin['handover_id'],middle['handover_id'],final['handover_id']} <= {s.source_id for s in card.provenance.sources}
    flags=draft['review_flags']
    assert len(flags['handover_chain'])==3
    assert flags['normal_operation']['minutes']==120 and flags['normal_operation']['source']=='worker'
    assert flags['completeness']['ready'] is False
    assert flags['needs_safety_review'] is True
    assert '커버 개방 중 위험 발견' in flags['safety_report']['text']
    assert service.record_work_report(deepcopy(final))['duplicate']
    assert len(service.storage.list_card_drafts())==1
    assert service.storage.get_handover(origin['handover_id'])['payload']==origin


def test_t4_retains_step_worker_and_actual_time(service):
    _,_,final=chain(service)
    final['work_report']['records'][0]['action_steps'][0].update(worker='교대 지원 근무자',performed_at='2026-10-16T01:35')
    service.record_work_report(final)
    draft=service.storage.list_card_drafts()[0]
    assert '교대 지원 근무자' in draft['card']['know_how']
    assert '2026-10-16T01:35' in draft['card']['know_how']
    assert draft['review_flags']['handover_chain'][-1]['record']['action_steps'][0]['worker']=='교대 지원 근무자'


def test_t4_history_retains_each_shifts_remaining_work(service):
    _, _, final = chain(service, origin_notes={'remaining_issue':'차압이 다시 상승함',
        'next_check':'필터 상태 재확인','next_check_at':'다음 교대 시작'})
    final['work_report']['records'][0].update(remaining_issue='교체 후 장기 관찰 필요',
                                              next_check='다음 가동에서 차압 확인',
                                              next_check_at='다음 가동 시')
    service.record_work_report(final)
    know_how = service.storage.list_card_drafts()[0]['card']['know_how']
    assert '남은 문제: 차압이 다시 상승함' in know_how
    assert '다음 확인 내용: 필터 상태 재확인' in know_how
    assert '확인 시점: 다음 교대 시작' in know_how
    assert '남은 문제: 교체 후 장기 관찰 필요' in know_how
    assert '다음 확인 내용: 다음 가동에서 차압 확인' in know_how
    assert '확인 시점: 다음 가동 시' in know_how


def test_three_followups_preserve_four_workers_times_and_saved_times(service):
    incident_id=None
    for index in range(4):
        note=captured(service)
        note['handover_id']=f'HO-FOUR-{index}'
        note['required_context']['author']=f'근무자 {index+1}'
        record=note['work_report']['records'][0]
        record['action_steps']=[{'action':f'점검 {index+1}','observed_result':f'결과 {index+1}','failed':False,
                                 'worker':f'지원 근무자 {index+1}','performed_at':f'2026-10-16T0{index+1}:20'}]
        if index<3:record.update(candidate=False,outcome='open',normal_run_status='unconfirmed',normal_run_minutes=None,normal_run_evidence='')
        if incident_id:record.update(incident_id=incident_id,followup_from={'handover_id':f'HO-FOUR-{index-1}','record_index':0})
        saved=service.record_work_report(note)
        incident_id=saved['incidents'][0]['incident_id']
    history=service.incident(incident_id)['incident']['records']
    assert len(history)==4 and all(item['created_at'] for item in history)
    for index,item in enumerate(history):
        assert item['required_context']['author']==f'근무자 {index+1}'
        assert item['record']['action_steps'][0]['worker']==f'지원 근무자 {index+1}'
        assert item['record']['action_steps'][0]['performed_at']==f'2026-10-16T0{index+1}:20'
    draft=service.storage.list_card_drafts()[0]
    assert draft['card']['tacit_type']=='T4'
    assert all(f'지원 근무자 {i+1}' in draft['card']['know_how'] for i in range(4))


@pytest.mark.parametrize('missing',['open','observing','duration','cause','step_result'])
def test_chain_with_insufficient_evidence_saves_only_log(service,missing):
    _,_,final=chain(service,causes_missing=missing=='cause');record=final['work_report']['records'][0]
    if missing=='open':record['outcome']='open'
    elif missing=='observing':record['normal_run_status']='observing'
    elif missing=='duration':record.update(normal_run_minutes=None,normal_run_evidence='')
    elif missing=='step_result':record['action_steps'][0]['observed_result']=''
    result=service.record_work_report(final)
    assert result['candidates'][0]['reason']=='insufficient_handover'
    assert service.storage.get_handover(final['handover_id']) is not None
    assert service.storage.list_card_drafts()==[]


def test_stale_followup_and_duplicate_incident_in_one_report_are_rejected(service):
    origin,_,final=chain(service)
    stale=deepcopy(final);stale['work_report']['records'][0]['followup_from']['handover_id']=origin['handover_id']
    with pytest.raises(ValueError,match='latest|최신'):service.record_work_report(stale)
    assert service.storage.get_handover(stale['handover_id']) is None
    final['work_report']['records'].append(deepcopy(final['work_report']['records'][0]))
    with pytest.raises(ValueError,match='once|한 번'):service.record_work_report(final)


def test_draft_storage_failure_rolls_back_final_record(service):
    _,_,final=chain(service)
    service.storage.connection.execute("CREATE TRIGGER reject_t4 BEFORE INSERT ON card_drafts BEGIN SELECT RAISE(ABORT,'t4 failure'); END")
    with pytest.raises(sqlite3.IntegrityError):service.record_work_report(final)
    assert service.storage.get_handover(final['handover_id']) is None
    incident_id=final['work_report']['records'][0]['incident_id']
    assert len(service.incident(incident_id)['incident']['records'])==2


def test_resolved_incident_cannot_be_continued_again(service):
    _,_,final=chain(service);service.record_work_report(final)
    again=deepcopy(final);again['handover_id']='HO-T4-AGAIN'
    again['work_report']['records'][0]['followup_from']['handover_id']=final['handover_id']
    with pytest.raises(ValueError,match='resolved|완료'):service.record_work_report(again)
    assert len(service.storage.list_card_drafts())==1


def test_resolved_but_incomplete_case_can_collect_missing_evidence(service):
    _,_,final=chain(service,causes_missing=True)
    assert service.record_work_report(final)['candidates'][0]['reason']=='insufficient_handover'
    supplement=deepcopy(final);supplement['handover_id']='HO-T4-SUPPLEMENT'
    record=supplement['work_report']['records'][0]
    record['followup_from']={'handover_id':final['handover_id'],'record_index':0}
    record['causes']=[{'equipment':record['equipment'],'certainty':'확인','note':'분해 점검으로 필터 오염 확인'}]
    assert service.record_work_report(supplement)['candidates'][0]['reason']=='pending_review'
    assert len(service.storage.list_card_drafts())==1


def test_t4_http_roundtrip_after_database_restart(service):
    import json
    import threading
    from pathlib import Path
    from http.server import ThreadingHTTPServer
    from urllib.request import Request,urlopen
    from shiftlink.mes.server import _Handler
    from shiftlink.mes.storage import MesStorage

    _,_,final=chain(service)
    handler=type('T4Handler',(_Handler,),{'service':service,'log_message':lambda *args:None})
    server=ThreadingHTTPServer(('127.0.0.1',0),handler)
    worker=threading.Thread(target=server.serve_forever);worker.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(Request(base+'/api/work-reports',json.dumps(final).encode(),{'Content-Type':'application/json'}),timeout=5) as response:
            result=json.load(response)
        assert result['candidates'][0]['reason']=='pending_review'
        db_path=Path(service.storage.connection.execute('PRAGMA database_list').fetchone()[2])
        service.storage.close();service.storage=MesStorage(db_path)
        with urlopen(base+'/api/incidents/'+result['incidents'][0]['incident_id'],timeout=5) as response:
            incident=json.load(response)['incident']
        assert len(incident['records'])==3 and len(incident['candidates'])==3
        assert incident['candidates'][-1]['draft_id']==result['candidates'][0]['draft_id']
        [draft]=service.storage.list_card_drafts()
        assert draft['card']['tacit_type']=='T4' and len(draft['review_flags']['handover_chain'])==3
    finally:
        server.shutdown();worker.join();server.server_close()
