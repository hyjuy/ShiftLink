"""An unchanged question gains reviewed work-log evidence, never an answer cache."""
from copy import deepcopy
import json

import pytest

from test_work_report_reuse_harness import service
from test_work_report_capture import captured
from test_publication_worker import ACTOR, vectors
from test_s30h import pipe, E, G

QUESTION = '압력 표시가 요동칠 때 어떤 순서로 점검하나요?'


@pytest.mark.parametrize('mode', ['extract', 's30h'])
def test_identical_question_learns_only_after_review_and_publication(service, pipe, monkeypatch, mode):
    if mode == 's30h':
        service.query_pipeline = pipe
        monkeypatch.setattr(E, 'judge_dist', lambda *a, **k: [1, 0, 0, 0])
    equipment = service.active_config.equipment[0].equipment_id
    request = {'question': QUESTION, 'equipment_id': equipment}
    before = service.query(request)
    assert before['knowledge_status'] == 'no_applicable_card'
    old_answer = deepcopy(service.storage.get_query(before['query_id'])['payload'])
    note = captured(service, query_id=before['query_id'], story='점검 후 스트레이너를 정비했습니다')
    saved = service.record_work_report(note)
    draft_id = saved['candidates'][0]['draft_id']
    draft = service.storage.get_card_draft(draft_id)
    report = deepcopy(service.storage.get_handover(note['handover_id'])['payload'])
    original_card = deepcopy(draft['card'])
    assert draft['review_flags']['work_report']['query_id'] == before['query_id']
    assert draft['review_flags']['origin_query']['question'] == QUESTION
    assert QUESTION in draft['card']['symptom']
    assert note['work_report']['records'][0]['story'] in draft['card']['symptom']
    assert any(source['source_id'] == before['query_id'] and source['locator'] == 'query_log' for source in draft['card']['provenance']['sources'])
    assert service.query(request)['knowledge_status'] == 'no_applicable_card'
    service.review_card_draft(draft_id, {'action': 'approve', 'reason': '조치 원문 확인', 'expected_revision': 0}, ACTOR)
    assert service.query(request)['knowledge_status'] == 'no_applicable_card'
    service.review_card_draft(draft_id, {'action': 'quality_pass', 'reason': '재사용 범위와 조치 결과 검수', 'expected_revision': 1}, ACTOR)
    assert service.query(request)['knowledge_status'] == 'no_applicable_card'
    embedded = []
    def embed(texts, *args):
        embedded.extend(texts)
        return vectors(texts, *args)
    assert service.publications.process_one(embedder=embed, now=100)
    assert any(QUESTION in text for text in embedded)
    if mode == 's30h':
        monkeypatch.setattr(E, 'judge_dist', lambda question, row, *a, **k: [0, 0, 1, 0] if row['metadata']['source'] == draft_id else [1, 0, 0, 0])
        monkeypatch.setattr(G, 'ask_raw', lambda *a, **k: {'raw': json.dumps({'insufficient_evidence': False, 'answer': '필터 오염과 교체 결과를 확인합니다 [S1]', 'citations': ['S1']})})
    after = service.query(request)
    assert after['knowledge_status'] == 'answered' and after['no_knowledge'] is False
    assert after['cited_card_ids'] == [draft_id]
    assert service.storage.get_query(before['query_id'])['payload'] == old_answer
    assert service.storage.get_handover(note['handover_id'])['payload'] == report
    assert service.storage.get_card_draft(draft_id)['card'] == original_card
    if mode == 's30h':
        monkeypatch.setattr(E, 'judge_dist', lambda *a, **k: [1, 0, 0, 0])
        assert service.query(request)['no_knowledge'], 'Same-question reuse must still obey the judge'
    service.review_card_draft(draft_id, {'action': 'reject', 'reason': '상반된 관측 발견', 'expected_revision': 2}, ACTOR)
    rejected = service.query(request)
    assert rejected['no_knowledge'] and draft_id not in rejected['cited_card_ids']
