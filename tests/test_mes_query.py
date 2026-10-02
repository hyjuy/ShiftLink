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
