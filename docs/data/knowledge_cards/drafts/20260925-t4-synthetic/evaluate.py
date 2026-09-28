"""Batch adapter for the existing B evaluator; no source approval or model judge."""
from pathlib import Path
from collections import Counter
from itertools import combinations
from dataclasses import asdict
from datetime import datetime, timezone
from copy import deepcopy
from difflib import SequenceMatcher
import hashlib
import json
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))
from pydantic import ValidationError
from eval.evaluators import evaluate_category_b
from shiftlink.agent.schemas import KnowledgeCard, HandoverMethod, SCHEMA_VERSION
from shiftlink.data.card_lint import lint_cards
from shiftlink.data.generation import _reject_unknown
from shiftlink.rag.retrieval import InMemoryToolProvider


def read(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cards, manifest = read('cards.json'), read('manifest.json')
    mapping = read('evidence-map.json')['cards']
    sources = read('synthetic-sources.json')
    narratives = read('narratives.json')
    policy = read('batch-policy.json')
    specs = read('specs-01-13.json') + read('specs-14-25.json')
    specs.sort(key=lambda s:s['method_key'])
    specs_hash = hashlib.sha256(json.dumps(specs,ensure_ascii=False,sort_keys=True,
                                          separators=(',', ':')).encode()).hexdigest()
    assert specs_hash == manifest['specs_sha256']
    content_hash = hashlib.sha256(json.dumps({'specs': specs, 'policy': policy},ensure_ascii=False,
                           sort_keys=True,separators=(',', ':')).encode()).hexdigest()
    assert content_hash == manifest['content_input_sha256']
    assert manifest['content_version'] == 'synthetic-' + content_hash[:12]
    assert policy == manifest['batch_policy']
    specs_by_key = {s['method_key']:s for s in specs}
    assert len(specs_by_key)==25
    assert len(cards) == len(mapping) == len(sources) == len(narratives) == 25
    assert len({c['card_id'] for c in cards}) == 25
    assert manifest['card_ids'] == [c['card_id'] for c in cards]
    assert not set(manifest['card_ids']) & set(manifest['id_inventory_used_ids'])
    for path, expected in manifest['id_inventory'].items():
        assert digest(ROOT / path) == expected, ('identifier inventory changed', path)
    original_path = HERE.parent / '20260925-t4-evidence-review/sources.json'
    assert digest(original_path) == manifest['original_review_sha256']
    original = json.loads(original_path.read_text(encoding='utf-8'))
    original_refs = {e['evidence_ref'] for e in original['evidence']}
    for s in original['sources']:
        assert digest(ROOT / s['path']) == s['sha256'], s['path']
    originals = json.loads((original_path.parent/'candidates.json').read_text(encoding='utf-8'))['candidates']
    positives, negative_groups, failures = [], Counter(), []
    dev_blocked = draft_excluded = original_fields = original_complete = 0
    for card, link, source, narrative in zip(cards, mapping, sources, narratives):
        checked = KnowledgeCard.model_validate(card)
        _reject_unknown(card, checked.model_dump(mode='json'))
        result = evaluate_category_b({'case_id':card['card_id'], 'input':card}, {'outcome':'valid'})
        assert result.passed, result
        positives.append(asdict(result))
        assert card['status']=='draft' and card['grade']=='L0' and card['split']=='dev'
        assert card['tacit_type']=='T4' and card['safety_review']=={'status':'pending_review','review_triggers':[]}
        assert card['provenance']['event_ids']==[]
        assert card['version']==manifest['content_version']
        assert datetime.fromisoformat(card['provenance']['generated_at'])==datetime.fromisoformat(manifest['generated_at'])
        assert card['provenance']['schema_version']==SCHEMA_VERSION
        assert card['generalization_evidence']['supporting_event_ids']==[]
        assert card['generalization_evidence']['contradicting_event_ids']==[]
        assert '[합성' in card['title'] and '[합성' in card['know_how']
        assert source['is_synthetic'] and not source['human_approval']
        assert not source['independent_factual_evidence']
        assert narrative['is_synthetic'] and not narrative['counts_as_factual_evidence']
        assert narrative['text'].startswith('[합성·인계 연습')
        assert narrative['persona_id']==card['provenance']['persona_id']==source['persona_id']
        assert link['card_id']==narrative['card_id']==card['card_id']
        assert source['source_id']==card['provenance']['sources'][0]['source_id']
        assert link['method_key']==source['method_key']==narrative['method_key']
        assert source['full_design']==specs_by_key[source['method_key']]
        assert source['persona_id']==source['full_design']['persona_id']
        assert source['field_values']==source['full_design']['handover_method']
        assert narrative['text']==source['full_design']['synthetic_narrative']
        assert card['provenance']['seed_ids']==[source['source_id']]
        assert card['provenance']['sources']==[{'source_id':source['source_id'],
               'locator':'synthetic-sources.json#'+source['method_key'],
               'document_version':manifest['content_version']}]
        hm = card['type_payload']['handover_method']
        assert hm==source['field_values']
        assert set(link['fields'])==set(HandoverMethod.model_fields)
        supported = 0
        for field, annotation in link['fields'].items():
            assert annotation['value']==hm[field]
            if annotation['kind']=='original':
                assert annotation['independent_factual_evidence'] is True
                assert annotation['synthetic_source_ref'] is None
                refs = annotation['original_evidence_refs']
                assert refs and set(refs)<=original_refs
                assert any(c['fields'][field].get('support')=='supported'
                           and c['fields'][field].get('value')==hm[field]
                           and set(refs)<=set(c['fields'][field]['evidence_refs']) for c in originals)
                supported += 1
            else:
                assert annotation['kind']=='synthetic_proposal'
                assert annotation['independent_factual_evidence'] is False
                assert annotation['original_evidence_refs']==[]
                assert annotation['synthetic_source_ref']==source['source_id']
            for mutation in ('missing','blank'):
                bad=deepcopy(card)
                bad_method=bad['type_payload']['handover_method']
                if mutation=='missing':
                    del bad_method[field]
                else:
                    bad_method[field]=['   '] if field=='required_context' else '   '
                probe = evaluate_category_b({'case_id':card['card_id']+'-'+mutation+'-'+field,'input':bad},
                                            {'outcome':'invalid'})
                matching_error=False
                try:
                    KnowledgeCard.model_validate(bad)
                except ValidationError as exc:
                    matching_error=any(tuple(e['loc'][:3])==('type_payload','handover_method',field)
                                       for e in exc.errors())
                if probe.passed and matching_error:
                    negative_groups[mutation+':'+field]+=1
                else:
                    failures.append({'card_id':card['card_id'],'mutation':mutation,'field':field})
        assert card['confidence']==supported/5
        original_fields+=supported
        original_complete+=int(supported==5)
        try:
            InMemoryToolProvider(cards=[checked])
        except ValueError as exc:
            assert 'does not accept dev/sealed cards' in str(exc)
            dev_blocked+=1
        # Transient probe only; never save this split or adopt a card.
        draft=checked.model_copy(update={'split':'kb'})
        provider=InMemoryToolProvider(cards=[draft])
        assert provider.cards==[]
        assert provider.search_cards(query=draft.title,equipment_ids=['COMMON'],k=1)==[]
        draft_excluded+=1
    assert not failures and sum(negative_groups.values())==250
    assert dev_blocked==draft_excluded==25
    lint=lint_cards(cards,known_fields=set(KnowledgeCard.model_fields))
    assert not any(f['severity']=='violation' for rows in lint['findings'].values() for f in rows)

    pairs=[]
    for a,b in combinations(sources,2):
        left,right=a['full_design'],b['full_design']
        # Name/equipment/persona are excluded. This heuristic only flags review pairs.
        atext=' '.join([left['trigger'],left['transfer_object'],left['verification_mechanism']])
        btext=' '.join([right['trigger'],right['transfer_object'],right['verification_mechanism']])
        ratio=SequenceMatcher(None,atext,btext).ratio()
        exact=a['field_values']==b['field_values']
        assert not exact, (a['method_key'],b['method_key'])
        pairs.append({'left':a['method_key'],'right':b['method_key'],'text_similarity':round(ratio,4),
                      'exact_method_duplicate':exact})
    result={'evaluated_at':datetime.now(timezone.utc).isoformat(), 'schema_version':SCHEMA_VERSION,
            'evaluation_scope':'new synthetic batch, existing evaluate_category_b called directly; no production approval',
            'cards_sha256':digest(HERE/'cards.json'), 'positive_cases':positives,
            'schema_passed':len(positives), 'schema_total':25,
            'negative_probe_passed':sum(negative_groups.values()), 'negative_probe_total':250,
            'negative_groups':dict(negative_groups), 'negative_failures':failures,
            'dev_gate_blocked':dev_blocked,'draft_gate_excluded':draft_excluded,
            'field_links_checked':len(mapping)*5,'source_direct_fields':original_fields,
            'source_direct_field_ratio':original_fields/(25*5),
            'original_complete_cards':original_complete,'independent_verified_site_events':0,
            'lint':lint,'pairwise_comparisons':len(pairs),
            'similarity_note':'Lexical triage only, not a semantic uniqueness score. Independent AI reviews remain necessary.',
            'most_similar_pairs':sorted(pairs,key=lambda p:p['text_similarity'],reverse=True)[:20],
            'all_pair_comparisons':pairs,
            'source_integrity_passed':True,'synthetic_traceability_passed':True,
            'human_source_approval':False,'human_safety_review':False,'adopted':False,
            'input_hashes':{p.name:digest(p) for p in HERE.glob('*.json')
                           if p.name not in {'harness-results.json','quality-results.json'}},
            'evaluator_code_sha256':digest(ROOT/'eval/evaluators.py'),
            'adapter_code_sha256':digest(Path(__file__))}
    (HERE/'harness-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['schema_passed','negative_probe_passed','dev_gate_blocked',
          'draft_gate_excluded','source_direct_fields','original_complete_cards','pairwise_comparisons']}))


if __name__=='__main__':
    main()
