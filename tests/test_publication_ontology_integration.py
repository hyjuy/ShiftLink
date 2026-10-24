"""A validated publication joins the current ontology without modifying its static artifact."""
from copy import deepcopy
import hashlib
from pathlib import Path
import pytest
from shiftlink.rag.graph_explain import explain
from test_work_report_reuse_harness import service
from test_publication_worker import quality_pass, vectors, ACTOR
from test_graph_explain import CARDS, BUILD
from test_s30h import pipe, E
from test_s30h_publication_integrity import published_history


def published(service):
    did=quality_pass(service)
    assert service.publications.process_one(embedder=vectors)
    return did,service.storage.get_card_draft(did)['review_flags']['publication']['card']


def describe(card, ids=None, **kw):
    row={'metadata':{'kind':'card','source':card['card_id'],'version':card['version']},'text':card['know_how']}
    return explain({'answer':'unchanged','cited_card_ids':[card['card_id']]},[card],
        'HPU','EQ-0001',mode='explain',depth=2,cited_chunks=[row],
        published_card_ids=[card['card_id']] if ids is None else ids,**kw)


def test_validated_field_publication_gets_current_classification_and_source(service):
    did,card=published(service);original=deepcopy(card)
    digest=hashlib.sha256((BUILD/'graph.json').read_bytes()).hexdigest()
    result=describe(card)
    assert result['status']=='ok'
    item,=result['cards'];assert item['card_id']==did
    assert item['classifications'] and item['paths'][0]['relation']=='PART_OF'
    assert item['held_citations']==card['provenance']['sources']
    assert item['citations']==[] and item['symptom_candidates']==[]
    assert result['publication_overlay']['card_ids']==[did]
    assert card==original and result['graph_sha256']==digest
    assert hashlib.sha256((BUILD/'graph.json').read_bytes()).hexdigest()==digest


@pytest.mark.parametrize('damage',['no_ticket','duplicate','wrong_asset_scope','draft','stale_chunk','missing_chunk'])
def test_unvalidated_or_stale_field_never_gets_an_overlay(service,damage):
    did,card=published(service);cards=[card];ids=[did]
    row={'metadata':{'kind':'card','source':did,'version':card['version']},'text':card['know_how']}
    if damage=='no_ticket':ids=[]
    if damage=='duplicate':cards*=2
    if damage=='wrong_asset_scope':card['mes_equipment_id']='EQ-9999'
    if damage=='draft':card['status']='draft'
    if damage=='stale_chunk':row['metadata']['version']='old'
    result=explain({'answer':'unchanged','cited_card_ids':[did]},cards,'HPU','EQ-0001',
        mode='explain',depth=2,cited_chunks=[] if damage=='missing_chunk' else [row],published_card_ids=ids)
    assert result['cards']==[] and result['status']=='unmatched'


def test_overlay_does_not_replace_a_changed_static_card(service):
    card=deepcopy(next(c for c in CARDS if c['card_id']=='K-1004'))
    card['know_how']+=' changed'
    assert describe(card)['cards']==[]


def test_overlay_keeps_off_withheld_and_bad_artifact_contract(service,tmp_path):
    did,card=published(service)
    for flag in ['no_knowledge','review_queue']:
        result=explain({'cited_card_ids':[did],flag:True},[card],'HPU','EQ-0001',mode='explain',published_card_ids=[did])
        assert result['status']=='withheld' and result['cards']==[]
    assert explain({},[card],'HPU','EQ-0001',mode='off',published_card_ids=[did]) is None
    assert describe(card,path=tmp_path/'missing')['status']=='unavailable'


def test_validated_publications_share_only_original_versioned_citations(service):
    did,first=published(service);second=deepcopy(first);second['card_id']='K-7999'
    for c,loc in [(first,'p.5'),(second,'p.9')]:
        c['provenance']['sources'].append({'source_id':'manual','document_version':'v1','locator':loc})
    result=explain({'cited_card_ids':[did]},[first,second],'HPU','EQ-0001',mode='explain',depth=2,
        published_card_ids=[did,'K-7999'])
    root,=result['cards'];related,=root['related_cards'];path,=related['paths']
    assert path['relation']=='CITES' and path['cited_locators']==['p.5'] and path['related_locators']==['p.9']
    second['provenance']['sources'][-1]['document_version']='v2'
    result=explain({'cited_card_ids':[did]},[first,second],'HPU','EQ-0001',mode='explain',depth=2,
        published_card_ids=[did,'K-7999'])
    assert result['cards'][0]['related_cards']==[]


