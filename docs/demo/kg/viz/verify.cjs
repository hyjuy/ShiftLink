/* Run: node docs/demo/kg/viz/verify.cjs. No packages; uses installed Chrome and CDP. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const viz = __dirname, kg = path.dirname(viz), qa = path.join(viz,'.qa');
const chrome = process.env.KG_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const reports = [], failures = [];
const delay = ms => new Promise(resolve => setTimeout(resolve,ms));
async function serve(root) {
  const requests = [];
  let graphOverride;
  const server = http.createServer((req,res) => {
    const pathname = decodeURIComponent(new URL(req.url,'http://localhost').pathname);
    requests.push(pathname);
    if (pathname === '/build/graph.json' && graphOverride !== undefined) {
      res.setHeader('Content-Type','application/json; charset=utf-8'); res.end(JSON.stringify(graphOverride)); return;
    }
    const file = path.resolve(root,'.' + pathname.replace(/\/$/,'/index.html'));
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
      res.writeHead(404); res.end('Not found'); return;
    }
    res.setHeader('Content-Type',file.endsWith('.html') ? 'text/html; charset=utf-8' : file.endsWith('.json') ? 'application/json; charset=utf-8' : 'text/plain');
    res.end(fs.readFileSync(file));
  });
  server.listen(0,'127.0.0.1'); await once(server,'listening');
  return {server,requests,setGraph:value=>{graphOverride=value;},url:'http://127.0.0.1:' + server.address().port};
}
async function main() {
  assert(fs.existsSync(chrome),'Installed Chrome required (KG_CHROME can override its path)');
  fs.mkdirSync(qa,{recursive:true});
  const profile = fs.mkdtempSync(path.join(qa,'profile-'));
  const normal = await serve(kg), missing = await serve(viz);
  const child = spawn(chrome,['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir=' + profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
  let ws;
  try {
    const portFile = path.join(profile,'DevToolsActivePort');
    for (let i=0;i<100 && !fs.existsSync(portFile);i++) await delay(100);
    assert(fs.existsSync(portFile),'Chrome DevTools port available');
    const port = fs.readFileSync(portFile,'utf8').split('\n')[0];
    console.log('Chrome DevTools port:',port);
    const targets = await (await fetch('http://127.0.0.1:' + port + '/json',{signal:AbortSignal.timeout(10000)})).json();
    ws = new WebSocket(targets.find(t => t.type === 'page').webSocketDebuggerUrl);
    await once(ws,'open');
    let seq=0; const pending=new Map();
    ws.addEventListener('message',event => {
      const message=JSON.parse(event.data);
      if (message.method === 'Runtime.exceptionThrown') failures.push(message.params.exceptionDetails.text);
      if (message.id) {const job=pending.get(message.id);pending.delete(message.id);message.error ? job.reject(Error(message.error.message)) : job.resolve(message.result);}
    });
    const send=(method,params={})=>new Promise((resolve,reject)=>{
      const id=++seq,timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout: '+method));},10000);
      pending.set(id,{resolve:value=>{clearTimeout(timer);resolve(value);},reject:error=>{clearTimeout(timer);reject(error);}});
      ws.send(JSON.stringify({id,method,params}));
    });
    const evaluate=async expression=>{
      const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
      assert(!r.exceptionDetails,JSON.stringify(r.exceptionDetails)); return r.result.value;
    };
    const check=async(expression,name)=>{assert(await evaluate(expression),name);reports.push('PASS ' + name);};
    const navigate=async(url,ready)=>{
      await send('Page.navigate',{url});
      for(let i=0;i<100;i++){if(await evaluate('Boolean(' + ready + ')'))return;await delay(50);}
      throw Error('Navigation timeout: '+url);
    };
    await send('Runtime.enable'); await send('Page.enable');console.log('CDP connected');
    await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
    await navigate(normal.url+'/viz/?mock=1&selftest=1',"document.getElementById('selftest') && !document.getElementById('selftest').hidden");
    const embedded=await evaluate("document.getElementById('selftest').textContent");
    assert(embedded.includes('PASS 필터 초기화'),embedded);reports.push(embedded);
    await check("document.querySelectorAll('#nodes option').length===12",'mock: 12 nodes');
    await evaluate("document.getElementById('nodes').focus();document.getElementById('nodes').selectedIndex=0");
    await send('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowDown',code:'ArrowDown',windowsVirtualKeyCode:40,nativeVirtualKeyCode:40});
    await send('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowDown',code:'ArrowDown',windowsVirtualKeyCode:40,nativeVirtualKeyCode:40});
    await check("document.getElementById('nodes').selectedIndex===1 && document.getElementById('selection-id').textContent===document.getElementById('nodes').value",'native keyboard list selection');
    await evaluate("document.getElementById('nodes').value='card:MOCK-HPU-001@mock-v1';document.getElementById('nodes').dispatchEvent(new Event('change'))");
    await check("document.getElementById('detail').textContent.includes('p. 12, Fig. 3') && document.getElementById('detail').textContent.includes('p. 13, Table 2')",'both citation locators visible');
    await check("document.getElementById('status').textContent.includes('선택: 가짜 카드 · 펌프 출구 압력 관측')",'status tracks current selected node');
    await evaluate("document.getElementById('selftest').hidden=true;document.getElementById('raw-props').open=true");
    const shot=async name=>{
      const metrics=await send('Page.getLayoutMetrics');
      const r=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width:metrics.cssContentSize.width,height:metrics.cssContentSize.height,scale:1}});
      fs.writeFileSync(path.join(qa,name),Buffer.from(r.data,'base64'));
    };
    await shot('desktop.png');
    await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
    await evaluate('renderGraph()');
    await check('document.documentElement.scrollWidth<=390','mobile: no page horizontal overflow');
    await check("document.querySelector('#graph svg').getBoundingClientRect().width>=720 && document.getElementById('graph').scrollWidth>document.getElementById('graph').clientWidth",'mobile: readable graph uses local horizontal scrolling');
    await check("(()=>{const r=document.querySelector('#graph .selected rect').getBoundingClientRect(),h=document.getElementById('graph').getBoundingClientRect();return r.left>=h.left && r.right<=h.right;})()",'mobile: selected node is fully visible');
    await shot('mobile.png');
    await navigate(missing.url+'/?mock=0',"document.getElementById('error') && !document.getElementById('error').hidden");
    await check("document.getElementById('error-message').textContent.includes('HTTP 404') && document.getElementById('error').textContent.includes('python -m http.server')",'actual missing file HTTP 404 and execution guide');
    assert(!missing.requests.includes('/mock_graph.json'),'No automatic fallback request');reports.push('PASS no automatic mock fallback request');
    await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});await shot('missing-file.png');
    await evaluate("document.getElementById('retry').click()"); await delay(150);
    await check("!document.getElementById('error').hidden && document.getElementById('workspace').hidden",'retry retains missing-file error');
    if (fs.existsSync(path.join(kg,'build','graph.json'))) {
      await navigate(normal.url+'/viz/',"document.getElementById('workspace') && (!document.getElementById('workspace').hidden || !document.getElementById('error').hidden)");
      await check("document.getElementById('error').hidden && document.getElementById('dataset').textContent.includes('실제 파일')",'existing real graph loads without mock');
      reports.push('INFO actual graph '+await evaluate("document.getElementById('status').textContent"));
      const actual = JSON.parse(fs.readFileSync(path.join(kg,'build','graph.json'),'utf8'));
      await check(`model.nodes.length===${actual.nodes.length} && model.edges.length===${actual.edges.length}`,'actual: browser counts match generated graph');
      if (actual.nodes.some(n=>n.type==='Symptom')) {
        await check("model.nodes.filter(n=>n.type==='Symptom').length===18 && model.edges.filter(e=>e.type==='DESCRIBES_SYMPTOM').length===20",'integrated: 18 symptom concepts and 20 candidate edges');
        await evaluate("document.getElementById('type-filter').value='Symptom';document.getElementById('type-filter').dispatchEvent(new Event('change'))");
        await check("document.getElementById('nodes').options.length===18 && document.getElementById('badges').textContent.includes('검수 전')",'integrated: symptom type filter and review badge');
        await evaluate("document.getElementById('equipment-filter').value='HPU';document.getElementById('equipment-filter').dispatchEvent(new Event('change'))");
        await check("document.getElementById('nodes').options.length>0 && [...document.getElementById('nodes').options].every(o=>model.scopes.get(o.value).has('HPU'))",'integrated: equipment filter includes linked symptoms');
        await evaluate("chooseNeighbor(model.edges.find(e=>e.type==='DESCRIBES_SYMPTOM' && model.byId.get(e.source).props.card_id==='K-1323').source)");
        await check("document.getElementById('badges').textContent.includes('증상 연결 후보 · 검수 전') && model.edges.filter(e=>e.source===selectedId && e.type==='DESCRIBES_SYMPTOM').length===3",'integrated: composite card preserves three symptom candidates');
        await evaluate("document.querySelector('#detail button').click()");
        await check("document.getElementById('selection-id').textContent===selectedId",'integrated: real neighbor button updates selection');
        await evaluate("chooseNeighbor(model.nodes.find(n=>n.type==='CardVersion' && model.edges.some(e=>e.type==='CITES' && e.source===n.id && e.props.locators.length)).id)");
        await check("(()=>{const es=model.edges.filter(e=>e.type==='CITES' && e.source===selectedId);return es.every(e=>e.props.locators.every(l=>document.getElementById('detail').textContent.includes(l))) && JSON.stringify(model.byId.get(selectedId).props,null,2)===document.querySelector('#raw-props pre').textContent;})()",'integrated: original card props and all citation locators preserved in detail');
        await evaluate("chooseNeighbor(model.nodes.find(n=>n.type==='CardVersion' && n.props.safety_flag).id)");
        await check("document.getElementById('badges').textContent.includes('안전 카드 · 증상 연결 보류') && !model.edges.some(e=>e.type==='DESCRIBES_SYMPTOM' && e.source===selectedId)",'integrated: safety card is held without symptom edges');
        await evaluate("chooseNeighbor(model.nodes.find(n=>n.type==='CardVersion' && n.props.symptom===null).id)");
        await check("!model.edges.some(e=>e.type==='DESCRIBES_SYMPTOM' && e.source===selectedId) && document.getElementById('badges').textContent.includes('보류')",'integrated: null symptom card stays held');
        await evaluate("chooseNeighbor(model.nodes.find(n=>n.type==='CardVersion' && n.props.provenance.sources.some(s=>!s.document_version)).id)");
        await check("document.getElementById('detail').textContent.includes('판본 미지정 인용')",'integrated: unversioned citations remain visible');
        await evaluate("chooseNeighbor(model.nodes.find(n=>n.type==='Symptom').id)");
      }
      await evaluate("document.getElementById('reset').click();document.getElementById('nodes').focus();document.getElementById('nodes').selectedIndex=0;document.getElementById('nodes').dispatchEvent(new Event('change'))");
      const beforeKey=await evaluate("document.getElementById('nodes').value");
      await send('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowDown',code:'ArrowDown',windowsVirtualKeyCode:40,nativeVirtualKeyCode:40});
      await send('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowDown',code:'ArrowDown',windowsVirtualKeyCode:40,nativeVirtualKeyCode:40});
      await check(`document.getElementById('nodes').value!==${JSON.stringify(beforeKey)} && document.getElementById('selection-id').textContent===document.getElementById('nodes').value`,'integrated: real graph native keyboard changes selection');
      await evaluate("chooseNeighbor(model.nodes.find(n=>n.type==='Asset').id)");
      await check("document.getElementById('badges').textContent.includes('합성 장비') && model.nodes.filter(n=>n.type==='Asset').length===10 && !model.nodes.some(n=>n.type==='AssetPart')",'integrated: synthetic assets and no AssetPart');
      await evaluate("chooseNeighbor(model.nodes.find(n=>n.type==='Symptom').id)");
      await shot('actual-file.png');
      await navigate(normal.url+'/viz/?selftest=1',"document.getElementById('workspace') && (!document.getElementById('workspace').hidden || !document.getElementById('error').hidden)");
      await check("document.getElementById('error').hidden && document.getElementById('selftest').hidden",'real mode selftest query does not run mock-only checks');
    }
    const mock=JSON.parse(fs.readFileSync(path.join(viz,'mock_graph.json'),'utf8'));
    const assetless={nodes:mock.nodes.filter(n=>n.type!=='Asset'),edges:mock.edges.filter(e=>e.type!=='INSTANCE_OF')};
    normal.setGraph(assetless);
    await navigate(normal.url+'/viz/?fixture=assetless',"document.getElementById('workspace') && !document.getElementById('workspace').hidden");
    await check("document.getElementById('dataset').textContent==='실제 파일'",'assetless graph does not claim synthetic assets included');
    normal.setGraph({nodes:[],edges:[]});
    await navigate(normal.url+'/viz/?fixture=empty',"document.getElementById('workspace') && !document.getElementById('workspace').hidden");
    await check("document.getElementById('dataset').textContent==='실제 파일' && document.getElementById('nodes').options.length===0",'valid empty graph has truthful banner and empty state');
    const invalid=structuredClone(mock);invalid.nodes.find(n=>n.type==='CardVersion').props.provenance.sources=[null];normal.setGraph(invalid);
    await navigate(normal.url+'/viz/?fixture=null-source',"document.getElementById('error') && !document.getElementById('error').hidden");
    await check("document.getElementById('error-message').textContent.includes('원본 인용 항목') && document.getElementById('workspace').hidden",'null provenance source rejected before selection rendering');
    assert.equal(failures.length,0,'No browser Runtime exceptions');reports.push('PASS no browser Runtime exceptions');
    fs.writeFileSync(path.join(qa,'browser-results.txt'),reports.join('\n')+'\n','utf8');
    console.log(reports.join('\n'));
    await send('Browser.close');
  } finally {
    if(ws)ws.close();
    if(child.exitCode===null){child.kill();await Promise.race([once(child,'exit'),delay(3000)]);}
    normal.server.close();missing.server.close();
    // Only this run's newly created temporary browser profile is eligible for cleanup.
    assert(path.dirname(profile)===qa && path.basename(profile).startsWith('profile-'));
    for(let attempt=0;attempt<5;attempt++){
      try{fs.rmSync(profile,{recursive:true,force:true});break;}catch{await delay(200);}
    }
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
