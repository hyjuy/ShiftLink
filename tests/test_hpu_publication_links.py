"""Only actual, still-current citations may describe their original HPU incident."""
from copy import deepcopy
import json
import sqlite3

import pytest

from shiftlink.mes import publication_ontology
from shiftlink.agent.pipeline import JudgeUnavailableError
from test_ontology_api import api, arguments, service, bundle, default_off
from test_publication_worker import ACTOR, vectors


@pytest.fixture
def published(api, service, bundle, monkeypatch):
    monkeypatch.setenv('SHIFTLINK_HPU_ONTOLOGY','explain')
    did=service.storage.list_card_drafts()[0]['draft_id']
    for revision, action in enumerate(('approve','quality_pass')):
        service.review_card_draft(did, {'action':action,'reason':'원문 확인','expected_revision':revision}, ACTOR)
    assert service.publications.process_one(embedder=vectors)
    request={'question':'필터 오염 확인 필터 교체 압력','equipment_id':'EQ-0001',
             'incident_id':bundle['incident']['incident_id']}
    result=service.query(request)
    assert result['cited_card_ids']==[did]
    return did, result, request


def cards(graph):
    return [n for n in graph['nodes'] if n['type']=='CardVersion']


def test_publication_link_is_opt_in_actual_citation_and_preserves_sources(api, published, service):
    did, result, request=published
    before=list(service.storage.connection.iterdump())
    status, base=api[0]()
    assert status==200 and not cards(base)
    status, graph=api[0]('?query_id='+result['query_id'])
    assert status==200 and len(cards(graph))==1
    assert cards(graph)[0]['properties']['card_id']==did
    edge,=[e for e in graph['edges'] if e['type']=='DERIVED_FROM_INCIDENT']
    assert edge['source']==cards(graph)[0]['id']
    assert edge['target'] in {n['id'] for n in graph['nodes'] if n['type']=='Incident'}
    assert edge['provenance']['query_id']==result['query_id']
    assert graph['snapshot_hash']!=base['snapshot_hash']
    assert list(service.storage.connection.iterdump())==before
    assert 'publication_overlay' not in result


def test_before_publication_or_without_citation_never_links(api, bundle, monkeypatch):
    monkeypatch.setenv('SHIFTLINK_HPU_ONTOLOGY','explain')
    qid=bundle['queries'][0]['query_id']
    status, graph=api[0]('?query_id='+qid)
    assert status==200 and not cards(graph)
    assert graph['publication_overlay']['card_ids']==[]
    assert api[0]('?query_id=missing')[0]==404


def test_rejection_removes_links_but_preserves_old_answer_and_source(api, published, service):
    did, result, request=published
    old=deepcopy(service.storage.get_query(result['query_id']))
    _, graph=api[0]('?query_id='+result['query_id'])
    service.review_card_draft(did,{'action':'reject','reason':'반례','expected_revision':2},ACTOR)
    status, rejected=api[0]('?query_id='+result['query_id'])
    assert status==200 and not cards(rejected)
    assert any(r['reason']=='publication_not_current' for r in rejected['unresolved'])
    assert service.storage.get_query(result['query_id'])==old
    assert api[0]('?query_id='+result['query_id']+'&snapshot_hash='+graph['snapshot_hash'])[0]==409
    assert not service.query(request)['cited_card_ids']


def test_rejection_during_query_keeps_existing_final_ticket_guard(api, published, service, monkeypatch):
    did, result, request=published
    original=service.query_pipeline.run
    def reject(payload):
        output=original(payload)
        service.review_card_draft(did,{'action':'reject','reason':'질의 중 변경','expected_revision':2},ACTOR)
        return output
    monkeypatch.setattr(service.query_pipeline,'run',reject)
    with pytest.raises(JudgeUnavailableError): service.query(request)
    assert not cards(api[0]('?query_id='+result['query_id'])[1])


def test_rejection_during_projection_rechecks_ticket(api, published, service, monkeypatch):
    did, result, _=published
    original=publication_ontology.add_links
    changed=[]
    def reject(*args, **kwargs):
        graph=original(*args, **kwargs)
        if not changed:
            changed.append(True)
            service.review_card_draft(did,{'action':'reject','reason':'설명 중 변경','expected_revision':2},ACTOR)
        return graph
    monkeypatch.setattr(publication_ontology,'add_links',reject)
    status, graph=api[0]('?query_id='+result['query_id'])
    assert status==200 and not cards(graph)
    assert any(r['reason']=='publication_changed' for r in graph['unresolved'])


def test_changed_index_is_excluded_without_repairing_or_writing(api, published, service):
    did, result, _=published
    con=service.storage.connection
    row=con.execute('SELECT payload FROM knowledge_publications WHERE draft_id=?',(did,)).fetchone()
    payload=json.loads(row[0]);payload['chunks'][0]['text']='tampered'
    with con: con.execute('UPDATE knowledge_publications SET payload=? WHERE draft_id=?',(json.dumps(payload),did))
    before=list(con.iterdump())
    status, graph=api[0]('?query_id='+result['query_id'])
    assert status==200 and not cards(graph)
    assert any(r['reason']=='publication_integrity_mismatch' for r in graph['unresolved'])
    assert list(con.iterdump())==before


