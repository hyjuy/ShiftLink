"""Deterministic query -> report -> incident -> draft harness; no external model."""
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from shiftlink.agent.pipeline import FixedPipeline, JudgeUnavailableError
from shiftlink.agent.response import AgentResponse
from shiftlink.agent.schemas import KnowledgeCard
from shiftlink.mes.server import MesService, _Handler
from shiftlink.mes.storage import MesStorage
from shiftlink.rag.retrieval import InMemoryToolProvider

CASES = json.loads((Path(__file__).parent / 'fixtures/work_report_reuse_cases.json').read_text(encoding='utf-8'))


def never_call_model(**kwargs):
    raise AssertionError('Knowledge-gap harness must not call an external model')


def select_pipeline(service, kind='gap'):
    if kind == 'gap':
        service.query_pipeline = FixedPipeline(model=never_call_model, answer_mode='extract',
            tools=InMemoryToolProvider(cards=[], equipment_db=service.catalog.data['equipment'],
                                       equipment_types=service.catalog.data['equipment_types']))
    else:
        response = AgentResponse(mode='query', no_knowledge=kind in ('withheld', 'unverified'),
            review_queue=kind == 'withheld', cited_card_ids=['K-1001'] if kind == 'answered' else [],
            unverified_card_ids=['K-1001'] if kind == 'unverified' else [])
        service.query_pipeline = SimpleNamespace(run=lambda payload: SimpleNamespace(output=response))


@pytest.fixture
def service(tmp_path):
    instance = MesService(Path('docs/data/reference/00_plant_and_relations.json'), MesStorage(tmp_path / 'mes.sqlite3'))
    select_pipeline(instance)
    yield instance
    instance.storage.close()


def ask(service, equipment_id=None, **extra):
    return service.query({'question':'압력이 낮고 경보가 발생했습니다',
                          'equipment_id':equipment_id or service.active_config.equipment[0].equipment_id, **extra})


def report(service, query_id=None, report_id='HO-REUSE-HARNESS'):
    eq = service.active_config.equipment[0].equipment_id
    record = {'type':'고장·정비', 'equipment':[eq], 'story':'필터를 점검하고 청소했습니다',
        'causes':[{'equipment':[eq], 'certainty':'추정', 'note':'필터 오염 가능성'}],
        'result':'작업자 확인: 정상 운전', 'pms':None, 'candidate':True}
    if query_id is not None:
        record['query_id'] = query_id
    return {'handover_id':report_id, 'kind':'work_log', 'equipment_id':eq, 'equipment_ids':[eq],
        'memo_text':'필터 점검 후 정상 운전 확인',
        'required_context':{'author':'하네스 작업자', 'start_at':'2026-10-16T08:00', 'end_at':'2026-10-16T17:00'},
        'work_report':{'legacy_memo':'', 'mes_context':'', 'records':[record]}}


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['id'])
def test_candidate_scenario_matrix(service, case):
    query_id = None
    if case['query']:
        select_pipeline(service, case['query'])
        query_id = ask(service)['query_id']
    note = report(service, query_id)
    record = note['work_report']['records'][0]
    record['candidate'] = case.get('candidate', True)
    if 'causes' in case:
        record['causes'] = case['causes']
    if 'result' in case:
        record['result'] = case['result']
    if case.get('config_changed'):
        service.active_config = replace(service.active_config, config_id='changed-config')
    saved = service.record_work_report(note)
    [decision] = saved['candidates']
    assert decision['reason'] == case['expected']
    assert decision['record_index'] == 0
    assert decision['incident_id'] == saved['incidents'][0]['incident_id']
    drafts = service.storage.list_card_drafts()
    if case['expected'] == 'pending_review':
        [draft] = drafts
        KnowledgeCard.model_validate(draft['card'])
        assert decision['draft_id'] == draft['draft_id']
        assert draft['status'] == 'pending_review'
        assert (draft['card']['status'], draft['card']['grade'], draft['card']['split']) == ('draft', 'L0', 'dev')
        flags = draft['review_flags']
        assert not flags['completeness']['ready']
        assert flags['completeness']['resolved_records'] == 0
        assert flags['records'][0]['mes_recovered'] is False
        assert flags['work_report']['incident_id'] == decision['incident_id']
        assert flags['work_report']['query_id'] == query_id
        assert flags['reported_causes'] == record['causes']
        if 'resolution' not in record:
            assert flags['unstructured_work_report'] is True
            assert flags['records'][0]['result'] == 'unconfirmed'
            assert flags['worker_result_text'] == record['result']
            assert record['story'] in draft['card']['know_how']
            assert draft['card']['type_payload']['steps'][0]['action'] != record['story']
        assert any(source['source_id'] == note['handover_id'] and source['locator'] == 'work_report.records[0]'
                   for source in draft['card']['provenance']['sources'])
    else:
        assert drafts == []
        assert decision['draft_id'] is None
    assert service.storage.get_handover(note['handover_id'])['payload'] == note
    assert service.work_report(note['handover_id'])['report']['candidates'] == saved['candidates']


