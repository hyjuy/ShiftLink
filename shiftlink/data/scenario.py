"""Event spec -> validated synthetic scenario file (feeds narrative.py and generation.py).

Run ``python -m shiftlink.data.scenario --help`` for the command adapter.

The author writes what only a person can decide — symptom, cause, correct actions,
observations. This module computes what is mechanical and error-prone by hand:
prototype lineage, split assignment, id allocation, canary tokens, and reference
checks against the catalog. It proposes a split; it never edits the assignment
table or the source registry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SPEC_VERSION = 'event-spec-v1'
# docs/data/policies/source-and-split-contract.md: UTF-8 SHA-256, big-endian, mod 12.
SPLIT_INPUT = 'shiftlink-split-v1:{group_id}'
MODULUS = 12
BUCKETS = {**{b: 'kb' for b in range(0, 7)},
           **{b: 'dev' for b in (7, 8)},
           **{b: 'sealed' for b in (9, 10, 11)}}
# The four keys the contract uses to judge prototype identity (§59).
PROTOTYPE_KEYS = ('case_type', 'root_equipment_type', 'relation_path_types',
                  'primary_symptom_class')
CANARY_PREFIX = 'zzk9'
GROUND_TRUTH = ['true_cause', 'true_actions', 'true_cause_equipment_ids',
                'cards_expected', 'canary_token']
PRE_ACTION = ['symptom_text', 'severity', 'timeline(관측까지)', 'traversed_relation_ids']
POST_ACTION = ['revision_candidate_ids', 'timeline(행동 이후)']

CATALOG = Path('docs/data/reference/00_plant_and_relations.json')
SCENARIOS = Path('docs/data/scenarios')


class Observation(BaseModel):
    model_config = ConfigDict(extra='allow')
    equipment_id: str
    observed_at: str
    observer_persona_id: str
    obs_kind: str
    component_id: str | None = None


class EventSpec(BaseModel):
    """What the author must decide. Ids, split and canary are NOT here."""

    model_config = ConfigDict(extra='forbid')
    # Prototype identity — fixed before the hash is seen (contract: no re-rolling).
    case_type: str
    root_equipment_type: str
    relation_path_types: list[str]
    primary_symptom_class: str
    pattern_name: str
    # Event body.
    line_id: str
    primary_equipment_id: str
    segment_ids: list[str] = Field(default_factory=list)
    occurred_at: str
    reported_at: str | None = None
    symptom_text: str = Field(min_length=1)
    severity: str
    scenario: str
    title: str
    observations: list[Observation] = Field(min_length=1)
    operating_context: dict[str, Any] = Field(default_factory=dict)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    # Ground truth — author-written. A model must not invent these.
    true_cause: str = Field(min_length=1)
    true_actions: list[str]
    true_cause_equipment_ids: list[str] = Field(default_factory=list)
    extra_event_fields: dict[str, Any] = Field(default_factory=dict)


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def assign_split(group_id: str) -> tuple[int, str]:
    """Contract §63. The caller must fix group_id before looking at this result."""
    digest = hashlib.sha256(SPLIT_INPUT.format(group_id=group_id).encode('utf-8')).digest()
    bucket = int.from_bytes(digest, 'big') % MODULUS
    return bucket, BUCKETS[bucket]


def prototype_key(spec: dict) -> tuple:
    """Contract §59. relation_path_types is compared sorted."""
    return (spec['case_type'], spec['root_equipment_type'],
            tuple(sorted(spec['relation_path_types'])), spec['primary_symptom_class'])


def canary_token(event_id: str) -> str:
    """Deterministic so a regenerated scenario keeps its token. Detection, not secrecy."""
    tail = hashlib.sha256(event_id.encode('utf-8')).hexdigest()[:4]
    return f'{CANARY_PREFIX}-{event_id.lower().replace("-", "")}-{tail}'


def _catalog_ids(catalog: dict) -> dict[str, set]:
    return {
        'equipment': {row['equipment_id'] for row in catalog.get('equipment', [])},
        'component': {row['component_id'] for row in catalog.get('components', [])},
        'segment': {row['segment_id'] for row in catalog.get('process_segments', [])},
        'line': {row['line_id'] for row in catalog.get('production_lines', [])},
    }


def _component_owner(catalog: dict) -> dict[str, str]:
    return {row['component_id']: row['equipment_id'] for row in catalog.get('components', [])}


def _check_references(spec: EventSpec, catalog: dict, persona_ids: set[str]) -> None:
    known = _catalog_ids(catalog)
    owner = _component_owner(catalog)
    missing = []
    if spec.line_id not in known['line']:
        missing.append(f'line_id {spec.line_id}')
    if spec.primary_equipment_id not in known['equipment']:
        missing.append(f'primary_equipment_id {spec.primary_equipment_id}')
    for segment in spec.segment_ids:
        if segment not in known['segment']:
            missing.append(f'segment_id {segment}')
    for equipment in spec.true_cause_equipment_ids:
        if equipment not in known['equipment']:
            missing.append(f'true_cause_equipment_ids {equipment}')
    for index, observation in enumerate(spec.observations):
        if observation.equipment_id not in known['equipment']:
            missing.append(f'observations[{index}].equipment_id {observation.equipment_id}')
        if observation.component_id and observation.component_id not in known['component']:
            missing.append(f'observations[{index}].component_id {observation.component_id}')
        elif observation.component_id:
            # Existing is not enough: the part must belong to the observed equipment.
            # A real part id on the wrong machine passes an existence check silently.
            actual = owner[observation.component_id]
            if actual != observation.equipment_id:
                missing.append(
                    f'observations[{index}].component_id {observation.component_id} '
                    f'belongs to {actual}, not {observation.equipment_id}')
        if observation.observer_persona_id not in persona_ids:
            missing.append(
                f'observations[{index}].observer_persona_id {observation.observer_persona_id}')
    if missing:
        raise ValueError('Unknown catalog references: ' + '; '.join(missing))


def _scan_existing(*scenario_dirs: Path) -> dict[str, Any]:
    """Collect ids and pending prototypes across every scenario directory.

    Unapproved scenarios live outside docs/data/scenarios. Scanning only the
    approved directory re-issues ids and prototype numbers already taken, which
    silently merges two unrelated lineages into one split group.
    """
    used = {'event': set(), 'observation': set(), 'context': set(), 'prototypes': []}
    for scenario_dir in scenario_dirs:
        if not scenario_dir.exists():
            continue
        for path in sorted(scenario_dir.glob('*.json')):
            data = json.loads(path.read_text(encoding='utf-8-sig'))
            event = data.get('event')
            if not event:
                continue
            used['event'].add(event['event_id'])
            snapshot = data.get('operating_context_snapshot') or {}
            if snapshot.get('context_id'):
                used['context'].add(snapshot['context_id'])
            for observation in data.get('observations', []):
                used['observation'].add(observation['observation_id'])
            identity = data.get('_meta', {}).get('prototype_identity')
            used['prototypes'].append({
                'prototype_id': event['prototype_id'], 'split': event.get('split'),
                # Identity keys let a matching spec reuse this pending prototype.
                # Without them the prototype id is still reserved, which is the
                # part that must never be reissued.
                **(identity or {})})
    return used


def _next_id(prefix: str, used: set[str], width: int = 4) -> str:
    numbers = [int(m.group(1)) for i in used
               if (m := re.fullmatch(rf'{prefix}-(\d{{{width}}})', i))]
    return f'{prefix}-{max(numbers, default=0) + 1:0{width}d}'


def resolve_prototype(spec: dict, catalog: dict, assignments: list[dict],
                      pending: list[dict] | None = None) -> dict:
    """Reuse the existing prototype when the four identity keys match.

    An existing assignment wins over the hash (contract §63). Only a genuinely new
    lineage gets a fresh id and a hash-derived split.

    ``pending`` carries prototypes proposed by earlier runs but not yet written to
    the catalog or the assignment table. Their ids are reserved even when their
    identity keys are unknown, so a new lineage cannot be handed an id that another
    unapproved scenario is already using.
    """
    key = prototype_key(spec)
    pending = pending or []
    for prototype in catalog.get('event_prototypes', []):
        if prototype_key(prototype) == key:
            group = prototype['prototype_id']
            existing = next((a for a in assignments if a['group_id'] == group), None)
            return {'prototype_id': group, 'group_id': group,
                    'split': (existing or prototype).get('split')
                    or prototype.get('assigned_split'),
                    'basis': 'existing_catalog_assignment', 'is_new': False}
    for prototype in pending:
        if all(k in prototype for k in PROTOTYPE_KEYS) and prototype_key(prototype) == key:
            return {'prototype_id': prototype['prototype_id'],
                    'group_id': prototype['prototype_id'], 'split': prototype['split'],
                    'basis': 'pending_proposal_reuse', 'is_new': False}
    used = ({p['prototype_id'] for p in catalog.get('event_prototypes', [])}
            | {p['prototype_id'] for p in pending}
            | {a['group_id'] for a in assignments})
    group = _next_id('PT', used)
    bucket, split = assign_split(group)
    return {'prototype_id': group, 'group_id': group, 'split': split, 'bucket': bucket,
            'basis': 'new_group_assignment_hash', 'is_new': True}


def build_scenario(spec: dict, *, catalog: dict, persona_ids: set[str],
                   assignments: list[dict], used: dict) -> dict:
    """Assemble one scenario file. Ground truth stays in the file but is marked."""
    parsed = EventSpec.model_validate(spec)
    _check_references(parsed, catalog, persona_ids)
    prototype = resolve_prototype(spec, catalog, assignments, used.get('prototypes'))
    if prototype['split'] not in ('kb', 'dev', 'sealed'):
        raise ValueError(f"Unresolved split for {prototype['group_id']}")

    event_id = _next_id('EV', used['event'])
    context_id = 'CTX-' + event_id.split('-')[1]
    if context_id in used['context']:
        raise ValueError(f'Context id already used: {context_id}')
    observations, observation_id = [], None
    for observation in parsed.observations:
        observation_id = _next_id('OB', used['observation'])
        used['observation'].add(observation_id)
        observations.append({'observation_id': observation_id, 'event_id': event_id,
                             **observation.model_dump(exclude_none=False),
                             'is_synthetic': True})

    event = {
        'event_id': event_id, 'prototype_id': prototype['prototype_id'],
        'line_id': parsed.line_id, 'context_id': context_id, 'scenario': parsed.scenario,
        'case_type': parsed.case_type, 'equipment': parsed.root_equipment_type,
        'primary_equipment_id': parsed.primary_equipment_id,
        'segment_ids': parsed.segment_ids, 'occurred_at': parsed.occurred_at,
        'reported_at': parsed.reported_at, 'symptom_text': parsed.symptom_text,
        'severity': parsed.severity, 'timeline': parsed.timeline,
        **parsed.extra_event_fields,
        'true_cause': parsed.true_cause, 'true_actions': parsed.true_actions,
        'true_cause_equipment_ids': parsed.true_cause_equipment_ids,
        'canary_token': canary_token(event_id),
        'split': prototype['split'], 'is_synthetic': True,
        '_visibility': {'pre_action': PRE_ACTION, 'ground_truth': GROUND_TRUTH,
                        'post_action': POST_ACTION},
    }
    scenario = {
        '_meta': {'title': parsed.title, 'prototype_id': prototype['prototype_id'],
                  'split': prototype['split'], 'all_numbers_are': '[가상 값]',
                  'spec_version': SPEC_VERSION,
                  # Lets a later run match this pending prototype instead of
                  # opening a second lineage for the same pattern.
                  'prototype_identity': {k: spec[k] for k in PROTOTYPE_KEYS},
                  'references': '기준정보·관계·페르소나 ID는 00_plant_and_relations.json 참조',
                  'visibility_rule': 'post_action / ground_truth 표시된 블록은 t시점 검색·프롬프트에 '
                                     '노출되지 않는다(B3-4)',
                  'human_review_required': True},
        'operating_context_snapshot': {'context_id': context_id, 'line_id': parsed.line_id,
                                       **parsed.operating_context, 'is_synthetic': True},
        'event': event,
        'observations': observations,
    }
    proposal = dict(prototype, pattern_name=parsed.pattern_name, event_id=event_id,
                    registered=False)
    return {'scenario': scenario, 'assignment_proposal': proposal}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, default=CATALOG)
    parser.add_argument('--scenarios', type=Path, nargs='+', default=[SCENARIOS],
                        help='Scenario dirs scanned for id collisions; pass the pending '
                             'output dir too or ids will be reissued')
    parser.add_argument('--personas', type=Path, default=Path('seeds/personas_v0.1.yaml'))
    parser.add_argument('--splits', type=Path, default=Path('splits/prototype_split.json'))
    parser.add_argument('--out', type=Path, default=Path('artifacts/scenarios'))
    args = parser.parse_args(argv)
    import yaml
    try:
        catalog = json.loads(args.catalog.read_text(encoding='utf-8-sig'))
        personas = yaml.safe_load(args.personas.read_text(encoding='utf-8'))['personas']
        policy = json.loads(args.splits.read_text(encoding='utf-8-sig'))
        result = build_scenario(
            json.loads(args.spec.read_text(encoding='utf-8-sig')), catalog=catalog,
            persona_ids={p['persona_id'] for p in personas},
            assignments=policy['assignments'],
            used=_scan_existing(*args.scenarios, args.out))
    except (OSError, ValueError, KeyError, yaml.YAMLError) as exc:
        print(_dump({'status': 'failed', 'error_type': type(exc).__name__, 'error': str(exc)}))
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    event_id = result['scenario']['event']['event_id']
    (args.out / f'{event_id}.json').write_text(
        json.dumps(result['scenario'], ensure_ascii=False, indent=1), encoding='utf-8')
    (args.out / f'{event_id}_assignment.json').write_text(
        json.dumps(result['assignment_proposal'], ensure_ascii=False, indent=1), encoding='utf-8')
    print(_dump({'status': 'written', 'event_id': event_id,
                 'split': result['assignment_proposal']['split'],
                 'basis': result['assignment_proposal']['basis'],
                 'out': str(args.out / f'{event_id}.json')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
