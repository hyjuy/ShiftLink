"""Generate visual-check frames from the actual MES engine and installed sensor bands."""
import json
from pathlib import Path

from shiftlink.mes.configuration import from_catalog
from shiftlink.mes.contracts import Run
from shiftlink.mes.engine import MesEngine

root = Path(__file__).resolve().parents[1]
catalog = json.loads((root / 'docs/data/reference/00_plant_and_relations.json').read_text(encoding='utf-8'))
config = from_catalog(catalog)
frames = []
for spec in config.scenarios:
    engine = MesEngine(Run.create(seed=3, config_id=config.config_id), config)
    engine.start()
    engine.tick()
    engine.set_scenario(spec.scenario_id)
    snapshot = engine.snapshot.as_dict()
    snapshot['config_id'] = config.config_id
    snapshot['run_id'] = engine.run.run_id
    expected = [{'equipment_id': m.equipment_id, 'signal': m.signal,
                 'state': 'unavailable' if m.quality != 'good' else 'low' if m.value < s.normal_min else 'high' if m.value > s.normal_max else 'normal'}
                for eq in config.equipment for s in eq.signals
                for m in engine.snapshot.measurements
                if m.equipment_id == eq.equipment_id and m.signal == s.signal
                and s.normal_min is not None and s.normal_max is not None
                ]
    frames.append({'scenario_id': spec.scenario_id, 'snapshot': snapshot, 'expected': expected})
folder = root / 'unity/ShiftLinkFactory/Checks'
folder.mkdir(parents=True, exist_ok=True)
(folder / 'sensor-motion-frames.json').write_text(json.dumps({'frames': frames}, ensure_ascii=False, default=str), encoding='utf-8')
print(f'Generated {len(frames)} actual MES scenario frames')

products = {
    'HPU': ('Bosch Rexroth ABPAC', 'https://www.boschrexroth.com/en/de/connected-hydraulics/products/abpac/'),
    'GR': ('SEW X series industrial gearbox', 'https://www.sew-eurodrive.de/en/generation-xe/'),
    'RT': ('Butech Bliss Coil & Sheet Runout Conveyors', 'https://butechbliss.com/equipment/material-handling-equipment/coil-sheet-runout-conveyors/'),
    'CV': ('Mayfran flat-top / Miven Mayfran hinged steel belt', 'https://www.mayfran.com/products/material-and-scrap-handling-recycling/'),
    'PDP': ('ABB MNS exterior', 'https://new.abb.com/medium-voltage/switchgear/3d-ecatalogue/low-voltage/mns-front'),
    'CAU': ('Atlas Copco GA enclosed screw compressor', 'https://www.atlascopco.com/en-us/compressors/products/air-compressor/rotary-screw-compressor/ga-plus-screw-compressor'),
}
physical = {
    'hpu_pressure': 'pressure gauge pointer', 'hpu_oil_level': 'oil sight glass level',
    'air_pressure': 'pressure gauge pointer', 'gr_rpm': 'designated input drive shaft rotation; no output gear-ratio inference',
    'breaker_trip': 'external breaker handle indication', 'cv_speed': 'belt travel / steel slat travel',
    'rt_speed': 'roller surface-speed rotation',
}
illustrative = {
    'gr_vib_rms': 'bounded housing vibration', 'gr_oil_leak': 'pulsing leak marker; location not inferred from sensor',
    'rt_vib_rms': 'bounded bearing cover vibration', 'cv_vib_rms': 'bounded drum bearing cover vibration',
    'rt_clamp_press': 'loaded clamp demo cycle only with normal pressure',
    'rt_lift_delay': 'loaded lift demo cycle timing; stroke not measured',
    'cv_belt_tension': 'tensioner demo travel; pressure not converted to force',
}
equipment = []
for eq in config.equipment:
    family = eq.code.split('-')[0]
    channels = []
    for signal in eq.signals:
        persona = 'V-12' if family in {'RT','CV','CAU'} else 'V-11' if family == 'HPU' or signal.signal in {'gr_vib_rms','gr_oil_leak'} else 'V-13'
        channels.append({'signal': signal.signal, 'unit': signal.unit, 'normal_band': [signal.normal_min,signal.normal_max],
                         'acquisition': signal.semantics.get('acquisition'), 'persona_id': persona,
                         'sensor_visual': 'normal steady green / out-of-band amber pulse / unavailable grey',
                         'physical_motion': physical.get(signal.signal), 'illustrative_motion': illustrative.get(signal.signal),
                         'scenario_id': f'sensor_anomaly_{eq.equipment_id}_{signal.signal}'})
    equipment.append({'equipment_id':eq.equipment_id,'code':eq.code,'reference_product':products[family][0],
                      'source_url':products[family][1],'channels':channels})
motion_map = {'is_synthetic':True,'config_id':config.config_id,'persona_source':'seeds/personas_v0.1.yaml',
    'persona_rule':'Event/sensor facts are shared; personas only change observation focus and wording, never physics or approvals',
    'operating_mode_override':{'hpu_accumulator_precharge':{'gas_pressure_bar':[130,140],'fluid_pressure_bar':0,'manifold_pressure_bar':0}},
    'scenario_count':len(frames),'sensor_count':sum(len(e.signals) for e in config.equipment),
    'assumptions':['Exterior references and process adaptations; not exact OEM CAD or installed product certification',
                   'Existing MES material IDs and coil/scrap transport preserved',
                   'Lift/clamp/diverter displacements are demo cycles, not measured position telemetry',
                   'V-11 sensory-first, V-12 measurement-first, V-13 maintenance-record-first; no invented maintenance or restart approval'],
    'equipment':equipment}
(root / 'unity/ShiftLinkFactory/Assets/Models/EquipmentTypes/process-motion-map.json').write_text(json.dumps(motion_map,ensure_ascii=False,indent=2),encoding='utf-8')
