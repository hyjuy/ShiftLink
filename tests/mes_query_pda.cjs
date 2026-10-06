const assert = require('node:assert/strict');
const { queryApiPayload, responseCards, scanTarget, staleResponse, outboxLabels, refreshOutbox, outboxItemView, releaseContext, alertTarget, failScan, symptomsFor, S } = require('../shiftlink/mes/web/pda.js');
assert.deepEqual(queryApiPayload('q', {source:'camera_scan', scanId:'SC-1', eq:{equipment_id:'EQ-1'}}),
  {question:'q', scan_id:'SC-1'});
assert.deepEqual(queryApiPayload('q', {source:'manual_selection', eq:{equipment_id:'EQ-2'}}),
  {question:'q', equipment_id:'EQ-2'});
const card = {card_id:'K-1'};
const result = responseCards({cited_card_ids:['K-1'], safety_notices:[{card_id:'K-S', safety_basis:'stop'}],
  unverified_card_ids:[], review_queue:false}, [card]);
assert.equal(result.actions[0].card, card);
assert.equal(result.safety[0].card_id, 'K-S');
assert.equal(responseCards({cited_card_ids:['K-1'], review_queue:true, safety_notices:[]}, [card]).actions.length, 0);
// 로컬 카드 없는 공지: card_id 유지·missing 표시, undefined 없이.
assert.equal(result.safety[0].missing, true);
assert.equal(result.safety[0].safety_basis, 'stop');
// B4·D1: 안전 카드는 조치·제외에서 빠지고 원본 title·know_how 유지, stop_conditions 는 별도.
const s1 = {card_id:'K-S1', title:'원본 제목', know_how:'원본 본문', safety_basis:'조문 1', safety_flag:true};
const s2 = {card_id:'K-S2', title:'공지 없는 안전 카드', safety_flag:true};
const r2 = responseCards({cited_card_ids:['K-1', 'K-S1', 'K-S2'], unverified_card_ids:['K-S1'], review_queue:false,
  safety_notices:[{card_id:'K-S1', safety_basis:'x', stop_conditions:['압력 상승 시 멈춤']}]}, [card, s1, s2]);
assert.deepEqual(r2.actions.map((x) => x.card.card_id), ['K-1']);
assert.equal(r2.excluded.length, 0);
assert.deepEqual(r2.safety.map((x) => x.card_id), ['K-S1', 'K-S2']);
assert.equal(r2.safety[0].title, '원본 제목');
assert.equal(r2.safety[0].know_how, '원본 본문');
assert.equal(r2.safety[0].safety_basis, '조문 1');
assert.deepEqual(r2.safety[0].stop_conditions, ['압력 상승 시 멈춤']);
// B3·D2: 구성에 없는 code는 같은 유형 설비로 대체하지 않는다.
const eqs = [{equipment_id:'EQ-1', code:'RT-01', type:'RT'}];
assert.equal(scanTarget({code:'RT-03', class:'RT'}, eqs), null);
assert.equal(scanTarget({code:'RT-01', class:'RT'}, eqs), eqs[0]);
assert.equal(scanTarget({class:'RT'}, eqs), null);
// B1: 질의를 보낸 뒤 설비가 바뀌면 응답을 버린다.
assert.equal(staleResponse('EQ-1', {waitAbort:false, eq:{equipment_id:'EQ-1'}}), false);
assert.equal(staleResponse('EQ-1', {waitAbort:false, eq:{equipment_id:'EQ-2'}}), true);
assert.equal(staleResponse('EQ-1', {waitAbort:true, eq:{equipment_id:'EQ-1'}}), true);
assert.equal(staleResponse('EQ-1', {waitAbort:false, eq:null}), true);
// C1·C2: 서버 인용 카드에 로컬 판정(rankCards)을 card_id로 붙인다. 판정 없으면 지어내지 않는다.
const kA = {card_id:'K-A'}, kB = {card_id:'K-B'}, kC = {card_id:'K-C'}, kU = {card_id:'K-U'};
const local = {actions:[{card:kA, excluded:false, conds:[{state:'match', text:'일치'}], why:'조건 일치 · HPU 설비 카드'}],
  excluded:[{card:kB, excluded:true, conds:[{state:'miss', text:'불일치'}], why:'HPU 설비 카드'}]};
const r3 = responseCards({cited_card_ids:['K-A', 'K-B', 'K-C'], unverified_card_ids:['K-U'], safety_notices:[], review_queue:false},
  [kA, kB, kC, kU], local);
