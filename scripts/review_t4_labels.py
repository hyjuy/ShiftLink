"""Reproduce targeted T4 ranks and separate relabeling from retrieval changes."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from eval.qa.route_score import route, route_ok
from eval.qa.score import score_item
from eval.qa.label_contract import validate_label
from shiftlink.rag.loader import load_card_provider

TARGETS = ['H-008', 'H-012', 'H-016', 'H-017', 'H-018', 'H-019']
QA = ROOT / 'eval/qa/20260930-T4'
KB = ROOT / 'docs/data/knowledge_cards/kb/kb_cards.json'
OUT = ROOT / 'artifacts/t4-label-review-20261001'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def snapshot():
    kb_bytes = KB.read_bytes()
    provider = load_card_provider(KB).provider
    data = {name: load(QA / name) for name in ('questions_raw.json', 'labels.json', 'qa_dev_t4.json')}
    rows = []
    for item in data['qa_dev_t4.json']:
        if item['qid'] not in TARGETS:
            continue
        ranked = route(provider, item, handover=True)
        rows.append({'qid': item['qid'], 'question': item['question'], 'ranked': ranked,
                     'route_ok': route_ok(item, ranked)})
    assert KB.read_bytes() == kb_bytes, 'KB changed during search; rerun to get one consistent snapshot'
    return {'kb_sha256': hashlib.sha256(kb_bytes).hexdigest(), 'mode': 'handover', 'k': 5,
            'data': data, 'rows': rows}


def compare(before, after):
    old_items = {r['qid']: r for r in before['data']['qa_dev_t4.json']}
    new_items = {r['qid']: r for r in after['data']['qa_dev_t4.json']}
    old_rows = {r['qid']: r for r in before['rows']}
    rows = []
    for row in after['rows']:
        qid, ranked = row['qid'], row['ranked']
        # This is a rank-1 citation PROBE, not a generated answer score.
        probe = {'cited': ranked[:1], 'ranked': ranked, 'safety': [], 'no_knowledge': not ranked}
        rows.append({'qid': qid, 'ranks_unchanged': ranked == old_rows[qid]['ranked'],
                     'ranked': ranked, 'old_label_score_on_same_rank1_probe': score_item(old_items[qid], probe),
                     'new_label_score_on_same_rank1_probe': score_item(new_items[qid], probe)})
    cards = {c['card_id']: c for c in load(KB)['cards']}
    raw = after['data']['questions_raw.json']
    labels = after['data']['labels.json']
    dev = after['data']['qa_dev_t4.json']
    assert len(raw) == len(labels) == len(dev) == 20
    assert len({q['qid'] for q in raw}) == 20
    for question, label, item in zip(raw, labels, dev):
        assert question['qid'] == label['qid'] == item['qid']
        assert item == {**question, **label, 'split': 'dev'}
        validate_label(label, cards)
        if item['qid'] not in TARGETS:
            assert item == old_items[item['qid']], 'Unrelated question changed'
    t4 = load(ROOT / 'docs/data/knowledge_cards/kb/20260930-T4/cards.json')
    assert all(cards[c['card_id']] == c for c in t4), 'T4 card copies differ'
    return {'validation': '20 unique IDs, JSON/label contract/card IDs, merged copies, untouched 14 items, T4 card copies passed',
            'kb_unchanged': before['kb_sha256'] == after['kb_sha256'],
            'questions_unchanged': before['data']['questions_raw.json'] == after['data']['questions_raw.json'],
            'retrieval_improvement': False, 'rows': rows,
            'limitations': ['Old and new labels are scored on the SAME current ranks; an initial KB hash change prevents historical search comparison.',
                            'No LLM answers were generated; citation probes do not measure answer completeness.',
                            'Deferred items do not count as unanswerable abstention successes.',
                            'Scores on different eligible denominators must not be compared as search improvement.']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('before', 'after'))
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    result = snapshot()
    if args.phase == 'after':
        result['comparison'] = compare(load(OUT / 'before.json'), result)
    destination = OUT / f'{args.phase}.json'
    if args.phase == 'before' and destination.exists():
        raise SystemExit('Refusing to overwrite the pre-adjudication snapshot')
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for row in result['rows']:
        print(row['qid'], row['ranked'], 'route_ok=', row['route_ok'])
    print('saved', destination)


if __name__ == '__main__':
    main()
