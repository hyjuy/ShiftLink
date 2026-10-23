"""Test the verifier, not a claim that the unchanged application passes its challenge."""
from copy import deepcopy
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

from shiftlink.rag2 import field_history as F

ROOT = Path(__file__).resolve().parents[1]
HARNESS = runpy.run_path(str(ROOT / 'scripts/check_knowledge_publication.py'))


@pytest.mark.parametrize('damage', ['duplicate', 'oracle', 'role', 'type', 'missing-old-question'])
def test_integration_matrix_cannot_drop_or_relabel_preservation_cases(tmp_path, damage):
    cases = deepcopy(HARNESS['load_history_cases'](ROOT, profile='integration'))
    if damage == 'duplicate':
        cases[-1] = deepcopy(cases[0])
    elif damage == 'oracle':
        cases[0]['oracle'] = ''
    elif damage == 'role':
        cases[0]['preserve_main_request'] = cases[0]['history']
    elif damage == 'type':
        cases[0] = None
    else:
        cases[0]['question'] = 'replacement with the same row count'
    for path, data in [(HARNESS['INTEGRATION_CASES'], cases),
                       (HARNESS['HISTORY_CASES'], HARNESS['load_history_cases'](ROOT))]:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError):
        HARNESS['load_history_cases'](tmp_path, profile='integration')


@pytest.mark.parametrize('role', ['preserve_main_request', 'preserve_local_history'])
def test_integration_total_cannot_hide_a_preservation_regression(role):
    cases = HARNESS['load_history_cases'](ROOT, profile='integration')
    oracle = {c['question']: c['history'] for c in cases}
    witness = next(c for c in cases if c[role])
    report = HARNESS['evaluate_history'](ROOT, profile='integration', classifier=lambda q:
        not oracle[q] if q == witness['question'] else oracle[q])
    key = 'main_current_requests' if role == 'preserve_main_request' else 'local_verbatim_history'
    assert report['passed'] == 282 and not report['ok']
    assert report['preservation_failures'][key] == [witness['id']]
    assert report['subject'] == 'injected_classifier'


def test_scope_profiles_cover_named_boundaries():
    cases = HARNESS['load_history_cases'](ROOT)
    assert len(cases) == 30
    assert {c['family'] for c in cases} == {
        'history-control', 'request-control', 'mixed-action', 'mixed-safety',
        'future-markers', 'past-report-synonym'}
    for profile in ('minimal', 'adversarial', 'full'):
        selected = [c for c in cases if profile in c['profiles']]
        assert {c['history'] for c in selected} == {True, False}
        assert {'mixed-action', 'mixed-safety'} <= {c['family'] for c in selected}


@pytest.mark.parametrize('damage', ['duplicate', 'empty', 'boolean', 'oracle', 'profile'])
def test_scope_matrix_rejects_invalid_oracles(tmp_path, damage):
    cases = deepcopy(HARNESS['load_history_cases'](ROOT))
    if damage == 'duplicate':
        cases.append(cases[0])
    elif damage == 'empty':
        cases = []
    elif damage == 'boolean':
        cases[0]['history'] = 'false'
    elif damage == 'oracle':
        cases[0]['oracle'] = ''
    else:
        cases[0]['profiles'] = ['typo']
    target = tmp_path / HARNESS['HISTORY_CASES']
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(cases), encoding='utf-8')
    with pytest.raises(ValueError):
        HARNESS['load_history_cases'](tmp_path)


def test_perfect_oracle_is_only_a_verifier_control():
    cases = HARNESS['load_history_cases'](ROOT)
    oracle = {c['question']: c['history'] for c in cases}
    report = HARNESS['evaluate_history'](ROOT, classifier=oracle.__getitem__)
    assert report['ok'] and report['passed'] == report['total'] == 30
    assert report['subject'] == 'injected_classifier'
    assert report['semantic_failed'] == 0


@pytest.mark.parametrize('mutant', ['always-history', 'always-current', 'drop-request',
                                   'unshield-quote', 'drop-mes-request', 'swallow-future'])
