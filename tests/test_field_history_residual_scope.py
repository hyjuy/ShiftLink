"""Counterexamples around the four residual scope families; no oracle changes."""
from copy import deepcopy
import json

import pytest

from shiftlink.rag2.field_history import is_history_question
from test_s30h_publication_integrity import published_history, output, G, service, pipe

HISTORY = [
    "근무일지에 '교체를 진행해줘'라고 기록한 시각과 결과만 알려줘",
    '근무일지에 “작업을 시작해주세요”라고 문의했던 시각과 결과만 알려줘',
    "근무일지에 '오늘 필터 교체 안전성을 알려줘'라고 적었던 시각과 결과만 알려줘",
    '근무일지에 “모레 교체 가능해”라고 적었던 시각과 결과만 알려줘',
    '근무일지에 ‘다음 교대에 교체 가능해’라고 기록했던 시각과 결과만 알려줘',
    '근무일지의 결과와 시각만 알려줘. 모레 교체 가능한지는 묻지 않아.',
    '근무일지의 결과와 시각만 알려줘. 다음 교대에 교체 가능한지는 묻지 않아.',
    '근무일지의 결과와 시각만 알려줘. 나중에 교체 가능한지는 묻지 않아.',
    '과거 근무일지에서 모레 교체 가능한지 검토했던 결과와 시각만 알려줘',
    '과거 근무일지에서 다음 교대에 교체 가능한지 확인했던 결과와 시각만 알려줘',
    '근무일지에서 모레 교체 가능한지 판단한 뒤 진행했던 결과와 시각은?',
    '과거 근무일지에서 모레 교체 안전성을 판단했던 결과와 시각만 알려줘',
    '과거 근무일지에서 모레 교체 안전성을 알려줬던 결과와 시각만 알려줘',
]
CURRENT = [
    "근무일지에 '교체 가능해'라고 적었던 결과를 보고 교체를 진행해주세요",
    "근무일지에 '진행해줘'라고 기록했던 시각과 결과와 내일 필터 교체 안전성을 알려줘",
    '근무일지 결과와 오늘의 펌프 교체 안전성을 알려주세요',
    '근무일지 결과와 내일 압력이 0.6 bar이면 필터 교체 안전성을 알려줘',
    '근무일지 결과와 모레 필터 교체 안전성을 알려줘',
    '근무일지 결과와 다음 교대에 교체 가능한지 판단한 뒤 진행해주세요',
    '근무일지 결과와 나중에 교체 가능 여부를 확인한 결과를 알려줘',
    '근무일지 결과만 알려줘. 모레 교체 가능한지는 묻지 않아. 지금 교체 가능한가요?',
    '근무일지 결과만 알려줘. 다음 교대에 교체 가능한지는 묻지 않아. 오늘 필터 교체 안전성을 알려줘',
    '근무일지에서 교체 가능한지 판단한 뒤 진행했던 결과와 교체를 진행해줘',
    '근무일지 결과와 내일 교체 안전성을 알려.',
    '근무일지 결과와 내일 교체 안전성을 알려 줘',
    '근무일지 결과와 내일 필터 교체 안전성을 알려주실래요?',
]


# Exact twelve findings from the previous independent audit, with paired active controls.
REGRESSION12 = [('근무일지에 “교체 가능해”라고 적었던 결과와 시각을 보고 작업을 진행시켜줘', False),
 ('근무일지 결과와 시각만 알려줘. 교체를 진행해줘라는 요청은 하지 않아.', True),
 ('근무일지 결과와 시각만 알려줘. 교체를 진행해주세요라는 요청은 하지 않습니다.', True),
 ('근무일지 결과와 시각만 알려줘. 교체를 진행해줘라고 묻지 않아.', True),
 ('근무일지 결과와 시각만 알려줘. 교체를 진행해줘라는 지시는 제외해.', True),
 ('근무일지에 교체를 진행해줘라고 기록한 시각과 결과만 알려줘', True),
 ("근무일지에 '교체를 진행해줘'라고 요청했던 시각과 결과만 알려줘", True),
 ("근무일지에 '작업을 시작해주세요'라고 지시했던 시각과 결과만 알려줘", True),
 ("근무일지의 '교체해줘'라는 요청을 받았던 시각과 처리 결과만 알려줘", True),
 ("근무일지에 적힌 '교체를 진행해주세요' 지시의 시각과 결과만 알려줘", True),
 ('근무일지에서 교체를 진행해줘서 해결됐던 결과와 시각은?', True),
 ('근무일지의 결과와 시각만 알려줘. 교체를 진행해줘라는 요청은 하지 않아.', True)]
HISTORY += [q for q, history in REGRESSION12 if history]
CURRENT += [q for q, history in REGRESSION12 if not history]

# A completed or excluded mention must not hide a subsequent independent request.
CURRENT += [q + " 그리고 작업을 진행해줘" for q, history in REGRESSION12 if history]


