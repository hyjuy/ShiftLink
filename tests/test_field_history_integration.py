"""Keep MAIN judgement transfer and historical raw answers as independent contracts."""
from copy import deepcopy
import json
from pathlib import Path
import runpy

import pytest

from shiftlink.rag2.field_history import is_history_question
from test_s30h_publication_integrity import published_history, output, G, service, pipe

ROOT = Path(__file__).resolve().parents[1]
HARNESS = runpy.run_path(str(ROOT / 'scripts/check_knowledge_publication.py'))
CASES = HARNESS['load_history_cases'](ROOT, profile='integration')
NOVEL = HARNESS['load_novel_history_cases'](ROOT)
REAUDIT = HARNESS['load_history_cases'](ROOT, profile='reaudit')
STABILITY = HARNESS['load_history_cases'](ROOT, profile='stability')
POSTAUDIT = HARNESS['load_history_cases'](ROOT, profile='postaudit')
FOLLOWUP = [
    {'id':'followup-read-honorific','question':'근무일지의 결과와 시각만 읽어주실 수 있나요?', 'history':True,
     'oracle':'Honorific capability concerns displaying recorded facts only.'},
    {'id':'followup-confirm-honorific','question':'근무일지에 기록된 담당자와 시각을 확인해 주실래요?', 'history':True,
     'oracle':'Confirmation object is explicitly recorded metadata.'},
    {'id':'followup-raw-polite','question':'근무일지 결과와 시각 원문으로 부탁드려요', 'history':True,
     'oracle':'Polite nominal request asks only for original record text.'},
    {'id':'followup-current-nominal','question':'근무일지 결과만 알려줘. 지금 밸브 상태 확인 부탁드려요, 재가동 가능 여부는 묻지 않습니다.', 'history':False,
     'oracle':'Independent current condition confirmation precedes a distinct excluded permission question.'},
    {'id':'followup-current-connective','question':'근무일지 결과만 알려줘. 지금 밸브 상태 확인 부탁드리고 압력 안전성은 묻지 않습니다.', 'history':False,
     'oracle':'Nominal request connected with -고 must survive the unrelated exclusion.'},
    {'id':'followup-confirm-object','question':'근무일지의 결과를 보고 밸브 상태를 확인해줘', 'history':False,
     'oracle':'Worklog is a premise; the requested confirmation object is equipment condition.'},
]
CONTEXT = json.loads((ROOT/'tests/fixtures/field_history_stability_context_cases.json').read_text(encoding='utf-8'))
assert len(CONTEXT)==8 and sum(c['history'] for c in CONTEXT)==4
assert len({c['question'] for c in CONTEXT})==8
FOLLOWUP += CONTEXT


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['id'])
def test_integration_scope_matches_fixed_oracle(case):
    assert is_history_question(case['question']) is case['history'], case['oracle']


@pytest.mark.parametrize('case', NOVEL, ids=lambda c: c['id'])
def test_integration_scope_matches_cross_lens_oracle(case):
    assert is_history_question(case['question']) is case['history'], case['oracle']


@pytest.mark.parametrize('case', REAUDIT, ids=lambda c: c['id'])
def test_reaudit_scope_matches_four_family_oracle(case):
    assert is_history_question(case['question']) is case['history'], case['oracle']


@pytest.mark.parametrize('case', POSTAUDIT, ids=lambda c: c['id'])
def test_postfix_independent_audit_oracle(case):
    assert is_history_question(case['question']) is case['history'], case['oracle']


@pytest.mark.parametrize('case', STABILITY, ids=lambda c:c['id'])
def test_stability_oracles_remain_independent(case):
    assert is_history_question(case['question']) is case['history'],case['oracle']


@pytest.mark.parametrize('case', FOLLOWUP, ids=lambda c: c['id'])
def test_followup_record_and_current_objects_remain_distinct(case):
    assert is_history_question(case['question']) is case['history'], case['oracle']


def test_main_requests_and_verbatim_history_survive_publication(published_history, monkeypatch, tmp_path):
    svc, did = published_history
    original = deepcopy(svc.storage.get_card_draft(did))
    reports = deepcopy(svc.storage.list_work_reports())
    assert reports
    card = original['review_flags']['publication']['card']
    previous = svc.query({'equipment_id': 'EQ-0001', 'question': '근무일지 조치 순서와 시각과 결과만 알려줘'})
    previous_saved = deepcopy(svc.storage.get_query(previous['query_id']))
    calls = []
    monkeypatch.setattr(G, 'ask_raw', lambda prompt, *a, **k:
                        calls.append(prompt) or output('자료 확인 [S1].', ['S1']))
    observations = []
    for case in CASES + NOVEL + REAUDIT + FOLLOWUP + POSTAUDIT + STABILITY:
        calls.clear()
        result = svc.query({'equipment_id': 'EQ-0001', 'question': case['question']})
        invariants = {
            'card': svc.storage.get_card_draft(did) == original,
            'worklogs': svc.storage.list_work_reports() == reports,
            'previous_answer': svc.storage.get_query(previous['query_id']) == previous_saved,
            'new_answer': svc.storage.get_query(result['query_id'])['payload']['answer'] == result['answer']}
        raw = all(card[k] in result['answer'] for k in ('title', 'know_how', 'rationale'))
        details = all(v in result['answer'] for v in ('137분', '09:10', '09:20', '검증자'))
        history = (result['s30h_trace']['route'] == 'record_history' and not calls and raw and details
                   and '현재 MES(' not in result['answer'])
        current = (result['s30h_trace']['route'] != 'record_history' and bool(calls)
                   and case['question'] in calls[0] and '[MES]' in calls[0])
        observations.append({**case, 'passed': history if case['history'] else current,
                             'route': result['s30h_trace']['route'], 'calls': len(calls),
                             'raw_answer': raw, 'invariants': invariants})
        assert all(invariants.values()), case['id']
        assert result['cited_card_ids'] == [did] and not result['no_knowledge'], case['id']
    (tmp_path / 'integration-observations.json').write_text(
        json.dumps(observations, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'cases': len(observations), 'passed': sum(r['passed'] for r in observations),
                      'main_requests_passed': sum(r['passed'] and r.get('preserve_main_request', False) for r in observations),
                      'local_history_passed': sum(r['passed'] and r.get('preserve_local_history', False) for r in observations)},
                     ensure_ascii=False))
    assert all(r['passed'] for r in observations), [r['id'] for r in observations if not r['passed']]
