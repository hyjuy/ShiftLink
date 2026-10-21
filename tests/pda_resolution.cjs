const assert = require('node:assert/strict');
const {riskyAction, resolveError, sessionPayload, draftNotice} = require('../shiftlink/mes/web/pda.js');

// 위험 조치: 서버 SAFETY_WORDS와 같은 말이면 잠금 응답을 받는다
assert.equal(riskyAction('팬 차단기 트립 원인 확인 후 재투입'), true);
assert.equal(riskyAction('재가동 후 유온 추이 확인'), true);
assert.equal(riskyAction('쿨러 핀 에어 블로우 청소'), false);
assert.equal(riskyAction(undefined), false);


// 저장 전 검사: 본 것·부품·조치(효과 없음 제외)·원인·결과
const r = {sessionId: 'RS-1', symptom: '쿨러 팬이 멈춰 있음', componentId: 'cooling', components: [{component_id: 'cooling'}], steps: [{order: 1}],
  cause: '팬 차단기 트립', causeCustom: '', result: 'resolved'};
assert.equal(resolveError(r), '');
assert.match(resolveError({...r, sessionId: null}), /시작하지 못했습니다/);
assert.match(resolveError({...r, symptom: ' '}), /현장에서 본 것/);
assert.match(resolveError({...r, componentId: ''}), /부품/);
assert.equal(resolveError({...r, componentId: '', components: []}), '');   // 부품이 등록되지 않은 설비(PDP·CAU)는 묻지 않는다
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

// 한 일 칩: 끝낸 칩은 done(체크됨)으로 남고, 재가동은 MES 단계를 다 끝낸 뒤에만 누를 수 있다. 이전 현장 기록은 목록에 없다
const {actionChips} = require('../shiftlink/mes/web/pda.js');
const actions = [{text: '유면·냉각·밸브 점검', source: 'mes_recovery'}, {text: '냉각 성능 복구', source: 'mes_recovery'},
  {text: '재가동 (라인 복구 시작)', source: 'mes_restart'}, {text: '팬 차단기 올림', source: 'field_record'}];
let chips = actionChips({actions, steps: [{action: '유면·냉각·밸브 점검', order: 1}]});
assert.deepEqual(chips.map((c) => c.text), ['유면·냉각·밸브 점검', '냉각 성능 복구', '재가동 (라인 복구 시작)']);
assert.deepEqual(chips.map((c) => !!c.done), [true, false, false]);
assert.equal(chips.find((c) => c.text.startsWith('재가동')).disabled, true);
assert.equal(chips[1].tag, 'MES 단계');
assert.equal(chips.every((c) => c.mes), true);
chips = actionChips({actions, steps: [{action: '유면·냉각·밸브 점검'}, {action: '냉각 성능 복구'}]});
assert.deepEqual(chips.map((c) => [c.text, c.disabled]), [['유면·냉각·밸브 점검', false], ['냉각 성능 복구', false], ['재가동 (라인 복구 시작)', false]]);
// 카드 칩: T3 단계는 태그 '카드 · N단계', 문장 줄(S1…)은 태그 없이 카드 머리글 아래에. T1(check=false)은 체크 못 함. 서버 risky를 함께 넘긴다
const withCard = [{text: '모터 전원을 차단하고 재기동을 방지한다', source: 'card_step', card_id: 'K-1025', step_id: 'ST-01', n: 1, risky: true, tacit_type: 'T3', check: true},
  {text: '정비 전에는 압력을 뺀다', source: 'card_step', card_id: 'K-1006', step_id: 'S2', n: 2, risky: false, tacit_type: 'T5', check: true},
  {text: '이 소리면 베어링을 의심한다', source: 'card_step', card_id: 'K-1026', step_id: 'S1', n: 1, risky: false, tacit_type: 'T1', check: false}, ...actions];
chips = actionChips({actions: withCard, steps: [{action: '모터 전원을 차단하고 재기동을 방지한다', order: 1, card: {card_id: 'K-1025', step_id: 'ST-01'}}]});
assert.deepEqual([chips[0].tag, chips[0].card, !!chips[0].done, chips[0].type], ['K-1025 · 1단계', {card_id: 'K-1025', step_id: 'ST-01', risky: true}, true, 'T3']);
assert.equal(chips.some((c) => c.type === 'T1'), false);   // 판단 문장(T1)은 목록에서 뺀다
assert.deepEqual([chips[1].tag, chips[1].check], ['', true]);
assert.equal(chips[2].card, null);
console.log('PDA action chips PASS');

// 「모두 완료」 묶음: MES 단계·카드별, 남은 칩 둘 이상, 잠긴 칩(재가동)·끝낸 칩은 묶지 않는다
const {actionGroups} = require('../shiftlink/mes/web/pda.js');
const twoCard = [{text: 'A1', source: 'card_step', card_id: 'K-1', step_id: 'ST-01', n: 1}, {text: 'A2', source: 'card_step', card_id: 'K-1', step_id: 'ST-02', n: 2},
  {text: 'B1', source: 'card_step', card_id: 'K-2', step_id: 'ST-01', n: 1}, ...actions];
let groups = actionGroups(actionChips({actions: twoCard, steps: []}));
assert.deepEqual(groups.map((g) => [g.label, g.chips.map((c) => c.text)]),
  [['K-1', ['A1', 'A2']], ['MES 단계', ['유면·냉각·밸브 점검', '냉각 성능 복구']]]);
