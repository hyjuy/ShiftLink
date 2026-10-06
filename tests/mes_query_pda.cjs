const assert = require('node:assert/strict');
const { queryApiPayload, responseCards, outboxLabels, refreshOutbox, outboxItemView } = require('../shiftlink/mes/web/pda.js');
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
refreshOutbox(async () => { throw new Error('down'); }).then((labels) => {
  assert.deepEqual(labels, {pending:'', conflict:''});
  console.log('MES query PDA contract PASS');
});
