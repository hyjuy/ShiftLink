const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('shiftlink/mes/web/pda.js', 'utf8');

async function check(fail) {
  const calls = [];
  let signal;
  const image = {hidden:true, src:'', async decode() {}, removeAttribute() {this.src='';}};
  const context = vm.createContext({URLSearchParams, AbortController, AbortSignal,
    fetch:async (path, options) => {
      calls.push(path);
      assert.equal(path, '/api/unity/config');
      if(calls.length===1) return {ok:true, json:async()=>({enabled:true})};
      assert.match(image.src, /^\/api\/unity\/stream\?/);
      image.onload(); signal=options.signal;
      return {ok:!fail, status:502, json:async()=>({stream_live:true})};
    }});
  vm.runInContext(source, context);
  context.document={getElementById:()=>image};
  context.setTimeout = fn => {
    vm.runInContext("S.scanRun++; S.screen='home'; stopUnityCamera();", context);
    fn();
  };
  vm.runInContext(`
    show = name => { S.screen=name; };
    setScanState = (kind,text) => { S.cameraStatus=text; };
  `, context);
  await vm.runInContext('startScan()', context);
  assert.deepEqual(calls, ['/api/unity/config', '/api/unity/config']);
  assert.equal(image.hidden, true, 'leaving scan clears the video');
  assert.equal(image.src, '');
  assert.equal(signal.aborted, true, 'pending frame request is cancelled');
  assert.equal(vm.runInContext('S.online', context), null, 'camera state must not overwrite MES connection state');
  if(fail) assert.match(vm.runInContext('S.cameraStatus', context), /자동 재연결/);
}
check(false).then(()=>check(true)).then(()=>console.log('Unity camera start, cleanup, failure and MES isolation PASS'))
  .catch(error=>{console.error(error);process.exitCode=1;});
