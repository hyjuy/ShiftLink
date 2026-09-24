"""Stage A narrative synthesis: ground truth must not reach the prompt or the text."""

import json
from pathlib import Path

import pytest
import yaml

from shiftlink.data.generation import ApprovedScope
from shiftlink.data.narrative import build_prompt, generate_narrative

SCENARIO = Path('docs/data/scenarios/EV-0031_upstream_cause.json')
PERSONAS = Path('seeds/personas_v0.1.yaml')
CATALOG = Path('docs/data/reference/00_plant_and_relations.json')


@pytest.fixture
def scenario() -> dict:
    return json.loads(SCENARIO.read_text(encoding='utf-8-sig'))


@pytest.fixture
def catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding='utf-8-sig'))


@pytest.fixture
def persona() -> dict:
    personas = yaml.safe_load(PERSONAS.read_text(encoding='utf-8'))['personas']
    return next(p for p in personas if p['persona_id'] == 'V-01')


def test_prompt_excludes_ground_truth(scenario, persona, catalog) -> None:
    prompt, _ = build_prompt(scenario, persona, catalog)
    event = scenario['event']
    assert event['canary_token'] not in prompt
    assert event['true_cause'] not in prompt
    for action in event['true_actions']:
        assert action not in prompt
    for card_id in event['cards_expected']:
        assert card_id not in prompt


def test_prompt_excludes_post_action_timeline(scenario, persona, catalog) -> None:
    prompt, _ = build_prompt(scenario, persona, catalog)
    later = [t['text'] for t in scenario['event']['timeline']
             if t['kind'] in ('action', 'outcome', 'handover')]
    assert later, 'fixture must contain post-action timeline entries'
    for text in later:
        assert text not in prompt


def test_prompt_only_exposes_the_personas_own_observations(scenario, persona, catalog) -> None:
    prompt, observation_ids = build_prompt(scenario, persona, catalog)
    assert observation_ids == ['OB-0103', 'OB-0104', 'OB-0105']
    others = [o for o in scenario['observations']
              if o['observer_persona_id'] != persona['persona_id'] and o['qualitative_text']]
    assert others, 'fixture must contain other personas observations'
    for other in others:
        assert other['qualitative_text'] not in prompt


def test_timeline_does_not_leak_other_personas_readings(scenario, persona, catalog) -> None:
    """The ledger timeline merges every persona's sightings; V-01 must not see V-02's."""
    prompt, _ = build_prompt(scenario, persona, catalog)
    theirs = [t['text'] for t in scenario['event']['timeline']
              if t['kind'] == 'observation' and 'RT-03' in t['text']]
    assert theirs, 'fixture must contain another persona observation in the timeline'
    for text in theirs:
        assert text not in prompt


def test_canary_leak_is_rejected(scenario, persona, catalog) -> None:
    token = scenario['event']['canary_token']
    with pytest.raises(ValueError, match='Canary'):
        generate_narrative(scenario, persona, catalog, source_id='SD-901',
                           generate=lambda _: f'감속기 저음 들림. {token}')


def test_internal_id_leak_is_rejected(scenario, persona, catalog) -> None:
    with pytest.raises(ValueError, match='Internal ID'):
        generate_narrative(scenario, persona, catalog, source_id='SD-901',
                           generate=lambda _: 'EV-0031 관련해서 감속기 저음 들림.')


def test_proposal_is_pending_review_and_case_scoped(scenario, persona, catalog) -> None:
    text = '16:26경 감속기 입력측에서 규칙적인 저음 들림. 진동 3.4, 베어링 온도 64.5 확인했다.'
    result = generate_narrative(scenario, persona, catalog, source_id='SD-901',
                                generate=lambda _: text)
    scope = result['registry_proposal']['proposed_scope']
    assert result['registry_proposal']['review_status'] == 'pending_review'
    assert result['registry_proposal']['approved_scope'] == []
    assert result['human_review_required'] is True
    assert scope['kind'] == 'case'
    assert scope['group_id'] == scenario['event']['prototype_id']
    assert scope['reference_ids'] == ['EV-0031']
    # generation.py rehashes the excerpt against this value; they must agree exactly.
    import hashlib
    assert scope['text_sha256'] == hashlib.sha256(text.encode('utf-8')).hexdigest()


def test_proposed_scope_is_copyable_into_the_registry(scenario, persona, catalog) -> None:
    """A reviewer adds reviewed_by/reviewed_at and pastes the rest verbatim.

    ApprovedScope forbids extra keys, so any helper field here would be rejected
    at approval time rather than now.
    """
    result = generate_narrative(scenario, persona, catalog, source_id='SD-901',
                                generate=lambda _: 'GR-01 입력측 저음. 진동 3.4 확인.')
    scope = dict(result['registry_proposal']['proposed_scope'],
                 reviewed_by='검토자', reviewed_at='2026-09-24T09:00:00+09:00')
    approved = ApprovedScope.model_validate(scope)
    assert approved.kind == 'case'
    assert result['registry_proposal']['derived_from_observation_ids'] == [
        'OB-0103', 'OB-0104', 'OB-0105']


def test_sealed_scenario_is_refused(scenario, persona, catalog) -> None:
    """Sealed is evaluation holdout; generating from it burns the eval set."""
    sealed = dict(scenario, event=dict(scenario['event'], split='sealed'))
    with pytest.raises(ValueError, match='Sealed'):
        build_prompt(sealed, persona, catalog)


def test_missing_split_is_refused(scenario, persona, catalog) -> None:
    """Silence must not read as permission."""
    unmarked = dict(scenario, _meta={}, event={k: v for k, v in scenario['event'].items()
                                               if k != 'split'})
    with pytest.raises(ValueError, match='split must be kb or dev'):
        build_prompt(unmarked, persona, catalog)
