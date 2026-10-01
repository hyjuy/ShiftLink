"""Semantic audit harness: check relationships, context, and diagnostic use."""
from datetime import timedelta
import hashlib
import json

import pytest

from shiftlink.mes.card_adapter import MesCardAdapter
from shiftlink.mes.configuration import from_catalog, from_payload, to_payload
from shiftlink.mes.contracts import Run
from shiftlink.mes.engine import MesEngine
from shiftlink.rag.retrieval import InMemoryToolProvider
from tests.test_mes_utility_scenarios import CATALOG, Observer


def readings(snapshot, equipment_id):
    return {m.signal: m for m in snapshot.measurements if m.equipment_id == equipment_id}


@pytest.mark.parametrize('seed', [3, 17, 91])
def test_normal_cooler_temperatures_respect_heat_transfer(seed):
    config = from_catalog(CATALOG)
    engine = MesEngine(Run.create(seed=seed, config_id=config.config_id), config)
    engine.start()
    for _ in range(60):
        values = readings(engine.tick(), 'EQ-0001')
        assert values['hpu_cooler_oil_out_temp'].value < values['hpu_cooler_oil_in_temp'].value
        assert values['hpu_cooler_water_out_temp'].value > values['hpu_cooler_water_in_temp'].value


def test_cooler_without_separate_circulation_has_no_stopped_oil_flow():
    config = from_catalog(CATALOG)
    engine = MesEngine(Run.create(seed=3, config_id=config.config_id), config)
    assert readings(engine.snapshot, 'EQ-0001')['hpu_cooler_oil_flow'].value == 0
    engine.start()
    assert readings(engine.tick(), 'EQ-0001')['hpu_cooler_oil_flow'].value > 0


def test_queue_occupancy_tracks_material_instead_of_independent_noise():
    config = from_catalog(CATALOG)
    engine = MesEngine(Run.create(seed=3, config_id=config.config_id), config)
    engine.start()
    for _ in range(60):
        snapshot = engine.tick()
        for eq in config.equipment:
            values = readings(snapshot, eq.equipment_id)
            if 'cv_queue_len' not in values:
                continue
            count = sum(c['equipment_id'] == eq.equipment_id for c in snapshot.coils)
            assert values['cv_queue_len'].value == min(100, round(100 * count / eq.coil_capacity, 3))


@pytest.mark.parametrize('eq_id,signal', [
    ('EQ-0007', 'rt_lift_delay'),
])
def test_measurements_without_required_context_are_not_diagnostic_evidence(eq_id, signal):
    config = from_catalog(CATALOG)
    engine = MesEngine(Run.create(seed=3, config_id=config.config_id), config)
    engine.start()
    engine.tick()
    assert readings(engine.snapshot, eq_id)[signal].quality == 'unavailable'
    provider = InMemoryToolProvider([], equipment_db=CATALOG['equipment'], equipment_types=CATALOG['equipment_types'])
    result = MesCardAdapter(Observer(engine), config, provider).search(engine.run.run_id, eq_id, 'semantic audit')
    assert signal not in {o.signal for o in result['request'].observations}
    engine.set_scenario(f'sensor_anomaly_{eq_id}_{signal}')
    assert readings(engine.snapshot, eq_id)[signal].quality == 'good'


def test_accumulator_operating_pressure_is_distinct_from_discharged_precharge():
    config = from_catalog(CATALOG)
    engine = MesEngine(Run.create(seed=3, config_id=config.config_id), config)
    engine.start()
    for _ in range(60):
        values = readings(engine.tick(), 'EQ-0001')
        assert values['hpu_accumulator_gas_pressure'].value == values['hpu_accumulator_fluid_pressure'].value
    engine.set_scenario('hpu_accumulator_precharge')
    values = readings(engine.snapshot, 'EQ-0001')
    assert values['hpu_accumulator_gas_pressure'].value == 135
    assert values['hpu_accumulator_fluid_pressure'].value == 0
    assert values['hpu_pressure'].value == 0
    assert not engine.snapshot.active_alarms
    assert next(e for e in engine.snapshot.equipment if e.equipment_id == 'EQ-0001').fault_level == 'normal'


def test_sensor_acquisition_and_reference_definitions_survive_configuration_storage():
    config = from_catalog(CATALOG)
    restored = from_payload(to_payload(config))
    assert restored == config
    specs = {s.signal: s for eq in restored.equipment for s in eq.signals}
    for signal in ('bus_voltage', 'cv_belt_tension', 'cv_queue_len', 'cv_idler_speed_ratio',
                   'fluid_viscosity', 'gr_oil_water_content', 'hpu_return_submergence', 'hpu_suction_head'):
        semantics = specs[signal].semantics
        assert semantics['acquisition'] in ('continuous', 'derived', 'event', 'manual_sample')
        assert semantics['location']
        assert semantics['reference']
        assert semantics['applicability']
        assert semantics['model']


