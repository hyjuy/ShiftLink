"""Synthetic event assembly: split lineage, catalog references, ground-truth marking."""

import json
from pathlib import Path

import pytest
import yaml

from shiftlink.data.scenario import (
    GROUND_TRUTH, assign_split, build_scenario, canary_token, prototype_key,
    resolve_prototype,
)

CATALOG = Path('docs/data/reference/00_plant_and_relations.json')
PERSONAS = Path('seeds/personas_v0.1.yaml')
SPLITS = Path('splits/prototype_split.json')


@pytest.fixture
def catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding='utf-8-sig'))


@pytest.fixture
def persona_ids() -> set:
    return {p['persona_id']
            for p in yaml.safe_load(PERSONAS.read_text(encoding='utf-8'))['personas']}


@pytest.fixture
def assignments() -> list:
    return json.loads(SPLITS.read_text(encoding='utf-8-sig'))['assignments']


@pytest.fixture
def used() -> dict:
    return {'event': {'EV-0031', 'EV-0032', 'EV-0033'}, 'observation': {'OB-0101'},
            'context': {'CTX-0031'}, 'prototypes': []}


@pytest.fixture
def spec() -> dict:
    return {
        'case_type': 'lubrication_starvation',
        'root_equipment_type': 'GR',
        'relation_path_types': ['drive'],
        'primary_symptom_class': '윤활 부족에 따른 구동부 발열',
        'pattern_name': '윤활 공급 저하의 구동부 발열',
        'title': '구동 감속기 윤활 부족 사건',
        'line_id': 'LN-0001',
        'primary_equipment_id': 'EQ-0004',
        'segment_ids': ['SG-0002'],
        'occurred_at': '2026-07-14T02:10:00+09:00',
        'reported_at': '2026-07-14T02:15:00+09:00',
        'symptom_text': '감속기 하우징 표면이 평소보다 뜨겁고 유면계가 하한에 가깝다.',
        'severity': 'medium',
        'scenario': 'S2',
        'observations': [
            {'equipment_id': 'EQ-0004', 'component_id': 'CP-0007',
             'observed_at': '2026-07-14T02:12:00+09:00', 'observer_persona_id': 'V-11',
             'obs_kind': 'sensory', 'qualitative_text': '하우징이 손대기 어려울 만큼 뜨겁다'},
            {'equipment_id': 'EQ-0004', 'observed_at': '2026-07-14T02:14:00+09:00',
             'observer_persona_id': 'V-13', 'obs_kind': 'measurement',
             'signal': 'gr_brg_temp', 'value': 78.0, 'unit': 'degC',
             'judgment_vs_normal': 'above'},
        ],
        'operating_context': {'captured_at': '2026-07-14T02:10:00+09:00',
                              'op_mode': 'running_normal', 'shift_code': 'C'},
        'timeline': [{'at': '2026-07-14T02:12:00+09:00', 'kind': 'observation',
                      'text': '하우징 발열 확인'}],
        'true_cause': '윤활유 공급 배관 부분 막힘으로 유량이 줄어 베어링 발열이 발생했다.',
        'true_actions': ['감속기 유면·유온 재측정', '차기 정지 시 윤활 배관 점검 요청'],
        'true_cause_equipment_ids': ['EQ-0004'],
    }


def test_split_hash_matches_the_recorded_reference_value() -> None:
    """The contract's hash rule, checked against a value computed outside this module."""
    bucket, split = assign_split('SRC-KOSHA-M101-2012-CONVEYOR-SAFETY')
    assert (bucket, split) == (4, 'kb')


def test_split_buckets_cover_the_documented_ranges() -> None:
    from shiftlink.data.scenario import BUCKETS
    assert [BUCKETS[b] for b in range(12)] == ['kb'] * 7 + ['dev'] * 2 + ['sealed'] * 3


def test_existing_prototype_is_reused_instead_of_rehashed(catalog, assignments) -> None:
    """An existing assignment wins over the hash; the same lineage must not be re-rolled."""
    existing = catalog['event_prototypes'][0]
    resolved = resolve_prototype(existing, catalog, assignments)
    assert resolved['prototype_id'] == existing['prototype_id']
    assert resolved['is_new'] is False
    assert resolved['split'] == existing['assigned_split']


def test_prototype_key_ignores_relation_path_order() -> None:
    a = {'case_type': 'x', 'root_equipment_type': 'GR',
         'relation_path_types': ['drive', 'material_flow'], 'primary_symptom_class': 's'}
    b = dict(a, relation_path_types=['material_flow', 'drive'])
    assert prototype_key(a) == prototype_key(b)


def test_new_lineage_gets_fresh_id_and_hash_split(spec, catalog, assignments) -> None:
    resolved = resolve_prototype(spec, catalog, assignments)
    assert resolved['is_new'] is True
    assert resolved['prototype_id'] not in {p['prototype_id']
                                            for p in catalog['event_prototypes']}
    assert resolved['split'] == assign_split(resolved['prototype_id'])[1]


def test_unknown_catalog_reference_is_rejected(spec, catalog, persona_ids,
                                               assignments, used) -> None:
    spec['observations'][0]['equipment_id'] = 'EQ-9999'
    with pytest.raises(ValueError, match='Unknown catalog references'):
        build_scenario(spec, catalog=catalog, persona_ids=persona_ids,
                       assignments=assignments, used=used)


