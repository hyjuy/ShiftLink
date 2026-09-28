"""Assemble explicitly synthetic sandbox drafts; never register or adopt them."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))
from shiftlink.agent.schemas import KnowledgeCard, SCHEMA_VERSION


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def sha(obj):
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


def save(name, obj):
    (HERE / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    policy = read(HERE / 'batch-policy.json')
    specs = read(HERE / 'specs-01-13.json') + read(HERE / 'specs-14-25.json')
    specs.sort(key=lambda s: s['method_key'])
    assert [s['method_key'] for s in specs] == [f'M{i:02}' for i in range(1, 26)]
    previous = HERE.parent / '20260925-t4-evidence-review'
    original = read(previous / 'sources.json')
    prior_candidates = read(previous / 'candidates.json')['candidates']
    evidence = {e['evidence_ref']: e for e in original['evidence']}
    old_values = [c['fields'] for c in prior_candidates]
    used_ids, scanned = set(), {}
    for directory in ['seeds', 'docs/data/knowledge_cards', 'eval/fixtures/dev']:
        for path in sorted((ROOT / directory).rglob('*.json')):
            if HERE in path.parents:
                continue
            data = path.read_bytes()
            # Identifier inventory only; no old card content becomes generation evidence.
            used_ids.update(re.findall(r'K-\d{4}', data.decode('utf-8-sig')))
            scanned[path.relative_to(ROOT).as_posix()] = hashlib.sha256(data).hexdigest()
    available = [f'K-{i:04}' for i in range(1, 10000) if f'K-{i:04}' not in used_ids]
    assert len(available) >= 25
    content_hash = sha({'specs': specs, 'policy': policy})
    version = 'synthetic-' + content_hash[:12]
    now = datetime.now(timezone.utc).isoformat()
    cards, sources, mappings, narratives = [], [], [], []
    for spec, card_id in zip(specs, available):
        key, method = spec['method_key'], spec['handover_method']
        source_id = f"SYN-T4-{sha(specs)[:8]}-{key}"
        original_support = {f: refs for f, refs in spec['original_field_support'].items() if refs}
        assert set(original_support) <= set(method)
        for field, refs in original_support.items():
            assert refs and set(refs) <= evidence.keys()
            assert any(old[field].get('support') == 'supported'
                       and old[field].get('value') == method[field]
                       and set(refs) <= set(old[field]['evidence_refs'])
                       for old in old_values), (key, field, 'unproven original support')
        assert set(spec['related_original_evidence']) <= evidence.keys()
        confidence = len(original_support) / 5
        confidence_basis = policy['confidence_definition'] + f' 本 카드 측정: {len(original_support)}/5={confidence:g}.'
        confidence_basis = confidence_basis.replace('本 카드', '이 카드')
        know_how = ('[합성 개발용 인계 방법] ' + ' '.join(spec['procedure'])
                    + ' 미완료 처리: ' + spec['unresolved_handling']
                    + ' ' + policy['safety_boundary'])
        payload = dict(card_id=card_id, version=version, grade='L0', status='draft',
                       tacit_type='T4', equipment=policy['equipment'], component=policy['component'],
                       scenario=policy['scenario'], title='[합성·개발용] ' + spec['title'],
                       know_how=know_how, rationale='[합성 설계 이유] ' + spec['rationale'],
                       safety_flag=True, safety_basis='[합성 설계 경계; 현장 안전 근거 아님] ' + policy['safety_boundary'],
                       confidence=confidence, split=policy['split'],
                       type_payload={'handover_method': method},
                       generalization_evidence={'supporting_event_ids': [], 'contradicting_event_ids': [],
                           'generalization_scope': '합성 인계 연습·개발 검토만. 검증된 현장 사건과 독립 표본은 0건.',
                           'confidence_basis': confidence_basis},
                       safety_review={'status': 'pending_review'},
                       provenance={'seed_ids': [source_id], 'persona_id': spec['persona_id'], 'event_ids': [],
                           'generator': 'Codex multi-agent synthetic authoring + ' + Path(__file__).relative_to(ROOT).as_posix(),
                           'generated_at': now, 'extraction_method': 'explicit_synthetic_protocol_design_not_factual_extraction',
                           'prompt_version': policy['policy_version'], 'schema_version': SCHEMA_VERSION,
                           'sources': [{'source_id': source_id, 'locator': f'synthetic-sources.json#{key}',
                                        'document_version': version}]})
        card = KnowledgeCard.model_validate(payload).model_dump(mode='json', exclude_none=True)
        cards.append(card)
        source = dict(source_id=source_id, method_key=key, is_synthetic=True, persona_id=spec['persona_id'],
                      kind='synthetic_protocol_design', human_approval=False, independent_factual_evidence=False,
                      field_values=method, full_design=spec, authoring_policy=policy['policy_version'])
        sources.append(source)
        mapped_fields = {}
        for field, value in method.items():
            refs = original_support.get(field, [])
            mapped_fields[field] = {'kind': 'original' if refs else 'synthetic_proposal',
                                    'value': value, 'original_evidence_refs': refs,
                                    'synthetic_source_ref': None if refs else source_id,
                                    'independent_factual_evidence': bool(refs)}
        mappings.append(dict(card_id=card_id, method_key=key, fields=mapped_fields,
                             related_original_evidence=spec['related_original_evidence'],
                             related_evidence_role='배경·주제 연관만. 보완 문장의 직접 원문 근거가 아님.',
                             distinguishing_feature=spec['distinguishing_feature']))
        narratives.append(dict(card_id=card_id,method_key=key,persona_id=spec['persona_id'],is_synthetic=True,
                               counts_as_factual_evidence=False, text=spec['synthetic_narrative']))
    save('cards.json', cards)
    save('synthetic-sources.json', sources)
    save('evidence-map.json', {'original_review': '../20260925-t4-evidence-review/sources.json',
                            'cards': mappings})
    save('narratives.json', narratives)
    save('manifest.json', {'is_synthetic': True, 'batch_policy': policy, 'generated_at': now,
                          'content_version': version, 'specs_sha256': sha(specs), 'content_input_sha256': content_hash,
                          'card_ids': [c['card_id'] for c in cards], 'id_inventory': scanned,
                          'id_inventory_used_ids': sorted(used_ids),
                          'operational_registry_modified': False, 'production_generation_run': False,
                          'original_review_sha256': hashlib.sha256((previous/'sources.json').read_bytes()).hexdigest(),
                          'human_source_approval': False, 'human_safety_review': False, 'adopted': False})
    lines = ['# 합성 T4 개발용 초안 25건', '',
             '원문 검증 카드가 아닌 합성 인계 방법 설계다. 모두 draft/L0/dev이며 수신 확인은 작업·운전·재가동 승인과 다르다.', '',
             '| 카드 | 인계 방법 | 원문 직접 지지 필드 |', '|---|---|---:|']
    for card, spec in zip(cards, specs):
        lines.append(f"| {card['card_id']} ({spec['method_key']}) | {spec['title']} | {sum(bool(v) for v in spec['original_field_support'].values())}/5 |")
    for card, spec, mapping in zip(cards, specs, mappings):
        lines += ['', f"## {card['card_id']} · {spec['title']}", '',
                  f"합성 설계 · persona_id={spec['persona_id']} · status=draft · grade=L0 · split=dev", '',
                  '**적용 상황:** ' + spec['trigger'], '', '**방법:** ' + ' '.join(spec['procedure']), '',
                  '| 필드 | 내용 | 근거 구분 |', '|---|---|---|']
        for field,item in mapping['fields'].items():
            value = ' / '.join(item['value']) if isinstance(item['value'],list) else item['value']
            support = '원문: ' + ', '.join(item['original_evidence_refs']) if item['kind']=='original' else '합성 제안'
            lines.append(f'| {field} | {value} | {support} |')
        lines += ['', '**미완료 처리:** '+spec['unresolved_handling'], '',
                  '**다른 카드와의 차이:** '+spec['distinguishing_feature'], '',
                  '**합성 설계 이유:** '+spec['rationale'], '', '**합성 인계문:**', '', spec['synthetic_narrative']]
    (HERE/'cards.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'cards':len(cards),'version':version,'first_id':cards[0]['card_id'],'last_id':cards[-1]['card_id']}))


if __name__ == '__main__':
    main()