HISTORY += [
    "근무일지에 '지금 교체해줘'라는 요청을 받았던 시각과 결과만 알려줘",
    "근무일지에 적힌 '내일 작업을 시작해주세요' 지시의 시각과 결과만 알려줘",
    '근무일지에서 작업을 진행시켜줘서 해결됐던 결과와 시각은?',
    '근무일지에 작업을 진행시켜줘라고 요청했던 결과와 시각은?',
]
CURRENT += [
    "근무일지 결과와 시각을 보고 '교체해줘'라고 요청해주세요",
    "근무일지 결과와 시각을 보고 '교체해줘'라는 요청을 해줘",
    '근무일지에 교체를 진행해줘라고 기록한 결과와 시각을 보고 작업을 진행시켜줘',
    '근무일지에서 교체를 진행해줘서 해결됐던 결과와 시각을 보고 작업을 시작해주세요',
]


CURRENT += [
    '근무일지 결과와 시각을 보고 작업을 진행해줘요',
    '근무일지 결과와 시각을 보고 작업을 진행해줘야 해',
    '근무일지 결과와 시각을 보고 작업을 진행해줘도 돼?',
    '근무일지 결과와 시각을 보고 작업을 진행해줘서는 안 돼',
]


@pytest.mark.parametrize('question,expected', [(q, True) for q in HISTORY] + [(q, False) for q in CURRENT])
def test_residual_scope_has_explicit_history_and_request_controls(question, expected):
    assert is_history_question(question) is expected


@pytest.mark.parametrize('question', HISTORY)
def test_residual_history_preserves_verbatim_card_and_saved_answer(published_history, monkeypatch, question):
    svc, did = published_history
    previous = svc.query({'equipment_id': 'EQ-0001', 'question': '근무일지 조치 순서와 시각과 결과만 알려줘'})
    previous_saved = deepcopy(svc.storage.get_query(previous['query_id']))
    original = deepcopy(svc.storage.get_card_draft(did))
    original_reports = deepcopy(svc.storage.list_work_reports())
    assert original_reports
    card = original['review_flags']['publication']['card']
    calls = []
    monkeypatch.setattr(G, 'ask_raw', lambda *a, **k: calls.append(a) or output('자료 확인 [S1].', ['S1']))
    result = svc.query({'equipment_id': 'EQ-0001', 'question': question})
    print(json.dumps({'question': question, 'route': result['s30h_trace']['route'],
                      'calls': len(calls), 'card_unchanged': svc.storage.get_card_draft(did) == original,
                      'reports_unchanged': svc.storage.list_work_reports() == original_reports,
                      'previous_answer_unchanged': svc.storage.get_query(previous['query_id']) == previous_saved,
                      'saved_answer_matches': svc.storage.get_query(result['query_id'])['payload']['answer'] == result['answer']}, ensure_ascii=False))
    assert svc.storage.get_query(previous['query_id']) == previous_saved
    assert svc.storage.get_card_draft(did) == original
    assert svc.storage.list_work_reports() == original_reports
    assert svc.storage.get_query(result['query_id'])['payload']['answer'] == result['answer']
    assert result['s30h_trace']['route'] == 'record_history' and not calls
    assert result['cited_card_ids'] == [did] and not result['no_knowledge']
    assert all(card[key] in result['answer'] for key in ('title', 'know_how', 'rationale'))
    assert all(v in result['answer'] for v in ('137분', '09:10', '09:20', '검증자'))
    assert '현재 MES(' not in result['answer']


@pytest.mark.parametrize('question', CURRENT)
def test_residual_request_keeps_original_question_and_mes(published_history, monkeypatch, question):
    svc, did = published_history
    previous = svc.query({'equipment_id': 'EQ-0001', 'question': '근무일지 조치 순서와 시각과 결과만 알려줘'})
    previous_saved = deepcopy(svc.storage.get_query(previous['query_id']))
    original = deepcopy(svc.storage.get_card_draft(did))
    original_reports = deepcopy(svc.storage.list_work_reports())
    assert original_reports
    calls = []
    monkeypatch.setattr(G, 'ask_raw', lambda prompt, *a, **k:
                        calls.append(prompt) or output('자료 확인 [S1].', ['S1']))
    result = svc.query({'equipment_id': 'EQ-0001', 'question': question})
    print(json.dumps({'question': question, 'route': result['s30h_trace']['route'],
                      'calls': len(calls), 'card_unchanged': svc.storage.get_card_draft(did) == original,
                      'reports_unchanged': svc.storage.list_work_reports() == original_reports,
                      'previous_answer_unchanged': svc.storage.get_query(previous['query_id']) == previous_saved,
                      'saved_answer_matches': svc.storage.get_query(result['query_id'])['payload']['answer'] == result['answer']}, ensure_ascii=False))
    assert svc.storage.get_query(previous['query_id']) == previous_saved
    assert svc.storage.get_card_draft(did) == original
    assert svc.storage.list_work_reports() == original_reports
    assert svc.storage.get_query(result['query_id'])['payload']['answer'] == result['answer']
    assert calls and question in calls[0] and '[MES]' in calls[0]
    assert result['s30h_trace']['route'] != 'record_history'
