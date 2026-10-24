"""Runtime graph retrieval: ontology paths, bounded expansion and publication isolation."""
from copy import deepcopy, copy
from concurrent.futures import ThreadPoolExecutor
import importlib
import json

import numpy as np
import pytest

from test_s30h import pipe, S, E, G, chunk, answer
from test_work_report_reuse_harness import service
from test_publication_worker import quality_pass, vectors, ACTOR
from test_publication_browser import publication_web


def graph_module():
    return importlib.import_module('shiftlink.rag.knowledge_graph')


def card(cid, component='pump', equipment='HPU', sources=None, **extra):
    return {'card_id':cid,'version':'v1','status':'accepted','grade':'L1','split':'kb',
            'equipment':equipment,'component':component,'know_how':'펌프 압력 152 bar 확인',
            'provenance':{'sources':sources or []},**extra}


def source(version='manual-v1', locator='p.5', sid='M-1'):
    return {'source_id':sid,'document_version':version,'locator':locator}


def test_ontology_paths_use_exact_classifications_and_document_versions():
    kg=graph_module().KnowledgeGraph([card('A',sources=[source()]),card('B'),
        card('C',component='motor',sources=[source()]),card('D',component='motor',sources=[source('v2')])], 'HPU','EQ-0001')
    found=kg.neighbors('A',['B','C','D'])
    assert [p['card_id'] for p in found]==['B','C']
    assert found[0]['relations']==['ABOUT','ABOUT']
    assert found[0]['nodes'][1]['type']=='EquipmentType'
    assert found[0]['nodes'][1]['level']=='classification'
    assert found[1]['relations']==['CITES','CITES']
    assert found[1]['nodes'][1]['document_version']=='manual-v1'
    assert kg.summary()['edge_counts']['PART_OF']==2


@pytest.mark.parametrize('missing',[None,'',' '])
def test_unversioned_or_unlocated_source_cannot_connect_cards(missing):
    kg=graph_module().KnowledgeGraph([card('A',sources=[source(missing)]),
        card('B',component='motor',sources=[source(missing)])],'HPU','EQ-0001')
    assert kg.neighbors('A',['B'])==[]
    kg=graph_module().KnowledgeGraph([card('A',sources=[source(locator=missing)]),
        card('B',component='motor',sources=[source(locator=missing)])],'HPU','EQ-0001')
    assert kg.neighbors('A',['B'])==[]


@pytest.mark.parametrize('changes',[{'status':'draft'},{'status':'rejected'},{'grade':'L0'},
    {'split':'dev'},{'equipment':'GR'},{'mes_equipment_id':'EQ-9999'},{'component':''},{'version':''}])
def test_ineligible_cards_never_become_graph_neighbors(changes):
    kg=graph_module().KnowledgeGraph([card('A'),card('B',**changes)],'HPU','EQ-0001')
    assert kg.neighbors('A',['B'])==[]
    assert kg.summary()['node_counts']['CardVersion']==1


def test_missing_equipment_scope_and_ambiguous_versions_fail_closed():
    mod=graph_module()
    assert mod.KnowledgeGraph([card('A'),card('B')],None,None).neighbors('A',['B'])==[]
    kg=mod.KnowledgeGraph([card('A'),card('B'),card('B',version='v2')],'HPU','EQ-0001')
    assert kg.neighbors('A',['B'])==[]
    assert kg.neighbors('unknown',['A'])==[]
    kg=mod.KnowledgeGraph([card('A',mes_equipment_id='EQ-0001'),card('B')],'HPU',None)
    assert kg.neighbors('A',['B'])==[]


def test_ids_preserve_values_and_no_symptom_or_causality_edges_are_invented():
    raw='x/@% 한글'
    kg=graph_module().KnowledgeGraph([card(raw,component=raw,sources=[source(sid=raw)]),
                                     card('B',component=raw)],'HPU','EQ-0001')
    path=kg.neighbors(raw,['B'])[0]
    assert path['nodes'][0]['card_id']==raw and path['nodes'][1]['component']==raw
    assert set(kg.summary()['edge_counts'])=={'ABOUT','PART_OF','CITES'}
    assert 'Symptom' not in kg.summary()['node_counts']
    assert kg.neighbors(raw,['B'])==[path]  # deterministic, no traversal mutation


def ranked_rows():
    rows=[chunk('seed','card','A','HPU')]
    rows += [chunk(f's{i}','source',f'manual{i}','HPU',page=1) for i in range(35)]
    rows += [chunk('neighbor'+cid,'card',cid,'HPU') for cid in ('B','C','D')]
    return rows


def test_graph_expands_beyond_dense_top30_with_bounded_trace():
    rows=ranked_rows(); original=deepcopy(rows)
    ranking,trace=graph_module().expand_ranking(rows,list(range(len(rows))),
        [card(x) for x in ('A','B','C','D')],'HPU','EQ-0001',top=30)
    assert ranking[:3]==[0,36,37] and len(ranking)==30
    assert len(set(ranking))==30 and 38 not in ranking
    assert [p['card_id'] for p in trace['paths']]==['B','C']
    assert trace['schema_version']=='shiftlink-retrieval-graph-v1'
    assert rows==original