def test_query_publication_search_explanation_and_rejection_share_one_snapshot(service,pipe,monkeypatch):
    monkeypatch.setenv('SHIFTLINK_KG_MODE','explain');monkeypatch.setenv('SHIFTLINK_KG_DEPTH','2')
    did=quality_pass(service);pipe.cards=[];service.query_pipeline=pipe
    monkeypatch.setattr(E,'judge_dist',lambda q,r,*a,**kw:[0,0,1,0] if r['chunk_id'].startswith('field_') else [1,0,0,0])
    request={'question':'필터 교체 기록의 조치 순서와 관찰 결과는?','equipment_id':'EQ-0001'}
    before=service.query(request)
    assert before['no_knowledge'] and before['s30h_trace']['knowledge_graph']['node_counts']['CardVersion']==0
    assert service.publications.process_one(embedder=vectors)
    after=service.query(request)
    assert after['knowledge_status']=='answered' and after['cited_card_ids']==[did]
    assert after['graph_context']['status']=='ok'
    assert after['graph_context']['publication_overlay']['card_ids']==[did]
    assert after['s30h_trace']['knowledge_graph']['node_counts']['CardVersion']==1
    saved=service.storage.get_query(after['query_id'])['payload']
    assert saved['graph_context']==after['graph_context']
    assert saved['s30h_trace']['knowledge_graph']==after['s30h_trace']['knowledge_graph']
    service.review_card_draft(did,{'action':'reject','reason':'격리 재검토','expected_revision':2},ACTOR)
    rejected=service.query(request)
    assert rejected['no_knowledge'] and not rejected['cited_card_ids']
    assert rejected['graph_context']['cards']==[]
    assert rejected['s30h_trace']['knowledge_graph']['node_counts']['CardVersion']==0
    assert all(not r['chunk_id'].startswith('field_') for r in pipe.rows)
    assert service.storage.get_query(after['query_id'])['payload']==saved


def test_field_joins_existing_ontology_type_and_static_document(service):
    did,card=published(service)
    manual=next(c for c in CARDS if c['card_id']=='K-1004')
    ref=next(r for r in manual['provenance']['sources'] if r.get('document_version'))
    card['provenance']['sources'].append({**ref,'locator':'field reference'})
    result=explain({'cited_card_ids':[did]},[card,manual],'HPU','EQ-0001',mode='explain',depth=2,
        published_card_ids=[did])
    root,=result['cards']
    assert root['paths'][0]['nodes'][-1]=='type:HPU'
    assert [c['card_id'] for c in root['related_cards']]==['K-1004']
    path=root['related_cards'][0]['paths'][0]
    assert path['relation']=='CITES' and path['cited_locators']==['field reference']
    assert ref['locator'] in path['related_locators']


@pytest.mark.parametrize('question,history,missing', [
    ('근무일지에서 필터 교체 후 137분 관찰 결과와 시각만 알려줘', True, False),
    ('근무일지의 결과를 보고 밸브 상태를 확인해줘', False, False),
    ('근무일지에서 필터 교체 후 37분 관찰 결과와 시각만 알려줘', True, True),
])
def test_graph_neighbor_preserves_main_history_and_current_contracts(published_history, monkeypatch, question, history, missing):
    import numpy as np
    from test_s30h import chunk, G
    from test_s30h_publication_integrity import output
    svc, did = published_history
    pipeline = svc.query_pipeline
    original = deepcopy(svc.storage.get_card_draft(did))
    reports = deepcopy(svc.storage.list_work_reports())
    card = original['review_flags']['publication']['card']
    pipeline.cards = [{**card, 'card_id':'STATIC-SEED'}]
    pipeline.rows = [chunk('seed', 'card', 'STATIC-SEED', 'HPU', text=card['know_how'])] + [
        chunk(f'manual-{i}', 'source', f'manual-{i}', 'HPU', page=1) for i in range(35)]
    pipeline.vec = np.array([[3,0,0,0]] + [[2.5,0,0,0]] * 35, dtype=np.float32)
    pipeline.folders = np.array(['HPU'] * 36)
    monkeypatch.setattr(pipeline, '_embed', lambda q:np.array([.5,.5,.5,.5], dtype=np.float32))
    calls = []
    monkeypatch.setattr(G, 'ask_raw', lambda prompt, *a, **kw:
                        calls.append(prompt) or output('자료 확인 [S1].', ['S1']))
    result = svc.query({'equipment_id':'EQ-0001', 'question':question})
    assert any(path['card_id']==did for path in result['s30h_trace']['knowledge_graph']['paths'])
    if missing:
        assert result['no_knowledge'] and not result['cited_card_ids'] and not calls
        assert result['s30h_trace']['route']=='drop_all'
    elif history:
        assert result['s30h_trace']['route']=='record_history' and not calls
        assert all(card[k] in result['answer'] for k in ('title','know_how','rationale'))
        assert all(v in result['answer'] for v in ('137분','09:10','09:20','검증자'))
        assert '[MES]' not in result['answer']
    else:
        assert result['s30h_trace']['route']!='record_history' and len(calls)==1
        assert question in calls[0] and '[MES]' in calls[0]
    assert svc.storage.get_card_draft(did)==original
    assert svc.storage.list_work_reports()==reports
    assert svc.storage.get_query(result['query_id'])['payload']['answer']==result['answer']
