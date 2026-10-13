const assert = require('node:assert/strict');
const {riskyAction, mesSummary, resolveError, sessionPayload, draftNotice} = require('../shiftlink/mes/web/pda.js');

// 위험 조치: 서버 SAFETY_WORDS와 같은 말이면 잠금 응답을 받는다
assert.equal(riskyAction('팬 차단기 트립 원인 확인 후 재투입'), true);
assert.equal(riskyAction('재가동 후 유온 추이 확인'), true);
assert.equal(riskyAction('쿨러 핀 에어 블로우 청소'), false);
assert.equal(riskyAction(undefined), false);

// MES 요약 한 줄: 첫 이상 신호 + 외 N + 경보
const before = {simulated_at: '2026-10-13T08:59:00+00:00', alarms: ['AL-HYD-HOT'],
  out_of_range: [{signal: 'hpu_oil_temp', name: '유압유 온도', value: 78, state: 'high'},
                 {signal: 'hpu_cooler_oil_in_temp', name: '냉각기 오일 입구 온도', value: 78, state: 'high'}]};
assert.match(mesSummary('조치 전', before), /^조치 전 MES 자동 기록 · .+ · 유압유 온도 78 ▲ 외 1 · 경보 AL-HYD-HOT$/);
assert.match(mesSummary('조치 후', {simulated_at: null, out_of_range: [], alarms: []}), /이상 신호 없음 · 경보 없음$/);
assert.match(mesSummary('조치 전', null), /기록하고 있습니다/);

// 저장 전 검사: 본 것·부품·조치(효과 없음 제외)·원인·결과
const r = {sessionId: 'RS-1', symptom: '쿨러 팬이 멈춰 있음', componentId: 'cooling', steps: [{order: 1}],
  cause: '팬 차단기 트립', causeCustom: '', result: 'resolved'};
assert.equal(resolveError(r), '');
assert.match(resolveError({...r, sessionId: null}), /시작하지 못했습니다/);
assert.match(resolveError({...r, symptom: ' '}), /현장에서 본 것/);
assert.match(resolveError({...r, componentId: ''}), /부품/);
assert.match(resolveError({...r, steps: []}), /조치를 하나 이상/);
assert.equal(resolveError({...r, steps: [], result: 'failed'}), '');
assert.match(resolveError({...r, cause: '', causeCustom: ' '}), /원인 모름/);
assert.equal(resolveError({...r, cause: '', causeCustom: '쿨러 팬 모터 소손'}), '');

// 보내는 내용: 조치·센서값은 서버가 세션에서 채우므로 작업자 입력만
assert.deepEqual(sessionPayload({...r, symptom: ' 쿨러 팬이 멈춰 있음 '}),
  {session_id: 'RS-1', symptom: '쿨러 팬이 멈춰 있음', cause: '팬 차단기 트립', component_id: 'cooling', result: 'resolved'});
assert.equal(sessionPayload({...r, causeCustom: ' 쿨러 팬 모터 소손 '}).cause, '쿨러 팬 모터 소손');

// 인계 응답의 draft → 확인 문구 (카드 내용은 응답에 없다)
assert.match(draftNotice({created: true, reason: 'pending_review', mes_verdict: 'recovered'}), /관리자 검수를 기다립니다.* · MES 정상 복귀 확인$/);
assert.match(draftNotice({created: false, reason: 'supporting', mes_verdict: 'unconfirmed'}), /확인 불가\(복구 기록 없음\)/);
assert.match(draftNotice({created: false, reason: 'contradicting', mes_verdict: 'not_yet'}), /MES는 아직 이상/);
assert.match(draftNotice({created: false, reason: 'supporting', mes_recovered: true}), /MES 정상 복귀 확인$/);  // 예전 응답
assert.match(draftNotice({created: false, reason: 'already_exists'}), /이미 카드 초안이/);
assert.equal(draftNotice(undefined), '');
console.log('PDA resolution session PASS');

// 한 일 칩: 끝낸 MES 단계는 숨기고, 재가동은 MES 단계를 다 끝낸 뒤에만 누를 수 있다
const {actionChips} = require('../shiftlink/mes/web/pda.js');
const actions = [{text: '유면·냉각·밸브 점검', source: 'mes_recovery'}, {text: '냉각 성능 복구', source: 'mes_recovery'},
  {text: '재가동 (라인 복구 시작)', source: 'mes_restart'}, {text: '팬 차단기 올림', source: 'field_record'}];
let chips = actionChips({actions, steps: [{action: '유면·냉각·밸브 점검'}]});
assert.deepEqual(chips.map((c) => c.text), ['냉각 성능 복구', '재가동 (라인 복구 시작)', '팬 차단기 올림']);
assert.equal(chips.find((c) => c.text.startsWith('재가동')).disabled, true);
assert.equal(chips[0].tag, 'MES 단계');
chips = actionChips({actions, steps: [{action: '유면·냉각·밸브 점검'}, {action: '냉각 성능 복구'}, {action: '팬 차단기 올림'}]});
assert.deepEqual(chips.map((c) => [c.text, c.disabled]), [['재가동 (라인 복구 시작)', false], ['팬 차단기 올림', false]]);
console.log('PDA action chips PASS');
