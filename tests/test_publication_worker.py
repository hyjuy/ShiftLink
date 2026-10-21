"""Crash-out harness: a vector is not searchable until the matching review commits."""
from copy import deepcopy
from dataclasses import replace
import json
from threading import Event, Thread

import pytest

from test_work_report_capture import captured
from test_work_report_reuse_harness import service, ask
from shiftlink.agent.schemas import KnowledgeCard
from shiftlink.mes.storage import MesStorage


ACTOR = {'id':'quality-reviewer','name':'검수자'}


def quality_pass(service, note=None):
    saved = service.record_work_report(note or captured(service))
    draft_id = saved['candidates'][0]['draft_id']
    for revision, action in enumerate(('approve','quality_pass')):
        service.review_card_draft(draft_id, {'action':action,'reason':'원문·조치·적용 조건 확인',
                                           'expected_revision':revision}, ACTOR)
    return draft_id


def vectors(texts, model, host):
    assert model == 'embeddinggemma:300m'
    assert texts and all(text.startswith('title: none | text: ') for text in texts)
    return [[3.,4.,0.,0.] for _ in texts]


def test_question_to_log_to_review_to_embedding_to_rag_and_restart(service, tmp_path):
    query = ask(service)
    assert query['knowledge_status'] == 'no_applicable_card'
    note = captured(service)
    note['work_report']['records'][0]['query_id'] = query['query_id']
    draft_id = quality_pass(service, note)
    original = deepcopy(service.storage.get_card_draft(draft_id)['card'])
    assert service.publications.process_one(embedder=vectors, now=100)
    assert not service.publications.process_one(embedder=lambda *args:pytest.fail('duplicate embedding'), now=101)
    draft = service.storage.get_card_draft(draft_id)
    pub = draft['review_flags']['publication']
    assert pub['state'] == 'published' and pub['searchable']
    assert pub['model'] == 'embeddinggemma:300m' and pub['dimension'] == 4
    assert draft['card'] == original and original['status'] == 'draft'
    assert draft['revision'] == 2 and len(draft['reviews']) == 2
    after = service.query({'question':'필터 오염 확인 필터 교체 압력', 'equipment_id':note['equipment_id']})
    assert draft_id in after['cited_card_ids'] and not after['no_knowledge']
    # Persisted pool must restore without the worker regenerating vectors.
    reopened = MesStorage(tmp_path/'mes.sqlite3')
    try:
        from shiftlink.mes.server import MesService
        from pathlib import Path
        from test_work_report_reuse_harness import select_pipeline
        restored = MesService(Path('docs/data/reference/00_plant_and_relations.json'), reopened)
        select_pipeline(restored)
        answer = restored.query({'question':'필터 오염 확인 필터 교체 압력','equipment_id':note['equipment_id']})
        assert draft_id in answer['cited_card_ids']
    finally:
        reopened.close()


@pytest.mark.parametrize('bad', [[], [[0.,0.]], [[float('nan'),1.]], [[True,1.]], [[1.]], [[1.,0.],[0.,1.]]])
def test_invalid_embeddings_do_not_publish(service, bad):
    draft_id = quality_pass(service)
    assert service.publications.process_one(embedder=lambda *args:bad, now=100)
    pub = service.storage.get_card_draft(draft_id)['review_flags']['publication']
    assert pub['state'] == 'embedding_failed' and pub['searchable'] is False
    assert service.storage.connection.execute('SELECT count(*) FROM knowledge_publications').fetchone()[0] == 0


def test_failed_embedding_retries_without_holding_mes_lock(service):
    draft_id = quality_pass(service)
    def unavailable(*args):
        # Network work must allow another thread to query/tick/review.
        available = Event()
        def acquire():
            with service._lock:available.set()
        thread = Thread(target=acquire);thread.start();thread.join(2)
        assert available.is_set()
        raise ConnectionError('embedding server down')
    service.publications.process_one(embedder=unavailable, now=100)
    failed = service.storage.get_card_draft(draft_id)['review_flags']['publication']
    assert failed['attempts'] == 1 and failed['retry_at'] > 100
    assert not service.publications.process_one(embedder=vectors, now=100)
    assert service.publications.process_one(embedder=vectors, now=failed['retry_at'])
    assert service.storage.get_card_draft(draft_id)['review_flags']['publication']['state'] == 'published'


