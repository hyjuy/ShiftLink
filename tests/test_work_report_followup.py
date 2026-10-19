"""Follow-up reports retain one incident and validate their source and observation evidence."""
from copy import deepcopy
from pathlib import Path
import json
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

from test_work_report_reuse_harness import service, report
from shiftlink.mes.server import _Handler
from shiftlink.mes.storage import MesStorage


def followup(service, origin='HO-ORIGIN'):
    first=report(service,report_id=origin)
    first['work_report']['records'][0].update(candidate=False,outcome='open')
    saved=service.record_work_report(first)
    note=report(service,report_id=origin+'-NEXT')
    note['work_report']['records'][0].update(candidate=False,
        incident_id=saved['incidents'][0]['incident_id'],
        followup_from={'handover_id':origin,'record_index':0},
        outcome='resolved',solution='추가 점검 후 필터 교체',
        normal_run_minutes=120,normal_run_status='no_recurrence',
        normal_run_evidence='10:00~12:00 연속 운전 확인, 정지·재발 없음')
    return first,note


def test_followup_keeps_original_and_one_incident(service):
    original,note=followup(service)
    saved=service.record_work_report(note)
    incident_id=note['work_report']['records'][0]['incident_id']
    assert saved['incidents'][0]['incident_id']==incident_id
    incident=service.incident(incident_id)['incident']
    assert [r['handover_id'] for r in incident['records']]==[original['handover_id'],note['handover_id']]
    assert incident['records'][1]['record']==note['work_report']['records'][0]
    assert service.storage.get_handover(original['handover_id'])['payload']==original
    assert len(service.incidents()['incidents'])==1
    assert incident['records'][0]['required_context']==original['required_context']
    assert service.record_work_report(deepcopy(note))['duplicate']
    assert len(service.incident(incident_id)['incident']['records'])==2


def test_followup_source_must_belong_to_incident(service):
    _,note=followup(service)
    other=report(service,report_id='HO-OTHER')
    other['work_report']['records'][0]['candidate']=False
    service.record_work_report(other)
    note['work_report']['records'][0]['followup_from']['handover_id']='HO-OTHER'
    with pytest.raises(ValueError,match='source|이전'):
        service.record_work_report(note)
    assert service.storage.get_handover(note['handover_id']) is None


@pytest.mark.parametrize('closed',[False,True])
def test_incident_id_without_followup_source_cannot_append(service,closed):
    from test_work_report_capture import captured
    original=captured(service)
    if not closed:original['work_report']['records'][0]['candidate']=False
    saved=service.record_work_report(original)
    note=captured(service)
    note['handover_id']='HO-NO-PARENT'
    note['work_report']['records'][0]['incident_id']=saved['incidents'][0]['incident_id']
    with pytest.raises(ValueError,match='이전 인계'):
        service.record_work_report(note)
    assert service.storage.get_handover(note['handover_id']) is None
    assert len(service.incident(saved['incidents'][0]['incident_id'])['incident']['records'])==1


@pytest.mark.parametrize('change',['missing_source','bad_index','missing_incident','negative','nan','bad_status','missing_evidence','false_continuity'])
def test_invalid_followup_is_not_saved(service,change):
    _,note=followup(service)
    record=note['work_report']['records'][0]
    if change=='missing_source':record['followup_from']['handover_id']='HO-MISSING'
    elif change=='bad_index':record['followup_from']['record_index']=True
    elif change=='missing_incident':del record['incident_id']
    elif change=='negative':record['normal_run_minutes']=-1
    elif change=='nan':record['normal_run_minutes']=float('nan')
    elif change=='bad_status':record['normal_run_status']='fake'
    elif change=='missing_evidence':record['normal_run_evidence']=' '
    elif change=='false_continuity':record['normal_run_status']='unconfirmed'
    with pytest.raises(ValueError):service.record_work_report(note)
    assert service.storage.get_handover(note['handover_id']) is None


def test_unconfirmed_observation_does_not_invent_duration(service):
    _,note=followup(service)
    record=note['work_report']['records'][0]
    record.update(outcome='open',normal_run_minutes=None,normal_run_status='unconfirmed',normal_run_evidence='')
    service.record_work_report(note)
    assert service.incident(record['incident_id'])['incident']['records'][-1]['record']['normal_run_minutes'] is None


def test_followup_http_roundtrip_and_restart(service):
    _,note=followup(service)
    handler=type('FollowupHandler',(_Handler,),{'service':service,'log_message':lambda *args:None})
    server=ThreadingHTTPServer(('127.0.0.1',0),handler)
    worker=Thread(target=server.serve_forever);worker.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        request=Request(base+'/api/work-reports',json.dumps(note).encode(),{'Content-Type':'application/json'})
        with urlopen(request,timeout=5) as response:saved=json.load(response)
        incident_id=saved['incidents'][0]['incident_id']
        with urlopen(base+'/api/incidents/'+incident_id,timeout=5) as response:incident=json.load(response)['incident']
        assert len(incident['records'])==2
        assert incident['records'][-1]['record']['normal_run_minutes']==120
        invalid=deepcopy(note);invalid['handover_id']='HO-INVALID';invalid['work_report']['records'][0]['followup_from']['record_index']=1
        with pytest.raises(HTTPError) as caught:
            urlopen(Request(base+'/api/work-reports',json.dumps(invalid).encode(),{'Content-Type':'application/json'}),timeout=5)
        assert caught.value.code==400;caught.value.close()
        db_path=Path(service.storage.connection.execute('PRAGMA database_list').fetchone()[2])
        reopened=MesStorage(db_path)
        try:assert reopened.get_incident(incident_id)['records'][-1]['record']==note['work_report']['records'][0]
        finally:reopened.close()
    finally:
        server.shutdown();worker.join();server.server_close()
