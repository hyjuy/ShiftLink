"""Regressions for the isolated-device citation and work-log history failures."""
import json

import pytest

from test_s30h import pipe, E, G
from test_work_report_reuse_harness import service
from test_work_report_capture import captured
from test_publication_worker import quality_pass, vectors
from shiftlink.rag2.field_history import is_history_question, record_sources


def output(text, citations):
    return {'raw': json.dumps({'insufficient_evidence': False, 'answer': text,
                               'citations': citations}, ensure_ascii=False)}


@pytest.mark.parametrize('question,text,citations', [
    ('조치 결과는?', '정상 운전은 120분입니다 [S1].', ['S1']),
    ('120분 정상 운전했나요?', '120분 정상 운전했습니다 [S1].', ['S1']),
    ('조치 결과는?', '120분 정상 운전했습니다 [S1]. 압력을 확인했습니다 [S2].', ['S1', 'S2']),
])
def test_number_must_be_supported_by_its_cited_source(question, text, citations):
    evidence = [{'text': '필터 교체 후에도 압력이 회복되지 않았다.'},
                {'text': '필터 교체 후 120분 정상 운전했다.'}]
    result = G.check(output(text, citations), evidence, question)
    assert result['abstain'] and result['reason'] == 'unsupported_number'
    assert result['number_violations'] == ['120']


def test_supported_numbers_keep_their_source_and_answer():
    evidence = [{'text': '필터 교체 후 120분 정상 운전했다. 차압 0.6 bar.'}]
    result = G.check(output('120분 정상 운전, 차압 0.6 bar [S1].', ['S1']), evidence, '')
    assert not result['abstain'] and result['valid_cites'] == ['S1']


def test_runtime_abstains_instead_of_saving_a_wrong_numeric_citation(pipe, monkeypatch):
    monkeypatch.setattr(E, 'judge_dist', lambda *a, **k: [0, 0, 1, 0])
    monkeypatch.setattr(G, 'ask_raw', lambda *a, **k: output('120분 정상 운전 [S1].', ['S1']))
    result = pipe.run({'question': '필터 조치 결과는?', 'eq_id': 'EQ-0001'})
    assert result.output.no_knowledge and not result.output.cited_card_ids
    assert result.tool_results['abstain_reason'] == 'unsupported_number'


def test_numeric_failure_is_withheld_not_a_new_knowledge_gap(service, pipe, monkeypatch):
    service.query_pipeline = pipe
    monkeypatch.setattr(E, 'judge_dist', lambda *a, **k: [0, 0, 1, 0])
    monkeypatch.setattr(G, 'ask_raw', lambda *a, **k: output('120분 정상 운전 [S1].', ['S1']))
    result = service.query({'question': '필터 조치 결과는?', 'equipment_id': 'EQ-0001'})
    assert result['knowledge_status'] == 'answer_withheld' and result['review_queue']
    assert result['cited_card_ids'] == []


@pytest.fixture
def published_history(service, pipe, monkeypatch):
    note = captured(service)
    record = note['work_report']['records'][0]
    record.update(normal_run_minutes=137, normal_run_evidence='137분 연속 운전, 정지·재발 없음')
    record['action_steps'][0].update(worker='검증자', performed_at='2026-10-22T09:10')
    record['action_steps'][1].update(worker='검증자', performed_at='2026-10-22T09:20')
    service.query_pipeline = pipe
    draft_id = quality_pass(service, note)
    service.publications.process_one(embedder=vectors)
    pipe.mes_block = pipe.mes_prefix = pipe.unobserved_guard = True
    monkeypatch.setattr(E, 'judge_dist', lambda q, row, *a, **k:
                        [0, 0, 1, 0] if row['metadata']['source'] == draft_id else [1, 0, 0, 0])
    monkeypatch.setattr(G, 'ask_raw', lambda *a, **k: output(
        'MES 정지 중이어서 정상 운전 기록은 없습니다 [M]. 조치 시각은 2026-10-22T09:10 [S1].', ['M', 'S1']))
    return service, draft_id


