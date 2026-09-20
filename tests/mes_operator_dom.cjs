// DOM-contract tests, not browser layout or assistive-technology tests.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const elements = new Map();
const document = {activeElement:null, addEventListener(){}, querySelectorAll(){return [];}, querySelector(s){
  if (!elements.has(s)) elements.set(s,{addEventListener(){}}); return elements.get(s);
}};
const scope={document,fetch:async()=>{throw new Error('offline');},AbortSignal,setInterval(){},Date};
const source=fs.readFileSync('shiftlink/mes/web/app.js','utf8').replace('  refresh();','  globalThis.testView = setView;\n  refresh();');
vm.runInNewContext(source,scope);
function focusable(attrs={}) {return {hasAttribute:k=>k in attrs,getAttribute:k=>attrs[k],focus(){document.activeElement=this;}};}
const first=focusable({'data-equipment':'HPU','data-relation':'HPU|RT1|hydraulic'});
const second=focusable({'data-equipment':'HPU','data-relation':'HPU|RT2|hydraulic'});
const replacement=focusable({'data-equipment':'HPU','data-relation':'HPU|RT2|hydraulic'});
let after=false;
const el={dataset:{},contains:n=>[first,second].includes(n),querySelectorAll:s=>s==='button,[role="button"]'?[first,replacement]:[],querySelector:()=>first,set innerHTML(v){after=true;}};
elements.set('#test',el);document.activeElement=second;
scope.testView('#test','new data');assert.ok(after);assert.equal(document.activeElement,replacement,'same source/type must retain exact destination');
const oldSummary=focusable(),newSummary=focusable();after=false;
const oldDetails={open:true},newDetails={open:false};
Object.assign(el,{dataset:{},contains:n=>n===oldSummary,querySelectorAll:s=>s==='summary'?[after?newSummary:oldSummary]:s==='details'?[after?newDetails:oldDetails]:[]});
document.activeElement=oldSummary;scope.testView('#test','updated evidence');
assert.equal(document.activeElement,newSummary);assert.equal(newDetails.open,true);
console.log('Refresh focus contract passed: exact relation and open summary');
