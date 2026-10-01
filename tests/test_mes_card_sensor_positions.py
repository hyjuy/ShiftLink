"""Card-specific measurement positions reach MES snapshots and card search."""
import pytest

from shiftlink.mes.configuration import from_catalog
from shiftlink.mes.contracts import Run
from shiftlink.mes.engine import MesEngine
from shiftlink.mes.card_adapter import MesCardAdapter
from shiftlink.rag.retrieval import InMemoryToolProvider
from tests.test_mes_utility_scenarios import CATALOG, Observer


POSITIONS = [
    ('EQ-0001', 'hpu_pump_outlet_pressure', 'bar', 145, 165),
    ('EQ-0001', 'fluid_viscosity', 'cSt', 20, 100),
    ('EQ-0004', 'gr_oil_water_content', 'ppm', 0, 300),
    ('EQ-0005', 'gr_oil_water_content', 'ppm', 0, 300),
    ('EQ-0002', 'breaker_pole_l1_temp', 'degC', 30, 45),
    ('EQ-0002', 'breaker_pole_l2_temp', 'degC', 30, 45),
    ('EQ-0002', 'breaker_pole_l3_temp', 'degC', 30, 45),
    ('EQ-0003', 'compressor_discharge_temp', 'degC', 70, 90),
    ('EQ-0003', 'compressor_separator_dp', 'bar', 0, 0.8),
    ('EQ-0003', 'air_nozzle_pressure', 'MPa', 0.1, 0.2),
    ('EQ-0001', 'hpu_cooler_oil_in_temp', 'degC', 35, 58),
    ('EQ-0001', 'hpu_cooler_oil_out_temp', 'degC', 35, 58),
    ('EQ-0001', 'hpu_cooler_water_in_temp', 'degC', 15, 30),
    ('EQ-0001', 'hpu_cooler_water_out_temp', 'degC', 20, 40),
    ('EQ-0001', 'hpu_cooler_oil_flow', 'L_min', 38, 46),
    ('EQ-0001', 'hpu_accumulator_gas_pressure', 'bar', 145, 165),
    ('EQ-0001', 'hpu_accumulator_fluid_pressure', 'bar', 145, 165),
    ('EQ-0001', 'hpu_return_submergence', 'mm', 100, 200),
    ('EQ-0001', 'hpu_suction_head', 'mm', 100, 200),
    ('EQ-0004', 'gr_surface_temp', 'degC', 20, 40),
    ('EQ-0005', 'gr_surface_temp', 'degC', 20, 40),
    ('EQ-0009', 'cv_idler_speed_ratio', 'pct', 80, 100),
    ('EQ-0010', 'cv_idler_speed_ratio', 'pct', 80, 100),
]


@pytest.mark.parametrize('eq_id,signal,unit,low,high', POSITIONS)
def test_card_position_observation_anomaly_and_recovery(eq_id, signal, unit, low, high):
    config = from_catalog(CATALOG)
    eq = next(e for e in config.equipment if e.equipment_id == eq_id)
    installed = {s.signal: s for s in eq.signals}
    assert signal in installed
    assert (installed[signal].unit, installed[signal].normal_min, installed[signal].normal_max) == (unit, low, high)
    engine = MesEngine(Run.create(seed=3, config_id=config.config_id), config)
    engine.start()
    engine.tick()
    provider = InMemoryToolProvider([], equipment_db=CATALOG['equipment'], equipment_types=CATALOG['equipment_types'])
    adapter = MesCardAdapter(Observer(engine), config, provider)
    observations = {o.signal: o for o in adapter.search(engine.run.run_id, eq_id, 'position')['request'].observations}
    assert observations[signal].unit == unit
    assert low <= observations[signal].value <= high
    assert observations[signal + '_state'].value == 'normal'
    engine.set_scenario(f'sensor_anomaly_{eq_id}_{signal}')
    observations = {o.signal: o for o in adapter.search(engine.run.run_id, eq_id, 'position')['request'].observations}
    assert observations[signal].value < low or observations[signal].value > high
    assert observations[signal + '_state'].value in ('low', 'high')
    engine.recover()
    engine.tick(2)
    restored = next(m for m in engine.snapshot.measurements if m.equipment_id == eq_id and m.signal == signal)
    assert low <= restored.value <= high


@pytest.mark.parametrize('scenario,eq_id,signal,value,unit', [
    ('hpu_no_outlet_pressure', 'EQ-0001', 'hpu_pump_outlet_pressure', 0, 'bar'),
    ('hpu_high_viscosity', 'EQ-0001', 'fluid_viscosity', 2500, 'cSt'),
    ('air_nozzle_overpressure', 'EQ-0003', 'air_nozzle_pressure', 0.25, 'MPa'),
])
def test_card_branch_values_reach_mes_search(scenario, eq_id, signal, value, unit):
    config = from_catalog(CATALOG)
    engine = MesEngine(Run.create(seed=3, config_id=config.config_id), config)
    engine.start()
    engine.set_scenario(scenario)
    provider = InMemoryToolProvider([], equipment_db=CATALOG['equipment'], equipment_types=CATALOG['equipment_types'])
    adapter = MesCardAdapter(Observer(engine), config, provider)
    observations = {o.signal: o for o in adapter.search(engine.run.run_id, eq_id, 'card branch')['request'].observations}
    assert (observations[signal].value, observations[signal].unit) == (value, unit)