def test_semantic_oracle_kills_mutants_without_baseline_failure_credit(mutant):
    cases = HARNESS['load_history_cases'](ROOT)
    oracle = {c['question']: c['history'] for c in cases}
    target = {'drop-request': 'mixed-action-quote-0',
              'unshield-quote': 'quoted-today',
              'drop-mes-request': 'current-permission',
              'swallow-future': 'future-control'}.get(mutant)
    def broken(question):
        if mutant == 'always-history':
            return True
        if mutant == 'always-current':
            return False
        case = next(c for c in cases if c['question'] == question)
        return not oracle[question] if case['id'] == target else oracle[question]
    report = HARNESS['evaluate_history'](ROOT, classifier=broken)
    assert not report['ok'] and report['semantic_failed'] > 0
    if target:
        assert [r['id'] for r in report['results'] if not r['passed']] == [target]


def test_known_failure_never_becomes_semantic_success():
    cases = HARNESS['load_history_cases'](ROOT)
    oracle = {c['question']: c['history'] for c in cases}
    target = next(c for c in cases if c['known_issue'])
    report = HARNESS['evaluate_history'](ROOT, classifier=lambda q:
        not oracle[q] if q == target['question'] else oracle[q])
    assert not report['ok'] and report['decision'] == 'blocked'
    assert report['known_failed'] == report['semantic_failed'] == 1


def test_classifier_error_is_not_a_known_semantic_failure():
    def broken(_):
        raise RuntimeError('deliberate verifier control')
    report = HARNESS['evaluate_history'](ROOT, profile='minimal', classifier=broken)
    assert not report['ok'] and report['unexpected_failed'] == report['total']
    assert report['known_failed'] == 0


def test_scope_cli_exit_matches_real_semantic_report():
    command = [sys.executable, '-X', 'utf8', '-B',
               str(ROOT / 'scripts/check_knowledge_publication.py'), '--history-scope', 'minimal']
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    report = json.loads(result.stdout)
    assert result.returncode == (0 if report['ok'] else 1)
    assert report['ok'] == (report['semantic_failed'] == 0)
    assert report['subject'] == 'runtime'
    assert report['total'] == 7 and report['classification_only']


@pytest.mark.parametrize('mutant', ['always-history', 'always-current', 'swallow-followup', 'global-current'])
def test_real_classifier_mutations_need_additional_baseline_pass_witnesses(mutant):
    before = HARNESS['evaluate_history'](ROOT)
    def broken(question):
        if mutant == 'always-history':
            return True
        if mutant == 'always-current':
            return False
        if mutant == 'global-current' and ('지금' in question or '현재' in question):
            return False
        if mutant == 'swallow-followup' and '라고 기록한' in question:
            question = question.split('라고 기록한')[0] + '라고 기록한 시각과 결과만 알려줘'
        return F.is_history_question(question)
    after = HARNESS['evaluate_history'](ROOT, classifier=broken)
    clean = {r['id'] for r in before['results'] if r['passed']}
    witnesses = [r['id'] for r in after['results'] if r['id'] in clean and not r['passed']]
    assert witnesses, 'Existing semantic failures cannot earn mutation credit'


