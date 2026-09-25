"""Event ledger + persona -> synthetic shift-log narrative (Stage A of card synthesis).

Run ``python -m shiftlink.data.narrative --help`` for the command adapter.
Ground truth never enters the prompt: fields are whitelisted in, not filtered out.
Output is a registry *proposal*; a human reviewer approves it before
``shiftlink.data.generation`` may cite it. This module never edits the registry.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
import hashlib
import json
from pathlib import Path
import re
import subprocess

import yaml

PROMPT_VERSION = 'persona-narrative-v1'
# Whitelist, not blacklist: anything not listed here is unreachable by the model.
EVENT_FIELDS = ('equipment', 'primary_equipment_id', 'segment_ids',
                'occurred_at', 'reported_at', 'symptom_text', 'severity')
CONTEXT_FIELDS = ('captured_at', 'op_mode', 'line_speed', 'product_code', 'shift_code',
                  'shift_date', 'stop_restart_state', 'active_alarms', 'measurements',
                  'segment_states', 'utility_states')
OBSERVATION_FIELDS = ('observed_at', 'equipment_id', 'component_id', 'obs_kind', 'signal',
                      'value', 'unit', 'qualitative_text', 'judgment_vs_normal')
# The shift log is written at t, so action/outcome/handover entries do not exist yet.
# 'observation' entries are excluded too: the ledger timeline merges every persona's
# sightings, and my_observations already carries the ones this writer actually made.
VISIBLE_TIMELINE = ('context',)
PERSONA_FIELDS = ('display_name', 'years', 'role_experience', 'responsibility_scope',
                  'equipment_focus', 'judgment_style', 'speech', 'known_biases')

NARRATIVE_PROMPT = '''너는 아래 페르소나의 현장 작업자다. 방금 네 교대에 일어난 일을 네가 직접 쓴 작업일지 원문을 작성한다.

규칙:
1. 원인을 단정하지 마라. 네가 보고·듣고·읽은 것과 계측값만 쓴다. 추정은 "…같다", "…로 보인다"로 표시한다.
2. 주어진 관측(observations)과 컨텍스트에 없는 수치·설비·시각을 만들어내지 마라.
3. 조치 결과·최종 판정·사후 정보는 쓰지 마라. 아직 모른다.
4. persona.recording_method.work_log의 기록 습관대로 쓰고, omission_risk에 해당하는 항목은 실제로 빠뜨려라. 완벽한 기록이 목표가 아니다.
5. 설비·구간은 아래에 주어진 호칭(HPU-01, RT-03 등) 그대로 쓴다. 코드나 번호를 새로 만들지 마라.
6. 150~500자. 현장 문체. 완결된 문장이 아니어도 된다.
7. 머리말·설명·따옴표 없이 일지 본문만 출력한다. JSON이 아니라 평문이다.

'''
FORBIDDEN_ID = re.compile(r'\b(?:EV|AR|K|AC|AX|OB|OC|RC|RV|EQ|CP|REL|CTX|SG|LN|EL|HO|ET|EG)-\d')
CATALOG = Path('docs/data/reference/00_plant_and_relations.json')


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _pick(row, fields):
    return {k: row[k] for k in fields if row.get(k) is not None}


def shop_floor_names(catalog: dict) -> dict[str, str]:
    """Internal id -> the name a worker actually writes (HPU-01, 입측 이송 구간)."""
    names = {}
    for key, identity in (('equipment', 'equipment_id'), ('components', 'component_id'),
                          ('process_segments', 'segment_id'), ('production_lines', 'line_id')):
        for row in catalog.get(key, []):
            names[row[identity]] = row.get('code') or row['name']
    return names


def _rename(payload, names: dict[str, str]) -> str:
    """Swap every internal id for its shop-floor name before the model ever sees it."""
    text = _dump(payload)
    for identity, name in names.items():
        text = text.replace(identity, name)
    found = FORBIDDEN_ID.search(text)
    if found:
        raise ValueError(f'Internal id has no shop-floor name: {found.group()}')
    return text


def _check_split(scenario: dict) -> None:
    """Sealed scenarios are evaluation holdout; generating from them burns the eval set.

    docs/data/README.md: sealed 시나리오는 개발·카드 생성·튜닝 입력으로 사용하지 않는다.
    An absent split is refused too — silence must not read as permission.
    """
    event = scenario.get('event') or {}
    split = event.get('split') or (scenario.get('_meta') or {}).get('split')
    if split == 'sealed':
        raise ValueError('Sealed scenario: evaluation holdout may not feed generation')
    if split not in ('kb', 'dev'):
        raise ValueError(f'Scenario split must be kb or dev, got {split!r}')


def build_prompt(scenario: dict, persona: dict, catalog: dict) -> tuple[str, list[str]]:
    """Assemble the Stage A prompt and the observation ids it exposes."""
    _check_split(scenario)
    event = scenario['event']
    snapshot = scenario.get('operating_context_snapshot') or {}
    mine = [o for o in scenario.get('observations', [])
            if o.get('observer_persona_id') == persona['persona_id']]
    if not mine:
        raise ValueError(f"Persona {persona['persona_id']} observed nothing in this event")
    payload = {
        'persona': {'persona_id': persona['persona_id'],
                    **_pick(persona, PERSONA_FIELDS),
                    'recording_method': persona.get('recording_method', {})},
        'event': _pick(event, EVENT_FIELDS),
        'operating_context': _pick(snapshot, CONTEXT_FIELDS),
        'my_observations': [_pick(o, OBSERVATION_FIELDS) for o in mine],
        'timeline_so_far': [t for t in event.get('timeline', [])
                            if t.get('kind') in VISIBLE_TIMELINE],
    }
    leaked = set(event.get('_visibility', {}).get('ground_truth', [])) & set(payload['event'])
    if leaked:
        raise ValueError(f'Ground truth fields reachable in prompt: {sorted(leaked)}')
    prompt = NARRATIVE_PROMPT + _rename(payload, shop_floor_names(catalog))
    return prompt, [o['observation_id'] for o in mine]


def _check_leak(text: str, scenario: dict) -> None:
    event = scenario['event']
    token = event.get('canary_token')
    if token and token in text:
        raise ValueError('Canary token leaked into the narrative')
    found = FORBIDDEN_ID.search(text)
    if found:
        raise ValueError(f'Internal ID leaked into the narrative: {found.group()}')
    if not text.strip():
        raise ValueError('Generator returned empty narrative')


def _proposal(text, scenario, persona, observation_ids, source_id):
    event = scenario['event']
    return {
        'source_id': source_id,
        'title': f"합성 작업일지 {event['event_id']} / {persona['persona_id']}",
        'aliases': [],
        'source_family': source_id,
        'url': None,
        'url_role': None,
        'purpose': '페르소나 기반 합성 사건 원문',
        'review_status': 'pending_review',
        'approved_scope': [],
        'is_synthetic': True,
        # Provenance for the reviewer, kept outside proposed_scope: generation.ApprovedScope
        # forbids extra keys, so anything in there must be copyable verbatim.
        'derived_from_observation_ids': observation_ids,
        # Reviewer adds reviewed_by/reviewed_at and moves this into approved_scope.
        'proposed_scope': {
            'scope_id': f"{event['event_id']}-{persona['persona_id']}-log",
            'locator': f"synthetic shift log, {event['event_id']}, {persona['persona_id']}",
            'document_version': f'synthetic-{PROMPT_VERSION}',
            'text_sha256': _hash(text),
            'allowed_claims': ['작성자가 관측·기록한 증상과 계측값'],
            'exclusions': ['고장 원인 확정', '조치의 적절성', '작성자가 관측하지 않은 설비의 상태'],
            'use_scope': '카드 초안 생성 근거',
            'kind': 'case',
            'group_id': event['prototype_id'],
            'reference_ids': [event['event_id']],
        },
    }


def generate_narrative(scenario: dict, persona: dict, catalog: dict, *,
                       generate: Callable[[str], str], source_id: str) -> dict:
    """Generate one narrative. Raises on ground-truth leakage; never writes the registry."""
    prompt, observation_ids = build_prompt(scenario, persona, catalog)
    text = generate(prompt)
    if not isinstance(text, str):
        raise ValueError('Generator must return text')
    text = text.strip()
    _check_leak(text, scenario)
    return {'text': text, 'prompt_sha256': _hash(prompt), 'prompt_version': PROMPT_VERSION,
            'human_review_required': True,
            'registry_proposal': _proposal(text, scenario, persona, observation_ids, source_id)}


def _load_persona(path: Path, persona_id: str) -> dict:
    personas = yaml.safe_load(path.read_text(encoding='utf-8'))['personas']
    for persona in personas:
        if persona['persona_id'] == persona_id:
            return persona
    raise ValueError(f'Unknown persona: {persona_id}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--scenario', type=Path, required=True)
    parser.add_argument('--persona', required=True, help='persona_id, e.g. V-11')
    parser.add_argument('--personas', type=Path, default=Path('seeds/personas_v0.1.yaml'))
    parser.add_argument('--catalog', type=Path, default=CATALOG)
    parser.add_argument('--source-id', help='New registry source_id, e.g. SD-901')
    parser.add_argument('--out', type=Path, default=Path('artifacts/narratives'))
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--print-prompt', action='store_true',
                        help='Write the assembled prompt to stdout and exit')
    adapter = parser.add_mutually_exclusive_group()
    adapter.add_argument('--candidate', type=Path, help='Import a narrative written elsewhere')
    adapter.add_argument('--generator-command', nargs=argparse.REMAINDER,
                         help='Command argv; reads UTF-8 prompt on stdin and returns text on stdout')
    args = parser.parse_args(argv)
    if args.generator_command == []:
        parser.error('--generator-command requires an executable')
    if not (args.print_prompt or args.candidate or args.generator_command):
        parser.error('one of --print-prompt, --candidate, --generator-command is required')
    if not args.print_prompt and not args.source_id:
        parser.error('--source-id is required when generating')

    def generate(prompt):
        if args.candidate:
            return args.candidate.read_text(encoding='utf-8-sig')
        return subprocess.run(args.generator_command, input=prompt, capture_output=True,
                              text=True, encoding='utf-8', timeout=args.timeout,
                              check=True, shell=False).stdout
    try:
        scenario = json.loads(args.scenario.read_text(encoding='utf-8-sig'))
        catalog = json.loads(args.catalog.read_text(encoding='utf-8-sig'))
        persona = _load_persona(args.personas, args.persona)
        if args.print_prompt:
            print(build_prompt(scenario, persona, catalog)[0])
            return 0
        result = generate_narrative(scenario, persona, catalog,
                                    generate=generate, source_id=args.source_id)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, yaml.YAMLError) as exc:
        print(_dump({'status': 'failed', 'error_type': type(exc).__name__, 'error': str(exc)}))
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    name = f"{scenario['event']['event_id']}_{args.persona}"
    (args.out / f'{name}.txt').write_text(result['text'], encoding='utf-8')
    (args.out / f'{name}.json').write_text(_dump(result), encoding='utf-8')
    print(_dump({'status': 'written', 'text_sha256': result['registry_proposal']
                 ['proposed_scope']['text_sha256'], 'out': str(args.out / f'{name}.json')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
