const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function harness(file, storedToken) {
  const nodes = {}, storage = new Map(storedToken ? [['shiftlink.mes.adminToken', storedToken]] : []);
  const node = id => nodes[id] ||= {textContent:'',hidden:false,events:{},classList:{toggle(){}},
    addEventListener(event, handler){this.events[event]=handler;},replaceChildren(){},querySelectorAll(){return [];},reset(){}};
  const context = vm.createContext({document:{getElementById:node,createElement:()=>node(Symbol())},
    sessionStorage:{getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)},
    AbortSignal,fetch:async()=>({ok:true,json:async()=>({drafts:[],administrator:{name:'MES관리자'}})})});
  vm.runInContext(fs.readFileSync(file,'utf8'),context);
  return {nodes,storage};
}
(async()=>{
  const dashboard = harness('shiftlink/mes/web/accounts.js','test-token');
  assert.equal(dashboard.nodes['admin-logout'].hidden,false);
  await dashboard.nodes['admin-logout'].events.click();
  assert.equal(dashboard.nodes['admin-logout'].hidden,true);
  assert.equal(dashboard.storage.size,0);
  const review = harness('shiftlink/mes/web/candidate-review.js','test-token');
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(review.nodes['review-logout'].hidden,false);
  await review.nodes['review-logout'].events.click();
  assert.equal(review.nodes['review-logout'].hidden,true);
  for(const [file,name,logout] of [['index.html',null,'admin-logout'],['knowledge-candidates.html','reviewer-name','review-logout']]) {
    const html=fs.readFileSync('shiftlink/mes/web/'+file,'utf8');
    const header=html.match(/<header class="app-header">[\s\S]*?<\/header>/)[0];
    if(name) {
      assert.doesNotMatch(header,/reviewer-name|admin-session/);
      assert.match(header,/class="header-side"[^]*MES 대시보드[^]*id="review-logout"/);
    }
    else {
      assert.doesNotMatch(header,/class="admin-session"/);
      assert.match(header,/class="header-status"[^]*id="board-clock"[^]*id="admin-logout"/);
      assert.match(header,/class="header-actions"[^]*지식카드 관리[^]*id="admin-open"[^]*id="open-pda"/);
      assert.doesNotMatch(header,/지식카드 후보/);
    }
    assert.equal((html.match(new RegExp('id="'+logout+'"','g'))||[]).length,1);
  }
  console.log('MES admin header: menu order, account controls and logout state passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
