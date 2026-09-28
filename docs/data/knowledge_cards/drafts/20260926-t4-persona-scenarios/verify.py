"""Check authored simulation records, not the effectiveness of a live simulation."""
import hashlib
import json
import sys
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
OLD = HERE.parent / '20260925-t4-synthetic'
sys.path.insert(0, str(ROOT))
from shiftlink.agent.schemas import KnowledgeCard, HandoverMethod

INPUTS = ('scenarios-01-13.json', 'scenarios-14-25.json')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(scene):
    assert scene['is_synthetic'] is True
    persona = scene['persona_id']
    assert persona in {'V-11', 'V-12', 'V-13'}
    assert all(scene[k].strip() for k in ('title', 'setting', 'distinctness'))
    facts = {f['id']: f for f in scene['fictional_facts']}
    assert facts and len(facts) == len(scene['fictional_facts'])
    for fact in facts.values():
        assert fact['text'].strip() and isinstance(fact['visible_to'], list)
        assert set(fact['visible_to']) <= {persona, 'recipient'}
    assert any(f['visible_to'] == [persona] for f in facts.values()), 'No initial information gap'
    said = set()
    for key in ('initial_handover', 'revised_handover'):
        utterance = scene[key]
        assert utterance['text'].strip() and utterance['claims']
        for claim in utterance['claims']:
            refs = claim['fact_refs']
            assert claim['text'].strip() and refs and set(refs) <= facts.keys()
            assert all(persona in facts[r]['visible_to'] for r in refs)
            said.update(refs)
    challenge = scene['recipient_challenge']
    assert challenge['text'].strip() and challenge['missing_or_misread']
    ack = scene['simulated_acknowledgement']
    assert ack['text'].strip() and ack['confirmed_fact_refs']
    assert set(ack['confirmed_fact_refs']) <= facts.keys()
    assert all('recipient' in facts[r]['visible_to'] or r in said for r in ack['confirmed_fact_refs'])
    assert set(scene['method_link']) == set(HandoverMethod.model_fields)
    for link in scene['method_link'].values():
        assert link['fact_refs'] and set(link['fact_refs']) <= facts.keys()
        assert all(facts[r]['visible_to'] for r in link['fact_refs']), 'Expected reply cannot support a method'
        assert link['explanation'].strip()
    state = scene['state_after']
    assert state['information_receipt'] in {'confirmed', 'pending'}
    assert state['information_resolution'] in {'resolved', 'pending'}
    assert state['physical_action_authorized'] is False
    assert scene['failure_variant']['reply'].strip()
    assert scene['failure_variant']['expected_rejection_reason'].strip()
    # References and visibility are mechanical; entailment needs the independent review.
    return len(facts)


