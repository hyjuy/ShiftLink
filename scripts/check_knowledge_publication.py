"""Fast publication drift and staged-syntax gate; no models, services or data writes."""
import argparse
import ast
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('shiftlink/mes/candidate_review.py','shiftlink/mes/publication.py','shiftlink/mes/query.py',
           'shiftlink/mes/server.py','shiftlink/mes/storage.py','shiftlink/rag/embedding.py',
           'shiftlink/rag2/embed.py','shiftlink/rag2/s30h.py','shiftlink/rag2/generate.py',
           'shiftlink/rag2/field_history.py',
           'shiftlink/rag/graph_explain.py','scripts/check_knowledge_publication.py')
MEMORY = 'docs/failures/knowledge-publication-integrity.md'
HISTORY_CASES = 'tests/fixtures/field_history_scope_cases.json'
INTEGRATION_CASES = 'tests/fixtures/field_history_integration_cases.json'
NOVEL_CASES = 'tests/fixtures/field_history_integration_novel_cases.json'
REAUDIT_CASES = 'tests/fixtures/field_history_reaudit_cases.json'
CLOSURE_CASES = 'tests/fixtures/field_history_closure_cases.json'
STABILITY_CASES = 'tests/fixtures/field_history_stability_cases.json'
POSTAUDIT_CASES = 'tests/fixtures/field_history_post67_cases.json'
HISTORY_PROFILES = ('minimal', 'adversarial', 'full')
INSTRUCTIONS = '.github/instructions/knowledge-publication.instructions.md'
WORKFLOW = '.github/workflows/knowledge-publication.yml'
HISTORY_TESTS = ('tests/test_field_history_boundaries.py', 'tests/test_field_history_intent.py',
                 'tests/test_field_history_request_scope.py', 'tests/test_field_history_evaluation.py',
                 'tests/test_s30h_publication_integrity.py', 'tests/test_field_history_residual_scope.py',
                 'tests/history_scope_challenge.py', 'tests/test_field_history_integration.py')


def load_novel_history_cases(root=ROOT):
    """Frozen cross-lens and independent judge cases, separate from the MAIN 283."""
    cases = json.loads((root/NOVEL_CASES).read_text(encoding='utf-8'))
    if not isinstance(cases, list) or len(cases) != 229:
        raise ValueError('Novel integration oracles must retain their 229 firm cases')
    for c in cases:
        if (not isinstance(c, dict) or type(c.get('history')) is not bool
                or any(not isinstance(c.get(k), str) or not c[k].strip()
                       for k in ('id', 'question', 'oracle', 'family'))
                or not isinstance(c.get('sources'), list) or not c['sources']):
            raise ValueError('Invalid novel integration oracle')
    if (len({c['id'] for c in cases}) != 229 or len({c['question'] for c in cases}) != 229
            or sum(c['history'] for c in cases) != 93):
        raise ValueError('Novel integration cohorts changed')
    return cases


