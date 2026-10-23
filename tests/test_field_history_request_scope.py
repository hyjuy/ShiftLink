"""Past quotations, conditional instructions and future decisions have distinct scopes."""
from copy import deepcopy

import pytest

from shiftlink.rag2.field_history import is_history_question
from test_s30h_publication_integrity import published_history, output, G, service, pipe


HISTORY = [
    "근무일지에 '교체할 수 있다'고 기록한 시각과 결과만 알려줘",
    "근무일지에 '교체 가능해'라고 기록한 시각과 결과만 알려줘",
    '과거 근무일지에서 교체할 수 있다고 판단했던 결과와 시각만 알려줘',
    '근무일지에서 교체 가능한가 검토한 결과와 시각은?',
    '근무일지에 교체 가능해? 라고 문의했던 결과와 시각은?',
    '근무일지의 교체 결과와 시각만 알려줘. 당시 교체 가능한가 판단한 근거만 알려줘',
    '과거 근무일지에서 교체할 수 있는지 판단하였던 결과와 시각은?',
    '과거 근무일지에서 교체할 수 있는지 판단했었던 결과와 시각은?',
    '근무일지에 “내일 교체 가능해”라고 기록한 시각과 결과만 알려줘',
    '근무일지에 "지금 교체할 수 있다"고 기록한 시각과 결과만 알려줘',
    '근무일지에 ‘현재 교체 가능한가요?’라고 문의했던 시각과 결과만 알려줘',
    '근무일지에서 교체 가능한지 판단한 뒤 진행했던 결과와 시각은?',
    '근무일지에서 교체 가능 여부를 확인한 후 작업을 시작했던 결과와 시각은?',
    "근무일지에 '교체 가능해'라고 기록한 뒤 진행했던 결과와 시각은?",
    "오늘 작성한 근무일지에 '교체 가능해'라고 기록한 결과와 시각은?",
    '과거 근무일지의 교체 안전성을 검토했던 결과와 시각은?',
    '오늘 근무일지의 교체 안전성을 검토했던 결과와 시각은?',
]
CURRENT = [
    '근무일지 결과를 보고 교체 가능한지 판단한 뒤 진행해줘',
    '근무일지 결과를 보고 교체 가능 여부를 확인한 후 작업을 시작해줘',
    '근무일지 결과를 보고 교체 가능한지 판단한 뒤 결과를 알려줘',
    '근무일지 결과를 보고 교체 가능한지 판단한 다음에 진행해주세요',
    '근무일지 결과와 내일 교체 가능 여부 판단 결과를 알려줘',
    '근무일지 결과와 내일 압력이 회복되면 교체 가능 여부 판단 결과를 알려줘',
    '근무일지 결과와 다음 주 교체 가능 여부 판단 결과를 알려줘',
    '근무일지 결과와 앞으로 교체 가능 여부 판단 결과를 알려줘',
    '근무일지 결과와 내일 교체 가능한지 판단한 결과를 알려줘',
    "근무일지에 '교체 가능해'라고 기록한 시각과 결과를 알려주고 오늘 교체 가능한가요?",
    "근무일지 결과와 '교체 가능해'라고 기록하기 전에 교체 가능한지 확인해줘",
    '근무일지에서 교체 가능한지 판단한 뒤 진행했던 결과와 오늘 교체할 수 있는지 알려줘',
    '근무일지 결과와 내일 가능 여부는 묻지 않아. 지금 교체 가능한가요?',
    "근무일지 결과와 '교체 가능해'라고 기록한 뒤 진행해줘",
    "근무일지에 '교체 가능해'라고 기록한 결과와 내일 교체 가능 여부 판단 결과를 알려줘",
    '근무일지의 교체 결과와 시각만 알려줘. 현재 상태는 판단하지 말고 오늘 교체 안전성을 알려줘',
]


@pytest.mark.parametrize('question,expected',
                         [(q, True) for q in HISTORY] + [(q, False) for q in CURRENT])
def test_request_scope(question, expected):
    assert is_history_question(question) is expected


@pytest.mark.parametrize('question', HISTORY)
def test_published_quoted_history_preserves_original(published_history, monkeypatch, question):
    svc, did = published_history
    original = deepcopy(svc.storage.get_card_draft(did))
    card = original['review_flags']['publication']['card']
    calls = []
    monkeypatch.setattr(G, 'ask_raw', lambda *a, **k: calls.append(a) or output('자료 확인 [S1].', ['S1']))
    result = svc.query({'equipment_id': 'EQ-0001', 'question': question})
    assert result['s30h_trace']['route'] == 'record_history'
    assert not calls and not result['no_knowledge']
    assert result['cited_card_ids'] == [did]
    assert all(card[key] in result['answer'] for key in ('title', 'know_how', 'rationale'))
    assert all(value in result['answer'] for value in ('137분', '09:10', '09:20', '검증자'))
    assert '현재 MES(' not in result['answer']
    assert svc.storage.get_card_draft(did) == original
    assert svc.storage.get_query(result['query_id'])['payload']['answer'] == result['answer']


@pytest.mark.parametrize('question', CURRENT)
def test_published_conditional_and_future_request_keeps_mes(published_history, monkeypatch, question):
    svc, did = published_history
    original = deepcopy(svc.storage.get_card_draft(did))
    calls = []
    monkeypatch.setattr(G, 'ask_raw', lambda prompt, *a, **k:
                        calls.append(prompt) or output('판단에 필요한 자료 확인 [S1].', ['S1']))
    result = svc.query({'equipment_id': 'EQ-0001', 'question': question})
    assert calls and '[MES]' in calls[0] and question in calls[0]
    assert result['s30h_trace']['route'] != 'record_history'
    assert result['cited_card_ids'] == [did]
    assert svc.storage.get_card_draft(did) == original
    assert svc.storage.get_query(result['query_id'])['payload']['answer'] == result['answer']
