"""Type-specific report contract tests, using isolated SQLite and synthetic measurements."""
import json
import sqlite3
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

import pytest

from test_work_report_reuse_harness import service, report, ask
from shiftlink.mes.server import _Handler
from shiftlink.mes.uploader import upload_pending


def typed_report(service, kind):
    note = report(service)
    note['work_report'].update(form_version=2, work_type=kind, remarks='')
    record = note['work_report']['records'][0]
    eq = service.active_config.equipment[0]
    record['candidate'] = False
    if kind == '정상 근무':
        note['work_report']['records'] = []
    elif kind == '정비 작업':
        record.update(type='PMS 정비', no_parts_used=False, parts=[{'equipment_id':eq.equipment_id,
            'name':'필터', 'part_number':'FILTER-01', 'quantity':2, 'unit':'개', 'usage':'교체'}])
    else:
        spec = eq.signals[0]
        record.update(type='고장·정비', sensor_unknown=False,
            fault_sensors=[{'equipment_id':eq.equipment_id, 'signal':spec.signal, 'unit':spec.unit,
                'problem':'수치 이상', 'before':{'value':50.0,'observed_at':'2026-10-16T09:00:00+09:00','source':'manual'},
                'after':{'value':40.0,'observed_at':'2026-10-16T09:30:00+09:00','source':'manual'}}],
            solution='필터 점검 및 청소', outcome='resolved')
    return note


@pytest.mark.parametrize('kind',['정상 근무','정비 작업','고장·이상 대응'])
def test_typed_report_persists_original_and_authoritative_sensor_evidence(service,kind):
    note = typed_report(service,kind)
    saved = service.record_work_report(note)
    evidence = saved['server_sensor_evidence']
    assert evidence['config_id'] == service.active_config.config_id
    assert evidence['run_id'] == service.engine.run.run_id
    assert evidence['scope'] == 'save_snapshot'
    assert all(m['equipment_id'] in note['equipment_ids'] for m in evidence['measurements'])
    before = asdict(service.engine.snapshot)['measurements']
    for m in evidence['measurements']:
        original = next((x for x in before if x['equipment_id']==m['equipment_id'] and x['signal']==m['signal']),None)
        if original:
            assert m['value'] == original['value'] and m['quality'] == original['quality']
        else:
            assert m['value'] is None and m['quality'] == 'missing'
    assert service.storage.get_handover(note['handover_id'])['payload'] == note
    detail = service.work_report(note['handover_id'])['report']
    assert detail['work_report'] == note['work_report']
    assert detail['server_sensor_evidence'] == evidence
    assert service.work_reports()['reports'][0]['server_sensor_evidence'] == evidence
    retry = service.record_work_report(note)
    assert retry['duplicate'] and retry['server_sensor_evidence'] == evidence


@pytest.mark.parametrize('change', ['missing_type','unknown_version','missing_details','normal_fault_record',
    'empty_parts','zero_quantity','nan_quantity','wrong_part_equipment','blank_part_name','blank_part_unit',
    'missing_sensor','unknown_sensor','wrong_sensor_equipment','wrong_unit','bad_sample_time','nan_value',
    'spoof_mes_sample','missing_solution','missing_outcome','missing_result'])
