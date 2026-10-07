const assert = require('node:assert/strict');
const {unityLocation, handoverStatus, mesHandoverContext} = require('../shiftlink/mes/web/pda.js');
const config = {route:['EQ-6','EQ-7','EQ-8','EQ-9']};
assert.match(unityLocation({equipment_id:'EQ-6',code:'RT-01'}, config, 5), /주 이송로 1번째.*X -8.1, Y 0, Z 0/);
assert.match(unityLocation({equipment_id:'EQ-4',code:'GR-01'}, config, 3), /X -11.9, Y 0, Z 3/);
assert.match(unityLocation({equipment_id:'EQ-3',code:'CAU-01'}, config, 2), /X 3, Y 3.2, Z 8/);
assert.equal(handoverStatus('open')[0], '조치 필요');
assert.equal(handoverStatus('needs_recheck')[0], '재확인 필요');
assert.equal(handoverStatus('unknown')[0], '상태 확인 필요');
const eq = {equipment_id:'EQ-4',code:'GR-01',signals:[{signal:'temp',name:'베어링 온도',unit:'℃',semantics:{}}]};
const snap = {simulated_at:'2026-10-07T10:00:00+09:00',measurements:[
  {equipment_id:'EQ-4',signal:'temp',value:64,unit:'℃',quality:'good',observed_at:'2026-10-07T09:59:59+09:00'},
  {equipment_id:'EQ-5',signal:'temp',value:99,unit:'℃',quality:'good'},
  {equipment_id:'EQ-4',signal:'temp',value:200,unit:'℃',quality:'bad'},
]};
const events = Array.from({length:8}, (_,i) => ({equipment_id:'EQ-4',occurred_at:'10:00',observation:'기록 '+i}));
events.push({equipment_id:'EQ-5',observation:'다른 설비'});
const text = mesHandoverContext(snap, events, eq);
assert.match(text, /베어링 온도: 64 ℃.*09:59:59/);
assert.doesNotMatch(text, /99|200|다른 설비|기록 2/);
assert.match(text, /기록 3/);
assert.match(text, /기록 7/);
console.log('PDA handover copy and MES import PASS');
