const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const context=vm.createContext({URLSearchParams});
vm.runInContext(fs.readFileSync('shiftlink/mes/web/pda.js','utf8'),context);
const time='2026-10-17T09:00:00+09:00',older='2026-10-17T08:59:50+09:00';
context.eq={equipment_id:'EQ-1',code:'HPU-01',signals:[
 {signal:'pressure',name:'압력',unit:'bar',min:145,max:165,semantics:{}},
 {signal:'temp',name:'유온',unit:'degC',min:40,max:58,semantics:{}}
]};
context.snap={simulated_at:time,equipment:[],active_alarms:[],measurements:[
 {equipment_id:'EQ-1',signal:'pressure',value:154.845,unit:'bar',quality:'good',observed_at:time},
 {equipment_id:'EQ-1',signal:'temp',value:47.05,unit:'degC',quality:'good',observed_at:time}
]};
const render=()=>vm.runInContext('reportMesContext(snap,[],[eq])',context);
let text=render();
assert.match(text,/압력: 154\.845 bar/);assert.match(text,/유온: 47\.05 ℃/);
assert.match(text,/정상 범위 145 ~ 165 bar/);
assert.match(text,/정상 범위 40 ~ 58 ℃/);
assert.equal(text.split('관측시각 · '+time).length-1,1,'one timestamp for measurements observed together');
assert.doesNotMatch(text,/ · 측정 /);
context.snap.measurements[1].observed_at=older;text=render();
assert.ok(text.includes('관측시각 · '+older),'different observation time stays identifiable');
assert.ok(text.indexOf('관측시각 · '+older)<text.indexOf('유온:'));
context.snap.measurements[1].quality='bad';text=render();
assert.doesNotMatch(text,/유온:/,'unusable measurements remain excluded');
assert.deepEqual(context.snap.measurements[0],{equipment_id:'EQ-1',signal:'pressure',value:154.845,unit:'bar',quality:'good',observed_at:time});
console.log('PASS: sensor units and original timestamps, common-time grouping, distinct-time groups, quality exclusions and unchanged source');