def test_invalid_typed_report_is_rejected_atomically(service,change):
    note = typed_report(service,'정비 작업' if change in ('empty_parts','zero_quantity','nan_quantity',
        'wrong_part_equipment','blank_part_name','blank_part_unit') else '고장·이상 대응')
    w = note['work_report']; r = w['records'][0]
    if change=='missing_type': w['work_type']=''
    elif change=='unknown_version': w['form_version']=99
    elif change=='missing_details': w['records']=[]
    elif change=='normal_fault_record': w['work_type']='정상 근무'
    elif change=='empty_parts': r['parts']=[]
    elif change=='zero_quantity': r['parts'][0]['quantity']=0
    elif change=='nan_quantity': r['parts'][0]['quantity']=float('nan')
    elif change=='wrong_part_equipment': r['parts'][0]['equipment_id']='UNKNOWN'
    elif change=='blank_part_name': r['parts'][0]['name']=' '
    elif change=='blank_part_unit': r['parts'][0]['unit']=' '
    elif change=='missing_sensor': r['fault_sensors']=[]
    elif change=='unknown_sensor': r['fault_sensors'][0]['signal']='UNKNOWN'
    elif change=='wrong_sensor_equipment': r['fault_sensors'][0]['equipment_id']='UNKNOWN'
    elif change=='wrong_unit': r['fault_sensors'][0]['unit']='WRONG'
    elif change=='bad_sample_time': r['fault_sensors'][0]['before']['observed_at']='bad'
    elif change=='nan_value': r['fault_sensors'][0]['before']['value']=float('nan')
    elif change=='spoof_mes_sample': r['fault_sensors'][0]['before']['source']='mes'
    elif change=='missing_solution': r['solution']=' '
    elif change=='missing_outcome': r['outcome']=''
    elif change=='missing_result': r['result']=' '
    with pytest.raises(ValueError): service.record_work_report(note)
    assert service.storage.pending_handovers()==[]
    assert service.incidents()['incidents']==[]


def test_unknown_sensor_and_no_parts_are_explicit_and_allowed(service):
    note = typed_report(service,'정비 작업')
    note['work_report']['records'][0].update(parts=[],no_parts_used=True)
    service.record_work_report(note)
    note = typed_report(service,'고장·이상 대응'); note['handover_id']='HO-UNKNOWN-SENSOR'
    note['work_report']['records'][0].update(type='이상증상',fault_sensors=[],sensor_unknown=True,outcome='open',solution='')
    saved = service.record_work_report(note)
    assert len(saved['incidents']) == 1


def test_typed_candidate_preserves_solution_and_worker_outcome_without_verifying(service):
    note=typed_report(service,'고장·이상 대응')
    note['work_report']['records'][0].update(candidate=True,query_id=ask(service)['query_id'])
    service.record_work_report(note)
    [draft]=service.storage.list_card_drafts()
    assert note['work_report']['records'][0]['solution'] in draft['card']['know_how']
    assert draft['review_flags']['worker_outcome']=='resolved'
    assert draft['review_flags']['fault_sensors']==note['work_report']['records'][0]['fault_sensors']
    assert not draft['review_flags']['completeness']['ready']
    assert draft['review_flags']['completeness']['resolved_records']==0


def test_sensor_evidence_failure_rolls_back_report(service):
    service.storage.connection.execute("CREATE TRIGGER reject_report_sensors BEFORE INSERT ON work_report_sensor_evidence "
        "BEGIN SELECT RAISE(ABORT,'harness storage failure'); END")
    with pytest.raises(sqlite3.IntegrityError): service.record_work_report(typed_report(service,'정상 근무'))
    assert service.storage.pending_handovers()==[]


def test_upload_includes_typed_fields_and_server_sensor_evidence(service):
    note=typed_report(service,'정비 작업'); saved=service.record_work_report(note); captured=[]
    class Cursor:
        rowcount=1
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def execute(self,sql,args): captured.append(json.loads(args[-2]))
    class Connection:
        def cursor(self): return Cursor()
        def close(self): pass
    assert upload_pending(service.storage,Connection)['uploaded']==1
    assert captured[0]['work_report']==note['work_report']
    assert captured[0]['server_sensor_evidence']==saved['server_sensor_evidence']


@pytest.mark.parametrize('kind',['정상 근무','정비 작업','고장·이상 대응'])
def test_typed_http_save_and_get(service,kind):
    handler=type('TypedReportHandler',(_Handler,),{'service':service})
    server=ThreadingHTTPServer(('127.0.0.1',0),handler)
    worker=threading.Thread(target=server.serve_forever);worker.start()
    try:
        note=typed_report(service,kind); base=f'http://127.0.0.1:{server.server_port}/api/work-reports'
        with urlopen(Request(base,json.dumps(note).encode(),{'Content-Type':'application/json'}),timeout=5) as response:
            saved=json.load(response)
        with urlopen(base+'/'+note['handover_id'],timeout=5) as response:
            detail=json.load(response)['report']
        assert detail['work_report']==note['work_report']
        assert detail['server_sensor_evidence']==saved['server_sensor_evidence']
    finally:
        server.shutdown();worker.join();server.server_close()