def test_query_id_evidence_and_gap_status_are_durable(service):
    response = ask(service)
    stored = service.storage.get_query(response['query_id'])['payload']
    assert response['knowledge_status'] == 'no_applicable_card'
    assert stored['knowledge_status'] == response['knowledge_status']
    assert stored['evidence'] == response['evidence']
    assert stored['query_context']['asset_id'] == service.active_config.equipment[0].asset_id
    assert 'scenario_id' not in json.dumps(stored)


def test_explicit_incident_query_metadata_never_reaches_model(service):
    note = report(service); note['work_report']['records'][0]['candidate'] = False
    incident_id = service.record_work_report(note)['incidents'][0]['incident_id']
    captured = []
    response = AgentResponse(mode='query', no_knowledge=True)
    service.query_pipeline = SimpleNamespace(run=lambda payload: captured.append(payload) or SimpleNamespace(output=response))
    result = ask(service, incident_id=incident_id)
    assert 'incident_id' not in captured[0] and 'query_id' not in captured[0]
    queries = service.incident(incident_id)['incident']['queries']
    assert queries[0]['query_id'] == result['query_id']
    with pytest.raises(ValueError): ask(service, incident_id='INC-missing')
    with pytest.raises(ValueError): ask(service, service.active_config.equipment[1].equipment_id, incident_id=incident_id)


def test_reference_validation_and_invalid_result_roll_back(service):
    query_id = ask(service)['query_id']
    notes = []
    bad = report(service, 'Q-missing'); notes.append(bad)
    bad = report(service, query_id); bad['work_report']['records'][0]['query_id'] = 3; notes.append(bad)
    bad = report(service, query_id); bad['work_report']['records'][0]['result'] = 3; notes.append(bad)
    bad = report(service, query_id)
    other = service.active_config.equipment[1].equipment_id
    bad['equipment_id'] = other; bad['equipment_ids'] = [other]
    bad['work_report']['records'][0]['equipment'] = [other]
    bad['work_report']['records'][0]['causes'] = []
    notes.append(bad)
    for note in notes:
        with pytest.raises(ValueError): service.record_work_report(note)
        assert service.storage.pending_handovers() == []
        assert service.incidents()['incidents'] == []
    eq = service.active_config.equipment[0]
    service.active_config = replace(service.active_config,
        equipment=(replace(eq, asset_id=eq.asset_id + '-new'), *service.active_config.equipment[1:]))
    with pytest.raises(ValueError): service.record_work_report(report(service, query_id))
    assert service.storage.list_card_drafts() == []


def test_spoofed_evidence_does_not_become_conditions_or_verified_recovery(service):
    response = ask(service)
    note = report(service, response['query_id'])
    eq = service.active_config.equipment[0]
    signal = eq.signals[0]
    note['work_report']['records'][0]['evidence'] = {'equipment_id':eq.equipment_id,
        'measurements':[{'equipment_id':eq.equipment_id,'signal':signal.signal,'value':999999,'quality':'good'}]}
    service.record_work_report(note)
    [draft] = service.storage.list_card_drafts()
    assert draft['card']['conditions'] == []
    assert not draft['review_flags']['records'][0]['mes_recovered']


def test_multiple_records_and_parallel_retries_do_not_duplicate_drafts(service):
    query_id = ask(service)['query_id']
    note = report(service, query_id)
    note['work_report']['records'].append(deepcopy(note['work_report']['records'][0]))
    with ThreadPoolExecutor(max_workers=4) as workers:
        results = list(workers.map(lambda _: service.record_work_report(note), range(4)))
    assert sum(not result['duplicate'] for result in results) == 1
    assert all(result['candidates'] == results[0]['candidates'] for result in results)
    assert len(service.storage.list_card_drafts()) == 2
    assert len({row['draft_id'] for row in results[0]['candidates']}) == 2
    for candidate in results[0]['candidates']:
        incident = service.incident(candidate['incident_id'])['incident']
        assert incident['queries'][0]['query_id'] == query_id
        assert incident['candidates'][0]['draft_id'] == candidate['draft_id']


def test_candidate_database_failure_is_atomic(service):
    query_id = ask(service)['query_id']
    service.storage.connection.execute("CREATE TRIGGER reject_draft BEFORE INSERT ON card_drafts "
        "BEGIN SELECT RAISE(ABORT, 'harness injected storage failure'); END")
    with pytest.raises(sqlite3.IntegrityError): service.record_work_report(report(service, query_id))
    assert service.storage.pending_handovers() == []
    assert service.incidents()['incidents'] == []
    assert service.storage.list_card_drafts() == []
    assert service.storage.connection.execute('SELECT COUNT(*) FROM incident_queries').fetchone()[0] == 0


