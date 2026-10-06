// 증상 선택지가 현재 MES 범위 이탈·카드 조건 순으로 올라오는지. node tests/pda_symptom_rank.cjs
const assert = require('node:assert/strict');
const { S, symptomsFor, alertOrder } = require('../shiftlink/mes/web/pda.js');
const eq = { equipment_id: 'EQ-0008', type: 'RT', signals: [
  { signal: 'rt_motor_current', name: '롤러 모터 전류', unit: 'A', min: 8, max: 16 }] };
S.eq = eq;
S.mes = { operating: 'running' };
S.cards = [
  { card_id: 'K-1017', equipment: 'RT', tacit_type: 'T1', symptom: '롤러에서 끽끽 소리' },
  { card_id: 'K-1208', equipment: 'RT', tacit_type: 'T2', mes_equipment_id: 'EQ-0008',
    symptom: '반송 중 rt_motor_current > 16 A', conditions: [{ signal: 'rt_motor_current_state', op: '==', value: 'high' }] },
  { card_id: 'K-1101', equipment: 'COMMON', tacit_type: 'T4', symptom: '다음 조에 넘겨야 한다' }];

S.observations = [{ signal: 'rt_motor_current', value: 12, unit: 'A', source: 'mes' }];   // 정상
assert.deepEqual(symptomsFor(eq).map((i) => i.score), [0, -3]);                       // T4 제외, 조건 불일치는 아래로
assert.equal(symptomsFor(eq)[0].text, '롤러에서 끽끽 소리');

S.observations = [{ signal: 'rt_motor_current', value: 20, unit: 'A', source: 'mes' }];   // 상한 초과
const top = symptomsFor(eq)[0];
assert.equal(top.text, '반송 중 rt_motor_current > 16 A');
assert.ok(top.score > 0 && top.why.includes('카드 조건 일치'));
// 정지 중 속도 0 은 '속도 낮음' 조건 일치로 치지 않는다
eq.signals.push({ signal: 'rt_speed', name: '반송 속도', unit: 'm_min', min: 20, max: 120, zeroStopped: true });
S.cards = [{ card_id: 'K-1207', equipment: 'RT', tacit_type: 'T2', mes_equipment_id: 'EQ-0008',
  symptom: '반송 지시가 있지만 물품이 이동하지 않는다.', conditions: [{ signal: 'rt_speed_state', op: '==', value: 'low' }] }];
S.observations = [{ signal: 'rt_speed', value: 0, unit: 'm_min', source: 'mes' }];
S.mes = { operating: 'stopped' };
assert.equal(symptomsFor(eq)[0].score, 0);
S.mes = { operating: 'running' };
assert.ok(symptomsFor(eq)[0].score > 0);
// '정상일 때' 조건 일치는 관련으로 올리지 않는다
S.cards = [{ card_id: 'K-1205', equipment: 'RT', tacit_type: 'T2', symptom: '이송 능력 저하',
  conditions: [{ signal: 'rt_speed_state', op: '==', value: 'normal' }] }];
S.observations = [{ signal: 'rt_speed', value: 50, unit: 'm_min', source: 'mes' }];
assert.equal(symptomsFor(eq)[0].score, 0);
// 고장 알림 순서: 선택 설비 → 심각도 → 먼저 난 경보 → 등록 순서
const E = (code) => ({ code });
const hpu = E('HPU-01'), cv = E('CV-01'), rt = E('RT-03'), gr = E('GR-02');
const order = (sel) => alertOrder([
  { eq: hpu, level: 2, at: '' }, { eq: cv, level: 1, at: '2026-01-01T00:00:05' },
  { eq: rt, level: 0, at: '2026-01-01T00:00:09' }, { eq: gr, level: 0, at: '2026-01-01T00:00:01' }], sel).map((f) => f.eq.code);
assert.deepEqual(order(null), ['GR-02', 'RT-03', 'CV-01', 'HPU-01']);
assert.deepEqual(order(hpu), ['HPU-01', 'GR-02', 'RT-03', 'CV-01']);
console.log('PDA symptom rank PASS');
