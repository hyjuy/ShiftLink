"""Read-only checks of inputs; writes only this batch's validation report."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))
from pydantic import ValidationError
from shiftlink.agent.schemas import KnowledgeCard
from shiftlink.data.generation import _reject_unknown
from shiftlink.rag.retrieval import InMemoryToolProvider

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    cards = read(HERE/'cards.json')
    specs = read(HERE/'specs.json')
    sources = read(HERE/'synthetic-sources.json')
    lineage = read(HERE/'lineage.json')
    original = {c['card_id']: c for c in read(HERE/'../20260925-t4-synthetic/cards.json')}
    assert len(cards) == len(specs) == len(sources) == 5
    assert {s['method_key'] for s in specs} == {'M07','M08','M13','M16','M18'}
    for name, expected in lineage['original_file_hashes'].items():
        assert digest(HERE/name) == expected, ('original changed', name)
    negatives = 0
    for c,s,source in zip(cards,specs,sources):
        parsed = KnowledgeCard.model_validate(c)
        _reject_unknown(c, parsed.model_dump(mode='json'))
        assert (c['tacit_type'], c['equipment'], c['status'], c['grade'], c['split']) == ('T4','COMMON','draft','L0','dev')
        assert c['confidence'] == original[c['card_id']]['confidence'] == 0
        assert c['safety_review'] == original[c['card_id']]['safety_review']
        assert c['provenance']['event_ids'] == []
        assert c['version'] == source['version'] == lineage['version']
        assert c['type_payload']['handover_method'] == s['handover_method'] == source['field_values']
        assert source['full_design'] == s
        assert c['provenance']['sources'][0]['source_id'] == source['source_id']
        locator = c['provenance']['sources'][0]['locator']
        filename, key = locator.split('#')
        assert filename == 'synthetic-sources.json' and key == s['method_key'] == source['method_key']
        assert all(text in c['know_how'] for text in s['procedure']+[s['unresolved_handling']])
        assert c['know_how'] in (HERE/'cards.md').read_text(encoding='utf-8')
        for field in s['handover_method']:
            for mode in ['missing', 'blank']:
                bad = deepcopy(c)
                if mode == 'missing': del bad['type_payload']['handover_method'][field]
                else: bad['type_payload']['handover_method'][field] = [' '] if field=='required_context' else ' '
                try: KnowledgeCard.model_validate(bad)
                except ValidationError as exc:
                    assert any(tuple(e['loc'][:3]) == ('type_payload','handover_method',field) for e in exc.errors())
                    negatives += 1
                else: raise AssertionError(('invalid field accepted',field,mode))
        try: InMemoryToolProvider(cards=[parsed])
        except ValueError as exc: assert 'does not accept dev/sealed cards' in str(exc)
        else: raise AssertionError('dev card accepted')
        assert not InMemoryToolProvider(cards=[parsed.model_copy(update={'split':'kb'})]).cards
    scenarios = read(HERE/'linked-scenarios.json')
    links = read(HERE/'scenario-links.json')
    assert len(scenarios)==len(links)==5
    refs = 0
    for scenario,link in zip(scenarios,links):
        assert scenario['method_key']==link['method_key']
        prior = next(x for x in read(HERE/link['original_path']) if x['method_key']==link['method_key'])
        assert scenario == prior, 'linked script changed'
        assert link['card_version']==lineage['version']
        assert link['card_id'] in {c['card_id'] for c in cards}
        fact_ids = {f['id'] for f in scenario['fictional_facts']}
        assert len(fact_ids)==len(scenario['fictional_facts'])
        assert next(f for f in scenario['fictional_facts'] if f['id']=='F8')['visible_to']==[]
        for step in ['initial_handover','revised_handover']:
            for claim in scenario[step]['claims']:
                assert set(claim['fact_refs']) <= fact_ids-{'F8'}; refs+=len(claim['fact_refs'])
        for field in scenario['method_link'].values():
            assert set(field['fact_refs']) <= fact_ids-{'F8'}; refs+=len(field['fact_refs'])
        assert set(scenario['simulated_acknowledgement']['confirmed_fact_refs']) <= fact_ids-{'F8'}
        assert scenario['state_after']=={'information_receipt':'confirmed','information_resolution':'pending','physical_action_authorized':False}
    cases = read(HERE/'boundary-cases.json')['cases']
    assert len({c['id'] for c in cases})==len(cases)==9
    assert all(set(c['method_keys']) <= {s['method_key'] for s in specs} for c in cases)
    assert all(c['expected']['physical_action_authorized'] is False for c in cases)
    effective = {**original, **{c['card_id']:c for c in cards}}
    equipment = read(HERE/'../20260926-t4-equipment/cards.json')
    assert len(effective)==25 and not set(effective)&{c['card_id'] for c in equipment}
    assert len(effective)+len(equipment)==45
    review_status = 'pending'
    if (HERE/'review-content-initial.json').exists():
        initial = read(HERE/'review-content-initial.json')
        assert initial['verdict']=='revise'
        for name,expected in initial['input_hashes'].items():
            path = HERE/'boundary-cases-initial.json' if name=='boundary-cases.json' else HERE/name
            assert digest(path)==expected, ('initial review snapshot mismatch',name)
    if (HERE/'review-content.json').exists():
        review=read(HERE/'review-content.json')
        for name,expected in review['input_hashes'].items():
            path = Path(name)
            if not path.is_absolute(): path = HERE/path
            assert digest(path)==expected, ('review stale',name)
        assert review['verdict']=='pass', 'independent review has open findings'
        review_status='pass_current_hashes'
    tracked=['specs.json','cards.json','cards.md','synthetic-sources.json','changes.json','linked-scenarios.json','scenario-links.json','boundary-cases.json','lineage.json','verify.py']
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'status':'pass','schema_pass':len(cards),'required_field_negative_rejections':negatives,'dev_load_rejections':len(cards),'draft_L0_exclusions_in_memory_only':len(cards),'original_files_unchanged':len(lineage['original_file_hashes']),'scenario_snapshots_unchanged':len(scenarios),'scenario_fact_references_checked':refs,'boundary_case_structure_checks':len(cases),'independent_content_review':review_status,'input_hashes':{n:digest(HERE/n) for n in tracked},'limits':'정적 스키마·참조·불변성 검사. 경계 사례 의미는 독립 내용 검토. 역할 실행·효과·현장 검증 아님. 기존 sealed/holdout 사건을 검증 입력으로 사용하지 않음.'}
    experiment = HERE/'experiment'
    if (experiment/'review-design.json').exists():
        design_review=read(experiment/'review-design.json')
        assert design_review['verdict']=='pass'
        for name,expected in design_review['input_hashes'].items():
            assert digest(experiment/name)==expected, ('design review stale',name)
        revisions=read(experiment/'review-revisions.json')
        assert digest(experiment/revisions['original_review'])==revisions['original_review_sha256']
        snapshots={s['original_path']:s for s in revisions['snapshots']}
        initial=read(experiment/revisions['original_review'])
        for name,expected in initial['input_hashes'].items():
            path=experiment/snapshots[name]['snapshot_path'] if name in snapshots else experiment/name
            assert digest(path)==expected, ('design initial snapshot mismatch',name)
        result['independent_design_review']='pass_current_hashes'
        result['design_review_inputs_checked']=len(design_review['input_hashes'])
        result['design_initial_snapshots_checked']=len(snapshots)
    if (HERE/'freeze.json').exists():
        frozen = read(HERE/'freeze.json')
        for name,expected in frozen['input_hashes'].items():
            assert digest(HERE/name)==expected, ('frozen input changed',name)
        result['frozen_inputs_match']=len(frozen['input_hashes'])
    (HERE/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['input_hashes']},ensure_ascii=False))

if __name__=='__main__': main()
