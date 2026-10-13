const fs=require('node:fs');
(async()=>{
 const pages=await(await fetch('http://127.0.0.1:19222/json')).json();
 const page=pages.find(p=>p.type==='page'); if(!page)throw Error('No Pi Chromium test page');
 const ws=new WebSocket(page.webSocketDebuggerUrl); await new Promise((ok,no)=>{ws.onopen=ok;ws.onerror=no;});
 let id=0; const pending=new Map(); ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id&&pending.has(m.id)){const [ok,no]=pending.get(m.id);pending.delete(m.id);m.error?no(Error(JSON.stringify(m.error))):ok(m.result);}};
 const call=(method,params={})=>new Promise((ok,no)=>{const n=++id;pending.set(n,[ok,no]);ws.send(JSON.stringify({id:n,method,params}));});
 const evaluate=async(expression)=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
 if(process.argv.includes('--hpu')) {
  await call('Page.navigate',{url:'http://raspberrypi:8080/api/unity/stream'});
  await new Promise(ok=>setTimeout(ok,1500));
  const root='unity/ShiftLinkFactory/Checks/',start=Date.now();
  fs.writeFileSync(root+'hpu-photo-request.flag','one HPU photo timing');
  console.log('READY HPU photo timing');
  let timing;
  for(let i=0;i<90;i++){await new Promise(ok=>setTimeout(ok,1000));if(fs.existsSync(root+'hpu-photo-timing.json')){timing=JSON.parse(fs.readFileSync(root+'hpu-photo-timing.json','utf8'));if(timing.move_unix_ms>=start&&!fs.existsSync(root+'hpu-photo-request.flag'))break;timing=null;}}
  if(!timing)throw Error('HPU photo timing timeout');
  const pi=await evaluate(`(async()=>{const start=performance.now();const baseline=(await(await fetch('/api/equipment/scan/recent?limit=1')).json()).scans[0];const preScanMs=performance.now()-start;const captureStart=performance.now();const response=await fetch('/api/unity/capture',{method:'POST',cache:'no-store',signal:AbortSignal.timeout(5000)});const result=await response.json();const api=performance.now()-start,captureApiMs=performance.now()-captureStart;const confirmStart=performance.now();let scan=null;if(result.confirmed&&result.sent){for(let i=0;i<10;i++){await new Promise(ok=>setTimeout(ok,500));const latest=(await(await fetch('/api/equipment/scan/recent?limit=1')).json()).scans[0];if(latest&&latest.scan_id!==baseline?.scan_id){scan=latest;break;}}}const confirmMs=performance.now()-confirmStart;const text=document.createElement('pre');text.style='color:white;font-size:24px';text.textContent=JSON.stringify(result);document.body.prepend(text);await new Promise(ok=>requestAnimationFrame(()=>requestAnimationFrame(ok)));return {endpoint:location.origin+'/api/unity/capture',http_status:response.status,api_ms:api,pre_scan_lookup_ms:preScanMs,capture_api_ms:captureApiMs,scan_confirm_ms:confirmMs,to_result_raf_ms:performance.now()-start,result,scan};})()`);
  fs.writeFileSync(root+'pi-hpu-photo-timing.json',JSON.stringify({unity:timing,pi,method:'near-HPU synthetic move to Unity PNG+metadata; Pi capture API/classification to result RAF; one trial'},null,2));console.log(JSON.stringify({unity:timing,pi}));ws.close();return;
 }
 const clocks=[]; for(let i=0;i<9;i++){const a=Date.now(),pi=await evaluate('Date.now()'),b=Date.now();clocks.push({rtt_ms:b-a,pi_minus_pc_ms:pi-(a+b)/2});}clocks.sort((a,b)=>a.rtt_ms-b.rtt_ms);
 await call('Page.navigate',{url:'http://raspberrypi:8080/api/unity/stream'});
 await new Promise(ok=>setTimeout(ok,1500));
 if(await evaluate('location.origin')!=='http://raspberrypi:8080')throw Error('Pi browser did not open configured PDA address');
 await evaluate(`(()=>{document.body.innerHTML='<div style="color:white">Unity movement timing test</div><img id="timing-video" style="width:100%;max-width:960px">';document.body.style.background='#111';const image=document.getElementById('timing-video'); const reconnect=()=>{image.src='/api/unity/stream?t='+Date.now();}; image.onerror=()=>setTimeout(reconnect,1000);image.onload=()=>setTimeout(reconnect,250);reconnect();const canvas=document.createElement('canvas');canvas.width=128;canvas.height=72;const c=canvas.getContext('2d',{willReadFrequently:true});window.movementDisplayEvents=[];let last='',lastSample=performance.now();window.movementRafGaps=[];function tick(){if(window.stopMarkerObserver)return;const now=performance.now();window.movementRafGaps.push(now-lastSample);lastSample=now;try{if(image.naturalWidth){c.drawImage(image,0,0,128,72);const p=c.getImageData(6,3,1,1).data;const color=p[0]>200&&p[1]<60&&p[2]<60?'red':p[1]>200&&p[0]<60&&p[2]<60?'green':'';if(color&&color!==last){window.movementDisplayEvents.push({color,pi_unix_ms:Date.now(),perf_ms:now});last=color;}}}catch(e){}requestAnimationFrame(tick);}requestAnimationFrame(tick);return {url:location.href,userAgent:navigator.userAgent};})()`);
 const root='unity/ShiftLinkFactory/Checks/';fs.writeFileSync(root+'movement-request.flag','synthetic movement measurement');
 console.log('READY Pi Chromium observer; clock',JSON.stringify(clocks[0]));
 for(let i=0;i<85;i++){await new Promise(ok=>setTimeout(ok,1000));if(i%10===0)console.log('observed color transitions',await evaluate('window.movementDisplayEvents.length'));if(fs.existsSync(root+'movement-events.json')){const input=JSON.parse(fs.readFileSync(root+'movement-events.json','utf8'));if(input.trials.length===20&&!fs.existsSync(root+'movement-request.flag'))break;}}
 await evaluate('window.stopMarkerObserver=true');
 const events=await evaluate('window.movementDisplayEvents');const gaps=await evaluate('window.movementRafGaps');
 const input=JSON.parse(fs.readFileSync(root+'movement-events.json','utf8'));
 const mapped=[];let j=0;for(const t of input.trials){while(j<events.length&&events[j].pi_unix_ms-clocks[0].pi_minus_pc_ms<t.input_unix_ms-10)j++;const event=events[j++];if(!event||event.color!==t.color)throw Error('Missing or mismatched visible marker for input '+t.sequence);mapped.push({...t,observed_pi_unix_ms:event.pi_unix_ms,estimated_input_to_decode_raf_ms:event.pi_unix_ms-clocks[0].pi_minus_pc_ms-t.input_unix_ms});}
 const result={url:'http://raspberrypi:8080/api/unity/stream',method:'synthetic controller.Step to decoded MJPEG pixel observed during Pi requestAnimationFrame; physical display scanout excluded',clock:clocks[0],trials:mapped,raf_gaps_ms:gaps};fs.writeFileSync(root+'pi-movement-latency.json',JSON.stringify(result,null,2));
 const lat=mapped.map(t=>t.estimated_input_to_decode_raf_ms).sort((a,b)=>a-b);console.log(JSON.stringify({samples:lat.length,median_ms:(lat[Math.floor((lat.length-1)/2)]+lat[Math.floor(lat.length/2)])/2,p95_ms:lat[Math.ceil(lat.length*.95)-1],max_ms:lat.at(-1),clock_uncertainty_ms:clocks[0].rtt_ms/2}));ws.close();
})().catch(e=>{console.error(e);process.exit(1);});
