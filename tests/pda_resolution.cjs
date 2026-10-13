const assert = require('node:assert/strict');
const {evidenceSummary, resolutionError, resolutionPayload, draftNotice} = require('../shiftlink/mes/web/pda.js');
const form = {symptom:'작동유 온도 경보', actions:[{action:'냉각기 팬 필터 청소', result:' 팬 풍량 회복 '}, {action:'', result:''}], result:'resolved', verification:'온도 정상'};
// 저장 전 검사: 서버와 같은 규칙(증상 필수, 조치 1개 이상, 해결이면 근거 필수)
assert.equal(resolutionError(form), '');
assert.equal(resolutionError({...form, symptom:'  '}), '현장에서 본 것을 적어 주세요.');
assert.equal(resolutionError({...form, actions:[{action:'', result:''}, {action:'  ', result:'x'}]}), '한 일을 한 가지 이상 적어 주세요.');
assert.equal(resolutionError({...form, verification:''}), '해결됐다고 본 근거를 적어 주세요.');
assert.equal(resolutionError({...form, result:'temporary', verification:''}), '');
assert.equal(resolutionError({...form, result:'failed', actions:[], verification:''}), '');
// 보내는 내용: 빈 조치는 빼고, 조치별 결과는 다듬어 함께 보내고, 질의 원문과 그 질의의 MES 근거를 그대로 붙인다
const evidence = {equipment_id:'EQ-0001', simulated_at:'2026-10-13T08:59:00+09:00',
  measurements:[{signal:'hpu_oil_temp', value:66.5, unit:'degC', used_for_conditions:true},
                {signal:'hpu_flow', value:1, unit:'lpm', used_for_conditions:false}]};
const turn = {question:'작동유 온도가 높아요', response:{evidence}};
const payload = resolutionPayload(form, turn);
assert.deepEqual(payload.actions, [{action:'냉각기 팬 필터 청소', result:'팬 풍량 회복'}]);
assert.equal(payload.question, '작동유 온도가 높아요');
assert.equal(payload.result, 'resolved');
assert.equal(payload.evidence, evidence);
assert.equal(resolutionPayload(form, {question:'q', response:{}}).evidence, null);
// 근거 한 줄: 조건에 쓴 측정값만 보인다
assert.match(evidenceSummary(evidence), /^MES 근거\(질의 시점 .+\): hpu_oil_temp 66\.5 /);
assert.doesNotMatch(evidenceSummary(evidence), /hpu_flow/);
assert.match(evidenceSummary(null), /MES 근거 없음/);
// 인계 응답의 draft → 확인 문구 (카드 내용은 응답에 없다)
assert.match(draftNotice({created:true, reason:'pending_review'}), /검수를 기다립니다 — 검수 전에는 검색에 나오지 않습니다$/);
assert.match(draftNotice({created:false, reason:'attempt_only'}), /카드 초안은 만들지 않습니다/);
assert.match(draftNotice({created:false, reason:'already_exists'}), /이미 카드 초안이 만들어져/);
assert.match(draftNotice({created:false, reason:'supporting'}), /근거로 더했습니다/);
assert.match(draftNotice({created:false, reason:'contradicting'}), /효과 없었던 기록/);
assert.equal(draftNotice(undefined), '');
console.log('PDA resolution record PASS');
