"""Pi real-time isolated HTTP -> installed worker -> actual PDA reader/Chromium.

No operating controls, service changes, alarms or kiosk profiles are touched.
Optional SSH relay adds Pi-Jetson-Pi transport; operating database/kiosk are excluded.
The empty test browser profile uses a basic password store to avoid locked desktop keyrings.
"""
import argparse,copy,gzip,hashlib,json,os,re,shutil,signal,subprocess,sys,threading,time
from datetime import datetime,timedelta,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse,parse_qs
from scripts.mes_causal_active_advisory import ActiveAdvisorySource,ActiveAdvisorySession
from scripts.mes_rms_qualification import load,save,p95
from shiftlink.pda.ai_insights import read_insights

def run(a):
 root=a.root;config=load(root/'deploy/analytics/source-config.json');profile=root/'deploy/analytics/normal-profile-rms16.json'
 binding=ActiveAdvisorySource(load(root/'docs/research/evidence/mes-causal-v14c-20261023/settings.json'),config,load(profile))
 manifest=load(a.data/'manifest.json');result=load(a.data/'candidate-result.json');assert result['summary']['passed'],'offline gate failed'
 chromium=shutil.which('chromium');assert chromium,'real Pi Chromium required';outcomes=[]
 names=['hydraulic_leak-01','cooling_loss-01','pneumatic_leak-01','drive_friction-01','stuck-EQ-0008-inside']
 page=(Path('/home/pi/shiftlink/app/shiftlink/mes/web/pda.html')).read_text();page=re.sub(r'<script\b[^>]*>[\s\S]*?</script>','',page,flags=re.I)
 js=(Path('/home/pi/shiftlink/app/shiftlink/mes/web/pda.js')).read_text();prefix=js[:js.index("\nif (typeof document !== 'undefined') {")];start=js.index('const WATCH_MS =');functions=js[start:js.index("document.addEventListener('click'",start)]
 for name in names:
  truth=load(a.data/'private'/(name+'.json'));case=next(c for c in manifest['cases'] if c['id']==name);raw=a.data/'data'/(name+'.json.gz')
  assert hashlib.sha256(raw.read_bytes()).hexdigest()==case['sha256']
  with gzip.open(raw,'rt') as z:frames=json.load(z)
  offset=datetime.now(timezone.utc)-timedelta(seconds=2)-datetime.fromisoformat(frames[truth['begin']-2]['simulated_at'])
  for f in frames:
   f['simulated_at']=(datetime.fromisoformat(f['simulated_at'])+offset).isoformat();f['is_synthetic']=True
   for m in f['measurements']:m['observed_at']=(datetime.fromisoformat(m['observed_at'])+offset).isoformat()
  with TemporaryDirectory(prefix='rms-realtime-') as tmp:
   tmp=Path(tmp);state_dir=tmp/'state';session=ActiveAdvisorySession(binding,state_dir/'checkpoint.json');session.defer_flush=True
   for f in frames:
    if f['sequence']>=truth['begin']:break
    session.feed(f,binding.config_id)
   session.flush();before_seq=session.cursor;assert before_seq==truth['begin']-1
   shared=dict(index=before_seq-1,telemetry=[],injected={},start=None,requests=[]);mutex=threading.Lock();output=tmp/'latest.json'
   class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,value,kind='application/json'):
     body=value.encode() if isinstance(value,str) else json.dumps(value).encode();self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_GET(self):
     parsed=urlparse(self.path)
     with mutex:current=shared['index'];shared['requests'].append(dict(path=parsed.path,at=time.monotonic()))
     f=copy.deepcopy(frames[current])
     if parsed.path=='/api/config':return self.send(dict(is_synthetic=True,config=config))
     if parsed.path=='/api/state':return self.send(f)
     if '/replay' in parsed.path:
      cursor=int(parse_qs(parsed.query)['sequence'][0]);return self.send(dict(run_id=f['run_id'],config_id=config['config_id'],is_synthetic=True,config_preserved=True,snapshots=[r for r in frames[:current+1] if r['sequence']>cursor],events=[]))
     if parsed.path=='/api/pda-state':
      f['ai_insights']=read_insights(output,f,binding.config_id)
      # Fixed synthetic legacy alarm exercises AI merge/ack/haptic independently
      # of legitimate sensor-range alarm changes. Model input retains all sensors.
      f['active_alarms']=[dict(equipment_id=truth['equipment_id'],label='기존 경보',severity='warning')];f['measurements']=[]
      return self.send(f)
     if parsed.path=='/':return self.send(html,'text/html; charset=utf-8')
     self.send_error(404)
    def do_POST(self):
     value=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
     with mutex:shared['telemetry'].append(value|dict(received=time.monotonic()))
     self.send(dict(ok=True))
   script=r'''
let vibrations=0;haptic=()=>vibrations++;notifyBubble=()=>{};
S.equipment=EQUIPMENT;let first=true;
async function draw(){try{const snap=await fetch('/api/pda-state').then(r=>r.json());S.snapshot=snap;$('notifyPanel').hidden=false;
renderAlert(faultsFrom(snap));renderNotifyPanel();
if(first){const all=$('notifyPanel').querySelector('.np-all');if(all&&!all.disabled)all.click();first=false;}
requestAnimationFrame(()=>requestAnimationFrame(()=>{
 const items=aiInsightsFrom(snap).items;const rows=[...$('notifyPanel').querySelectorAll('.np-row')];
 fetch('/telemetry',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sequence:snap.sequence,status:snap.ai_insights.status,items:items.map(i=>({id:i.event_id,equipment_id:i.equipment_id,sequence:(snap.ai_insights.items.find(r=>r.event_id===i.event_id)||{}).sequence})),rows:rows.length,vibrations,ack:Object.keys(S.alertAck||{}),visible:rows.some(r=>r.textContent.includes('AI 이상징후'))})});}));
}catch(e){fetch('/telemetry',{method:'POST',body:JSON.stringify({error:String(e)})});}}
draw();setInterval(draw,3000);
'''.replace('EQUIPMENT',json.dumps(config['equipment']))
   trap="<script>window.onerror=(m)=>fetch('/telemetry',{method:'POST',body:JSON.stringify({error:String(m)})});</script>"
   html=page.replace('</body>',trap+'<script>'+prefix+'\n'+functions+'\n'+script+'</script></body>')
   server=ThreadingHTTPServer(('127.0.0.1',a.source_port),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();url=a.worker_url or 'http://127.0.0.1:'+str(server.server_port)
   env=os.environ|dict(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
   worker_log=(a.out/(name+'-worker.log')).open('w');browser_log=(a.out/(name+'-browser.log')).open('w')
   worker=subprocess.Popen([sys.executable,'-B','-m','scripts.mes_causal_active_advisory','--mes-url',url,'--source-config',str(root/'deploy/analytics/source-config.json'),'--settings',str(root/'docs/research/evidence/mes-causal-v14c-20261023/settings.json'),'--normal-profile',str(profile),'--normal-profile-sha256',hashlib.sha256(profile.read_bytes()).hexdigest(),'--state-dir',str(state_dir),'--output',str(output),'--stop-file',str(tmp/'STOP')],cwd=root,env=env,stdout=worker_log,stderr=subprocess.STDOUT)
   browser=subprocess.Popen([chromium,'--headless','--enable-logging=stderr','--password-store=basic','--disable-gpu','--no-first-run','--disable-background-networking','--disable-extensions','--user-data-dir='+str(tmp/'chromium'),'--window-size=430,900',url],stdout=browser_log,stderr=subprocess.STDOUT,start_new_session=True)
   try:
    deadline=time.monotonic()+25
    while time.monotonic()<deadline:
     if worker.poll() is not None:raise RuntimeError('worker exited')
     with mutex:ready=any(v.get('status')=='ready' for v in shared['telemetry'])
     if ready:break
     time.sleep(.2)
    else:raise RuntimeError('worker/browser startup failed')
    first_seen=None;start=time.monotonic();first_notice=None;lags=[];compute=[];frames_sent=0
    # Start with first anomalous frame; every later frame follows one real second.
    for index in range(truth['begin']-1,min(len(frames),truth['begin']+150)):
     target=start+frames_sent;time.sleep(max(0,target-time.monotonic()));injected=time.monotonic()
     with mutex:shared['index']=index;shared['injected'][frames[index]['sequence']]=injected;telemetry=list(shared['telemetry'])
     frames_sent+=1
     if output.exists():
      report=load(output);lags.append(frames[index]['sequence']-report.get('processed_sequence',frames[index]['sequence']));compute.append(report.get('poll_seconds',0))
      if report.get('status')=='model_error':raise RuntimeError('real worker model_error')
     if first_seen is None:
      matching=[t for t in telemetry if t.get('visible') and any(i['equipment_id']==truth['equipment_id'] for i in t.get('items',[]))]
      if matching:first_seen=matching[0]['received'];first_notice=next(i['sequence'] for i in matching[0]['items'] if i['equipment_id']==truth['equipment_id'])
     if first_seen is not None and time.monotonic()-first_seen>=33:break
    with mutex:telemetry=list(shared['telemetry']);final_source=frames[shared['index']]['sequence'];fault_injected=shared['injected'][truth['begin']]
    catchup_deadline=time.monotonic()+5
    while time.monotonic()<catchup_deadline:
     final_report=load(output)
     if final_report.get('processed_sequence')==final_source:break
     time.sleep(.1)
    assert final_report.get('processed_sequence')==final_source,'worker did not consume the final source frame'
    assert first_seen is not None,'no rendered AI notice'
    visible=[v for v in telemetry if v.get('visible')];assert len(visible)>=10,'retention not observed past thirty frames'
    assert all(v['rows']==1 and v['vibrations']==1 and v['ack']==[truth['equipment_id']] for v in telemetry if 'rows' in v),'AI changed legacy rows/ack/vibration'
    ids={i['id'] for v in visible for i in v.get('items',[]) if i['equipment_id']==truth['equipment_id']};assert len(ids)==1,'duplicate AI identity'
    assert not any(v.get('error') for v in telemetry),'browser error'
    row=dict(case=name,frames_sent=frames_sent,source_to_visible_seconds=first_seen-fault_injected,first_notice_sequence=first_notice,model_notice_delay_frames=first_notice-truth['begin'],processed_frames=final_report['processed_sequence']-before_seq,visible_polls=len(visible),worker_poll_p95_seconds=p95(compute),max_processed_sequence_lag=max(lags),rows=1,legacy_vibrations=1,ai_added_vibrations=0,retained_beyond_thirty_frames=True)
    assert row['worker_poll_p95_seconds']<1 and max(lags)<=3 and row['source_to_visible_seconds']<=120
    outcomes.append(row);save(a.out/'progress.json',outcomes);print('REALTIME_CASE',json.dumps(row),flush=True)
   finally:
    worker.terminate()
    try:worker.wait(timeout=10)
    except subprocess.TimeoutExpired:worker.kill();worker.wait()
    os.killpg(browser.pid,signal.SIGTERM)
    try:browser.wait(timeout=10)
    except subprocess.TimeoutExpired:os.killpg(browser.pid,signal.SIGKILL);browser.wait()
    worker_log.close();browser_log.close();save(a.out/(name+'-diagnostic.json'),dict(telemetry=shared['telemetry'],requests=shared['requests'],worker_output=load(output) if output.exists() else None,browser_returncode=browser.returncode));(a.out/(name+'-page.html')).write_text(html);server.shutdown();server.server_close()
   assert 'analysis_error' not in (a.out/(name+'-worker.log')).read_text(),'worker logged an analysis error'
 summary=dict(passed=True,cases=outcomes,samples=len(outcomes),p95_source_to_visible_seconds=p95([r['source_to_visible_seconds'] for r in outcomes]),worst_source_to_visible_seconds=max(r['source_to_visible_seconds'] for r in outcomes),scope='actual 1Hz frames, worker HTTP/replay/fsync and installed PDA reader/alarm DOM in isolated Pi Chromium; five selected episodes; '+('Pi to Jetson to Pi SSH-relayed HTTP, excludes operating MES database and kiosk' if a.worker_url else 'Pi loopback HTTP, excludes Jetson and operating kiosk'))
 save(a.out/'result.json',summary);print('REALTIME_FINAL',json.dumps(summary),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--source-port',type=int,default=0);p.add_argument('--worker-url');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);run(a)
