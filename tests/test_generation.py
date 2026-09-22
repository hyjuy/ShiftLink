import hashlib
import json
import sqlite3
import sys

import pytest

from shiftlink.data.generation import generate_draft


def inputs():
    text = 'A noise change requires further observation; noise alone is not a diagnosis.'
    scope = dict(scope_id='noise', locator='section 1', document_version='test-v1',
                 text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                 allowed_claims=['Noise is an observation, not a diagnosis.'], exclusions=[],
                 reviewed_by='test-reviewer', reviewed_at='2026-09-22T00:00:00Z',
                 use_scope='Synthetic test only', kind='background')
    registry = dict(registry_version='1', sources=[dict(source_id='TEST-001',
                    review_status='approved_for_draft', approved_scope=[scope])])
    policy = dict(policy_version='1', assignments=[dict(group_id='PT-0003', split='kb')])
    request = dict(card_id='K-9001', version='test-v1', group_id='PT-0003',
                   persona_id='test-author', model_version='test-model',
                   confidence=0.4, confidence_basis='Reviewer-supplied test estimate',
                   excerpts=[dict(evidence_id='E1', source_id='TEST-001', scope_id='noise', text=text)])
    card = dict(tacit_type='T1', equipment='HPU', component='pump', scenario='S1',
                title='Noise observation', symptom='Noise changed',
                know_how='Gather further observations', rationale='Noise alone cannot diagnose damage')
    response = dict(card=card, evidence={f'/{k}':['E1'] for k in
                    ('component', 'title', 'symptom', 'know_how', 'rationale')})
    return request, registry, policy, response


def run(tmp_path, mutate=None, model=None):
    request, registry, policy, response = inputs()
    if mutate:
        mutate(request, registry, policy, response)
    calls = []
    def generate(prompt):
        calls.append(prompt)
        return model(prompt) if model else json.dumps(response)
    result = generate_draft(request, registry=registry, policy=policy,
                            generate=generate, database=tmp_path/'drafts.sqlite3')
    return result, calls


def test_draft_roundtrip_and_no_automatic_kb_adoption(tmp_path):
    from shiftlink.agent.schemas import KnowledgeCard
    from shiftlink.rag.retrieval import InMemoryToolProvider
    result, calls = run(tmp_path)
    assert result['status'] == 'draft_saved'
    assert len(calls) == 1
    with sqlite3.connect(tmp_path/'drafts.sqlite3') as db:
        card = KnowledgeCard.model_validate_json(db.execute('SELECT card_json FROM drafts').fetchone()[0])
        audit = json.loads(db.execute('SELECT audit_json FROM generation_runs').fetchone()[0])
    assert (card.status, card.grade, card.split) == ('draft', 'L0', 'kb')
    assert card.provenance.sources[0].locator == 'section 1'
    assert card.provenance.model_version == 'test-model'
    assert audit['evidence']['/know_how'] == ['E1']
    assert audit['human_review_required'] is True
    assert InMemoryToolProvider([card]).cards == []


@pytest.mark.parametrize('change', ['pending', 'hash', 'sealed', 'unknown_group', 'extra_input', 'case_group'])
def test_preflight_blocks_before_model(tmp_path, change):
    def mutate(q, r, p, output):
        if change == 'pending': r['sources'][0]['review_status'] = 'pending_review'
        if change == 'hash': q['excerpts'][0]['text'] += ' altered'
        if change == 'sealed': p['assignments'][0]['split'] = 'sealed'
        if change == 'unknown_group': q['group_id'] = 'unknown'
        if change == 'extra_input': q['true_cause'] = 'heldout answer'
        if change == 'case_group':
            r['sources'][0]['approved_scope'][0].update(kind='case', group_id='other')
    result, calls = run(tmp_path, mutate)
    assert result['status'] == 'needs_review'
    assert calls == []
    with sqlite3.connect(tmp_path/'drafts.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM drafts').fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM generation_runs').fetchone()[0] == 1


@pytest.mark.parametrize('change', ['missing_evidence', 'invented_evidence', 'extra_pointer',
    'invalid_schema', 'auto_approve', 'invented_event', 'unknown_field', 'nested_unknown'])
