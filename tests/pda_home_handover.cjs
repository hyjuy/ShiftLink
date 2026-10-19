const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Element {
  constructor() { this.children = []; this.textContent = ''; this.classList = {toggle(){}}; this.events = {}; }
  append(...children) { this.children.push(...children); }
  appendChild(child) { this.children.push(child); return child; }
  replaceChildren(...children) { this.children = children; this.textContent = ''; }
  setAttribute(name, value) { this[name] = value; }
  addEventListener(name, handler) { this.events[name] = handler; }
  text() { return [this.textContent, ...this.children.map(child => child.text())].join(' '); }
}
const nodes = {};
const context = vm.createContext({URLSearchParams});
vm.runInContext(fs.readFileSync(require.resolve('../shiftlink/mes/web/pda.js'), 'utf8'), context);
context.document = {getElementById:id => nodes[id] ||= new Element(), createElement:() => new Element()};
vm.runInContext(`
  renderHomeMade = () => {};
  openDutyDetail = (...args) => { globalThis.opened = args; };
  S.equipment = [{equipment_id:'EQ-1', code:'HPU-01'}];
  S.handovers = [{handover_id:'legacy', memo_text:'HPU-01 순회 점검', shift_date:'2026-10-15', author_name:'이전 근무자'}];
  S.savedHandovers = [
    {handover_id:'first', kind:'work_log', created_at:'2026-10-16T12:00:00+09:00',
      required_context:{start_at:'2026-10-16T08:00',author:'첫 근무자'}, equipment_ids:['EQ-1'],
      work_report:{records:[{equipment:['EQ-1'],story:'압력 저하',occurred_at:'2026-10-16T10:05',incident_id:'incident-1'}]}},
    {handover_id:'latest', kind:'work_log', created_at:'2026-10-17T12:00:00+09:00',
      required_context:{start_at:'2026-10-17T08:00',author:'현재 근무자'}, equipment_ids:['EQ-1'],
      work_report:{records:[{equipment:['EQ-1'],story:'<img src=x> 압력 재점검',occurred_at:'2026-10-17T11:00',
        incident_id:'incident-1',followup_from:{handover_id:'first',record_index:0},outcome:'open',result:'재점검 필요'}]}}
  ];
  renderHome();
`, context);
const list = nodes.homeHandover;
assert.equal(list.children.length, 2, 'home groups follow-up records like the handover screen');
assert.equal(nodes.homeHandoverCount.textContent, '전체 2건');
const first = list.children[0];
assert.equal(first.type, 'button', 'a home entry opens the corresponding detail');
assert.match(first.text(), /HPU-01/);
assert.match(first.text(), /<img src=x> 압력 재점검/);
assert.match(first.text(), /발생시각.*2026-10-16 10:05/);
assert.match(first.text(), /근무자.*현재 근무자/);
assert.equal(first.children[1].children[1].textContent, '<img src=x> 압력 재점검', 'primary fallback preserves the recorded situation literally');
assert.match(first.text(), /재점검 필요/, 'legacy result remains visible');
assert.equal(nodes.homeHandoverPending.textContent,'조치·확인 필요 2');
assert.equal(nodes.homeHandoverComplete.textContent,'해결·확인 완료 0');
first.events.click();
assert.equal(context.opened[0].handover_id, 'latest');
assert.equal(context.opened[1], 'home');
assert.equal(context.opened[2], 0);
assert.match(list.children[1].text(), /발생시각.*미기재/);
vm.runInContext('S.savedHandovers=[]; S.handovers=[]; renderHome()', context);
assert.equal(list.textContent, '등록된 인계 사항이 없습니다.');
assert.equal(nodes.homeHandoverCount.textContent, '전체 0건');
const html = fs.readFileSync(require.resolve('../shiftlink/mes/web/pda.html'), 'utf8');
const header = html.match(/<header id="globalHeader"[\s\S]*?<\/header>/)[0];
assert.match(header, /ShiftLink<\/span><\/button><button[^>]+id="globalPending"/);
assert.doesNotMatch(html, /id="(?:homePending|hoPending)"/);
vm.runInContext("paintOutbox({pending:'업로드 대기 10건',conflict:''})", context);
assert.equal(nodes.globalPending.textContent, '업로드 대기 10건');
assert.equal(nodes.globalPending.hidden, false);
vm.runInContext("paintOutbox({pending:'',conflict:''})", context);
assert.equal(nodes.globalPending.hidden, true);
console.log('PDA home handover: selected columns, incident grouping, order, detail and empty state passed');
