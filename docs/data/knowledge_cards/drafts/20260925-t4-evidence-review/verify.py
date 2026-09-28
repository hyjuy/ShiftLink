"""Verify this review packet; does not approve sources or generate card values.

Run with the bundled Python (pydantic + pypdf), from any directory.
"""
from pathlib import Path
from collections import defaultdict
from itertools import combinations
from datetime import datetime, timezone
import hashlib
import json
import re
import sys

from pydantic import ValidationError
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))
from shiftlink.agent.schemas import HandoverMethod, KnowledgeCard, SCHEMA_VERSION
import pydantic
import pypdf


def read(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(text):
    return re.sub(r'\s+', ' ', text).strip()


def errors(model, value):
    try:
        model.model_validate(value)
        return []
    except ValidationError as exc:
        return [{'location': '.'.join(map(str, e['loc'])), 'type': e['type'],
                 'message': e['msg']} for e in exc.errors()]


def main():
    packet, batch = read('sources.json'), read('candidates.json')
    cards, synthetic = read('cards.json'), read('synthetic-narratives.json')
    evidence = {e['evidence_ref']: e for e in packet['evidence']}
    assert len(evidence) == len(packet['evidence'])
    source_paths = {s['path'] for s in packet['sources']}
    assert source_paths == {p.relative_to(ROOT).as_posix()
                            for p in (ROOT / 'docs/data/events').rglob('*')
                            if p.suffix.lower() in {'.pdf', '.html'}}
    for source in packet['sources']:
        assert digest(ROOT / source['path']) == source['sha256'], source['path']
    for path, expected in packet['input_hashes'].items():
        assert digest(ROOT / path) == expected, path
    readers = {}
    for e in evidence.values():
        assert e['path'] in source_paths
        assert hashlib.sha256(e['excerpt'].encode()).hexdigest() == e['excerpt_sha256']
        if e['path'] not in readers:
            readers[e['path']] = PdfReader(ROOT / e['path'])
        page = readers[e['path']].pages[e['pdf_page'] - 1]
        assert e['excerpt'] in normalize(page.extract_text()), e['evidence_ref']

    required = set(HandoverMethod.model_fields)
    probes = []
    normalized = defaultdict(list)
    for c in batch['candidates']:
        assert set(c['fields']) == required
        assert c['disposition'] == '보완 대기' and not c['count_as_valid_draft']
        method = {}
        for field, item in c['fields'].items():
            assert set(item['evidence_refs']) <= evidence.keys()
            if item['support'] == 'supported':
                assert item['evidence_refs'] and item['value']
                method[field] = item['value']
            else:
                assert item['support'] in {'missing', 'partial'}
                assert 'value' not in item
        signature = normalize(json.dumps(method, ensure_ascii=False, sort_keys=True))
        normalized[signature].append(c['candidate_ref'])
        # This is a completion probe, not a newly generated KnowledgeCard.
        content = {'tacit_type': 'T4', 'title': c['title'],
                   'type_payload': {'handover_method': method}}
        method_errors = errors(HandoverMethod, method)
        card_errors = errors(KnowledgeCard, content)
        expected_missing = required - method.keys()
        assert {e['location'] for e in method_errors} == expected_missing
        assert all(e['type'] == 'missing' for e in method_errors)
        assert card_errors  # Missing management/content inputs must never be invented.
        probes.append({'candidate_ref': c['candidate_ref'],
                       'method_schema_passed': not method_errors,
                       'missing_method_fields': sorted(expected_missing),
                       'method_errors': method_errors,
                       'knowledge_card_completion_probe_passed': not card_errors,
                       'knowledge_card_completion_errors': card_errors})

    # No production drafts are permitted by the evidence and inputs in this packet.
    assert cards == []
    assert synthetic['is_synthetic'] and synthetic['counts_as_evidence'] is False
    assert {n['persona_id'] for n in synthetic['narratives']} == {'V-11', 'V-12', 'V-13'}
    assert all(n['is_synthetic'] and n['source_candidate_ref'] == 'Q01'
               and '[합성·원문 검토 메모]' in n['text'] for n in synthetic['narratives'])
    assert not any(ref.startswith(('V-', 'Q')) for ref in evidence)

    source_hashes = defaultdict(list)
    for s in packet['sources']:
        source_hashes[s['sha256']].append(s['path'])
    exact_duplicates = [refs for refs in normalized.values() if len(refs) > 1]
    assert not exact_duplicates
    assert len({c['candidate_ref'] for c in batch['candidates']}) == len(probes)
    pairs = [{'left': a['candidate_ref'], 'right': b['candidate_ref'],
              'comparison_basis': [a['substantive_difference'], b['substantive_difference']]}
             for a, b in combinations(batch['candidates'], 2)]
    result = {
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'schema_version': SCHEMA_VERSION,
        'runtime': {'python': sys.version.split()[0], 'pydantic': pydantic.__version__,
                    'pypdf': pypdf.__version__},
        'packet_integrity_passed': True,
        'source_files_checked': len(source_paths),
        'pdf_pages_in_inventory': sum(s['pdf_pages'] or 0 for s in packet['sources']),
        'exact_source_hash_duplicates': [p for p in source_hashes.values() if len(p) > 1],
        'excerpts_verified_against_pdf': len(evidence),
        'candidate_schema_probes': probes,
        'method_schema_pass_count': sum(p['method_schema_passed'] for p in probes),
        'whole_card_completion_pass_count': 0,
        'draft_cards_submitted_to_schema': len(cards),
        'draft_schema_check': 'not_applicable_no_eligible_cards',
        'normalized_method_duplicates': exact_duplicates,
        'pairwise_review_basis': pairs,
        'semantic_review': 'Assistant source-based comparison documented in review.md; not a human review or a general semantic detector.',
        'global_kb_duplicate_check': 'not_performed_no_eligible_cards',
        'target': 25, 'valid_drafts': 0, 'shortfall': 25,
        'independent_verified_site_events': 0,
        'human_source_approval_performed': False,
        'human_safety_review_performed': False,
        'card_adoption_performed': False,
        'pipeline_generation_run': 'not_run_missing_evidence_and_operator_inputs',
        'output_hashes': {n: digest(HERE / n) for n in ['sources.json', 'candidates.json',
                           'cards.json', 'synthetic-narratives.json', 'review.md', 'verify.py']},
    }
    (HERE / 'validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)
                                           + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ['packet_integrity_passed', 'source_files_checked',
          'excerpts_verified_against_pdf', 'method_schema_pass_count', 'valid_drafts', 'shortfall']}))


if __name__ == '__main__':
    main()
