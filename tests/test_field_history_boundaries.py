"""Exact history qualifiers and mixed current-action requests, using local fixtures."""
from copy import deepcopy

import pytest

from shiftlink.rag2.field_history import is_history_question, record_sources
from test_s30h_publication_integrity import published_history, output, G, service, pipe


@pytest.mark.parametrize('question', [
    '근무일지 필터 교체 순서와 결과를 알려주고 오늘 교체 가능한지 판단해줘',
    '근무일지의 교체 결과와 오늘 교체 가능 여부를 알려줘',
    '근무일지의 교체 결과를 보고 교체 가능할지 판단해주세요',
    '근무일지의 교체 결과를 보고 교체 가능한지 확인해줘',
])
def test_mixed_current_request_is_not_history_only(question):
    assert not is_history_question(question)


@pytest.mark.parametrize('question', [
    '오늘 근무일지의 필터 교체 순서와 관찰 결과만 알려주세요',
    '과거 근무일지에서 교체 가능했던 판단 결과와 시각은?',
    '현재 상태가 아니라 과거 근무일지의 교체 순서와 결과는?',
])
def test_pure_history_including_todays_record_stays_history(question):
    assert is_history_question(question)


@pytest.mark.parametrize('question_duration,record_duration,expected', [
    ('37분', '137분', False),
    ('137분', '1137분', False),
    ('137분', '0.137분', False),
    ('37분', '37.5분', False),
    ('37.5분', '137.5분', False),
    ('137분', '137분', True),
    ('137 분', '137분', True),
    ('137.5분', '137.5분', True),
    ('1,137분', '1137분', True),
    ('1137분', '1,137분', True),
    ('137분과 37분', '137분', False),
])
def test_duration_matches_whole_value(question_duration, record_duration, expected):
    card = {'card_id': 'K-7999', 'mes_equipment_id': 'EQ-0001',
            'status': 'accepted', 'grade': 'L1', 'split': 'kb',
            'provenance': {'generator': 'work-report-capture-v1'},
            'title': '필터 조치 기록', 'know_how': '필터 교체',
            'rationale': '정상 운전 ' + record_duration}
    row = {'chunk_id': 'field_K-7999_r2_0', 'metadata': {'source': 'K-7999'},
           'text': '검색 청크 사본'}
    original = deepcopy((card, row))
    selected = record_sources('근무일지의 ' + question_duration + ' 결과는?',
                              [row], [card], 'EQ-0001')
    assert bool(selected) is expected
    assert (card, row) == original


@pytest.mark.parametrize('date,expected', [
    ('2026-10-22', True),
    ('2026-10-23', False),
    ('2026-10-22T09:10', True),
    ('2026-10-22T09:11', False),
])
def test_exact_duration_preserves_date_scope(published_history, date, expected):
    service, did = published_history
    card = service.storage.get_card_draft(did)['review_flags']['publication']['card']
    row = {'chunk_id': f'field_{did}_r2_0', 'metadata': {'source': did}}
    assert bool(record_sources(date + ' 137분 관찰 결과', [row], [card], 'EQ-0001')) is expected


@pytest.mark.parametrize('duration', ['37분', '0.137분', '1137분'])
def test_published_history_rejects_wrong_duration(published_history, duration):
    service, did = published_history
    original = deepcopy(service.storage.get_card_draft(did))
    result = service.query({'equipment_id': 'EQ-0001',
                            'question': '근무일지의 필터 교체 순서와 ' + duration + ' 결과는?'})
    assert result['no_knowledge'] and result['cited_card_ids'] == []
    assert '137분' not in result['answer']
    assert service.storage.get_query(result['query_id'])['payload']['no_knowledge']
    assert service.storage.get_card_draft(did) == original


@pytest.mark.parametrize('question', [
    '근무일지 필터 교체 순서와 결과를 알려주고 오늘 교체 가능한지 판단해줘',
    '근무일지의 교체 결과와 오늘 교체 가능 여부를 알려줘',
    '근무일지의 교체 결과를 보고 교체 가능할지 판단해주세요',
])
def test_published_mixed_request_keeps_mes_and_model(published_history, monkeypatch, question):
    service, did = published_history
    original = deepcopy(service.storage.get_card_draft(did))
    calls = []
    monkeypatch.setattr(G, 'ask_raw', lambda prompt, *a, **k:
                        calls.append(prompt) or output('판단에 필요한 자료를 확인합니다 [S1].', ['S1']))
    result = service.query({'equipment_id': 'EQ-0001', 'question': question})
    assert calls and '[MES]' in calls[0] and question in calls[0]
    assert result['s30h_trace']['route'] != 'record_history'
    assert result['cited_card_ids'] == [did]
    assert service.storage.get_query(result['query_id'])['payload']['answer'] == result['answer']
    assert service.storage.get_card_draft(did) == original


def test_published_todays_history_still_preserves_original(published_history):
    service, did = published_history
    result = service.query({'equipment_id': 'EQ-0001',
                            'question': '오늘 근무일지의 137분 관찰 기록의 교체 순서와 결과는?'})
    assert result['s30h_trace']['route'] == 'record_history'
    assert result['cited_card_ids'] == [did]
    assert all(value in result['answer'] for value in ('137분', '09:10', '09:20', '검증자'))