def main():
    scenes = sorted([s for name in INPUTS for s in read(HERE/name)], key=lambda s: s['method_key'])
    assert [s['method_key'] for s in scenes] == [f'M{i:02}' for i in range(1, 26)]
    cards = read(OLD/'cards.json')
    mapping = read(OLD/'evidence-map.json')['cards']
    card_by_method = {m['method_key']: c for m, c in zip(mapping, cards, strict=True)}
    specs = {s['method_key']: s for n in ('specs-01-13.json', 'specs-14-25.json') for s in read(OLD/n)}
    facts_count = sum(validate(s) for s in scenes)
    for scene in scenes:
        assert scene['persona_id'] == specs[scene['method_key']]['persona_id']
        card = KnowledgeCard.model_validate(card_by_method[scene['method_key']])
        assert card.status == 'draft' and card.grade == 'L0' and card.split == 'dev'
    assert len({s['setting'] for s in scenes}) == len({s['distinctness'] for s in scenes}) == 25
    review = read(HERE/'review.json')
    for name in INPUTS:
        assert review['source_hashes'][name] == sha(HERE/name), 'Stale review: '+name
    checks = {c['method_key']: c for c in review['checks']}
    assert len(checks) == len(review['checks']) == 25 and set(checks) == set(card_by_method)
    for check in checks.values():
        assert check['outcome'] in {'pass', 'needs_revision'} and check['rationale'].strip()
        if check['outcome'] == 'pass':
            assert not any(f['severity'] == 'major' for f in check['findings'])
    rejected = []
    for mutation in ('unknown_reference', 'sender_private_access', 'missing_synthetic_label', 'invented_authority', 'circular_response_support'):
        bad = deepcopy(scenes[0])
        claim = bad['initial_handover']['claims'][0]
        if mutation == 'unknown_reference':
            claim['fact_refs'] = ['DOES-NOT-EXIST']
        elif mutation == 'sender_private_access':
            next(f for f in bad['fictional_facts'] if f['id'] == claim['fact_refs'][0])['visible_to'] = ['recipient']
        elif mutation == 'missing_synthetic_label':
            bad['is_synthetic'] = False
        elif mutation == 'invented_authority':
            bad['state_after']['physical_action_authorized'] = True
        else:
            hidden = next(f['id'] for f in bad['fictional_facts'] if not f['visible_to'])
            bad['method_link']['acknowledgement']['fact_refs'] = [hidden]
        try:
            validate(bad)
        except AssertionError:
            rejected.append(mutation)
    assert len(rejected) == 5
    result = {'checked_at': datetime.now(timezone.utc).isoformat(), 'scenario_count': len(scenes),
              'linked_card_schema_passed': len(cards), 'fictional_fact_count': facts_count,
              'method_field_links_checked': 125, 'persona_counts': dict(Counter(s['persona_id'] for s in scenes)),
              'independent_review_passed': sum(c['outcome']=='pass' for c in checks.values()),
              'integrity_negative_probes_rejected': rejected,
              'simulation_mode': 'authored_script', 'isolated_agent_execution_performed': False,
              'card_effectiveness_experiment_performed': False, 'real_site_validation_performed': False,
              'previous_card_scores_reused': False,
              'input_hashes': {n: sha(HERE/n) for n in (*INPUTS, 'review.json')},
              'linked_cards_sha256': sha(OLD/'cards.json'),
              'persona_file_sha256': sha(ROOT/'seeds/personas_v0.1.yaml'),
              'verifier_sha256': sha(Path(__file__))}
    (HERE/'validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    lines = ['# 페르소나 기반 가상 T4 인계 시나리오 25건', '',
             '사용자 요청에 따라 실제 기밀 인계자료 확보를 전제하지 않고 가상 제조업 상황을 구성했다. 기존 합성 T4 방법 25건에 가상 사실 원장, 최초 인계, 되물음, 보완 인계, 모의 수신 응답, 실패 응답 예시를 연결했다. 모든 인물·대화·문서 상태·응답은 합성이다.', '',
             f"문서 참조·관측범위 검사 {len(scenes)}/25건, 연결 카드 스키마 {len(cards)}/25건, 독립 AI 내용 검토 {result['independent_review_passed']}/25건. 검사 결과는 [validation.json](validation.json), 검토 의견은 [review.json](review.json)에 있다.", '',
             '이는 한 작성자가 원장과 대화 양쪽을 구성한 **대본형 예시**다. 카드 없이/있이 독립 에이전트를 실행해 효과를 측정한 결과는 아니다. 이전 94.9점은 이번 시나리오 점수로 재사용하지 않았다. 기존 카드의 식별자·confidence·승인 상태를 변경하지 않았다. 가상 원장 참조는 내부 일관성을 확인하기 위한 것이며 외부 실증 근거가 아니다.', '',
             '합성 데이터 방법과 후속 비교 실험 설계는 [논문 검토 노트](research.md)에 정리했다. 연결된 기존 카드 전문은 [cards.md](../20260925-t4-synthetic/cards.md)에 있다.', '',
             '수신 확인과 정보 해결은 서로 다른 상태다. 미확인·충돌을 정확하게 인수했다면 수신은 확인되더라도 정보 해결은 대기로 남는다. 일부 역할만 회신한 경우 전체 수신은 대기다. 대본의 수신 확인에서 물리적 작업 승인으로 넘어가지 않는다.', '']
    for s in scenes:
        key = s['method_key']
        lines += [f"## {key} · {s['title']}", '',
                  f"합성 · persona_id={s['persona_id']} · 연결 카드={card_by_method[key]['card_id']} · 독립 검토={checks[key]['outcome']}", '',
                  s['setting'], '', '**가상 사실·정보 접근 원장**', '',
                  '| 참조 | 가상 사실 또는 이번 연습의 규칙 | 최초 접근 주체 |', '|---|---|---|']
        for f in s['fictional_facts']:
            lines.append(f"| {f['id']} | {f['text'].replace('|', '/')} | {', '.join(f['visible_to']) or '사전 공개 없음: 대본 검토용'} |")
        lines += ['', '**송신자가 모르는 정보:** '+ '; '.join(s['sender_unknowns']), '']
        for label, field in [('최초 인계', 'initial_handover'), ('수신자의 되물음', 'recipient_challenge'),
                             ('보완 인계', 'revised_handover'), ('모의 수신 응답', 'simulated_acknowledgement')]:
            lines += [f"**{label}:** {s[field]['text']}", '']
        state = s['state_after']
        lines += [f"**대본 종료 상태:** 정보 수신={state['information_receipt']}, 정보 해결={state['information_resolution']}, 물리적 작업 승인 없음.", '',
                  '**잘못된 응답 예시:** '+s['failure_variant']['reply'], '',
                  '**거부해야 할 이유:** '+s['failure_variant']['expected_rejection_reason'], '',
                  '| T4 필드 | 가상 원장 연결 | 연결 설명 |', '|---|---|---|']
        for field, link in s['method_link'].items():
            lines.append(f"| {field} | {', '.join(link['fact_refs'])} | {link['explanation'].replace('|', '/')} |")
        lines += ['', '**실질적 차이:** '+s['distinctness'], '', '**독립 검토:** '+checks[key]['rationale'], '']
        for f in checks[key]['findings']:
            lines += [f"- {f['severity']}: {f['detail']}"]
        lines += ['']
    lines += ['## 재검증', '', '프로젝트 루트에서 다음 명령을 실행한다. 참조·표시·관측범위·상태와 검토 해시를 확인하며 대화 의미와 현장 효과를 자동 증명하지 않는다.', '',
              '```powershell', 'python docs/data/knowledge_cards/drafts/20260926-t4-persona-scenarios/verify.py', '```', '']
    (HERE/'README.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('scenario_count','linked_card_schema_passed','fictional_fact_count','independent_review_passed')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