def load_history_cases(root=ROOT, *, profile='full'):
    """Human-written semantic oracles, never inferred from observed runtime results."""
    if profile == 'closure':
        cases = json.loads((root/CLOSURE_CASES).read_text(encoding='utf-8'))
        if not isinstance(cases,list) or len(cases)!=84:
            raise ValueError('Closure requires all 72 independent and 12 bounded scope oracles')
        for c in cases:
            if (not isinstance(c,dict) or type(c.get('history')) is not bool
                or type(c.get('audit_lens')) is not int or c['audit_lens'] not in range(7)
                or any(not isinstance(c.get(k),str) or not c[k].strip() for k in ('id','question','oracle','family'))
                or not isinstance(c.get('sources'),list) or not c['sources']):
                raise ValueError('Invalid closure oracle or independent source')
        if (len({c['id'] for c in cases})!=84 or len({c['question'] for c in cases})!=84
            or any(sum(c['audit_lens']==n for c in cases)!=12 for n in range(7))
            or any(sum(c['history'] and c['audit_lens']==n for c in cases)!=6 for n in range(7))):
            raise ValueError('Closure independent cohorts changed')
        return cases
    if profile == 'stability':
        cases = json.loads((root/STABILITY_CASES).read_text(encoding='utf-8'))
        if not isinstance(cases,list) or len(cases)!=72:
            raise ValueError('Stability requires all 72 frozen independent oracles')
        for c in cases:
            if (not isinstance(c,dict) or any(type(c.get(k)) is not bool for k in
                ('history','target_failure','target_new_regression','preserve_final_contract','preserve_main_request'))
                or any(not isinstance(c.get(k),str) or not c[k].strip() for k in ('id','question','oracle','fix_family'))
                or not c.get('sources') or c['preserve_main_request'] is c['history']
                or c['target_failure'] is c['preserve_final_contract']):
                raise ValueError('Invalid stability oracle or preservation role')
        expected={'record-object':7,'record-context':10,'completed-scope':6,'reading-morphology':1,'new-request-purpose':7}
        counts={name:sum(c['target_failure'] and c['fix_family']==name for c in cases) for name in expected}
        if (len({c['id'] for c in cases})!=72 or len({c['question'] for c in cases})!=72
            or sum(c['history'] for c in cases)!=36 or sum(c['target_failure'] for c in cases)!=31
            or sum(c['target_new_regression'] for c in cases)!=1 or counts!=expected):
            raise ValueError('Stability cohorts or failure families changed')
        return cases
    if profile == 'postaudit':
        cases = json.loads((root/POSTAUDIT_CASES).read_text(encoding='utf-8'))
        if not isinstance(cases, list) or len(cases) != 76:
            raise ValueError('Post-fix audit must retain all 76 preregistered oracles')
        for c in cases:
            if (not isinstance(c, dict) or type(c.get('history')) is not bool
                    or any(not isinstance(c.get(k), str) or not c[k].strip()
                           for k in ('id','question','oracle','family'))
                    or not isinstance(c.get('sources'), list) or not c['sources']):
                raise ValueError('Invalid post-fix audit oracle')
        if (len({c['id'] for c in cases}) != 76 or len({c['question'] for c in cases}) != 76
                or sum(c['history'] for c in cases) != 38):
            raise ValueError('Post-fix audit independent cohorts changed')
        return cases
    if profile == 'reaudit':
        cases = json.loads((root/REAUDIT_CASES).read_text(encoding='utf-8'))
        if not isinstance(cases, list) or len(cases) != 150:
            raise ValueError('Reaudit must retain all 150 independently judged oracles')
        for c in cases:
            if (not isinstance(c, dict)
                    or any(not isinstance(c.get(k), str) or not c[k].strip()
                           for k in ('id', 'question', 'oracle', 'regression_family'))
                    or any(type(c.get(k)) is not bool for k in
                           ('history', 'target_regression', 'preserve_main_request', 'preserve_ce1_history'))
                    or c['preserve_main_request'] is c['history']
                    or (c['preserve_ce1_history'] and not c['history'])):
                raise ValueError('Invalid reaudit oracle or preservation role')
        counts = {f:sum(c['target_regression'] and c['regression_family']==f for c in cases)
                  for f in ('retrieval','completed-report','exclusion-particle','live-exclusion')}
        if (len({c['id'] for c in cases}) != 150 or len({c['question'] for c in cases}) != 150
                or sum(c['history'] for c in cases) != 77
                or sum(c['preserve_ce1_history'] for c in cases) != 44
                or sum(c['target_regression'] for c in cases) != 30
                or counts != {'retrieval':23,'completed-report':2,'exclusion-particle':1,'live-exclusion':4}):
            raise ValueError('Reaudit independent preservation cohorts changed')
        return cases
    if profile == 'integration':
        cases = json.loads((root/INTEGRATION_CASES).read_text(encoding='utf-8'))
        if not isinstance(cases, list) or len(cases) != 283:
            raise ValueError('Integration comparison must retain its fixed 283 oracles')
        for c in cases:
            if (not isinstance(c, dict)
                    or any(not isinstance(c.get(k), str) or not c[k].strip()
                    for k in ('id', 'question', 'oracle', 'family'))
                    or any(type(c.get(k)) is not bool for k in
                           ('history', 'preserve_main_request', 'preserve_local_history'))
                    or c['preserve_main_request'] is c['history']
                    or (c['preserve_local_history'] and not c['history'])):
                raise ValueError('Invalid integration oracle or preservation role')
        if (len({c['id'] for c in cases}) != 283 or len({c['question'] for c in cases}) != 283
                or sum(c['preserve_main_request'] for c in cases) != 158
                or sum(c['preserve_local_history'] for c in cases) != 95):
            raise ValueError('Integration preservation cohorts changed')
        expected = {c['question']: c['history'] for c in cases}
        if any(expected.get(c['question']) is not c['history'] for c in load_history_cases(root)):
            raise ValueError('Original thirty oracles must remain in integration comparison')
        return cases
    cases = json.loads((root/HISTORY_CASES).read_text(encoding='utf-8'))
    if profile not in HISTORY_PROFILES or not isinstance(cases, list) or not cases:
        raise ValueError('History cases must be nonempty and profile must be valid')
    ids, questions = set(), set()
    for case in cases:
        if (not isinstance(case, dict)
                or any(not isinstance(case.get(k), str) or not case[k].strip()
                       for k in ('id', 'family', 'question', 'oracle'))
                or type(case.get('history')) is not bool
                or not isinstance(case.get('profiles'), list) or not case['profiles']
                or any(p not in HISTORY_PROFILES for p in case['profiles'])
                or 'full' not in case['profiles']
                or case['id'] in ids or case['question'] in questions
                or (case.get('known_issue') is not None and
                    (not isinstance(case['known_issue'], str) or not case['known_issue'].strip()))):
            raise ValueError('Invalid or duplicate history oracle')
        ids.add(case['id']); questions.add(case['question'])
    for name in HISTORY_PROFILES:
        selected = [c for c in cases if name in c['profiles']]
        if {c['history'] for c in selected} != {True, False}:
            raise ValueError('Every history profile requires positive and negative controls')
    return [c for c in cases if profile in c['profiles']]


