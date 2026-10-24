const assert = require('node:assert/strict');
const {S, answerBody} = require('../shiftlink/mes/web/pda.js');
const previousDocument = global.document, previousEquipment = S.eq;
function element(tag) {
  return {tag, children: [], classList: {add() {}}, appendChild(child) {this.children.push(child);return child;}, addEventListener() {}};
}
global.document = {createElement: element};
try {
  S.eq = {equipment_id: 'EQ-0004'};
  const turn = {eqId:'EQ-0004', question:'진동 이상을 직접 점검하고 싶어요',
    response:{no_knowledge:true,cited_card_ids:[],answer:''}, ranked:{actions:[],excluded:[]}};
  const start = body => body.children.find(child=>child.tag==='button'&&child.textContent==='조치 시작');
  assert.ok(start(answerBody(turn)), 'no-card answer must allow direct action recording for current equipment');
  assert.equal(start(answerBody({...turn,eqId:'EQ-0001'})),undefined, 'do not record a different equipment answer');
  assert.equal(start(answerBody({...turn,response:{...turn.response,smalltalk:true}})),undefined);
  S.eq=null;
  assert.equal(start(answerBody(turn)),undefined, 'an equipment selection is required');
  S.eq=previousEquipment;
  assert.ok(start(answerBody({...turn,response:{...turn.response,cited_card_ids:['K-1002']}})), 'existing cited-card path remains available');
  console.log('PDA cardless direct-action entry PASS');
} finally {
  S.eq=previousEquipment;
  if (previousDocument===undefined) delete global.document; else global.document=previousDocument;
}