def test_bad_output_is_queued_not_saved(tmp_path, change):
    def mutate(q, r, p, o):
        if change == 'missing_evidence': del o['evidence']['/know_how']
        if change == 'invented_evidence': o['evidence']['/know_how'] = ['FAKE']
        if change == 'extra_pointer': o['evidence']['/nonexistent'] = ['E1']
        if change == 'invalid_schema': o['card']['symptom'] = ' '
        if change == 'auto_approve': o['card']['status'] = 'accepted'
        if change == 'unknown_field': o['card']['invented'] = True
        if change == 'nested_unknown': o['card']['type_payload'] = {'unexpected': 'ignored?'}
        if change == 'invented_event':
            o['card']['generalization_evidence'] = {'supporting_event_ids':['EV-9999']}
            o['evidence']['/generalization_evidence/supporting_event_ids/0'] = ['E1']
    result, calls = run(tmp_path, mutate)
    assert result['status'] == 'needs_review'
    assert len(calls) == 1
    with sqlite3.connect(tmp_path/'drafts.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM drafts').fetchone()[0] == 0


def test_duplicate_does_not_overwrite(tmp_path):
    assert run(tmp_path)[0]['status'] == 'draft_saved'
    assert run(tmp_path)[0]['status'] == 'needs_review'
    with sqlite3.connect(tmp_path/'drafts.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM drafts').fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM generation_runs').fetchone()[0] == 2


@pytest.mark.parametrize('bad', ['not JSON', '{"card":{},"card":{}}'])
def test_invalid_json_is_queued(tmp_path, bad):
    assert run(tmp_path, model=lambda prompt: bad)[0]['status'] == 'needs_review'


def test_model_failure_is_queued_without_exception_secrets(tmp_path):
    def failure(prompt):
        raise RuntimeError('secret connection details')
    result, _ = run(tmp_path, model=failure)
    assert result['status'] == 'needs_review'
    assert 'secret' not in json.dumps(result)


def test_dev_split_inherited(tmp_path):
    result, _ = run(tmp_path, lambda q, r, p, o: p['assignments'][0].update(split='dev'))
    assert result['status'] == 'draft_saved'
    with sqlite3.connect(tmp_path/'drafts.sqlite3') as db:
        assert json.loads(db.execute('SELECT card_json FROM drafts').fetchone()[0])['split'] == 'dev'


def test_cli_command_end_to_end(tmp_path, capsys):
    from shiftlink.data.generation import main
    q, registry, policy, response = inputs()
    for name, value in [('request',q), ('registry',registry), ('policy',policy), ('response',response)]:
        (tmp_path/f'{name}.json').write_text(json.dumps(value), encoding='utf-8')
    adapter = tmp_path/'adapter.py'
    adapter.write_text(
        'import sys, json, pathlib\n'
        'prompt = sys.stdin.buffer.read().decode("utf-8")\n'
        'assert "TEST-001" in prompt and "evidence_ids" in prompt\n'
        'sys.stdout.buffer.write(pathlib.Path(sys.argv[1]).read_bytes())\n', encoding='utf-8')
    args = ['--request',str(tmp_path/'request.json'),'--registry',str(tmp_path/'registry.json'),
            '--splits',str(tmp_path/'policy.json'),'--database',str(tmp_path/'cli.sqlite3')]
    assert main(args + ['--generator-command',sys.executable,str(adapter),str(tmp_path/'response.json')]) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'draft_saved'
    # Re-import cannot overwrite; the failed attempt remains inspectable.
    assert main(args + ['--candidate',str(tmp_path/'response.json')]) == 1
    assert json.loads(capsys.readouterr().out)['stage'] == 'storage'
    (tmp_path/'request.json').write_text('invalid JSON', encoding='utf-8')
    assert main(args + ['--candidate',str(tmp_path/'response.json')]) == 2
    assert json.loads(capsys.readouterr().out)['status'] == 'failed'


@pytest.mark.parametrize('change', ['duplicate_source','duplicate_group','duplicate_excerpt',
    'scope_missing','scope_blank','reference_background','reference_generated','policy_version',
    'blank_title','confidence_basis','empty_links','duplicate_links','no_links'])
