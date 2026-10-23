"""Opt-in STRICT product challenge. Known failures remain failures; no xfail.

Run explicitly: python -m pytest tests/history_scope_challenge.py -q
SHIFTLINK_HISTORY_PROFILE selects minimal, adversarial or full (default).
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import runpy

import pytest

from shiftlink.rag2.field_history import is_history_question
from test_s30h_publication_integrity import published_history, output, G, service, pipe, E

ROOT = Path(__file__).resolve().parents[1]
HARNESS = runpy.run_path(str(ROOT / 'scripts/check_knowledge_publication.py'))
CASES = HARNESS['load_history_cases'](ROOT, profile=os.environ.get('SHIFTLINK_HISTORY_PROFILE', 'full'))


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['id'])
def test_classifier_matches_semantic_oracle(case):
    assert is_history_question(case['question']) is case['history'], case['oracle']


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['id'])
def test_published_scope_matches_semantic_oracle(published_history, monkeypatch, case):
    svc, did = published_history
    original = deepcopy(svc.storage.get_card_draft(did))
    original_reports = deepcopy(svc.storage.list_work_reports())
    assert original_reports
    card = original['review_flags']['publication']['card']
    calls = []
    monkeypatch.setattr(G, 'ask_raw', lambda prompt, *a, **k:
                        calls.append(prompt) or output('자료 확인 [S1].', ['S1']))
    question = case['question']
    result = svc.query({'equipment_id': 'EQ-0001', 'question': question})
    unchanged = svc.storage.get_card_draft(did) == original
    saved = svc.storage.get_query(result['query_id'])['payload']['answer'] == result['answer']
    reports_unchanged = svc.storage.list_work_reports() == original_reports
    print(json.dumps({'id': case['id'], 'expected_history': case['history'],
                      'route': result['s30h_trace']['route'], 'calls': len(calls),
                      'question_and_mes': bool(calls and question in calls[0] and '[MES]' in calls[0]),
                      'card_unchanged': unchanged, 'work_reports_unchanged': reports_unchanged,
                      'saved_answer_matches': saved}, ensure_ascii=False))
    # Data invariants must be checked even when the later semantic gate fails.
    assert unchanged and reports_unchanged and saved
    assert result['cited_card_ids'] == [did] and not result['no_knowledge']
    if case['history']:
        assert result['s30h_trace']['route'] == 'record_history'
        assert not calls
        assert all(card[key] in result['answer'] for key in ('title', 'know_how', 'rationale'))
        assert all(v in result['answer'] for v in ('137분', '09:10', '09:20', '검증자'))
        assert '현재 MES(' not in result['answer']
    else:
        assert calls, case['oracle']
        assert question in calls[0] and '[MES]' in calls[0]
        assert result['s30h_trace']['route'] != 'record_history'


def test_rejected_history_cannot_be_resurrected(published_history, monkeypatch):
    svc, did = published_history
    original = deepcopy(svc.storage.get_card_draft(did))
    monkeypatch.setattr(E, 'judge_dist', lambda *a, **k: [1, 0, 0, 0])
    result = svc.query({'equipment_id': 'EQ-0001', 'question': '근무일지 필터 교체 순서와 결과는?'})
    assert result['no_knowledge'] and result['cited_card_ids'] == []
    assert '137분' not in result['answer']
    assert svc.storage.get_card_draft(did) == original


def test_wrong_duration_cannot_select_history(published_history):
    svc, did = published_history
    original = deepcopy(svc.storage.get_card_draft(did))
    result = svc.query({'equipment_id': 'EQ-0001', 'question': '근무일지 37분 관찰 결과와 시각은?'})
    assert result['no_knowledge'] and result['cited_card_ids'] == []
    assert '137분' not in result['answer']
    assert svc.storage.get_card_draft(did) == original