@pytest.mark.parametrize('eq_id,signal', [
    ('EQ-0001', 'fluid_viscosity'),
    ('EQ-0004', 'gr_oil_water_content'),
    ('EQ-0001', 'hpu_return_submergence'),
    ('EQ-0001', 'hpu_suction_head'),
])
def test_manual_sample_retains_value_and_time_until_next_sample(eq_id, signal):
    config = from_catalog(CATALOG)
    engine = MesEngine(Run.create(seed=3, config_id=config.config_id), config)
    initial = readings(engine.snapshot, eq_id)[signal]
    engine.start()
    for _ in range(59):
        assert readings(engine.tick(), eq_id)[signal] == initial
    refreshed = readings(engine.tick(), eq_id)[signal]
    assert refreshed.observed_at == initial.observed_at + timedelta(seconds=60)
    assert refreshed.quality == 'good'


@pytest.mark.parametrize('age,accepted', [(59, True), (60, False), (-1, False)])
def test_card_conditions_reject_stale_or_future_manual_samples(age, accepted):
    config = from_catalog(CATALOG)
    engine = MesEngine(Run.create(seed=3, config_id=config.config_id), config)
    engine.start()
    engine.tick()
    payload = engine.snapshot.as_dict()
    sample = next(m for m in payload['measurements'] if m['signal'] == 'fluid_viscosity')
    sample['observed_at'] = payload['simulated_at'] - timedelta(seconds=age)

    class FixedObserver:
        def observations(self, run_id, *, as_of=None):
            return {'config_id': config.config_id, 'snapshot': payload}

    provider = InMemoryToolProvider([], equipment_db=CATALOG['equipment'], equipment_types=CATALOG['equipment_types'])
    result = MesCardAdapter(FixedObserver(), config, provider).search(engine.run.run_id, 'EQ-0001', 'sample audit')
    assert ('fluid_viscosity' in {o.signal for o in result['request'].observations}) is accepted
    evidence = next(m for m in result['evidence']['measurements'] if m['signal'] == 'fluid_viscosity')
    assert evidence['used_for_conditions'] is accepted


def test_legacy_payload_omits_empty_semantics_and_preserves_hash():
    legacy = to_payload(from_catalog(CATALOG))
    for eq in legacy['equipment']:
        for signal in eq['signals']:
            signal.pop('semantics', None)
    legacy['config_id'] = 'placeholder'
    expected_hash = hashlib.sha256(json.dumps(legacy, sort_keys=True, ensure_ascii=False,
                                             separators=(',', ':')).encode()).hexdigest()
    legacy['config_id'] = expected_hash
    restored = from_payload(legacy)
    assert all(not s.semantics for eq in restored.equipment for s in eq.signals)
    assert restored.config_id == expected_hash
    assert to_payload(from_payload(to_payload(restored))) == to_payload(restored)
    assert all('semantics' not in s for eq in to_payload(restored)['equipment'] for s in eq['signals'])


def test_catalog_restart_upgrades_new_run_without_rewriting_history():
    from shiftlink.mes.storage import MesStorage
    from shiftlink.mes.server import MesService
    from pathlib import Path
    payload = to_payload(from_catalog(CATALOG))
    for eq in payload['equipment']:
        for signal in eq['signals']:
            signal.pop('semantics', None)
            if signal['signal'] == 'hpu_accumulator_gas_pressure':
                signal['normal_min'], signal['normal_max'] = 130, 140
    old = from_payload(payload)
    storage = MesStorage()
    try:
        storage.save_configuration(old.config_id, json.dumps(to_payload(old)))
        old_run = Run.create(seed=3, config_id=old.config_id)
        storage.create_run(old_run)
        service = MesService(Path(__file__).parents[1] / 'docs/data/reference/00_plant_and_relations.json', storage)
        assert service.active_config.config_id != old.config_id
        gas = next(s for e in service.active_config.equipment for s in e.signals if s.signal == 'hpu_accumulator_gas_pressure')
        assert (gas.normal_min, gas.normal_max) == (145, 165)
        assert storage.get_configuration(old.config_id) == to_payload(old)
        assert storage.get_run(old_run.run_id) == old_run
    finally:
        storage.close()


@pytest.mark.parametrize('capacity', [0, -1, True])
def test_occupancy_denominator_rejects_invalid_capacity(capacity):
    from dataclasses import replace
    from shiftlink.mes.configuration import validate
    config = from_catalog(CATALOG)
    changed = replace(config, equipment=(replace(config.equipment[0], coil_capacity=capacity), *config.equipment[1:]))
    assert any('coil_capacity' in error for error in validate(changed))


def test_sensor_definition_change_is_reviewable_in_configuration_diff():
    from dataclasses import replace
    from shiftlink.mes.configuration import diff, validate
    config = from_catalog(CATALOG)
    eq = config.equipment[0]
    signal = eq.signals[0]
    updated = replace(signal, semantics={**signal.semantics, 'reference': 'new reviewed reference'})
    changed = replace(config, equipment=(replace(eq, signals=(updated, *eq.signals[1:])), *config.equipment[1:]))
    assert diff(config, changed)['signal_changed'][0]['change'] == 'definition'
    bad = replace(changed, equipment=(replace(eq, signals=(replace(signal, semantics={'model': 'incomplete'}), *eq.signals[1:])), *config.equipment[1:]))
    assert any('semantics' in error for error in validate(bad))
