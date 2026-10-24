"""Regressions from the unchanged real-model HPU evaluation questions."""
from copy import deepcopy

import pytest

from shiftlink.rag2.field_history import is_history_question
from test_s30h_publication_integrity import published_history, service, pipe, E, G


@pytest.mark.parametrize('question', [
    '근무일지에서 압력 정상 범위 복귀와 재발 여부를 확인한 기록만 보여줘',
    '근무일지에서 필터 교체 후 217분 정상 운전했다는 기록만 보여줘',
])
def test_record_only_reading_is_history(question):
    assert is_history_question(question)


@pytest.mark.parametrize('question', [
    '근무일지의 기록을 보고 지금 필터를 교체해도 되는지 판단해줘',
    '근무일지에서 기록만 보여주고 내일 교체 순서를 정해줘',
    '근무일지의 기록을 바탕으로 압력 복귀 여부를 새로 분석해줘',
])
def test_record_word_cannot_hide_a_new_request(question):
    assert not is_history_question(question)


@pytest.mark.parametrize('duration,expected', [('137', True), ('217', False), ('999', False)])
def test_only_eligible_field_chunks_reach_judge(published_history, monkeypatch, duration, expected):
    service, did = published_history
    original = deepcopy(service.storage.get_card_draft(did))
    calls = []
    monkeypatch.setattr(E, 'judge_dist', lambda q, row, *a, **k:
                        calls.append(deepcopy(row)) or [0, 0, 1, 0])
    def no_generation(*a, **k):
        raise AssertionError('A record-only lookup must not generate replacement facts')
    monkeypatch.setattr(G, 'ask_raw', no_generation)
    monkeypatch.setattr(G, 'ask', no_generation)
    result = service.query({'question': f'근무일지에서 필터 교체 후 {duration}분 정상 운전했다는 기록만 보여줘',
                            'equipment_id': 'EQ-0001'})
    assert result['no_knowledge'] is not expected
    assert result['cited_card_ids'] == ([did] if expected else [])
    assert bool(calls) is expected
    assert all(r['chunk_id'].startswith('field_') and r['metadata']['source'] == did for r in calls)
    if not expected:
        assert '137분' not in result['answer']
    assert service.storage.get_card_draft(did) == original
    assert service.storage.get_query(result['query_id'])['payload']['answer'] == result['answer']


def test_static_event_cannot_replace_an_unavailable_work_log(published_history, monkeypatch):
    service, _ = published_history
    base = service.query_pipeline
    base.rows = [r for r in base.rows if not r['chunk_id'].startswith('field_')]
    # Use the same static-only view that remains after publication rejection.
    service.publications.snapshot = lambda *a, **k: (base, ())
    calls = []
    monkeypatch.setattr(E, 'judge_dist', lambda *a, **k: calls.append(a) or [0, 0, 1, 0])
    result = service.query({'question': '근무일지에서 필터 교체 후 137분 관찰 결과와 시각만 알려줘',
                            'equipment_id': 'EQ-0001'})
    assert result['no_knowledge'] and not result['cited_card_ids']
    assert not calls


def test_impossible_duration_skips_embedding_search(published_history, monkeypatch):
    service, _ = published_history
    def no_embedding(*a, **k):
        raise AssertionError('No matching reviewed record: no embedding request is needed')
    monkeypatch.setattr(service.query_pipeline, '_embed', no_embedding)
    result = service.query({'question': '근무일지에서 필터 교체 후 217분 정상 운전했다는 기록만 보여줘',
                            'equipment_id': 'EQ-0001'})
    assert result['no_knowledge'] and not result['cited_card_ids']