def test_query_failure_is_not_logged_as_a_knowledge_gap(service):
    def broken(payload):
        raise JudgeUnavailableError('harness injected judge outage')
    service.query_pipeline = SimpleNamespace(run=broken)
    with pytest.raises(JudgeUnavailableError): ask(service)
    assert service.storage.pending_queries() == []
    saved = service.record_work_report(report(service))
    assert saved['candidates'][0]['reason'] == 'missing_query'
    assert service.storage.list_card_drafts() == []


def test_http_query_to_report_to_draft_and_restart(service, tmp_path):
    handler = type('ReuseHarnessHandler', (_Handler,), {'service':service})
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    worker = threading.Thread(target=server.serve_forever); worker.start()
    def request(path, body=None):
        req = Request(f'http://127.0.0.1:{server.server_port}' + path,
                      json.dumps(body).encode() if body is not None else None, {'Content-Type':'application/json'})
        with urlopen(req, timeout=5) as response: return json.load(response)
    try:
        response = request('/api/query', {'question':'하네스에 등록되지 않은 고장',
                                         'equipment_id':service.active_config.equipment[0].equipment_id})
        note = report(service, response['query_id'])
        saved = request('/api/work-reports', note)
        [draft] = request('/api/card-drafts')['drafts']
        assert draft['draft_id'] == saved['candidates'][0]['draft_id']
        assert request('/api/work-reports')['reports'][0]['candidates'] == saved['candidates']
        query_id = response['query_id']
        incident_id = saved['incidents'][0]['incident_id']
        assert request('/api/incidents/' + incident_id)['incident']['queries'][0]['query_id'] == query_id
        with pytest.raises(HTTPError) as caught: request('/api/work-reports', {**note, 'memo_text':'changed'})
        assert caught.value.code == 409; caught.value.close()
    finally:
        server.shutdown(); worker.join(); server.server_close()
    reopened = MesStorage(tmp_path / 'mes.sqlite3')
    try:
        assert reopened.get_query(query_id)['payload']['knowledge_status'] == 'no_applicable_card'
        assert reopened.get_incident(incident_id)['candidates'] == saved['candidates']
        assert len(reopened.list_card_drafts()) == 1
        restored = MesService(Path('docs/data/reference/00_plant_and_relations.json'), reopened)
        retried = restored.record_work_report(note)
        assert retried['duplicate'] and retried['candidates'] == saved['candidates']
    finally:
        reopened.close()


def test_draft_does_not_modify_or_enter_published_kb(service):
    from shiftlink.rag.loader import load_card_provider
    kb_path = Path('docs/data/knowledge_cards/kb/kb_cards.json')
    before = kb_path.read_bytes()
    note = report(service, ask(service)['query_id'])
    draft_id = service.record_work_report(note)['candidates'][0]['draft_id']
    provider = load_card_provider(kb_path).provider
    assert draft_id not in {card.card_id for card in provider.cards}
    assert kb_path.read_bytes() == before
    assert ask(service)['knowledge_status'] == 'no_applicable_card'


def test_query_link_cannot_move_between_incidents(service):
    note = report(service); note['work_report']['records'][0]['candidate'] = False
    incident_id = service.record_work_report(note)['incidents'][0]['incident_id']
    query_id = ask(service, incident_id=incident_id)['query_id']
    followup = report(service, query_id, report_id='HO-FOLLOWUP')
    with pytest.raises(ValueError, match='another incident'): service.record_work_report(followup)
    followup['work_report']['records'][0]['incident_id'] = incident_id
    saved = service.record_work_report(followup)
    assert saved['candidates'][0]['incident_id'] == incident_id
    assert len(service.incident(incident_id)['incident']['queries']) == 1


def test_work_report_reference_does_not_shadow_legacy_handover_id(service):
    service.record_work_report(report(service, ask(service)['query_id']))
    eq = service.active_config.equipment[0].equipment_id
    saved = service.record_handover({'handover_id':'work-report:HO-REUSE-HARNESS:0',
        'memo_text':'별도 조치 기록', 'equipment_id':eq,
        'resolution':{'symptom':'다른 조치 기록의 고장 증상', 'cause':'원인 모름',
                      'actions':['필터 점검 및 청소'], 'result':'resolved', 'verification':'작업자가 정상 운전을 확인'}})
    assert saved['draft']['created'] is True
    assert len(service.storage.list_card_drafts()) == 2


@pytest.mark.parametrize('incident_id', [None, '', 123])
def test_invalid_incident_id_is_rejected_before_query_execution(service, incident_id):
    with pytest.raises(ValueError, match='incident_id'): ask(service, incident_id=incident_id)
    assert service.storage.pending_queries() == []


def test_card_id_exhaustion_keeps_report_unsaved(service, monkeypatch):
    query_id = ask(service)['query_id']
    note = report(service, query_id)
    note['work_report']['records'].append(deepcopy(note['work_report']['records'][0]))
    monkeypatch.setattr(service.storage, 'next_card_id', lambda *args: 'K-7999')
    with pytest.raises(ValueError, match='exhausted'): service.record_work_report(note)
    assert service.storage.pending_handovers() == []
    assert service.storage.list_card_drafts() == []
    assert service.incidents()['incidents'] == []