def test_rejection_during_embedding_cannot_resurrect_card(service):
    draft_id = quality_pass(service)
    def reject_while_embedding(*args):
        service.review_card_draft(draft_id, {'action':'reject','reason':'반대 근거 확인','expected_revision':2}, ACTOR)
        return vectors(*args)
    service.publications.process_one(embedder=reject_while_embedding, now=100)
    assert service.storage.get_card_draft(draft_id)['status'] == 'rejected'
    assert service.storage.connection.execute('SELECT count(*) FROM knowledge_publications').fetchone()[0] == 0


def test_re_review_removes_live_pool_and_invalidates_inflight_answer(service):
    from shiftlink.agent.pipeline import JudgeUnavailableError
    draft_id = quality_pass(service)
    service.publications.process_one(embedder=vectors, now=100)
    pipeline = service.query_pipeline
    original_run = pipeline.run
    def revoke(payload):
        result = original_run(payload)
        service.review_card_draft(draft_id, {'action':'request_changes','reason':'조건 재확인','expected_revision':2}, ACTOR)
        return result
    # The per-query copy retains this callback, simulating revocation during inference.
    pipeline.run = revoke
    with pytest.raises(JudgeUnavailableError):
        service.query({'question':'필터 교체 오염 확인','equipment_id':service.active_config.equipment[0].equipment_id})
    pipeline.run = original_run
    assert service.query({'question':'필터 교체 오염 확인','equipment_id':service.active_config.equipment[0].equipment_id})['no_knowledge']


def test_asset_change_and_other_installation_cannot_reuse_field_card(service):
    draft_id = quality_pass(service)
    service.publications.process_one(embedder=vectors, now=100)
    eq = service.active_config.equipment[0]
    other = service.active_config.equipment[1]
    assert service.query({'question':'필터 오염 교체','equipment_id':other.equipment_id})['no_knowledge']
    service.active_config = replace(service.active_config, equipment=(replace(eq,asset_id='replacement-asset'),*service.active_config.equipment[1:]))
    assert service.query({'question':'필터 오염 교체','equipment_id':eq.equipment_id})['no_knowledge']


def test_placeholder_draft_cannot_pass_quality_even_when_schema_valid(service):
    from test_work_report_reuse_harness import report
    query = ask(service)
    saved = service.record_work_report(report(service, query['query_id']))
    draft_id = saved['candidates'][0]['draft_id']
    assert KnowledgeCard.model_validate(service.storage.get_card_draft(draft_id)['card'])
    service.review_card_draft(draft_id, {'action':'approve','reason':'일차 검토','expected_revision':0}, ACTOR)
    with pytest.raises(ValueError, match='보완'):
        service.review_card_draft(draft_id, {'action':'quality_pass','reason':'검수','expected_revision':1}, ACTOR)


def test_commit_failure_does_not_leave_partial_search_pool(service):
    import sqlite3
    draft_id = quality_pass(service)
    service.storage.connection.execute("CREATE TRIGGER fail_index BEFORE INSERT ON knowledge_publications "
        "BEGIN SELECT RAISE(ABORT, 'test index commit unavailable'); END")
    service.publications.process_one(embedder=vectors, now=100)
    pub = service.storage.get_card_draft(draft_id)['review_flags']['publication']
    assert pub['state'] == 'embedding_failed' and not pub['searchable']
    assert service.storage.connection.execute('SELECT count(*) FROM knowledge_publications').fetchone()[0] == 0


def test_worker_recovers_expired_running_lease(service):
    draft_id = quality_pass(service)
    draft = service.storage.get_card_draft(draft_id)
    draft['review_flags']['publication'].update(state='embedding_running',retry_at=200,attempts=1)
    with service.storage.connection:
        service.storage.connection.execute('UPDATE card_drafts SET review_flags=? WHERE draft_id=?',
            (json.dumps(draft['review_flags']),draft_id))
    assert not service.publications.process_one(embedder=vectors, now=199)
    assert service.publications.process_one(embedder=vectors, now=200)
    assert service.storage.get_card_draft(draft_id)['review_flags']['publication']['state'] == 'published'
