// 관계도 카드 맨 아래 줄에 가장 크게 벗어난 센서값이 나오는지. node tests/mes_card_signal.cjs
const assert = require('node:assert/strict');
const { buildOperatorModel, flowView } = require('../shiftlink/mes/web/operator.js');
const config = { route: ['EQ-1'], relations: [], branches: [], equipment: [{ equipment_id: 'EQ-1', code: 'GR-02', profile_id: 'gr', signals: [
  { signal: 'gr_vib_rms', name: '감속기 진동 RMS', unit: 'mm_s', normal_min: 0.5, normal_max: 2.8 },
  { signal: 'gr_brg_temp', name: '감속기 베어링 온도', unit: 'degC', normal_min: 30, normal_max: 62 },
  { signal: 'gr_rpm', name: '감속기 회전속도', unit: 'rpm', normal_min: 900, normal_max: 1100, zero_when_stopped: true }] }] };
const snap = (state, ms) => ({ line_id: 'LN', equipment: [{ equipment_id: 'EQ-1', operating_state: state, fault_level: 'critical' }], coils: [], active_alarms: [],
  measurements: ms.map(([signal, value, unit]) => ({ equipment_id: 'EQ-1', signal, value, unit, quality: 'good' })) });
const html = (s) => flowView(buildOperatorModel(s, config, null));
// 진동 +25% 와 온도 +3% 중 진동
assert.match(html(snap('running', [['gr_vib_rms', 3.5, 'mm_s'], ['gr_brg_temp', 64, 'degC']])), /node-signal[^>]*>감속기 진동 RMS 3\.5 ▲/);
// 정지 중 회전속도 0 은 이상이 아니다 → 기존 문구
assert.doesNotMatch(html(snap('stopped', [['gr_rpm', 0, 'rpm']])), /node-signal/);
console.log('MES card signal PASS');