@pytest.mark.parametrize('question', [
    '이번 근무일지에서 필터 교체 후 137분 정상 운전을 확인한 기록의 조치 순서와 담당자, 조치 시각은?',
    '현재 MES 상태를 판단하지 말고, 과거 근무일지의 필터 점검과 교체 시각, 담당자, 137분 관찰 결과만 알려주세요.',
    '필터 오염을 확인하고 교체한 뒤 정상 운전을 확인한 기록의 조치 순서와 결과는?',
])
def test_history_preserves_each_step_and_worker_observation(published_history, question):
    service, draft_id = published_history
    result = service.query({'question': question, 'equipment_id': 'EQ-0001'})
    assert result['cited_card_ids'] == [draft_id] and not result['no_knowledge']
    assert '2026-10-22T09:10' in result['answer'] and '2026-10-22T09:20' in result['answer']
    assert '필터 오염 확인' in result['answer'] and '필터 교체' in result['answer']
    assert '137분' in result['answer'] and '검증자' in result['answer']
    assert '근무자 확인' in result['answer']
    assert '현재 MES(' not in result['answer'] and '기록은 없습니다' not in result['answer']
    assert result['s30h_trace']['route'] == 'record_history'


def test_history_does_not_resurrect_a_judge_rejected_card(published_history, monkeypatch):
    service, _ = published_history
    monkeypatch.setattr(E, 'judge_dist', lambda *a, **k: [1, 0, 0, 0])
    result = service.query({'question': '근무일지의 필터 교체 순서와 결과는?', 'equipment_id': 'EQ-0001'})
    assert result['no_knowledge'] and result['cited_card_ids'] == []
    assert '137분' not in result['answer'] and '현재 MES(' not in result['answer']


def test_unrecorded_history_duration_does_not_become_an_answer(published_history):
    service, _ = published_history
    result = service.query({'question': '근무일지에서 필터 교체 후 999분 관찰 결과와 시각은?',
                            'equipment_id': 'EQ-0001'})
    assert result['no_knowledge'] and result['cited_card_ids'] == []


def test_current_action_question_still_uses_the_model_and_mes(published_history, monkeypatch):
    service, _ = published_history
    calls = []
    monkeypatch.setattr(G, 'ask_raw', lambda p, *a, **k: calls.append(p) or output('자료 확인 [S1].', ['S1']))
    result = service.query({'question': '과거 근무일지를 참고해서 지금 필터를 교체해도 되나요?',
                            'equipment_id': 'EQ-0001'})
    assert calls and '[MES]' in calls[0]
    assert result['s30h_trace']['route'] != 'record_history'


@pytest.mark.parametrize('question', [
    '과거 근무일지를 참고해서 지금 필터를 교체해도 되나요?',
    '근무일지의 부품 제조사와 조치 결과는?',
    '근무일지의 필터 교체 방법을 추천해주세요.',
    '필터 차압 현재값은?',
    '근무일지에 기록된 부품의 정격과 품번은?',
])
def test_history_mode_is_not_an_action_or_unrecorded_specification_lookup(question):
    assert not is_history_question(question)


def test_record_source_requires_a_kept_field_card_and_preserves_query_local_data(published_history):
    service, did = published_history
    card = service.storage.get_card_draft(did)['review_flags']['publication']['card']
    row = {'chunk_id': f'field_{did}_r2_0', 'text': 'short chunk', 'metadata': {'source': did}}
    assert record_sources('137분 관찰 결과', [], [card], 'EQ-0001') == []
    assert record_sources('137분 관찰 결과', [row], [card], 'EQ-9999') == []
    assert record_sources('137분 관찰 결과', [row], [{**card, 'status': 'draft'}], 'EQ-0001') == []
    assert record_sources('137분 관찰 결과', [row], [{**card, 'provenance': {}}], 'EQ-0001') == []
    assert record_sources('137분 관찰 결과', [{**row, 'chunk_id': 'static_card'}], [card], 'EQ-0001') == []
    result = record_sources('2026-10-22 137분 관찰 결과', [row, row], [card], 'EQ-0001')
    assert len(result) == 1 and '2026-10-22T09:20' in result[0]['text']
    assert row['text'] == 'short chunk'
