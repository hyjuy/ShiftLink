const assert = require('node:assert/strict');
const {unityLocation, handoverStatus, mesHandoverContext, appendMesContext, dashSummary} = require('../shiftlink/mes/web/pda.js');
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
// 다시 불러오기: 이미 있는 줄은 붙이지 않고, 새 줄만 머리줄과 함께 붙인다
const first = appendMesContext('작업 메모', text);
assert.equal(appendMesContext(first, text), null);
const later = mesHandoverContext({...snap, simulated_at:'2026-10-07T10:05:00+09:00'},
  [...events, {equipment_id:'EQ-4',occurred_at:'10:04',observation:'새 기록'}], eq);
const second = appendMesContext(first, later);
assert.equal(second.match(/기록 7/g).length, 1);
assert.match(second, /10:05:00.*\n10:04 · 새 기록$/);
// 대시보드 요약: 후속 대기는 고장 사유로 기다리는 설비만, 인계는 끝나지 않은 항목만 센다
const dash = dashSummary({line_mode:'running', simulated_at:'2026-10-08T13:42:05+09:00',
  equipment:[{equipment_id:'EQ-6',operating_state:'waiting',wait_reason:'hydraulic_supply_low'},
             {equipment_id:'EQ-7',operating_state:'waiting',wait_reason:'material_shortage'}],
  coils:[{quality_status:'hold'},{}]},
  [{equipment_id:'EQ-6',code:'RT-01'},{equipment_id:'EQ-7',code:'RT-02'}],
  [{open_items:[{status:'open'},{status:'needs_recheck'},{status:'done'}]}],
  [{eq:{equipment_id:'EQ-1',code:'HPU-01'},items:['경보 출구 압력 저하']}]);
assert.match(dash.line, /^운전 중 · 모의 \d\d:\d\d$/);   // 표시 시각은 기기 시간대 기준
assert.deepEqual(dash.waiting, ['RT-01']);
assert.equal(dash.held, 1); assert.equal(dash.openItems, 2);
assert.deepEqual(dash.faults, [{equipment_id:'EQ-1',code:'HPU-01',items:['경보 출구 압력 저하']}]);
console.log('PDA handover copy and MES import PASS');