def test_approved_copy_must_match_live_query(api, published, service, tmp_path, monkeypatch):
    _, result, _=published
    path=tmp_path/'approved.sqlite3'
    with sqlite3.connect(path) as copy: service.storage.connection.backup(copy)
    monkeypatch.setenv('SHIFTLINK_HPU_ONTOLOGY_DB',str(path))
    assert cards(api[0]('?query_id='+result['query_id'])[1])
    with sqlite3.connect(path) as copy:
        copy.execute("UPDATE query_log SET payload=json_set(payload,'$.answer','different') WHERE query_id=?",(result['query_id'],))
    status, graph=api[0]('?query_id='+result['query_id'])
    assert status==200 and not cards(graph)
    assert any(r['reason']=='query_source_mismatch' for r in graph['unresolved'])


def test_later_review_cannot_relabel_old_citation_as_new_revision(api, published, service):
    did, result, _=published
    for revision, action in ((2,'reject'),(3,'approve'),(4,'quality_pass')):
        service.review_card_draft(did,{'action':action,'reason':'새 검수','expected_revision':revision},ACTOR)
    assert service.publications.process_one(embedder=vectors)
    status, graph=api[0]('?query_id='+result['query_id'])
    assert status==200 and not cards(graph)
    assert any(r['reason']=='citation_revision_unverified' for r in graph['unresolved'])


def test_legacy_citation_without_exact_ticket_is_not_inferred(api, published, service):
    _, result, _=published
    con=service.storage.connection
    with con:
        con.execute("UPDATE query_log SET payload=json_remove(payload,'$.publication_ticket') WHERE query_id=?",(result['query_id'],))
    status, graph=api[0]('?query_id='+result['query_id'])
    assert status==200 and not cards(graph)
    assert any(r['reason']=='citation_revision_unverified' for r in graph['unresolved'])


@pytest.mark.parametrize('change', ['asset','origin','report_copy'])
def test_asset_and_origin_boundaries(api, published, service, tmp_path, monkeypatch, change):
    from dataclasses import replace
    did, result, _=published
    if change=='asset':
        eq=service.active_config.equipment[0]
        service.active_config=replace(service.active_config,equipment=(replace(eq,asset_id='replacement'),*service.active_config.equipment[1:]))
    elif change=='origin':
        draft=service.storage.get_card_draft(did)
        draft['review_flags']['work_report']['incident_id']='another-incident'
        with service.storage.connection:
            service.storage.connection.execute('UPDATE card_drafts SET review_flags=? WHERE draft_id=?',(json.dumps(draft['review_flags']),did))
    else:
        path=tmp_path/'source.sqlite3'
        with sqlite3.connect(path) as con:
            service.storage.connection.backup(con)
            con.execute("UPDATE handover_outbox SET payload=json_set(payload,'$.work_report.records[0].story','changed source')")
        monkeypatch.setenv('SHIFTLINK_HPU_ONTOLOGY_DB',str(path))
    status, graph=api[0]('?query_id='+result['query_id'])
    assert status==200 and not cards(graph)
    assert any(r['reason'] in {'publication_not_current','publication_origin_mismatch'} for r in graph['unresolved'])


def test_query_inputs_and_answers_are_identical_across_modes(api, published, service, monkeypatch):
    _, _, request=published
    calls=[]
    original=type(service.query_pipeline).run
    def capture(pipeline, payload):
        calls.append(deepcopy(payload))
        return original(pipeline, payload)
    monkeypatch.setattr(type(service.query_pipeline),'run',capture)
    results=[]
    for mode in ('off','shadow','explain'):
        monkeypatch.setenv('SHIFTLINK_HPU_ONTOLOGY',mode)
        result=service.query(request)
        results.append({k:v for k,v in result.items() if k!='query_id'})
        saved=service.storage.get_query(result['query_id'])['payload']
        assert saved['publication_ticket']
        assert 'publication_ticket' not in result and 'publication_overlay' not in result
    assert calls[0]==calls[1]==calls[2]
    assert results[0]==results[1]==results[2]


def test_origin_record_hash_must_match_the_projected_snapshot(api, published, monkeypatch):
    from shiftlink.mes import ontology_api
    _, result, _=published
    original=ontology_api.run_shadow
    def changed(*args, **kwargs):
        output=original(*args, **kwargs)
        for node in output['graph']['nodes']:
            if node['provenance']['source_ref']['kind']=='report':
                node['provenance']['source_hash']='different-record-revision'
        return output
    monkeypatch.setattr(ontology_api,'run_shadow',changed)
    status, graph=api[0]('?query_id='+result['query_id'])
    assert status==200 and not cards(graph)
    assert any(r['reason']=='publication_origin_mismatch' for r in graph['unresolved'])
