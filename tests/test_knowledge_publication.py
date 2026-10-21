"""Quality approval prepares a durable artifact but cannot publish it to RAG."""
from copy import deepcopy
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

from test_candidate_management import review_api
from test_work_report_reuse_harness import service
from shiftlink.agent.schemas import KnowledgeCard
from shiftlink.mes.storage import MesStorage


def decide(request, token, draft_id, action, revision, reason='근거·조건·조치 결과 검수 완료'):
    return request('/api/admin/card-drafts/'+draft_id+'/review', {
        'action': action, 'reason': reason, 'expected_revision': revision}, token)['draft']


def test_quality_pass_structures_without_publishing_and_survives_restart(service, review_api):
    request, token, draft_id, _ = review_api
    original = deepcopy(service.storage.get_card_draft(draft_id))
    source = deepcopy(service.storage.get_handover(original['handover_id']))
    approved = decide(request, token, draft_id, 'approve', 0)
    assert 'publication' not in approved['review_flags']
    checked = decide(request, token, draft_id, 'quality_pass', 1)
    assert checked['status'] == 'quality_passed' and checked['revision'] == 2
    artifact = checked['review_flags']['publication']
    assert artifact['state'] == 'embedding_pending' and artifact['searchable'] is False
    assert artifact['review_revision'] == 2 and artifact['quality_checked_by'] == 'reviewer'
    card = KnowledgeCard.model_validate(artifact['card'])
    assert (card.status, card.grade, card.split) == ('accepted', 'L1', 'kb')
    assert card.card_id == original['card']['card_id']
    assert card.provenance == KnowledgeCard.model_validate(original['card']).provenance
    assert checked['card'] == original['card']
    assert service.storage.get_handover(original['handover_id']) == source
    assert card.know_how in artifact['embed_text']
    assert len(artifact['content_hash']) == 64
    assert checked['reviews'][-1]['action'] == 'quality_pass'
    path = Path(service.storage.connection.execute('PRAGMA database_list').fetchone()[2])
    reopened = MesStorage(path)
    try:
        assert reopened.get_card_draft(draft_id) == {key:value for key,value in checked.items() if key != 'sources'}
    finally:
        reopened.close()


@pytest.mark.parametrize('initial_action', [None, 'request_changes', 'reject'])
def test_quality_pass_requires_current_review_approval(service, review_api, initial_action):
    request, token, draft_id, _ = review_api
    revision = 0
    if initial_action:
        decide(request, token, draft_id, initial_action, 0)
        revision = 1
    before = service.storage.get_card_draft(draft_id)
    with pytest.raises(HTTPError) as error:
        decide(request, token, draft_id, 'quality_pass', revision)
    assert error.value.code == 400
    assert service.storage.get_card_draft(draft_id) == before


def test_quality_pass_requires_reason_admin_and_current_revision(service, review_api):
    request, token, draft_id, _ = review_api
    decide(request, token, draft_id, 'approve', 0)
    for auth, revision, reason, status in [(None,1,'검수',401),(token,1,' ',400),(token,0,'검수',409)]:
        with pytest.raises(HTTPError) as error:
            decide(request, auth, draft_id, 'quality_pass', revision, reason)
        assert error.value.code == status
    assert service.storage.get_card_draft(draft_id)['revision'] == 1


@pytest.mark.parametrize('bad_card', ['missing_steps', 'unknown_key'])
def test_schema_failure_leaves_approval_and_audit_unchanged(service, review_api, bad_card):
    request, token, draft_id, _ = review_api
    decide(request, token, draft_id, 'approve', 0)
    draft = service.storage.get_card_draft(draft_id)
    card = draft['card']
    if bad_card == 'missing_steps':
        card['type_payload']['steps'] = []
    else:
        card['invented_field'] = 'must not be silently dropped'
    with service.storage.connection:
        service.storage.connection.execute('UPDATE card_drafts SET card=? WHERE draft_id=?', (json.dumps(card),draft_id))
    before = service.storage.get_card_draft(draft_id)
    with pytest.raises(HTTPError) as error:
        decide(request, token, draft_id, 'quality_pass', 1)
    assert error.value.code == 400
    assert service.storage.get_card_draft(draft_id) == before


@pytest.mark.parametrize('action', ['approve', 'request_changes', 'reject'])
def test_re_review_invalidates_prepared_artifact(service, review_api, action):
    request, token, draft_id, _ = review_api
    decide(request, token, draft_id, 'approve', 0)
    prepared = decide(request, token, draft_id, 'quality_pass', 1)
    revised = decide(request, token, draft_id, action, 2)
    artifact = revised['review_flags']['publication']
    assert artifact['state'] == 'superseded' and artifact['searchable'] is False
    assert artifact['content_hash'] == prepared['review_flags']['publication']['content_hash']


def test_quality_artifact_and_audit_roll_back_together(service, review_api):
    request, token, draft_id, _ = review_api
    decide(request, token, draft_id, 'approve', 0)
    before = service.storage.get_card_draft(draft_id)
    service.storage.connection.execute("CREATE TRIGGER fail_quality BEFORE INSERT ON card_draft_reviews "
        "WHEN NEW.action='quality_pass' BEGIN SELECT RAISE(ABORT, 'test audit unavailable'); END")
    with pytest.raises(HTTPError) as error:
        decide(request, token, draft_id, 'quality_pass', 1)
    assert error.value.code == 500
    assert service.storage.get_card_draft(draft_id) == before


def test_repeated_quality_pass_needs_new_approval_and_keeps_content_hash(service, review_api):
    request, token, draft_id, _ = review_api
    decide(request, token, draft_id, 'approve', 0)
    first = decide(request, token, draft_id, 'quality_pass', 1)['review_flags']['publication']
    with pytest.raises(HTTPError) as error:
        decide(request, token, draft_id, 'quality_pass', 2)
    assert error.value.code == 400
    decide(request, token, draft_id, 'approve', 2)
    second = decide(request, token, draft_id, 'quality_pass', 3)['review_flags']['publication']
    assert first['content_hash'] == second['content_hash']
    assert first['embed_text'] == second['embed_text']
    assert second['review_revision'] == 4