groups = actionGroups(actionChips({actions: twoCard, steps: [{action: '유면·냉각·밸브 점검'}, {action: 'A1', card: {card_id: 'K-1', step_id: 'ST-01'}}]}));
assert.deepEqual(groups, []);
console.log('PDA action groups PASS');

// 조치 기록 → 근무일지 기록(새 양식): 단계 결과는 「MES 센서:」, 잠금 응답은 안전 사항, 카드 후보 없음, 세션 ID로 업로드 보류
const {sessionRecord} = require('../shiftlink/mes/web/pda.js');
const res = {sessionId: 'RS-9', turn: {question: '작동유 온도가 너무 높아요', started: Date.parse('2026-10-20T04:59:00Z'), response: {query_id: 'Q-1'}},
  before: {alarms: ['AL-HYD-HOT']}, components: [{component_id: 'cooling', name: '냉각 계통'}], componentId: 'cooling',
  symptom: '', cause: '쿨러 튜브 스케일', causeCustom: '', phase: 'wrap', result: 'resolved', verdict: {text: 'MES 정상 복귀 확인'},
  steps: [{order: 1, action: '팬 차단기 재투입', lockout: '예', result_text: '센서값 변화 없음', at: '2026-10-20T14:01'},
    {order: 2, action: '유온·공급 정상 확인', lockout: null, result_text: '유압유 온도 78→47', mes_linked: 'recovery_action:verify', card: null, at: '2026-10-20T14:03'},
    {order: 3, action: '재가동 (라인 복구 시작)', lockout: '해당 없음', result_text: '센서값 변화 없음', mes_linked: 'recover', at: '2026-10-20T14:04'},
    {order: 4, action: 'K-1002 1단계', lockout: null, result_text: '센서값 변화 없음', card: {card_id: 'K-1002'}, at: ''}]};
let rec = sessionRecord(res, 'EQ-0001');
assert.equal(rec.type, '고장·정비');
assert.equal(rec.occurred_at, '2026-10-20T13:59');   // 새 양식 필수 — 질문 보낸 시각(KST)
assert.equal(rec.story, '작동유 온도가 너무 높아요');
assert.deepEqual(rec.causes, [{equipment: ['EQ-0001'], certainty: '추정', note: '쿨러 튜브 스케일'}]);
assert.deepEqual(rec.action_steps[1], {action: '유온·공급 정상 확인', observed_result: 'MES 센서: 유압유 온도 78→47', failed: false, performed_at: '2026-10-20T14:03'});
assert.deepEqual([rec.restart_performed, rec.restart_type, rec.outcome, rec.normal_run_status], [true, 'abnormal_stop_restart', 'resolved', 'unconfirmed']);
assert.equal(rec.safety_notes, '에너지 차단(잠금) · 1. 팬 차단기 재투입: 예\n에너지 차단(잠금) · 3. 재가동 (라인 복구 시작): 해당 없음');
assert.deepEqual([rec.candidate, rec.query_id, rec.source_session_id, rec.references, 'operating_context' in rec],
  [false, 'Q-1', 'RS-9', 'K-1002', false]);   // 부품 이름은 운전 조건·주의사항 칸(지식카드 근거)에 넣지 않는다
// 자동 입력: 조치 전 벗어났던 신호 → 원인의 관련 센서(측정값·시각), 미해결이면 남은 문제·다음 확인 내용. 해결이면 넣지 않는다
const {S: appState} = require('../shiftlink/mes/web/pda.js');
appState.equipment = [{equipment_id: 'EQ-0001', signals: [{signal: 'hpu_pressure', unit: 'bar'}]}];
const out = {...res, result: 'failed', verdict: {verdict: 'not_yet', text: '아직 이상 (유압 공급 압력 116.0)'},
  before: {alarms: [], simulated_at: '2026-10-21T02:00:00+00:00', out_of_range: [{signal: 'hpu_pressure', name: '유압 공급 압력', value: 116, state: 'low'}]}};
rec = sessionRecord(out, 'EQ-0001');
assert.deepEqual(rec.causes[0].sensor_ref, {equipment_id: 'EQ-0001', signal: 'hpu_pressure'});
assert.deepEqual(rec.causes[0].sensor_reading, {value: 116, unit: 'bar', observed_at: '2026-10-21T02:00:00+00:00'});
assert.equal(rec.remaining_issue, '조치 후 MES: 아직 이상 (유압 공급 압력 116.0)');
assert.equal(rec.next_check, '유압 공급 압력 정상 범위 회복 여부');
rec = sessionRecord({...out, result: 'resolved', verdict: {verdict: 'recovered', text: 'MES 정상 복귀 확인'}}, 'EQ-0001');
assert.deepEqual(['remaining_issue' in rec, 'next_check' in rec], [false, false]);
// 마무리 전에 넘기면 미해결, 단계가 없으면 빈 단계 한 줄
rec = sessionRecord({...res, phase: 'work', result: null, verdict: null, steps: [], before: {alarms: []}, turn: {question: 'q', response: {}}}, 'EQ-0001');
assert.deepEqual([rec.type, rec.outcome, rec.action_steps.length, rec.restart_performed, 'query_id' in rec, 'normal_run_evidence' in rec],
  ['이상증상', 'open', 1, false, false, false]);
console.log('PDA session record PASS');
