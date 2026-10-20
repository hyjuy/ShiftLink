const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const context = vm.createContext({ URLSearchParams });
vm.runInContext(fs.readFileSync('shiftlink/mes/web/pda.js', 'utf8'), context);

const time = '2026-10-17T09:00:00+09:00';
const older = '2026-10-17T08:59:50+09:00';
context.eq = { equipment_id: 'EQ-1', code: 'HPU-01', signals: [
  { signal: 'pressure', name: '압력', unit: 'bar', min: 145, max: 165, semantics: {} },
  { signal: 'temp', name: '유온', unit: 'degC', min: 40, max: 58, semantics: {} },
] };
context.eq2 = { equipment_id: 'EQ-2', code: 'HPU-02', signals: [
  { signal: 'pressure', name: '압력', unit: 'bar', min: 145, max: 165, semantics: {} },
] };
context.snap = { simulated_at: time, equipment: [], active_alarms: [], measurements: [
  { equipment_id: 'EQ-1', signal: 'pressure', value: 154.845, unit: 'bar', quality: 'good', observed_at: time },
  { equipment_id: 'EQ-1', signal: 'temp', value: 47.05, unit: 'degC', quality: 'good', observed_at: time },
  { equipment_id: 'EQ-2', signal: 'pressure', value: 155.2, unit: 'bar', quality: 'good', observed_at: time },
] };
const render = (equipment = '[eq]') => vm.runInContext(`reportMesContext(snap, [], ${equipment})`, context);

let output = render();
assert.match(output, /압력: 154\.85 bar/);
assert.match(output, /유온: 47\.05 ℃/);
assert.match(output, /정상 범위 145\.00 ~ 165\.00 bar/);
assert.match(output, /정상 범위 40\.00 ~ 58\.00 ℃/);
assert.equal(output.split('측정시각 · ' + time).length - 1, 1, 'one timestamp for simultaneous measurements');
assert.equal(output.split('설비명 · HPU-01').length - 1, 1, 'equipment name appears once');
assert.doesNotMatch(output, /품질 good/);
assert.doesNotMatch(output, /MES 기준시각/);

output = render('[eq, eq2]');
assert.equal(output.split('측정시각 · ' + time).length - 1, 1, 'one timestamp across equipment');
assert.match(output, /설비명 · HPU-02[\s\S]*압력: 155\.20 bar/);
assert.equal(output.split('설비명 · HPU-02').length - 1, 1);

context.snap.measurements[1].observed_at = older;
output = render();
assert.ok(output.includes('측정시각 2 · ' + older), 'distinct measurement time stays identifiable');
assert.match(output, /유온: 47\.05 ℃[^\n]*측정시각 2/);
assert.equal(output.split(older).length - 1, 1, 'distinct timestamp appears once');

context.snap.measurements[1].quality = 'bad';
output = render();
assert.doesNotMatch(output, /유온:/, 'unusable measurements remain excluded');
assert.deepEqual(context.snap.measurements[0], {
  equipment_id: 'EQ-1', signal: 'pressure', value: 154.845, unit: 'bar', quality: 'good', observed_at: time,
});
console.log('PASS: MES measurements group common timestamps across equipment and retain distinct times');