def test_no_seed_no_valid_row_or_no_scope_preserves_dense_ranking():
    mod=graph_module(); rows=ranked_rows(); cards=[card('A'),card('B')]
    order=list(range(1,36))+[0,36]
    assert mod.expand_ranking(rows,order,cards,'HPU','EQ-0001',top=30)[0]==order[:30]
    rows[36]['metadata']['folder']='GR'
    assert mod.expand_ranking(rows,list(range(37)),cards,'HPU','EQ-0001',top=30)[1]['paths']==[]
    rows[36]['metadata']['folder']='HPU';rows[36]['metadata']['version']='stale'
    assert mod.expand_ranking(rows,list(range(37)),cards,'HPU','EQ-0001',top=30)[1]['paths']==[]
    assert mod.expand_ranking(rows,list(range(37)),cards,None,None,top=30)[1]['paths']==[]


def configure_graph_pipe(pipe,monkeypatch):
    rows=ranked_rows(); pipe.rows=rows; pipe.folders=np.array([r['metadata']['folder'] for r in rows])
    pipe.vec=np.array([[1-(i/100),0,0,0] for i in range(len(rows))],dtype=np.float32)
    pipe.cards=[card(x) for x in ('A','B','C','D')]
    monkeypatch.setattr(pipe,'_embed',lambda q:np.array([1,0,0,0],dtype=np.float32))
    return rows


def test_s30h_retrieval_uses_graph_and_judge_still_controls_answer(pipe,monkeypatch):
    configure_graph_pipe(pipe,monkeypatch)
    ev=pipe.evidence('pressure','HPU','EQ-0001')
    assert [r['chunk_id'] for r in ev][:3]==['seed','neighborB','neighborC']
    assert len(ev)<=S.CFG['max_chunks']
    seen=[]
    monkeypatch.setattr(E,'judge_dist',lambda q,r,*a,**kw:seen.append(r['chunk_id']) or [1,0,0,0])
    monkeypatch.setattr(G,'ask_raw',lambda *a,**kw:pytest.fail('graph cannot bypass judge'))
    result=pipe.run({'question':'pressure','eq_id':'EQ-0001'})
    assert result.output.no_knowledge and 'neighborB' in seen
    assert result.tool_results['knowledge_graph']['paths'][0]['card_id']=='B'
    assert result.tool_results['knowledge_graph']['paths'][0]['chunk_id']=='neighborB'


def test_graph_citation_comes_from_judged_original_chunk_not_path_text(pipe,monkeypatch):
    configure_graph_pipe(pipe,monkeypatch)
    monkeypatch.setattr(E,'judge_dist',lambda q,r,*a,**kw:[0,0,1,0] if r['chunk_id']=='neighborB' else [1,0,0,0])
    monkeypatch.setattr(G,'ask_raw',lambda *a,**kw:answer('압력 152 bar 확인 [S1]',['S1']))
    result=pipe.run({'question':'pressure','eq_id':'EQ-0001'})
    assert not result.output.no_knowledge and result.output.cited_card_ids==['B']
    assert result.tool_results['kept']==['neighborB']


def test_disabled_graph_is_baseline_and_budget_removed_paths_are_not_reported(pipe,monkeypatch):
    configure_graph_pipe(pipe,monkeypatch)
    pipe.knowledge_graph=False
    ev=pipe.evidence('q','HPU','EQ-0001')
    assert ev[1]['chunk_id']=='s0'
    pipe.knowledge_graph=True
    for r in pipe.rows[36:]:r['tokens']=S.CFG['max_tokens']+1
    ev=pipe.evidence('q','HPU','EQ-0001')
    assert ev.graph_trace['paths']==[]


def test_graph_query_views_do_not_share_cards_trace_or_candidate_state(pipe,monkeypatch):
    configure_graph_pipe(pipe,monkeypatch)
    left,right=copy(pipe),copy(pipe)
    right.cards=[card('A'),card('D')]
    with ThreadPoolExecutor(2) as pool:
        a,b=list(pool.map(lambda p:p.evidence('q','HPU','EQ-0001'),(left,right)))
    assert [p['card_id'] for p in a.graph_trace['paths']]==['B','C']
    assert [p['card_id'] for p in b.graph_trace['paths']]==['D']
    assert len(pipe.cards)==4


@pytest.mark.parametrize('setting,enabled',[(None,True),('0',False),('1',True)])
def test_service_graph_flag_defaults_to_enabled(pipe,tmp_path,monkeypatch,setting,enabled):
    from shiftlink.mes.query import build_query_pipeline
    monkeypatch.setenv('SHIFTLINK_ANSWER_MODE','s30h');monkeypatch.setenv('SHIFTLINK_S30H_INDEX',str(tmp_path))
    monkeypatch.delenv('SHIFTLINK_KNOWLEDGE_GRAPH',raising=False)
    if setting is not None:monkeypatch.setenv('SHIFTLINK_KNOWLEDGE_GRAPH',setting)
    assert build_query_pipeline().knowledge_graph is enabled


