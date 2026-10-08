const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('shiftlink/mes/web/pda.js', 'utf8');

// 「촬영」: 확신도 미만은 Jetson 기록을 기다리지 않고, 보냈으면 새 scan_id로 설비를 확정한다.
async function shoot(capture, scans) {
  const btn = {disabled:false, hidden:false};
  const context = vm.createContext({AbortSignal, fetch:async () => ({json:async () => capture})});
  vm.runInContext(source, context);
  context.document = {getElementById:() => btn};
  context.setTimeout = fn => fn();
  context.locked = null;
  vm.runInContext(`
    S.equipment = [{code:'HPU-01'}];
    setScanState = (kind, text) => { S.shot = kind + ':' + text; };
    lockScan = (eq, scan) => { locked = eq.code + ' ' + scan.scan_id; };
  `, context);
  context.scans = scans;
  vm.runInContext('latestScan = async () => scans.shift() || null', context);
  await vm.runInContext('shootScan()', context);
  assert.equal(btn.disabled, false);
  return {state:vm.runInContext('S.shot', context), locked:context.locked};
}

(async () => {
  const low = await shoot({class:'CAU', conf:0.6, confirmed:false, sent:false}, [{scan_id:'old'}]);
  assert.match(low.state, /^failed:확신도 낮음\(CAU 0\.60\)/);
  assert.equal(low.locked, null);
  const ok = await shoot({class:'HPU', conf:0.98, confirmed:true, sent:true},
    [{scan_id:'old', code:'HPU-01'}, {scan_id:'old', code:'HPU-01'}, {scan_id:'SC-new', code:'HPU-01'}]);
  assert.equal(ok.locked, 'HPU-01 SC-new');
  console.log('Unity shoot: low confidence rejected, sent shot locks the new scan PASS');
})().catch(error => { console.error(error); process.exitCode = 1; });
