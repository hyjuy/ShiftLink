"""The real S30h vector ranker, judge gate and immutable index snapshots."""
import json

import numpy as np
import pytest

from test_s30h import pipe, S, E, G
from test_work_report_reuse_harness import service
from test_publication_worker import quality_pass, vectors, ACTOR


def test_published_card_enters_dense_search_and_judge_can_still_reject(service, pipe, monkeypatch):
    service.query_pipeline = pipe
    draft_id = quality_pass(service)
    assert service.publications.process_one(embedder=vectors,now=100)
    monkeypatch.setattr(E,'judge_dist',lambda question,row,*args,**kwargs:[0,0,1,0] if row['metadata']['source']==draft_id else [1,0,0,0])
    monkeypatch.setattr(G,'ask_raw',lambda *args,**kwargs:{'raw':json.dumps({
        'insufficient_evidence':False,'answer':'필터 오염과 교체 결과를 확인합니다 [S1]','citations':['S1']})})
    result = service.query({'question':'필터 교체 오염','equipment_id':'EQ-0001'})
    assert result['cited_card_ids'] == [draft_id] and not result['no_knowledge']
    assert any(cid.startswith('field_'+draft_id) for cid in result['s30h_trace']['candidates'])
    assert len(pipe.rows) == 4 and pipe.vec.shape == (4,4)  # baseline was never mutated
    assert not any(row['chunk_id'].startswith('field_') for row in pipe.rows)
    monkeypatch.setattr(E,'judge_dist',lambda *args,**kwargs:[1,0,0,0])
    assert service.query({'question':'필터 교체 오염','equipment_id':'EQ-0001'})['no_knowledge']
    service.review_card_draft(draft_id,{'action':'reject','reason':'반대 근거','expected_revision':2},ACTOR)
    after = service.query({'question':'필터 교체 오염','equipment_id':'EQ-0001'})
    assert not any(cid.startswith('field_') for cid in after['s30h_trace']['candidates'])


@pytest.mark.parametrize('damage',['model','prefix','chunks','embedding_text'])
def test_index_manifest_or_text_drift_cannot_enter_search(service, pipe, damage):
    service.query_pipeline = pipe
    draft_id = quality_pass(service)
    service.publications.process_one(embedder=vectors,now=100)
    if damage=='embedding_text':
        draft = service.storage.get_card_draft(draft_id)
        draft['review_flags']['publication']['embed_text'] = '검수되지 않은 새 절차'
        with service.storage.connection:
            service.storage.connection.execute('UPDATE card_drafts SET review_flags=? WHERE draft_id=?',
                                               (json.dumps(draft['review_flags']),draft_id))
    else:
        raw = service.storage.connection.execute('SELECT payload FROM knowledge_publications').fetchone()[0]
        data = json.loads(raw)
        if damage=='model':data['manifest']['model']='different-model'
        elif damage=='prefix':data['manifest']['doc_prefix']='wrong prefix'
        else:data['chunks'][0]['text']='검수되지 않은 새 절차'
        with service.storage.connection:
            service.storage.connection.execute('UPDATE knowledge_publications SET payload=?',(json.dumps(data),))
    eq = service.active_config.equipment[0]
    with service._lock:
        view,ticket = service.publications.snapshot(pipe,eq.equipment_id,eq.asset_id,[])
    assert ticket == [] and view is pipe
    artifact = service.storage.get_card_draft(draft_id)['review_flags']['publication']
    assert artifact['state']=='embedding_failed' and artifact['searchable'] is False


@pytest.mark.parametrize('raw',['{broken',json.dumps({'vectors':[[0.,0.,0.,0.]]})])
def test_corrupt_index_row_is_excluded_without_breaking_other_queries(service,pipe,raw):
    service.query_pipeline = pipe
    draft_id=quality_pass(service)
    service.publications.process_one(embedder=vectors,now=100)
    with service.storage.connection:
        service.storage.connection.execute('UPDATE knowledge_publications SET payload=?',(raw,))
    eq=service.active_config.equipment[0]
    with service._lock:
        view,ticket=service.publications.snapshot(pipe,eq.equipment_id,eq.asset_id,[])
    assert view is pipe and ticket==[]
    assert not service.storage.get_card_draft(draft_id)['review_flags']['publication']['searchable']


def test_active_model_drift_and_dimension_mismatch_fail_closed(service, pipe, monkeypatch):
    service.query_pipeline = pipe
    draft_id = quality_pass(service)
    service.publications.process_one(embedder=lambda texts,*args:[[1.,0.] for _ in texts],now=100)
    assert service.storage.get_card_draft(draft_id)['review_flags']['publication']['state']=='embedding_failed'
    monkeypatch.setitem(S.CFG,'model','different-model')
    service.publications.process_one(embedder=vectors,now=500)
    assert service.storage.get_card_draft(draft_id)['review_flags']['publication']['state']=='embedding_failed'


def test_same_model_and_prefix_contract_is_shared_with_s30h():
    from shiftlink.rag.embedding import PUBLICATION_MODEL, prefixes
    from shiftlink.rag2.embed import prefixes as batch_prefixes
    assert PUBLICATION_MODEL == S.CFG['model']
    assert prefixes(PUBLICATION_MODEL) == batch_prefixes(S.CFG['model'])
