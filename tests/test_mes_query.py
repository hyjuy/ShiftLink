import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from shiftlink.agent.response import AgentResponse
from shiftlink.mes.server import MesService
from shiftlink.mes.query import query_service


@pytest.fixture
def service():
    service = MesService(Path('docs/data/reference/00_plant_and_relations.json'))
    yield service
    service.storage.close()


class Pipeline:
    def run(self, payload):
        self.payload = payload
        return SimpleNamespace(output=AgentResponse(mode='query', answer='grounded answer',
            cited_card_ids=['K-1'], safety_notices=[{'card_id': 'K-S', 'safety_basis': 'stop first'}]))


def test_latest_scan_and_current_mes_reach_pipeline(service):
    service.record_scan({'class': 'HPU', 'conf': .9, 'device_id': 'pi'})
    latest = service.record_scan({'class': 'GR', 'conf': .95, 'device_id': 'pi'})['scan']
    pipeline = Pipeline()
    result = query_service(service, {'question': 'bearing temperature'}, pipeline=pipeline)
    assert pipeline.payload['eq_id'] == latest['equipment_id']
    assert pipeline.payload['question'] == 'bearing temperature'
    assert pipeline.payload['observations']
    measurements = {r['signal']: r['value'] for r in service.state()['measurements']
                    if r['equipment_id'] == latest['equipment_id'] and r['quality'] == 'good'}
    assert all(o['value'] == measurements[o['signal']] for o in pipeline.payload['observations']
               if o['signal'] in measurements)
    assert result['scan']['scan_id'] == latest['scan_id']
    assert result['answer'] == 'grounded answer'
    assert result['cited_card_ids'] == ['K-1']
    assert result['safety_notices'][0]['card_id'] == 'K-S'
    assert 'scenario_id' not in json.dumps(result)
    assert all(r['equipment_id'] == latest['equipment_id'] for r in result['evidence']['measurements'])


def test_manual_selection_is_explicit_and_does_not_borrow_scan(service):
    service.record_scan({'class': 'HPU', 'conf': .9, 'device_id': 'pi'})
    pipeline = Pipeline()
    result = query_service(service, {'question': 'bearing', 'equipment_id': 'EQ-0004'}, pipeline=pipeline)
    assert pipeline.payload['eq_id'] == 'EQ-0004'
    assert result['scan'] is None


@pytest.mark.parametrize('body', [[], {}, {'question': ''}, {'question': 'x', 'observations': []},
                                       {'question': 'x', 'equipment_id': 'missing'}])
def test_invalid_query_rejected(service, body):
    with pytest.raises(ValueError):
        query_service(service, body, pipeline=Pipeline())


def test_question_without_scan_requires_equipment(service):
    with pytest.raises(ValueError, match='scan'):
        query_service(service, {'question': 'x'}, pipeline=Pipeline())


def test_query_http_returns_json_answer(service):
    import threading
    from http.server import ThreadingHTTPServer
    from urllib.request import Request, urlopen
    from shiftlink.mes.server import _Handler
    service.query_pipeline = Pipeline()
    service.record_scan({'class': 'GR', 'conf': .95, 'device_id': 'pi'})
    handler = type('QueryHandler', (_Handler,), {'service': service, 'web_root': Path('shiftlink/mes/web')})
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    try:
        req = Request(f'http://127.0.0.1:{server.server_port}/api/query',
                      json.dumps({'question': 'bearing'}).encode(), {'Content-Type': 'application/json'})
        with urlopen(req, timeout=5) as response:
            result = json.load(response)
        assert result['answer'] == 'grounded answer'
        assert result['cited_card_ids'] == ['K-1']
    finally:
        server.shutdown()
        worker.join()
        server.server_close()


def test_fixed_pipeline_retrieval_model_and_cache(service, monkeypatch):
    from shiftlink.mes import query
    monkeypatch.setenv('SHIFTLINK_ANSWER_MODE', 'model')  # this test covers the model-answer path; extract is the demo default
    calls = []
    pipeline = query.build_query_pipeline()
    def model(**kwargs):
        calls.append(kwargs)
        return {'answer': '등록된 설비 지식 확인',
                'cited_card_ids': [kwargs['tool_results']['ranked_cards'][0]['card_id']]}
    pipeline.model = model
    builds = []
    monkeypatch.setattr(query, 'build_query_pipeline', lambda: builds.append(True) or pipeline)
    service.record_scan({'class': 'HPU', 'conf': .95, 'device_id': 'pi'})
    question = next(c.title for c in pipeline.tools.cards if c.card_id == 'K-1001')
    result = query_service(service, {'question': question})
    query_service(service, {'question': question})
    assert builds == [True]
    assert calls and calls[0]['request'].observations
    assert result['cited_card_ids']
    assert result['safety_notices']
    assert not result['review_queue']


def test_demo_default_answers_from_the_card_without_calling_the_model(service, monkeypatch):
    from shiftlink.mes import query
    monkeypatch.delenv('SHIFTLINK_ANSWER_MODE', raising=False)
    pipeline = query.build_query_pipeline()
    def model(**kwargs):
        raise AssertionError('extract mode must not call the model')
    pipeline.model, pipeline.judge = model, lambda question, card: 3
    service.record_scan({'class': 'HPU', 'conf': .95, 'device_id': 'pi'})
    question = next(c.title for c in pipeline.tools.cards if c.card_id == 'K-1001')
    result = query_service(service, {'question': question}, pipeline=pipeline)
    assert result['cited_card_ids'] and not result['review_queue'] and not result['no_knowledge']
    assert result['safety_notices'] and result['answer'].endswith('참조)')


def test_scan_changed_rejected(service):
    first = service.record_scan({'class': 'HPU', 'conf': .9, 'device_id': 'pi'})['scan']
    service.record_scan({'class': 'GR', 'conf': .9, 'device_id': 'pi'})
    with pytest.raises(ValueError, match='scan changed'):
        query_service(service, {'question': 'q', 'scan_id': first['scan_id']}, pipeline=Pipeline())


def test_service_query_logs_answer_for_upload(service):
    service.query_pipeline = Pipeline()
    service.query({'question': 'bearing', 'equipment_id': 'EQ-0004'})
    [(_, _, payload)] = service.storage.pending_queries()
    logged = json.loads(payload)
    assert logged['question'] == 'bearing' and logged['cited_card_ids'] == ['K-1']
    assert logged['equipment_id'] == 'EQ-0004' and logged['latency_ms'] >= 0
