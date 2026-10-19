// 증상 질의 대화(10/8 최재영 요청). node tests/pda_chat.cjs
// 지키는 것: 메시지 하나 = /api/query 하나, 이전 대화를 보내지 않음 · 안전 수칙은 상단 바에서 접어서 표시 · 인계 초안.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Element {
  constructor() { this.children = []; this.parts = {}; this.textContent = ''; this.value = ''; this.hidden = false;
    this.className = ''; this.classList = {remove(){}, toggle(){}, add(){}}; this.style = {}; }
  set innerHTML(v) { this.children = []; this.parts = {}; }
  appendChild(c) { this.children.push(c); }
  querySelector(sel) { return this.parts[sel] ||= new Element(); }
  querySelectorAll(sel) { return [this.querySelector(sel + '1'), this.querySelector(sel + '2')]; }
  addEventListener(name, fn) { (this.events ||= {})[name] = fn; }
  setAttribute(name, value) { this[name] = value; }
  text() { return [this.textContent, ...this.children.map((x) => x.text()), ...Object.values(this.parts).map((x) => x.text())].join(' '); }
}
const nodes = {};
const context = vm.createContext({URLSearchParams, setInterval, clearInterval, setTimeout, Date, JSON, console});
vm.runInContext(fs.readFileSync(require.resolve('../shiftlink/mes/web/pda.js'), 'utf8'), context);
context.document = {getElementById: (id) => nodes[id] ||= new Element(), createElement: () => new Element()};
const run = (code) => vm.runInContext(code, context);

run(`S.eq = {equipment_id:'EQ-0001', code:'HPU-01', type:'HPU', group:'유압', signals:[
  {signal:'hpu_pressure', name:'유압 압력', unit:'bar', min:145, max:165, semantics:{}}]};
  S.source = 'manual_selection'; S.screen = 'chat';
  S.cards = [{card_id:'K-1003', equipment:'HPU', safety_flag:true, tacit_type:'T5', title:'과압 보호', know_how:'릴리프', conditions:[]},
    {card_id:'K-1001', equipment:'HPU', tacit_type:'T3', title:'무압', know_how:'확인', symptom:'펌프 출구 압력 없음'}];`);

// 1. 평소(정상 가동·범위 안)에는 접고, 정지·이상·범위 이탈·안전 카드 조건 일치·MES 못 읽음이면 펼친다.
const normal = {operating:'running', fault:'normal', alarms:[], diagnoses:[]};
const ok = [{signal:'hpu_pressure', value:155, unit:'bar', source:'mes'}];
context.normal = normal; context.ok = ok;
assert.equal(run('safetyAlert(normal, ok, S.cards.slice(0,1))'), false);
assert.equal(run(`safetyAlert({...normal, operating:'stopped'}, ok, [])`), true);
assert.equal(run(`safetyAlert({...normal, fault:'warning'}, ok, [])`), true);
assert.equal(run(`safetyAlert({...normal, alarms:['AL-HYD-HOT']}, ok, [])`), true);
assert.equal(run(`safetyAlert(normal, [{signal:'hpu_pressure', value:100, unit:'bar', source:'mes'}], [])`), true);
assert.equal(run('safetyAlert(null, ok, [])'), true, 'MES를 못 읽으면 정상으로 가정하지 않는다');
assert.equal(run(`safetyAlert(normal, ok, [{conditions:[{signal:'hpu_pressure', op:'>=', value:150}]}])`), true);
assert.equal(run(`safetyAlert(normal, ok, [{conditions:[{signal:'hpu_pressure_state', op:'==', value:'normal'}]}])`), false,
  "'정상일 때' 조건 일치는 이상 신호가 아니다");

// 2. 메시지 하나 = /api/query 하나. 두 번째 질문에도 이전 질문·답을 싣지 않는다.
const sent = [];
context.api = async (path, init) => {
  sent.push({path, body: JSON.parse(init.body)});
  const n = sent.length;
  return {ok: true, json: async () => n === 1
    ? {answer:'릴리프 밸브를 확인합니다', cited_card_ids:['K-1001'], safety_notices:[{card_id:'K-1003', stop_conditions:[]}], review_queue:false, no_knowledge:false}
    : {answer:'', cited_card_ids:[], safety_notices:[], review_queue:false, no_knowledge:true}};
};
(async () => {
  await run(`sendChat('펌프 출구 압력 없음', '펌프 출구 압력 표시 없음')`);
  nodes.question.value = '그럼 다음은?';
  await run('sendChat(currentQuestion())');
  assert.deepEqual(sent.map((x) => x.path), ['/api/query', '/api/query']);
  assert.deepEqual(sent[0].body, {question:'펌프 출구 압력 없음', equipment_id:'EQ-0001'});
  assert.deepEqual(sent[1].body, {question:'그럼 다음은?', equipment_id:'EQ-0001'}, '이전 대화를 모델에 넘기지 않는다');
  assert.equal(nodes.question.value, '', '직접 쓴 질문은 보낸 뒤 비운다');

  // 3. 안전 카드는 상단 바에만, 답 말풍선에는 해결 답변과 근거만 표시한다.
  const first = run('answerBody(S.chat[0])').text();
  assert.doesNotMatch(first, /K-1003|안전수칙 자세히/);
  assert.match(first, /릴리프 밸브를 확인합니다/);
  assert.match(nodes.askSafety.text(), /K-1003/);
  assert.equal(nodes.askSafety.children[0].open, false, '이상·정지 상태에도 최초에는 접는다');
  nodes.askSafety.children[0].open = true;
  nodes.askSafety.children[0].events.toggle();
  run("S.chat[0].ranked.safety[0].stop_conditions=['압력 해제 전 작업 중지'];renderAskSafety();");
  assert.equal(nodes.askSafety.children[0].open, true, '안전 정보 갱신 후에도 펼침 상태 유지');
  assert.match(nodes.askSafety.text(), /압력 해제 전 작업 중지/);
  nodes.askSafety.children[0].open = false;nodes.askSafety.children[0].events.toggle();
  run("S.chat.push({status:'done',ranked:{safety:[{card_id:'NEW',title:'새 수칙',know_how:'차단 확인',stop_conditions:[]}]}});renderAskSafety();");
  assert.equal(nodes.askSafety.children[0].open, false);
  assert.match(nodes.askSafety.text(), /새 수칙/);
  run('S.chat.pop();');
  assert.match(first, /참고 매뉴얼 보기 K-1001/);
  assert.match(run('answerBody(S.chat[1])').text(), /해당 지식 없음/);
  assert.equal(run('S.chat.length'), 2);

  // 4. 인계 초안은 마지막 질문과 답. 메모 칸 길이를 넘지 않는다.
  assert.equal(run('chatMemo(S.chat[0])'), '질문: 펌프 출구 압력 없음\n답: 릴리프 밸브를 확인합니다\n근거 카드: K-1001');
  assert.match(run('chatMemo(lastAnswer())'), /답: 해당 지식 없음/);
  assert.equal(run(`chatMemo({question:'q', response:{answer:'x'.repeat(5000)}, ranked:null})`).length, 4000);

  // 5. 답을 기다리는 동안 두 번째 질문은 보내지 않는다.
  context.api = () => new Promise(() => {});
  run(`sendChat('a')`); run(`sendChat('b')`);
  assert.equal(run(`S.chat.filter((t) => t.status === 'pending').length`), 1);
  console.log('PDA chat: one message one query, safety fold, handover draft PASS');
  process.exit(0);
})().catch((err) => { console.error(err); process.exit(1); });
