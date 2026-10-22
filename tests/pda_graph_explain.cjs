const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.textContent = ''; }
  appendChild(node) { this.children.push(node); }
  set innerHTML(_) { throw Error('Graph metadata must use textContent'); }
  text() { return [this.textContent, ...this.children.map(x => x.text())].join(' '); }
}
const context = vm.createContext({console, URLSearchParams, setInterval, clearInterval, setTimeout});
vm.runInContext(fs.readFileSync('shiftlink/mes/web/pda.js', 'utf8'), context);
context.document = {createElement: tag => new Element(tag)};
const run = code => vm.runInContext(code, context);
assert.equal(run('graphContextElement(null)'), null);
assert.equal(run('graphContextElement({mode:"explain",status:"withheld"})'), null);
const sample = {mode:'explain',status:'ok',cards:[{card_id:'K-1',version:'v1',
  classifications:[{equipment:'HPU',component:'pump'}],
  citations:[{source_id:'<img src=x onerror=alert(1)>',document_version:'v2',locators:['p.5','p.45']}],
  symptom_candidates:[{label:'거품',review_status:'needs_review'}],held_citations:[{source_id:'EV-1',locator:'원문'}]}]};
context.sample = sample;
const snapshot = JSON.stringify(sample), element = run('graphContextElement(sample)');
assert.equal(element.tag, 'details');
for (const text of ['K-1', 'v1', 'v2', 'p.5 / p.45', '<img', '검수 전', '판본 미확인']) assert(element.text().includes(text));
assert.equal(JSON.stringify(sample), snapshot);
assert(run('graphContextElement({mode:"explain",status:"unavailable"})').text().includes('기존 답변'));
assert(run('graphContextElement({mode:"explain",status:"unmatched"})').text().includes('판본'));
console.log('PASS graph explain DOM: optional, candidate/held labels, exact locators, text safety, immutable input');

const twoHop = structuredClone(sample);
twoHop.depth = 2;
twoHop.cards[0].paths = [{relation:'PART_OF',component:'pump',equipment:'HPU'}];
twoHop.cards[0].related_cards = [{card_id:'K-2',version:'v3',paths:[
  {relation:'DESCRIBES_SYMPTOM',label:'거품',review_status:'needs_review'},
  {relation:'CITES',source_id:'<img src=x onerror=alert(1)>',document_version:'v2',
   cited_locators:['p.5'],related_locators:['p.99']}
]}];
twoHop.cards[0].related_cards_omitted = 3;
context.twoHop = twoHop;
const immutable = JSON.stringify(twoHop), rendered = run('graphContextElement(twoHop)');
for (const text of ['연결된 참고 카드','답변 근거에 추가하지 않음','K-2','v3',
                    '검수 전 증상 후보 공유','인용 카드 위치 · p.5','참고 카드 위치 · p.99','3개 생략','pump → HPU']) {
  assert(rendered.text().includes(text),text);
}
assert(rendered.text().includes('<img'));
assert.equal(JSON.stringify(twoHop),immutable);
assert.equal(rendered.children.find(x=>x.tag==='section').children.find(x=>x.tag==='details').tag,'details');
console.log('PASS two-hop reference-only rendering, distinct locators, limits and immutable text');