@pytest.mark.parametrize('mutant', ['admit-invalid', 'suffix-duration', 'mutate-source', 'truncate-source'])
def test_record_mutations_need_additional_baseline_pass_witnesses(mutant):
    def observe(fn):
        results = {}
        for name, question, kept, expected, equipment in [
            ('valid', '137분 결과', True, True, 'EQ-0001'),
            ('wrong-duration', '37분 결과', True, False, 'EQ-0001'),
            ('judge-rejected', '137분 결과', False, False, 'EQ-0001'),
            ('other-asset', '137분 결과', True, False, 'EQ-9999')]:
            card = {'card_id': 'K-MUTATION', 'mes_equipment_id': 'EQ-0001',
                    'status': 'accepted', 'grade': 'L1', 'split': 'kb',
                    'provenance': {'generator': 'work-report-capture-v1'},
                    'title': '필터 조치 기록', 'know_how': '09:10 점검 09:20 교체 검증자',
                    'rationale': '137분 관찰 결과'}
            row = {'chunk_id': 'field_K-MUTATION_r2_0', 'metadata': {'source': 'K-MUTATION'},
                   'text': '검색 원문'}
            original = deepcopy((card, row))
            selected = fn(question, [row] if kept else [], [card], equipment)
            verbatim = not selected or all(card[k] in selected[0]['text']
                                           for k in ('title', 'know_how', 'rationale'))
            results[name] = bool(selected) is expected and (card, row) == original and verbatim
        return results
    def broken(question, evidence, cards, equipment):
        if mutant == 'admit-invalid':
            return [{'text': '\n'.join(cards[0][k] for k in ('title', 'know_how', 'rationale'))}]
        if mutant == 'suffix-duration' and question == '37분 결과':
            question = '137분 결과'
        selected = F.record_sources(question, evidence, cards, equipment)
        if selected and mutant == 'mutate-source':
            evidence[0]['text'] = selected[0]['text']
        if mutant == 'truncate-source':
            return [{**r, 'text': '137분 결과'} for r in selected]
        return selected
    before, after = observe(F.record_sources), observe(broken)
    assert all(before.values())
    assert any(before[k] and not after[k] for k in before)


@pytest.mark.parametrize('damage', ['duplicate', 'missing-oracle', 'wrong-label'])
def test_novel_integration_oracles_reject_schema_drift(tmp_path, damage):
    cases = deepcopy(HARNESS['load_novel_history_cases'](ROOT))
    if damage == 'duplicate':
        cases[-1] = deepcopy(cases[0])
    elif damage == 'missing-oracle':
        cases[0]['oracle'] = ''
    else:
        cases[0]['history'] = 'true'
    target = tmp_path / HARNESS['NOVEL_CASES']
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(cases), encoding='utf-8')
    with pytest.raises(ValueError):
        HARNESS['load_novel_history_cases'](tmp_path)


@pytest.mark.parametrize('family', ['retrieval','completed-report','exclusion-particle','live-exclusion'])
def test_each_reaudit_family_blocks_independently(family):
    cases = HARNESS['load_history_cases'](ROOT, profile='reaudit')
    oracle = {c['question']:c['history'] for c in cases}
    target = next(c for c in cases if c['target_regression'] and c['regression_family']==family)
    report = HARNESS['evaluate_history'](ROOT, profile='reaudit', classifier=lambda q:
        not oracle[q] if q==target['question'] else oracle[q])
    assert report['subject']=='injected_classifier' and not report['ok']
    assert report['passed']==149 and report['preservation_failures']['target_regressions']==[target['id']]
    if not target['history']:
        assert report['preservation_failures']['main_current_requests']==[target['id']]


@pytest.mark.parametrize('damage', ['duplicate','missing-oracle','wrong-role','wrong-family'])
def test_reaudit_oracles_and_independent_roles_cannot_drift(tmp_path,damage):
    cases = deepcopy(HARNESS['load_history_cases'](ROOT,profile='reaudit'))
    if damage=='duplicate':
        cases[-1]=deepcopy(cases[0])
    elif damage=='missing-oracle':
        cases[0]['oracle']=''
    elif damage=='wrong-role':
        cases[0]['preserve_main_request']=cases[0]['history']
    else:
        next(c for c in cases if c['target_regression'])['regression_family']='control'
    target=tmp_path/HARNESS['REAUDIT_CASES']
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(cases),encoding='utf-8')
    with pytest.raises(ValueError):
        HARNESS['load_history_cases'](tmp_path,profile='reaudit')