def test_additional_boundary_failures(tmp_path, change):
    def mutate(q,r,p,o):
        scope = r['sources'][0]['approved_scope'][0]
        if change == 'duplicate_source': r['sources'].append(r['sources'][0])
        if change == 'duplicate_group': p['assignments'].append(p['assignments'][0])
        if change == 'duplicate_excerpt': q['excerpts'].append(q['excerpts'][0])
        if change == 'scope_missing': q['excerpts'][0]['scope_id'] = 'missing'
        if change == 'scope_blank': scope['reviewed_by'] = ' '
        if change == 'reference_background': scope['reference_ids'] = ['EV-0001']
        if change == 'reference_generated': scope.update(kind='case',group_id='PT-0003',reference_ids=['K-0001'])
        if change == 'policy_version': p['policy_version'] = '999'
        if change == 'blank_title': o['card']['title'] = ' '
        if change == 'confidence_basis':
            o['card']['generalization_evidence'] = {'confidence_basis':'Invented certainty'}
            o['evidence']['/generalization_evidence/confidence_basis'] = ['E1']
        if change == 'empty_links': o['evidence']['/know_how'] = []
        if change == 'duplicate_links': o['evidence']['/know_how'] = ['E1','E1']
        if change == 'no_links': o.update(card={},evidence={})
    assert run(tmp_path, mutate)[0]['status'] == 'needs_review'


def test_reviewed_case_references_and_t3_steps(tmp_path):
    def mutate(q,r,p,o):
        r['sources'][0]['approved_scope'][0].update(kind='case',group_id='PT-0003',
                                                   reference_ids=['EV-9001','AR-9001'])
        o['card'].update(tacit_type='T3', type_payload={
            'steps':[{'step_id':'ST-01','order':1,'action':'Observe noise','expected_result':'Record observation'}],
            'tried_and_failed':[{'attempt_id':'AT-9001','restart_type':'unknown','action':'Observed',
                                 'observed_result':'Inconclusive','evidence_ids':['AR-9001']}]},
            generalization_evidence={'supporting_event_ids':['EV-9001']})
        for path in ('type_payload/steps/0/step_id','type_payload/steps/0/order',
            'type_payload/steps/0/action','type_payload/steps/0/expected_result',
            'type_payload/tried_and_failed/0/attempt_id','type_payload/tried_and_failed/0/restart_type',
            'type_payload/tried_and_failed/0/action','type_payload/tried_and_failed/0/observed_result',
            'type_payload/tried_and_failed/0/evidence_ids/0','generalization_evidence/supporting_event_ids/0'):
            o['evidence']['/'+path] = ['E1']
    result,_=run(tmp_path,mutate)
    assert result['status']=='draft_saved'


def test_current_registry_remains_unapproved(tmp_path):
    from pathlib import Path
    request,_,policy,_=inputs()
    registry=json.loads(Path('seeds/source_registry.json').read_text(encoding='utf-8'))
    request['excerpts'][0]['source_id']='SD-001'
    result=generate_draft(request, registry=registry, policy=policy,
                          generate=lambda _: pytest.fail('Must not call a model'),
                          database=tmp_path/'blocked.sqlite3')
    assert result['stage']=='preflight' and result['status']=='needs_review'


def test_storage_failure_rolls_back_draft(tmp_path):
    run(tmp_path)
    with sqlite3.connect(tmp_path/'drafts.sqlite3') as db:
        db.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON generation_runs "
                   "BEGIN SELECT RAISE(ABORT, 'test storage failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        run(tmp_path, lambda q,r,p,o: q.update(card_id='K-9002'))
    with sqlite3.connect(tmp_path/'drafts.sqlite3') as db:
        assert db.execute('SELECT card_id FROM drafts').fetchall()==[('K-9001',)]
        assert db.execute('SELECT count(*) FROM generation_runs').fetchone()[0]==1


def test_concurrent_duplicate_keeps_one_draft_and_two_audits(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(lambda _: run(tmp_path)[0]['status'], range(2)))
    assert sorted(outcomes)==['draft_saved','needs_review']
    with sqlite3.connect(tmp_path/'drafts.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM drafts').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM generation_runs').fetchone()[0]==2