assert.deepEqual(r3.actions.map((x) => x.card.card_id), ['K-A', 'K-C']);
assert.equal(r3.actions[0].why, 'Jetson 인용 · 조건 일치 · HPU 설비 카드');
assert.equal(r3.actions[0].conds[0].state, 'match');
assert.equal(r3.actions[1].why, 'Jetson 인용 · 로컬 조건 판정 없음');
// 실제 불일치만 miss. 서버 unverified 는 미평가 — 불일치로 단정하지 않는다. 둘 다 숨기지 않는다.
assert.deepEqual(r3.excluded.map((x) => [x.card.card_id, x.miss]), [['K-B', true], ['K-U', false]]);
assert.ok(r3.excluded[1].why.startsWith('미평가'));
assert.ok(!/불일치/.test(r3.excluded[1].why));
// B3: 재스캔 실패 시 이전 확정 해제 · 알림 확인 대상은 탭 시점 equipment_id로 고정.
const st = {eq:{equipment_id:'EQ-1'}, source:'camera_scan', scanId:'SC-1', tries:[{}], observations:[{}]};
releaseContext(st);
assert.equal(st.eq, null); assert.equal(st.source, null); assert.equal(st.scanId, null);
assert.equal(st.tries.length + st.observations.length, 0);
const eqs2 = [{equipment_id:'EQ-1', code:'HPU-01'}, {equipment_id:'EQ-2', code:'GR-01'}];
assert.equal(alertTarget('EQ-2', eqs2.slice().reverse()).code, 'GR-01');
assert.equal(alertTarget('EQ-9', eqs2), null);
assert.deepEqual(outboxLabels({handover:{pending:2, uploaded:1, conflict:0}}),
  {pending:'업로드 대기 2건', conflict:''});
assert.deepEqual(outboxLabels({handover:{pending:0, uploaded:0, conflict:1}}),
  {pending:'', conflict:'확인 필요 1건'});
assert.deepEqual(outboxLabels(null), {pending:'', conflict:''});
const item = outboxItemView({handover_id:'HO-1', created_at:'2026-10-06T15:00:00+09:00', memo_text:'유압 점검 필요',
  equipment_id:'EQ-1', required_context:{recipient_role:'정비', timing:''}, attempts:[{}], observations:[]},
  [{equipment_id:'EQ-1', code:'HPU-01'}]);
assert.equal(item.memo, '유압 점검 필요');
assert.ok(item.kid.startsWith('HO-1 · '));
assert.deepEqual(item.lines, ['설비 HPU-01', '받는 사람 정비', '시도 1건 · 관찰 0건']);
assert.equal(outboxItemView({handover_id:'HO-2', created_at:'x', memo_text:'m'}, []).lines[0], '설비 지정 안 함');
// B1(라운드 10): 서버 안전 공지를 현재 설비와 대조 — 일치는 지침, 불일치는 경고만(본문·멈춤 조건 없음), missing은 유지.
const eqH = {equipment_id:'EQ-1', code:'HPU-01', type:'HPU'};
const sH = {card_id:'K-SH', equipment:'HPU', title:'유압 안전', know_how:'잔압 제거', safety_basis:'조문', safety_flag:true};
const sC = {card_id:'K-SC', equipment:'CV', title:'벨트 안전', know_how:'벨트 잠금', safety_basis:'조문', safety_flag:true};
const r5 = responseCards({cited_card_ids:['K-SC'], review_queue:false, safety_notices:[
  {card_id:'K-SH', stop_conditions:['압력 상승']}, {card_id:'K-SC', stop_conditions:['벨트 회전']}, {card_id:'K-X'}]},
  [sH, sC], null, eqH);
assert.deepEqual(r5.safety.map((x) => x.card_id), ['K-SH', 'K-SC', 'K-X']);
assert.equal(r5.safety[0].know_how, '잔압 제거'); assert.ok(!r5.safety[0].mismatch);
assert.deepEqual(r5.safety[1], {card_id:'K-SC', mismatch:true, eqCode:'HPU-01', stop_conditions:[]});
assert.equal(r5.safety[2].missing, true);
assert.equal(r5.actions.length, 0);
// B4(라운드 10): safety_flag 카드는 유형과 무관하게 증상 선택지에서 빠진다(T6 K-1215 등).
const eqC = {equipment_id:'EQ-2', code:'CV-01', type:'CV', signals:[]};
S.eq = eqC; S.observations = []; S.mes = {operating:'running'};
S.cards = [{card_id:'K-1215', equipment:'CV', tacit_type:'T6', safety_flag:true, symptom:'끼임 비상정지 후 재가동'},
  {card_id:'K-1011', equipment:'CV', tacit_type:'T1', symptom:'아이들러 마찰음'}];
assert.deepEqual(symptomsFor(eqC).map((i) => i.text), ['아이들러 마찰음']);
// B3(라운드 10): 스캔 시간 초과·Jetson 연결 실패도 이전 확정을 해제한다.
global.document = {getElementById: () => ({classList:{remove(){}}, style:{}})};
S.eq = eqC; S.source = 'camera_scan'; S.scanId = 'SC-1'; S.screen = 'home';
failScan(S.scanRun, '인식 안 됨 — 직접 선택');
assert.equal(S.eq, null); assert.equal(S.scanId, null);
delete global.document;
refreshOutbox(async () => { throw new Error('down'); }).then((labels) => {
  assert.deepEqual(labels, {pending:'', conflict:''});
  console.log('MES query PDA contract PASS');
});
