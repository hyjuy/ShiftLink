"""Past decisions and negated requests must not become present MES judgements."""
from copy import deepcopy

import pytest

from shiftlink.rag2.field_history import is_history_question
from test_s30h_publication_integrity import published_history, output, G, service, pipe


HISTORY = [
    '근무일지 과거 교체 가능 여부 판단 결과는?',
    '근무일지 과거 교체 가능한지 확인했던 결과는?',
    '과거 근무일지에서 교체 가능한지 판단했던 결과와 시각은?',
    '과거 근무일지의 필터 교체 가능 여부 판단 결과와 시각은?',
    '과거 근무일지의 작업 가능 여부 판단 결과와 시각만 알려줘',
    '과거 근무일지의 작업 가능한지 판단한 결과와 시각만 알려줘',
    '과거 근무일지의 작업 가능할지 판단한 결과와 시각만 알려줘',
    '근무일지의 교체 순서와 결과에서 당시 교체 가능한지 판단했던 근거는?',
    '근무일지의 교체 순서와 결과만 알려줘. 오늘 작업 가능 여부는 묻지 않아.',
    '오늘 근무일지의 교체 가능 여부 판단 결과와 시각은?',
    '근무일지의 교체 순서와 결과만 알려줘. 현재 상태는 판단하지 말고.',
    '근무일지의 결과만 알려줘. 지금 작업 가능한지는 묻지 않습니다.',
]
CURRENT = [
    '근무일지 결과와 오늘 교체 가능해?',
    '근무일지 결과와 오늘 교체할 수 있어?',
    '근무일지 결과와 오늘 작업 안전성을 평가해줘',
    '근무일지의 교체 결과와 오늘 교체 가능한가요?',
    '근무일지의 교체 결과와 오늘 교체할 수 있는지 알려줘',
    '근무일지 결과와 오늘 교체 가능합니까?',
    '근무일지 결과와 오늘 교체 가능하겠어?',
    '과거 근무일지의 작업 가능 여부 판단 결과와 오늘 교체 가능한가요?',
    '과거 근무일지의 가능한지 판단했던 결과와 오늘 교체 가능 여부를 알려줘',
    '근무일지 결과와 교체 가능한가요?',
    '근무일지 결과와 오늘 교체 가능 여부 판단 결과를 알려줘',
    '근무일지 결과만 알려줘. 오늘 가능 여부는 묻지 않아. 지금 교체할 수 있어?',
    '현재 상태가 아니라 과거 근무일지 결과를 알려주고 오늘 교체 가능한가요?',
    '근무일지 결과와 오늘 교체 가능한지 알려주고 현재 정격은 묻지 않아.',
]


@pytest.mark.parametrize('question,expected',
                         [(q, True) for q in HISTORY] + [(q, False) for q in CURRENT])
def test_history_intent_scope(question, expected):
    assert is_history_question(question) is expected


@pytest.mark.parametrize('question', HISTORY)
def test_published_past_decision_preserves_original(published_history, monkeypatch, question):
    svc, did = published_history
    original = deepcopy(svc.storage.get_card_draft(did))
    calls = []
    monkeypatch.setattr(G, 'ask_raw', lambda *a, **k: calls.append(a) or output('자료 확인 [S1].', ['S1']))
    result = svc.query({'equipment_id': 'EQ-0001', 'question': question})
    assert result['s30h_trace']['route'] == 'record_history'
    assert not calls and not result['no_knowledge']
    assert result['cited_card_ids'] == [did]
    assert all(v in result['answer'] for v in ('137분', '09:10', '09:20', '검증자', '필터 오염 확인', '필터 교체'))
    card = original['review_flags']['publication']['card']
    assert all(card[key] in result['answer'] for key in ('title', 'know_how', 'rationale'))
    assert '현재 MES(' not in result['answer']
    assert svc.storage.get_query(result['query_id'])['payload']['answer'] == result['answer']
    assert svc.storage.get_card_draft(did) == original


@pytest.mark.parametrize('question', CURRENT)
def test_published_current_paraphrase_uses_mes(published_history, monkeypatch, question):
    svc, did = published_history
    original = deepcopy(svc.storage.get_card_draft(did))
    calls = []
    monkeypatch.setattr(G, 'ask_raw', lambda prompt, *a, **k:
                        calls.append(prompt) or output('현재 판단에 필요한 자료 확인 [S1].', ['S1']))
    result = svc.query({'equipment_id': 'EQ-0001', 'question': question})
    assert calls and '[MES]' in calls[0] and question in calls[0]
    assert result['s30h_trace']['route'] != 'record_history'
    assert result['cited_card_ids'] == [did]
    assert svc.storage.get_query(result['query_id'])['payload']['answer'] == result['answer']
    assert svc.storage.get_card_draft(did) == original