def test_publication_graph_reads_only_current_asset_reviewed_snapshot(service,pipe,monkeypatch):
    draft_id=quality_pass(service)
    draft=service.storage.get_card_draft(draft_id)
    published_card=draft['review_flags']['publication']['card']
    seed={**published_card,'card_id':'STATIC-SEED'}
    pipe.cards=[seed]
    pipe.rows=[chunk('static-seed','card','STATIC-SEED','HPU',text=published_card['know_how'])]+[
        chunk(f'dense-{i}','source',f'manual-{i}','HPU',page=1) for i in range(35)]
    pipe.folders=np.array(['HPU']*36)
    pipe.vec=np.array([[1-i/200,0,0,0] for i in range(36)],dtype=np.float32)
    monkeypatch.setattr(pipe,'_embed',lambda q:np.array([1,0,0,0],dtype=np.float32))
    service.query_pipeline=pipe
    monkeypatch.setattr(E,'judge_dist',lambda *a,**kw:[1,0,0,0])
    before=service.query({'question':'필터 오염','equipment_id':'EQ-0001'})
    assert before['s30h_trace']['knowledge_graph']['paths']==[]
    assert service.publications.process_one(embedder=vectors,now=100)
    after=service.query({'question':'필터 오염','equipment_id':'EQ-0001'})
    assert any(p['card_id']==draft_id for p in after['s30h_trace']['knowledge_graph']['paths'])
    other=service.query({'question':'필터 오염','equipment_id':'EQ-0004'})
    assert not any(p['card_id']==draft_id for p in other['s30h_trace']['knowledge_graph']['paths'])
    service.review_card_draft(draft_id,{'action':'reject','reason':'재검토','expected_revision':2},ACTOR)
    rejected=service.query({'question':'필터 오염','equipment_id':'EQ-0001'})
    assert rejected['s30h_trace']['knowledge_graph']['paths']==[]
    assert not any(r['chunk_id'].startswith('field_') for r in pipe.rows)

def test_unversioned_stale_chunk_cannot_use_current_card_relations():
    rows=ranked_rows()
    rows[36]['text']='이전 판본의 다른 작업 절차'
    ranked,trace=graph_module().expand_ranking(rows,list(range(len(rows))),[card('A'),card('B')],
                                             'HPU','EQ-0001',top=30)
    assert trace['paths']==[] and 36 not in ranked

def test_ontology_rejects_wrong_edge_domain_and_explicit_version_is_honored():
    mod=graph_module();kg=mod.KnowledgeGraph([card('A')],'HPU','EQ-0001')
    cn=next(n for n,v in kg.nodes.items() if v['type']=='CardVersion')
    with pytest.raises(ValueError,match='domain/range'):
        kg._edge('PART_OF',cn,cn)
    rows=ranked_rows();rows[36]['text']='검수된 조각';rows[36]['metadata']['version']='v1'
    _,trace=mod.expand_ranking(rows,list(range(len(rows))),[card('A'),card('B')],'HPU','EQ-0001',top=30)
    assert trace['paths'][0]['card_id']=='B'


def test_runtime_graph_http_response_and_persisted_trace(service,pipe,monkeypatch,publication_web,tmp_path):
    from pathlib import Path
    sync_playwright = pytest.importorskip('playwright.sync_api').sync_playwright
    configure_graph_pipe(pipe,monkeypatch)
    service.query_pipeline=pipe
    monkeypatch.setattr(E,'judge_dist',lambda *a,**kw:[1,0,0,0])
    with sync_playwright() as playwright:
        import os
        channel=os.environ.get('SHIFTLINK_BROWSER_CHANNEL','chrome')
        browser=playwright.chromium.launch(headless=True,**({'channel':channel} if channel else {}))
        try:
            page=browser.new_page()
            page.goto(publication_web+'/')
            response=page.evaluate('''async () => {
                const r=await fetch('/api/query',{method:'POST',headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({question:'압력 점검',equipment_id:'EQ-0001'})});
                return {status:r.status,body:await r.json()};
            }''')
        finally:
            browser.close()
    assert response['status']==200
    result=response['body']; trace=result['s30h_trace']['knowledge_graph']
    assert [p['card_id'] for p in trace['paths']]==['B','C']
    assert result['no_knowledge']  # graph evidence still rejected by judge
    saved=service.storage.get_query(result['query_id'])['payload']
    assert saved['s30h_trace']['knowledge_graph']==trace
    (tmp_path/'browser-response.json').write_text(
        json.dumps(response,ensure_ascii=False,indent=2),encoding='utf-8')



def test_citation_paths_keep_each_cards_original_page_locator():
    kg=graph_module().KnowledgeGraph([card('A',sources=[source(locator='p.5'),source(locator='p.45')]),
        card('B',component='motor',sources=[source(locator='p.9')])],'HPU','EQ-0001')
    path=kg.neighbors('A',['B'])[0]
    assert path['edges'][0]['locators']==['p.5','p.45']
    assert path['edges'][1]['locators']==['p.9']