def test_unknown_persona_is_rejected(spec, catalog, persona_ids, assignments, used) -> None:
    spec['observations'][0]['observer_persona_id'] = 'V-99'
    with pytest.raises(ValueError, match='observer_persona_id'):
        build_scenario(spec, catalog=catalog, persona_ids=persona_ids,
                       assignments=assignments, used=used)


def test_ids_do_not_collide_with_existing_scenarios(spec, catalog, persona_ids,
                                                    assignments, used) -> None:
    result = build_scenario(spec, catalog=catalog, persona_ids=persona_ids,
                            assignments=assignments, used=used)
    event = result['scenario']['event']
    assert event['event_id'] == 'EV-0034'
    assert event['context_id'] == 'CTX-0034'
    assert [o['observation_id'] for o in result['scenario']['observations']] == [
        'OB-0102', 'OB-0103']


def test_ground_truth_is_marked_and_canary_issued(spec, catalog, persona_ids,
                                                  assignments, used) -> None:
    result = build_scenario(spec, catalog=catalog, persona_ids=persona_ids,
                            assignments=assignments, used=used)
    event = result['scenario']['event']
    assert event['_visibility']['ground_truth'] == GROUND_TRUTH
    assert event['canary_token'] == canary_token(event['event_id'])
    assert event['canary_token'].startswith('zzk9-ev0034-')
    assert event['is_synthetic'] is True
    # narrative.py reads _visibility.ground_truth to refuse leaking fields.
    for field in ('true_cause', 'true_actions', 'canary_token'):
        assert field in event['_visibility']['ground_truth']


def test_assignment_is_proposed_not_registered(spec, catalog, persona_ids,
                                               assignments, used) -> None:
    """This module never edits splits/prototype_split.json."""
    result = build_scenario(spec, catalog=catalog, persona_ids=persona_ids,
                            assignments=assignments, used=used)
    assert result['assignment_proposal']['registered'] is False
    assert result['scenario']['_meta']['human_review_required'] is True


def test_pending_prototype_id_is_never_reissued(spec, catalog, assignments) -> None:
    """A lineage proposed but not yet registered still owns its PT id.

    Reissuing it merges two unrelated lineages into one split group.
    """
    first = resolve_prototype(spec, catalog, assignments, pending=[])
    other = dict(spec, case_type='some_other_pattern',
                 primary_symptom_class='전혀 다른 증상')
    second = resolve_prototype(other, catalog, assignments,
                               pending=[{'prototype_id': first['prototype_id'],
                                         'split': first['split']}])
    assert second['prototype_id'] != first['prototype_id']
    assert second['is_new'] is True


def test_pending_prototype_is_reused_when_identity_matches(spec, catalog,
                                                           assignments) -> None:
    """The same pattern must not open a second lineage."""
    first = resolve_prototype(spec, catalog, assignments, pending=[])
    pending = [{'prototype_id': first['prototype_id'], 'split': first['split'],
                **{k: spec[k] for k in ('case_type', 'root_equipment_type',
                                        'relation_path_types', 'primary_symptom_class')}}]
    second = resolve_prototype(spec, catalog, assignments, pending=pending)
    assert second['prototype_id'] == first['prototype_id']
    assert second['is_new'] is False
    assert second['basis'] == 'pending_proposal_reuse'


def test_component_on_the_wrong_equipment_is_rejected(spec, catalog, persona_ids,
                                                      assignments, used) -> None:
    """CP-0018 exists, but it belongs to EQ-0006 — an existence check alone passes it."""
    spec['observations'][0]['equipment_id'] = 'EQ-0009'
    spec['observations'][0]['component_id'] = 'CP-0018'
    with pytest.raises(ValueError, match='belongs to EQ-0006'):
        build_scenario(spec, catalog=catalog, persona_ids=persona_ids,
                       assignments=assignments, used=used)


def test_scan_covers_every_directory(tmp_path) -> None:
    from shiftlink.data.scenario import _scan_existing
    pending = tmp_path / 'pending'
    pending.mkdir()
    (pending / 'EV-0099.json').write_text(json.dumps({
        'event': {'event_id': 'EV-0099', 'prototype_id': 'PT-0099', 'split': 'dev'},
        'operating_context_snapshot': {'context_id': 'CTX-0099'},
        'observations': [{'observation_id': 'OB-0999'}]}), encoding='utf-8')
    used = _scan_existing(Path('docs/data/scenarios'), pending)
    assert 'EV-0099' in used['event'] and 'EV-0031' in used['event']
    assert 'OB-0999' in used['observation']
    assert any(p['prototype_id'] == 'PT-0099' for p in used['prototypes'])


def test_prototype_identity_is_recorded_for_later_reuse(spec, catalog, persona_ids,
                                                        assignments, used) -> None:
    result = build_scenario(spec, catalog=catalog, persona_ids=persona_ids,
                            assignments=assignments, used=used)
    identity = result['scenario']['_meta']['prototype_identity']
    assert identity['case_type'] == spec['case_type']
    assert identity['primary_symptom_class'] == spec['primary_symptom_class']
