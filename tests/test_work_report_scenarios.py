"""HTTP/SQLite simulations of operator logs, shift handovers and review drafts."""
from copy import deepcopy
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from test_work_report_capture import captured
from test_work_report_reuse_harness import service
from shiftlink.agent.schemas import KnowledgeCard
from shiftlink.mes.server import _Handler
from shiftlink.mes.storage import MesStorage


@pytest.fixture
def http_api(service):
    handler = type('ScenarioHandler', (_Handler,), {'service': service, 'log_message': lambda *args: None})
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()

    def request(path, body=None, status=200):
        req = Request(f'http://127.0.0.1:{server.server_port}{path}',
                      None if body is None else json.dumps(body).encode(),
                      {'Content-Type': 'application/json'})
        try:
            response = urlopen(req, timeout=5)
        except HTTPError as exc:
            response = exc
        with response:
            result = json.load(response)
            assert response.status == status, result
        return result

    yield request
    server.shutdown()
    thread.join()
    server.server_close()


def note(service, identifier, *, day=15, worker='김민수', resolved=True, **changes):
    payload = captured(service, **changes)
    payload['handover_id'] = identifier
    payload['required_context'].update(author=worker, start_at=f'2026-10-{day:02d}T08:00',
                                       end_at=f'2026-10-{day:02d}T16:00')
    record = payload['work_report']['records'][0]
    record['occurred_at'] = f'2026-10-{day:02d}T08:10'
    for i, step in enumerate(record['action_steps']):
        step.update(worker=worker, performed_at=f'2026-10-{day:02d}T09:{i * 10:02d}')
    if not resolved:
        record.update(outcome='open', normal_run_status='unconfirmed', normal_run_minutes=None,
                      normal_run_evidence='', result='미해결, 다음 근무 확인 필요')
    return payload


@pytest.mark.parametrize('scenario,changes,expected', [
    ('diagnostic_resolution', {}, 'T3'),
    ('restart_after_failed_attempt', {'restart_performed': True, 'restart_type': 'maintenance_restart'}, 'T6'),
    ('safety_report_is_not_t5', {'safety_notes': '전원 차단 없이 커버를 여는 위험 발견'}, 'T3'),
    ('routine_maintenance_not_requested', {'type': 'PMS 정비', 'candidate': False}, None),
    ('normal_log_no_candidate', {'type': '추가 기록', 'candidate': False}, None),
    ('resolved_not_requested', {'candidate': False}, None),
])
def test_http_single_log_candidate_routes(service, http_api, scenario, changes, expected):
    payload = note(service, f'HO-SIM-{scenario}', **changes)
    if scenario == 'restart_after_failed_attempt':
        payload['work_report']['records'][0]['action_steps'][0]['failed'] = True
    saved = http_api('/api/work-reports', payload)
    restored = http_api('/api/work-reports/' + payload['handover_id'])['report']
    assert restored['work_report'] == payload['work_report']
    assert restored['required_context']['author'] == '김민수'
    assert restored['created_at']
    drafts = service.storage.list_card_drafts()
    if expected is None:
        assert drafts == []
    else:
        [draft] = drafts
        card = KnowledgeCard.model_validate(draft['card'])
        assert card.tacit_type == expected
        assert (card.status, card.grade, card.split) == ('draft', 'L0', 'dev')
        assert saved['candidates'][0]['draft_id'] == draft['draft_id']
        assert draft['status'] == 'pending_review'
        assert draft['review_flags']['normal_operation']['source'] == 'worker'
        assert not draft['review_flags']['completeness']['ready']
        assert '김민수' in card.know_how and '2026-10-15T09:00' in card.know_how
        if scenario == 'safety_report_is_not_t5':
            assert draft['review_flags']['safety_report']['status'] == 'needs_document_review'
        if scenario == 'restart_after_failed_attempt':
            assert card.type_payload.tried_and_failed[0].observed_result == '오염 확인'
    assert http_api('/api/work-reports', deepcopy(payload))['duplicate']
    assert len(service.storage.list_card_drafts()) == len(drafts)


@pytest.mark.parametrize('missing', ['cause', 'step_result', 'normal_duration', 'normal_evidence', 'unresolved', 'observing'])
def test_http_insufficient_logs_remain_saved_without_candidate(service, http_api, missing):
    payload = note(service, 'HO-SIM-MISSING-' + missing)
    record = payload['work_report']['records'][0]
    if missing == 'cause':
        record['causes'] = []
    elif missing == 'step_result':
        record['action_steps'][0]['observed_result'] = ''
    elif missing == 'normal_duration':
        record['normal_run_minutes'] = None
    elif missing == 'normal_evidence':
        record.update(normal_run_minutes=None, normal_run_evidence='')
    elif missing == 'unresolved':
        record['outcome'] = 'open'
    else:
        record['normal_run_status'] = 'observing'
    saved = http_api('/api/work-reports', payload)
    assert saved['candidates'][0]['reason'] == 'insufficient_capture'
    assert http_api('/api/work-reports/' + payload['handover_id'])['report']['work_report'] == payload['work_report']
    assert service.storage.list_card_drafts() == []


