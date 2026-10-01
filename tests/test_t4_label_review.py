"""Adjudicated gold: alternatives, conjunctions and deferred items are distinct."""
import json
from pathlib import Path
import pytest
from eval.qa.score import score_item, run, summarize
from eval.qa.route_score import route_ok
from eval.qa.report import verdict, render_report
from eval.qa.label_contract import validate_label

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'eval/qa/20260930-T4'


def outcome(cited=(), ranked=(), safety=()):
    return dict(cited=list(cited), ranked=list(ranked), safety=list(safety), no_knowledge=False)


def label(**extra):
    return dict(answerable=True, primary_card_ids=['K-1104', 'K-1108'],
                acceptable_card_ids=[], safety_card_ids=[], **extra)


def test_legacy_multiple_primary_still_means_alternatives():
    assert score_item(label(), outcome(['K-1104']))['hit']
    assert score_item(label(), outcome(['K-1108']))['hit']


@pytest.mark.parametrize('ids,complete', [(['K-1104'], False), (['K-1108'], False), (['K-1104', 'K-1108'], True)])
def test_joint_answer_requires_the_whole_set(ids, complete):
    item = label(primary_card_sets=[['K-1104', 'K-1108']])
    score = score_item(item, outcome(ids, ids))
    assert score['hit'] is complete
    assert score['retrieval_hit_at_k'] is complete
    assert score['retrieval_hit_at_1'] is None
    assert not score['partial']
    assert route_ok(item, ids) is None


def test_safety_reference_is_not_an_answer():
    item = {**label(), 'safety_card_ids': ['K-1024']}
    score = score_item(item, outcome(['K-1024'], safety=['K-1024']))
    assert score['safety_ok'] and not score['hit']
    assert score['wrong_cite_rate'] == 1


def test_alternative_complete_sets_do_not_require_every_alternative():
    item = dict(answerable=True, primary_card_ids=['A', 'B', 'C'], acceptable_card_ids=[], safety_card_ids=[], primary_card_sets=[['A', 'B'], ['C']])
    assert not score_item(item, outcome(['A']))['hit']
    assert score_item(item, outcome(['A', 'B']))['hit']
    assert score_item(item, outcome(['C'], ['C']))['retrieval_hit_at_1']


def test_label_validation_rejects_unknown_ids_and_inconsistent_groups():
    item = dict(qid='test', **label(), key_facts=[])
    cards = {'K-1104': {}, 'K-1108': {}}
    validate_label(item, cards)
    with pytest.raises(ValueError, match='unknown card'):
        validate_label({**item, 'acceptable_card_ids': ['UNKNOWN']}, cards)
    with pytest.raises(ValueError, match='union differs'):
        validate_label({**item, 'primary_card_sets': [['K-1104']]}, cards)


def test_deferred_item_neither_calls_model_nor_rewards_abstention():
    class MustNotRun:
        def run(self, request):
            raise AssertionError('deferred question should not be sent to a model')
    item = dict(qid='H-019', eq_id='GR', question='진행 중 점검 완료 확인', observations={},
                answerable=False, primary_card_ids=[], acceptable_card_ids=[], safety_card_ids=[],
                evaluation_status='deferred', defer_reason='완료 확인 근거 없음')
    score = score_item(item, outcome())
    assert score == {'evaluation_deferred': True}
    rows = run([item], MustNotRun(), mode='handover')
    summary = summarize(rows)
    assert summary['deferred'] == 1 and summary['evaluated'] == 0
    assert summary['answerable'] == summary['unanswerable'] == 0
    assert summary['abstain_ok'] is None
    assert route_ok(item, []) is None
    assert verdict(score) == 'deferred'


def test_reviewed_dataset_is_consistent_and_does_not_invent_question_facts():
    raw = json.loads((BASE / 'questions_raw.json').read_text(encoding='utf-8'))
    labels = json.loads((BASE / 'labels.json').read_text(encoding='utf-8'))
    dev = json.loads((BASE / 'qa_dev_t4.json').read_text(encoding='utf-8'))
    audit = json.loads((BASE / 'adjudication_20261001.json').read_text(encoding='utf-8'))
    by_id = {item['qid']: item for item in dev}
    for question, answer in zip(raw, labels):
        assert by_id[question['qid']] == {**question, **answer, 'split': 'dev'}
    for reviewed in audit['items']:
        item = by_id[reviewed['qid']]
        assert item['question'] == reviewed['original_question']
        assert item['primary_card_ids'] == reviewed['final_label']['primary_card_ids']
        assert item['acceptable_card_ids'] == item['safety_card_ids'] == []
    assert by_id['H-008']['primary_card_ids'] == ['K-1104']
    assert by_id['H-012']['primary_card_ids'] == ['K-1108']
    assert by_id['H-017']['primary_card_ids'] == ['K-1108']
    assert by_id['H-016']['primary_card_sets'] == [['K-1104', 'K-1108']]
    assert by_id['H-018']['evaluation_status'] == 'deferred'
    assert by_id['H-019']['answerable'] is True
    assert by_id['H-019']['primary_card_ids'] == ['K-1401']
    assert by_id['H-019'].get('evaluation_status', 'active') == 'active'


def test_completion_answer_is_backed_by_a_loaded_source_procedure():
    from shiftlink.rag.loader import load_card_provider
    from eval.qa.route_score import route
    item = next(x for x in json.loads((BASE / 'qa_dev_t4.json').read_text(encoding='utf-8')) if x['qid'] == 'H-019')
    provider = load_card_provider(ROOT / 'docs/data/knowledge_cards/kb/kb_cards.json').provider
    cards = {c.card_id: c for c in provider.cards}
    assert 'K-1401' in cards
    card = cards['K-1401']
    assert card.tacit_type == 'T3'
    assert card.provenance.event_ids == []
    assert any('hsg250.pdf' in s.source_id for s in card.provenance.sources)
    validate_label(item, {cid: c.model_dump() for cid, c in cards.items()})
    ranked = route(provider, item, handover=True)
    assert route_ok(item, ranked) is True
    assert score_item(item, outcome(['K-1401']))['hit'] is True


def test_report_exposes_adjudication_and_manual_fact_checks():
    item = dict(qid='H-016', eq_id='GR', question='소리와 온도 미확인',
                primary_card_ids=['K-1104', 'K-1108'], acceptable_card_ids=[],
                primary_card_sets=[['K-1104', 'K-1108']], key_facts=['온도는 확인 못 함'], label_note='두 근거 모두 필요')
    row = dict(qid='H-016', eq_id='GR', score={'hit': False, 'partial': False}, cited=['K-1104'], ranked=[], safety=[], answer='소리 기록')
    rendered = render_report({'rows': [row]}, [item])
    assert 'K-1104 + K-1108' in rendered
    assert '온도는 확인 못 함' in rendered
    assert '두 근거 모두 필요' in rendered
