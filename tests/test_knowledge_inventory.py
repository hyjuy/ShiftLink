"""Jetson inventory reconciled with main publication lifecycle; no live model."""
from copy import deepcopy
from urllib.error import HTTPError

import pytest
from test_work_report_reuse_harness import service
from test_candidate_management import review_api
from test_knowledge_publication import decide
from test_publication_worker import vectors
from shiftlink.mes.storage import MesStorage
from shiftlink.mes.server import kb_cards


def test_inventory_sync_is_validated_idempotent_and_durable(tmp_path):
    path=tmp_path/'inventory.sqlite3';store=MesStorage(path)
    card=deepcopy(kb_cards()['cards'][0])
    try:
        store.sync_knowledge_cards([card])
        row=tuple(store.connection.execute('SELECT payload,updated_at FROM knowledge_cards').fetchone())
        store.sync_knowledge_cards([card])
        assert tuple(store.connection.execute('SELECT payload,updated_at FROM knowledge_cards').fetchone())==row
        for bad in [{**card,'status':'draft'}, {**card,'grade':'L0'}, {**card,'split':'dev'}]:
            with pytest.raises(ValueError):store.sync_knowledge_cards([bad])
        with pytest.raises(ValueError):store.sync_knowledge_cards([card,card])
        assert store.list_knowledge_cards()==[card]
    finally:store.close()
    reopened=MesStorage(path)
    try:assert reopened.list_knowledge_cards()==[card]
    finally:reopened.close()


def test_inventory_is_not_a_publication_shortcut(service,review_api):
    request,token,draft_id,_=review_api
    original=deepcopy(service.storage.get_card_draft(draft_id)['card'])
    data=request('/api/knowledge-cards')
    assert data['cards']==service.storage.list_knowledge_cards()
    assert len(data['cards'])==86 and data['summary']['pending_review']==1
    assert draft_id not in {c['card_id'] for c in data['cards']}
    decide(request,token,draft_id,'approve',0)
    data=request('/api/knowledge-cards')
    assert data['summary']['review_approved']==1
    assert service.storage.get_card_draft(draft_id)['card']==original
    decide(request,token,draft_id,'quality_pass',1)
    data=request('/api/knowledge-cards')
    assert data['summary']['quality_passed']==1 and data['summary']['published']==86
    draft=next(d for d in data['drafts'] if d['draft_id']==draft_id)
    assert draft['review_flags']['publication']['state']=='embedding_pending'
    assert draft['review_flags']['publication']['searchable'] is False
    assert service.publications.process_one(embedder=vectors)
    data=request('/api/knowledge-cards')
    draft=next(d for d in data['drafts'] if d['draft_id']==draft_id)
    assert draft['review_flags']['publication']['state']=='published'
    assert draft['review_flags']['publication']['searchable'] is True
    assert data['summary']['published']==86
    decide(request,token,draft_id,'request_changes',2)
    data=request('/api/knowledge-cards')
    assert data['summary']['changes_requested']==1 and data['summary']['quality_passed']==0
    assert service.storage.get_card_draft(draft_id)['card']==original


def test_inventory_ignores_obsolete_static_rows(service,monkeypatch):
    import shiftlink.mes.server as server
    cards=deepcopy(kb_cards()['cards'])
    monkeypatch.setattr(server,'kb_cards',lambda:{'cards':cards[1:],'is_synthetic':True})
    result=service.knowledge_inventory()
    assert result['summary']['published']==85
    assert cards[0]['card_id'] not in {c['card_id'] for c in result['cards']}
    assert len(service.storage.list_knowledge_cards())==86


def test_pda_serve_switch_does_not_disable_knowledge_api(review_api,monkeypatch):
    request,_,_,_=review_api
    monkeypatch.setenv('SHIFTLINK_SERVE_PDA','0')
    for path in ['/pda.html','/static/pda.js']:
        with pytest.raises(HTTPError) as caught:request(path)
        assert caught.value.code==404
    assert request('/api/knowledge-cards')['summary']['published']==86
