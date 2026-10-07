// Normal occupancy is process information, not a standalone equipment fault.
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const { S, equipmentFrom, faultsFrom, usableReadings } = require('../shiftlink/mes/web/pda.js');
const fixture = JSON.parse(execFileSync('python', ['-c', `
import json
from pathlib import Path
from shiftlink.mes.configuration import from_catalog, to_payload
from shiftlink.mes.contracts import Run
from shiftlink.mes.engine import MesEngine
catalog = json.loads(Path('docs/data/reference/00_plant_and_relations.json').read_text(encoding='utf-8'))
config = from_catalog(catalog)
engine = MesEngine(Run.create(seed=3, config_id=config.config_id), config)
engine.start()
normal = []
for _ in range(120):
    engine.tick()
    normal.append(engine.snapshot.as_dict())
engine.set_scenario('downstream_block')
blocked = engine.snapshot.as_dict()
engine.recover()
engine.tick(2)
print(json.dumps(dict(config=to_payload(config), catalog=catalog, normal=normal,
                     blocked=blocked, recovered=engine.snapshot.as_dict()), default=str))
`], { cwd: require('node:path').join(__dirname, '..'), encoding: 'utf8', maxBuffer: 8 * 1024 * 1024 }));
S.equipment = equipmentFrom(fixture.config, fixture.catalog);
const cv = S.equipment.find(eq => eq.code === 'CV-01');
const hasCv = snap => faultsFrom(snap).some(f => f.eq === cv);
const full = fixture.normal.filter(snap => usableReadings(snap, cv).kept.some(o => o.signal === 'cv_queue_len' && o.value === 100));
assert.ok(full.length > 0, 'integration fixture must include real normal full occupancy');
assert.ok(fixture.normal.every(snap => !hasCv(snap)), 'normal moving CV must not produce a fault banner');
assert.ok(full.every(snap => snap.active_alarms.length === 0));
assert.ok(hasCv(fixture.blocked), 'explicit downstream block alarm must remain visible');
assert.ok(!hasCv(fixture.recovered), 'recovery must remove fault even if occupied');

const at = '2026-10-07T00:00:00+00:00';
const reading = (signal, value) => ({ equipment_id: cv.equipment_id, signal, value,
  unit: cv.signals.find(s => s.signal === signal).unit, quality: 'good', observed_at: at });
const snap = { simulated_at: at, equipment: [{equipment_id:cv.equipment_id, operating_state:'running', fault_level:'normal'}],
  measurements:[reading('cv_queue_len', 100)], active_alarms:[], symptom_diagnostics:[] };
assert.equal(hasCv(snap), false);
assert.equal(usableReadings(snap, cv).kept[0].value, 100, 'occupancy remains available to sensor display and queries');
snap.measurements.push(reading('cv_speed', 0));
assert.ok(hasCv(snap), 'speed loss remains visible alongside full occupancy');
snap.measurements.pop();
snap.symptom_diagnostics.push({equipment_id:cv.equipment_id, symptom:'이송 저항·정체', status:'candidate'});
assert.ok(hasCv(snap), 'combined symptom diagnosis remains visible');
snap.symptom_diagnostics = [];
snap.equipment[0].fault_level = 'warning';
assert.ok(hasCv(snap), 'MES fault state remains visible without an alarm');
snap.equipment[0].fault_level = 'critical';
assert.equal(faultsFrom(snap).find(f => f.eq === cv).level, 0);
snap.equipment[0].fault_level = 'normal';
snap.measurements = [reading('cv_motor_current', cv.signals.find(s => s.signal === 'cv_motor_current').max + 1)];
assert.ok(hasCv(snap), 'other numeric deviations are not suppressed');
console.log('PDA CV occupancy, real MES normal flow, downstream fault and recovery PASS');