def evaluate_history(root=ROOT, *, profile='full', classifier=None):
    """Strict classifier diagnostic; known defects still block the product verdict."""
    cases = load_history_cases(root, profile=profile)
    source = root/'shiftlink/rag2/field_history.py'
    injected = classifier is not None
    if classifier is None:
        classifier = runpy.run_path(str(source))['is_history_question']
    results = []
    for case in cases:
        error, actual = None, None
        try:
            actual = classifier(case['question'])
            if type(actual) is not bool:
                raise TypeError('Classifier must return bool')
        except Exception as exc:
            error = type(exc).__name__
        results.append({**case, 'actual_history': actual, 'error': error,
                        'passed': error is None and actual is case['history']})
    failed = [r for r in results if not r['passed']]
    known = sum(bool(r.get('known_issue')) and r['error'] is None for r in failed)
    return {'ok': not failed, 'decision': 'blocked' if failed else 'pass',
            'check_kind': 'history_semantic', 'classification_only': True,
            'subject': 'injected_classifier' if injected else 'runtime', 'profile': profile,
            'total': len(results), 'passed': len(results)-len(failed),
            'semantic_failed': len(failed), 'known_failed': known,
            'unexpected_failed': len(failed)-known, 'results': results,
            'runtime_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'cases_sha256': hashlib.sha256((root/({'integration':INTEGRATION_CASES,
                'reaudit':REAUDIT_CASES,'postaudit':POSTAUDIT_CASES,'stability':STABILITY_CASES,'closure':CLOSURE_CASES}.get(profile,HISTORY_CASES))).read_bytes()).hexdigest(),
            'preservation_failures': {
                'main_current_requests': [r['id'] for r in failed if r.get('preserve_main_request')],
                'local_verbatim_history': [r['id'] for r in failed if r.get('preserve_local_history')],
                'target_regressions': [r['id'] for r in failed if r.get('target_regression')],
                'ce1_verbatim_history': [r['id'] for r in failed if r.get('preserve_ce1_history')]}}


def literal(root, path, name):
    tree = ast.parse((root/path).read_text(encoding='utf-8'))
    return next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
                and any(isinstance(target,ast.Name) and target.id==name for target in node.targets))