def test_http_four_shifts_restart_duplicate_recurrence_and_isolated_incidents(service, http_api):
    """Four actual saves, three followups, worker attribution, DB restart, recurrence."""
    incident_id = None
    reports = []
    workers = ['김민수', '이서준', '박지훈', '최유진']
    for i, worker in enumerate(workers):
        payload = note(service, f'HO-SIM-CHAIN-{i}', day=14 + i, worker=worker, resolved=i == 3)
        record = payload['work_report']['records'][0]
        record.update(story=f'{i + 1}번째 근무: 압력 저하 후속 조치',
                      follow_up='다음 근무에서 재발·압력 확인' if i < 3 else '')
        record['action_steps'][0].update(action=f'{i + 1}차 점검 시도', observed_result='효과 없음' if i < 2 else '복귀 확인', failed=i < 2)
        if i:
            record.update(incident_id=incident_id, followup_from={'handover_id': reports[-1]['handover_id'], 'record_index': 0},
                          occurred_at=reports[0]['work_report']['records'][0]['occurred_at'])
            record['causes'] = []
        saved = http_api('/api/work-reports', payload)
        incident_id = saved['incidents'][0]['incident_id']
        assert saved['candidates'][0]['reason'] == ('pending_review' if i == 3 else 'insufficient_handover' if i else 'insufficient_capture')
        assert len(service.storage.list_card_drafts()) == (1 if i == 3 else 0)
        reports.append(deepcopy(payload))
        if i == 1:
            db_path = Path(service.storage.connection.execute('PRAGMA database_list').fetchone()[2])
            service.storage.close()
            service.storage = MesStorage(db_path)
    history = http_api('/api/incidents/' + incident_id)['incident']
    assert [r['required_context']['author'] for r in history['records']] == workers
    assert all(r['created_at'] for r in history['records'])
    for i, item in enumerate(history['records']):
        assert item['record'] == reports[i]['work_report']['records'][0]
        assert item['record']['action_steps'][0]['worker'] == workers[i]
        assert item['record']['occurred_at'] == '2026-10-14T08:10'
    [draft] = service.storage.list_card_drafts()
    assert KnowledgeCard.model_validate(draft['card']).tacit_type == 'T4'
    assert len(draft['review_flags']['handover_chain']) == 4
    assert all(worker in draft['card']['know_how'] for worker in workers)
    for payload in reports:
        assert http_api('/api/work-reports', payload)['duplicate']
    assert len(service.storage.list_card_drafts()) == 1
    closed = note(service, 'HO-SIM-CLOSED')
    closed['work_report']['records'][0].update(incident_id=incident_id,
        followup_from={'handover_id': reports[-1]['handover_id'], 'record_index': 0})
    http_api('/api/work-reports', closed, status=400)
    assert service.storage.get_handover(closed['handover_id']) is None
    recurrence = note(service, 'HO-SIM-RECURRENCE', day=18, resolved=False)
    assert http_api('/api/work-reports', recurrence)['incidents'][0]['incident_id'] != incident_id
    assert len(service.storage.list_card_drafts()) == 1


def test_http_two_cases_in_one_report_and_rejected_atomic_changes(service, http_api):
    payload = note(service, 'HO-SIM-MULTIPLE', resolved=False)
    second = deepcopy(payload['work_report']['records'][0])
    second['equipment'] = [service.active_config.equipment[1].equipment_id]
    second['causes'][0]['equipment'] = second['equipment'][:]
    second['story'] = '다른 설비의 독립 이상'
    payload['equipment_id'] = None
    payload['equipment_ids'].extend(second['equipment'])
    payload['work_report']['records'].append(second)
    saved = http_api('/api/work-reports', payload)
    assert len({link['incident_id'] for link in saved['incidents']}) == 2
    assert service.storage.list_card_drafts() == []
    incident_id = saved['incidents'][0]['incident_id']
    followup = note(service, 'HO-SIM-NEXT', resolved=False)
    followup['work_report']['records'][0].update(incident_id=incident_id,
        followup_from={'handover_id': payload['handover_id'], 'record_index': 0})
    http_api('/api/work-reports', followup)
    stale = deepcopy(followup)
    stale['handover_id'] = 'HO-SIM-STALE'
    http_api('/api/work-reports', stale, status=400)
    assert service.storage.get_handover(stale['handover_id']) is None
    invalid = note(service, 'HO-SIM-INVALID')
    invalid['work_report']['records'][0]['action_steps'][0]['performed_at'] = '2026-02-30T09:10'
    http_api('/api/work-reports', invalid, status=400)
    assert service.storage.get_handover(invalid['handover_id']) is None
    assert len(http_api('/api/incidents/' + incident_id)['incident']['records']) == 2
