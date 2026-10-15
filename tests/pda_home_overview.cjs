const assert = require('node:assert/strict');
const {homeEquipmentSummary, homeWatch, S} = require('../shiftlink/mes/web/pda.js');
const equipment = [{equipment_id:'EQ-1'}, {equipment_id:'EQ-2'}];
const faults = [{eq:equipment[0]}, {eq:equipment[0]}, {eq:{equipment_id:'outside-config'}}];
assert.deepEqual(homeEquipmentSummary(equipment, faults, true), {total:2,normal:1,abnormal:1});
assert.deepEqual(homeEquipmentSummary(equipment, faults, false), {total:2,normal:null,abnormal:null}, 'unavailable data must not imply normal equipment');
assert.deepEqual(homeEquipmentSummary(equipment, [], true), {total:2,normal:2,abnormal:0});
assert.deepEqual(homeEquipmentSummary([], [], true), {total:0,normal:0,abnormal:0});
// 홈 '지켜볼 설비': 해결 후에도 반복된 증상 먼저, 그다음 최근 조치해 재발 기간 안인 증상(최근 것 먼저).
// 설비·증상당 한 줄, 3줄까지. 반복 중 '해결 후 재발'이 없는 증상(임시 조치 반복)은 관찰 중일 때만 나온다.
S.equipment = [{equipment_id:'EQ-0009', code:'CV-01'}, {equipment_id:'EQ-0001', code:'HPU-01'},
  {equipment_id:'EQ-0003', code:'CAU-01'}, {equipment_id:'EQ-0004', code:'GR-01'}];
const inc = (id, eq, al, label, outcome, recovered) => ({incident_id:id, equipment_id:eq, alarm_code:al, label, outcome, recovered_at:recovered});
const an = {now:'2026-10-15T07:00:00+09:00',
  repeats:[{equipment_id:'EQ-0009', alarm_code:'AL-DSB-QUE', label:'출측 코일 정체', count:8, resolved_recurred:7, incidents:['c1', 'c2']},
           {equipment_id:'EQ-0004', alarm_code:'AL-GR-HOT', label:'감속기 과열', count:5, resolved_recurred:0, incidents:['g1']}],
  incidents:[inc('c2', 'EQ-0009', 'AL-DSB-QUE', '출측 코일 정체', 'watching', '2026-10-14T06:00:00+09:00'),
             inc('h2', 'EQ-0001', 'AL-HYD-HOT', '유압유 과열', 'watching', '2026-10-12T05:00:00+09:00'),
             inc('a1', 'EQ-0003', 'AL-AIR-LOW', '공압 공급 저하', 'watching', '2026-10-11T10:00:00+09:00'),
             inc('h1', 'EQ-0001', 'AL-HYD-HOT', '유압유 과열', 'recurred', '2026-10-09T16:00:00+09:00'),
             inc('x1', 'EQ-0002', 'AL-PDP-TRIP', '배전 트립', 'watching', '2026-10-10T08:00:00+09:00'),
             inc('g1', 'EQ-0004', 'AL-GR-HOT', '감속기 과열', 'held', '2026-10-03T13:00:00+09:00')]};
const w = homeWatch(an);
assert.deepEqual(w.map((r) => [r.code, r.label, r.meta, r.unresolved]), [
  ['CV-01', '출측 코일 정체', '4주 8회', true],
  ['HPU-01', '유압유 과열', '3일 전 조치', false],
  ['CAU-01', '공압 공급 저하', '3일 전 조치', false]]);
assert.deepEqual(w[1].incidents, ['h2', 'h1']);   // 누르면 그 증상의 지난 조치 전부
assert.deepEqual(homeWatch({...an, repeats:[], incidents:[]}), []);
// 해결 후 재발이 있었어도 마지막 조치가 재발 기간을 넘겨 버텼으면(재발 없음) 지켜볼 대상이 아니다 — 예: PDP-01을 K-1317로 고침
const fixed = homeWatch({...an, repeats:[...an.repeats, {equipment_id:'EQ-0002', alarm_code:'AL-PDP-TRIP', label:'배전 트립',
  count:4, resolved_recurred:3, incidents:['p1']}], incidents:[inc('p1', 'EQ-0002', 'AL-PDP-TRIP', '배전 트립', 'held', '2026-10-02T10:00:00+09:00'),
  ...an.incidents.filter((i) => i.equipment_id !== 'EQ-0002')]});
assert.ok(!fixed.some((r) => r.code === 'EQ-0002' || r.label === '배전 트립'));
console.log('PDA live home overview PASS');
// 대시보드 정지 손실 보기: 생산·손실·설비별 %는 모두 계획 생산량 대비, 색 종류
const {lossView} = require('../shiftlink/mes/web/pda.js');
S.equipment = [{equipment_id:'EQ-0001', code:'HPU-01'}, {equipment_id:'EQ-0007', code:'RT-02'}];
const lv = lossView({planned:1800, lost:51, produced:1749}, [
  {equipment_id:'EQ-0001', coils:17, stop_min:97, halts_line:true}, {equipment_id:'EQ-0007', coils:9, stop_min:51, halts_line:true}]);