def check(root=ROOT, *, staged=True):
    errors=[]
    for path in SOURCES:
        try:
            ast.parse((root/path).read_text(encoding='utf-8'),filename=path)
            if staged:
                result=subprocess.run(['git','show',':'+path],cwd=root,capture_output=True)
                if result.returncode==0:ast.parse(result.stdout.decode('utf-8'),filename='index:'+path)
        except (OSError,SyntaxError,UnicodeError) as error:
            errors.append(f'Python syntax: {path}: {type(error).__name__}')
    try:
        model=literal(root,'shiftlink/rag/embedding.py','PUBLICATION_MODEL')
        if model != literal(root,'shiftlink/rag2/generate.py','CONFIGS')['C']['model']:
            errors.append('Embedding model differs from S30h config C; re-embedding/migration required')
        class Options(HTMLParser):
            def __init__(self):
                super().__init__()
                self.values=set()
            def handle_starttag(self,tag,attrs):
                if tag=='option':self.values.add(dict(attrs).get('value'))
        parser=Options();parser.feed((root/'shiftlink/mes/web/knowledge-candidates.html').read_text(encoding='utf-8'))
        states=set(literal(root,'shiftlink/mes/candidate_review.py','STATUSES').values())|{'pending_review'}
        if states-parser.values:errors.append('MES status filter missing: '+','.join(sorted(states-parser.values)))
        memory=(root/MEMORY).read_text(encoding='utf-8')
        references=re.findall(r'(tests/[\w]+\.py)::(test_\w+)',memory)
        if not references:errors.append('Failure memory has no executable regression references')
        for path,name in references:
            tree=ast.parse((root/path).read_text(encoding='utf-8'))
            if name not in {node.name for node in ast.walk(tree) if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}:
                errors.append(f'Stale regression reference: {path}::{name}')
        load_history_cases(root)
        load_history_cases(root, profile='integration')
        load_novel_history_cases(root)
        load_history_cases(root, profile='reaudit')
        load_history_cases(root, profile='postaudit')
        load_history_cases(root, profile='stability')
        load_history_cases(root, profile='closure')
        instruction = (root/INSTRUCTIONS).read_text(encoding='utf-8')
        scope = yaml.safe_load(instruction.split('---')[1])['applyTo']
        rag2_scopes = re.findall(r'shiftlink/rag2/(?:\{[^}]*\}|[^,]+)\.py', scope)
        if not any('field_history' in s for s in rag2_scopes) or 'tests/test_field_history*.py' not in scope:
            errors.append('History routing is missing from scoped instructions')
        if '--history-scope full' not in instruction or 'tests/history_scope_challenge.py' not in instruction:
            errors.append('Strict history diagnostic command is missing from instructions')
        if '--history-scope integration' not in instruction:
            errors.append('Main/local preservation diagnostic is missing from instructions')
        if '--history-scope reaudit' not in instruction:
            errors.append('Four-family reaudit diagnostic is missing from instructions')
        if '--history-scope postaudit' not in instruction:
            errors.append('Independent post-fix diagnostic is missing from instructions')
        if '--history-scope stability' not in instruction:
            errors.append('Stability diagnostic is missing from instructions')
        if '--history-scope closure' not in instruction:
            errors.append('Bounded closure diagnostic is missing from instructions')
        workflow = yaml.safe_load((root/WORKFLOW).read_text(encoding='utf-8'))
        triggers = workflow.get('on', workflow.get(True, {}))
        paths = triggers['pull_request']['paths']
        required = ('tests/test_field_history*.py', HISTORY_CASES, INTEGRATION_CASES, NOVEL_CASES, REAUDIT_CASES, POSTAUDIT_CASES, STABILITY_CASES, CLOSURE_CASES,
                    'tests/history_scope_challenge.py', INSTRUCTIONS)
        for path in required:
            if path not in paths:
                errors.append('History workflow trigger missing: '+path)
        commands = '\n'.join(s.get('run', '') for s in workflow['jobs']['publication']['steps']).split()
        for path in HISTORY_TESTS:
            if path not in commands:
                errors.append('History workflow test missing: '+path)
    except (OSError,SyntaxError,ValueError,KeyError,StopIteration,TypeError,IndexError,yaml.YAMLError) as error:
        errors.append(f'Drift metadata: {type(error).__name__}: {error}')
    return errors


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history-scope', choices=(*HISTORY_PROFILES, 'integration', 'reaudit', 'postaudit', 'stability', 'closure'),
                        help='Strict semantic diagnostic; exits 1 even for known defects')
    args = parser.parse_args()
    if args.history_scope:
        report = evaluate_history(profile=args.history_scope)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        sys.exit(0 if report['ok'] else 1)
    errors=check()
    print(json.dumps({'ok':not errors,'errors':errors,'staged_python_checked':True,
                      'check_kind':'metadata_and_syntax','history_semantics_evaluated':False},
                     ensure_ascii=False,indent=2))
    sys.exit(bool(errors))