@pytest.mark.parametrize('damage', ['duplicate','missing-oracle','wrong-label','missing-source'])
def test_postfix_independent_oracles_cannot_drift(tmp_path,damage):
    cases = deepcopy(HARNESS['load_history_cases'](ROOT,profile='postaudit'))
    if damage=='duplicate':
        cases[-1]=deepcopy(cases[0])
    elif damage=='missing-oracle':
        cases[0]['oracle']=''
    elif damage=='wrong-label':
        cases[0]['history']='true'
    else:
        cases[0]['sources']=[]
    target=tmp_path/HARNESS['POSTAUDIT_CASES']
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(cases),encoding='utf-8')
    with pytest.raises(ValueError):
        HARNESS['load_history_cases'](tmp_path,profile='postaudit')


@pytest.mark.parametrize('history', [True,False])
def test_postfix_audit_cannot_trade_current_requests_for_raw_history(history):
    cases=HARNESS['load_history_cases'](ROOT,profile='postaudit')
    oracle={c['question']:c['history'] for c in cases}
    target=next(c for c in cases if c['history'] is history)
    report=HARNESS['evaluate_history'](ROOT,profile='postaudit',classifier=lambda q:
        not oracle[q] if q==target['question'] else oracle[q])
    assert not report['ok'] and report['decision']=='blocked'
    assert report['passed']==75 and report['semantic_failed']==1
    assert [r['id'] for r in report['results'] if not r['passed']]==[target['id']]


@pytest.mark.parametrize('family',['record-object','record-context','completed-scope','reading-morphology','new-request-purpose'])
def test_stability_failure_families_block_independently(family):
    cases=HARNESS['load_history_cases'](ROOT,profile='stability')
    oracle={c['question']:c['history'] for c in cases}
    target=next(c for c in cases if c['target_failure'] and c['fix_family']==family)
    report=HARNESS['evaluate_history'](ROOT,profile='stability',classifier=lambda q:
        not oracle[q] if q==target['question'] else oracle[q])
    assert not report['ok'] and report['passed']==71
    assert [r['id'] for r in report['results'] if not r['passed']]==[target['id']]


@pytest.mark.parametrize('damage',['duplicate','missing-oracle','wrong-role','wrong-family'])
def test_stability_human_oracles_and_roles_cannot_drift(tmp_path,damage):
    cases=deepcopy(HARNESS['load_history_cases'](ROOT,profile='stability'))
    if damage=='duplicate':cases[-1]=deepcopy(cases[0])
    elif damage=='missing-oracle':cases[0]['oracle']=''
    elif damage=='wrong-role':cases[0]['preserve_final_contract']=cases[0]['target_failure']
    else:next(c for c in cases if c['target_failure'])['fix_family']='control'
    target=tmp_path/HARNESS['STABILITY_CASES']
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(cases),encoding='utf-8')
    with pytest.raises(ValueError):HARNESS['load_history_cases'](tmp_path,profile='stability')


@pytest.mark.parametrize('history',[True,False])
def test_closure_cannot_trade_new_requests_for_history(history):
    cases=HARNESS['load_history_cases'](ROOT,profile='closure')
    oracle={c['question']:c['history'] for c in cases}
    target=next(c for c in cases if c['history'] is history)
    report=HARNESS['evaluate_history'](ROOT,profile='closure',classifier=lambda q:
        not oracle[q] if q==target['question'] else oracle[q])
    assert not report['ok'] and report['decision']=='blocked' and report['passed']==83
    assert [r['id'] for r in report['results'] if not r['passed']]==[target['id']]


@pytest.mark.parametrize('damage',['duplicate','wrong-label','missing-source','missing-lens','wrong-cohort'])
def test_closure_oracles_and_independent_cohorts_cannot_drift(tmp_path,damage):
    cases=deepcopy(HARNESS['load_history_cases'](ROOT,profile='closure'))
    if damage=='duplicate':cases[-1]=deepcopy(cases[0])
    elif damage=='wrong-label':cases[0]['history']='true'
    elif damage=='missing-source':cases[0]['sources']=[]
    elif damage=='missing-lens':cases[0].pop('audit_lens')
    else:cases[0]['audit_lens']=0
    target=tmp_path/HARNESS['CLOSURE_CASES']
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(cases),encoding='utf-8')
    with pytest.raises(ValueError):HARNESS['load_history_cases'](tmp_path,profile='closure')