assert.equal(lv.lostPct, 2.8);
assert.deepEqual(lv.rows.map((r) => [r.kind, r.planPct]), [['hpu', 0.9], ['rt', 0.5]]);   // 모두 계획(1,800개) 대비
assert.equal(lv.producedPct, 97.2);
assert.deepEqual(lossView(null, []).rows, []);
assert.equal(lossView({planned:1800, lost:0, produced:1800}, []).lostPct, 0);
console.log('PDA loss view PASS');
// 원형 조각은 6개까지: 손실 상위 5대는 설비 색, 나머지는 회색 '기타' 한 조각 — 설비 줄 표지 색도 같은 규칙
S.equipment = ['HPU-01', 'RT-02', 'CV-01', 'CAU-01', 'GR-02', 'RT-03', 'PDP-01'].map((code, i) => ({equipment_id: 'E' + i, code}));
const many = lossView({planned: 1800, lost: 60, produced: 1740},
  [17, 9, 7, 7, 6, 4, 0].map((coils, i) => ({equipment_id: 'E' + i, coils, stop_min: 1, halts_line: true})));
assert.deepEqual(many.slices.map((s) => [s.equipment_id, s.coils, s.color]),
  [['E0', 17, 'var(--hpu)'], ['E1', 9, 'var(--rt)'], ['E2', 7, 'var(--cv)'], ['E3', 7, 'var(--cau)'], ['E4', 6, 'var(--gr)'],
   [null, 4, 'var(--tx-3)']]);
assert.deepEqual(many.rows.map((r) => r.color).slice(4), ['var(--gr)', 'var(--tx-3)', 'var(--tx-3)']);
console.log('PDA loss ring slices PASS');
// 손실 도넛: 12시부터 시계 방향, 라벨은 조각 가운데 바깥 — 오른쪽 절반은 왼쪽 정렬, 같은 쪽 라벨은 16px 이상 떨어진다
const {lossDonut} = require('../shiftlink/mes/web/pda.js');
const arcs = lossDonut([{equipment_id: 'A', coils: 17, color: 'x'}, {equipment_id: 'B', coils: 9, color: 'x'},
  {equipment_id: 'C', coils: 7, color: 'x'}, {equipment_id: 'D', coils: 7, color: 'x'}, {equipment_id: 'E', coils: 6, color: 'x'},
  {equipment_id: null, coils: 4, color: 'x'}]);
assert.equal(arcs.length, 6);
assert.equal(arcs[0].anchor, 'start');                 // 첫 조각(0~122°) 가운데는 오른쪽
assert.ok(arcs[0].d.startsWith('M264.0 43.0 A'));     // 12시(위)에서 시작
assert.equal(arcs[5].anchor, 'end');                   // 마지막 조각(331~360°)은 왼쪽
['start', 'end'].forEach((side) => {
  const ys = arcs.filter((a) => a.anchor === side).map((a) => a.ly).sort((p, q) => p - q);
  ys.forEach((y, i) => { if (i) assert.ok(y - ys[i - 1] >= 16, side + ' labels overlap'); });
});
assert.ok(lossDonut([{equipment_id: 'A', coils: 5, color: 'x'}])[0].d.includes(' A52 52 0 1 1 264 147'));   // 한 조각 = 원
assert.deepEqual(lossDonut([]), []);
console.log('PDA loss donut PASS');
// 생산 링: 생산 비율 다음(계획의 97.2% 지점)부터 12시까지 손실 조각을 잇는다 — 마지막 조각은 12시(위)에서 끝난다
const {madeRingArcs} = require('../shiftlink/mes/web/pda.js');
const made = madeRingArcs(1800, 1749, [{coils: 17, color: 'a'}, {coils: 34, color: 'b'}]);
assert.equal(made.length, 2);
assert.ok(made[1].d.endsWith(' 66.0 43.0'));   // 끝점 = 생산 링 12시(cx 66, cy 95 − r 52, 손실 도넛과 같은 크기)
console.log('PDA made ring PASS');
// 링 안 손실 개수: 조각 호가 18px 이상이면 링 안(조각 가운데, 반지름 r), 아니면 바깥 라벨 옆
const thin = lossDonut([{equipment_id: 'A', coils: 60, color: 'x'}, {equipment_id: 'B', coils: 1, color: 'x'}]);
assert.deepEqual(thin.map((a) => a.inside), [true, false]);
assert.equal(Math.round(Math.hypot(thin[0].nx - 264, thin[0].ny - 95)), 52);   // 링 굵기 가운데
console.log('PDA loss donut numbers PASS');
