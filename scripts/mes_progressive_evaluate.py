"""Frozen progressive-generator qualification against the installed Pi release."""
import argparse, gzip, hashlib, json, math, secrets, sys, time, uuid
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--release',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
sys.path.insert(0,str(a.source_root));sys.path.insert(1,str(a.release))
# Select the unchanged installed analysis package, with the new generator isolated.
import scripts
scripts.__path__=[str(a.release/'scripts')]
import shiftlink.pda
shiftlink.pda.__path__=[str(Path('/home/pi/shiftlink/app/shiftlink/pda'))]
from scripts.mes_causal_active_advisory import ActiveAdvisorySource, ActiveAdvisorySession
from shiftlink.mes.progressive_factory import ProgressiveFactoryEngine, MECHANISMS
from shiftlink.mes.configuration import from_payload
from shiftlink.mes.contracts import Run
from shiftlink.pda.ai_insights import read_insights

def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False))
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def percentile(x):return sorted(x)[math.ceil(.95*len(x))-1] if x else None
def verify():
 lock=load(a.out/'candidate-lock.json');assert all(sha(Path(p))==h for p,h in lock['files'].items())
 assert sha(a.out/'protocol.json')==lock['protocol_sha256']

def snapshot(engine):
 f=json.loads(json.dumps(asdict(engine.snapshot),default=lambda x:x.isoformat()))
 f['config_id']=engine.config.config_id
 assert len(f['measurements'])==69
 assert not {'truth','faults','signal_targets','intensity'}&f.keys()
 return f

def generate():
 verify();cfg=from_payload(load(a.release/'deploy/analytics/source-config.json'));counts=Counter();cases=[];rejected=[]
 for attempt in range(256):
  if all(counts[k]==6 for k in MECHANISMS):break
  seed=secrets.randbits(63);nonce=uuid.uuid4().hex
  engine=ProgressiveFactoryEngine(Run.create(seed,datetime.now(timezone.utc),cfg.config_id),cfg,run_nonce=nonce);engine.start();frames=[]
  while engine.scheduler.active is None:
   engine.tick();frames.append(snapshot(engine))
  fault=dict(engine.scheduler.active);kind=fault['kind']
  if counts[kind]>=6:rejected.append(dict(seed=seed,nonce=nonce,kind=kind));continue
  begin=fault['start']
  while engine.snapshot.sequence<begin+300:engine.tick();frames.append(snapshot(engine))
  end=engine.snapshot.sequence;engine.pause();paused=snapshot(engine);engine.repair_fault(fault['equipment_id']);engine.resume()
  for _ in range(160):engine.tick();frames.append(snapshot(engine))
  assert engine.scheduler.active is None
  counts[kind]+=1;ident=f'{kind}-{counts[kind]:02d}'
  path=a.out/'data'/(ident+'.json.gz');path.parent.mkdir(exist_ok=True)
  with gzip.open(path,'wt',encoding='utf-8',compresslevel=1) as z:json.dump(frames,z,separators=(',',':'))
  save(a.out/'private'/(ident+'.json'),dict(fault=fault,repair_sequence=end,paused=paused))
  cases.append(dict(id=ident,kind=kind,seed=seed,nonce=nonce,run_id=engine.run.run_id,frames=len(frames),sha256=sha(path)))
 else:raise RuntimeError('could not fill preregistered kind quotas')
 for n in range(8):
  seed=secrets.randbits(63);nonce=uuid.uuid4().hex
  engine=ProgressiveFactoryEngine(Run.create(seed,datetime.now(timezone.utc),cfg.config_id),cfg,run_nonce=nonce);engine.scheduler.next_fault=10**12;engine.start();frames=[]
  for _ in range(900):engine.tick();frames.append(snapshot(engine))
  assert engine.scheduler.active is None
  ident=f'normal-{n+1:02d}';path=a.out/'data'/(ident+'.json.gz')
  with gzip.open(path,'wt',encoding='utf-8',compresslevel=1) as z:json.dump(frames,z,separators=(',',':'))
  cases.append(dict(id=ident,kind='normal',seed=seed,nonce=nonce,run_id=engine.run.run_id,frames=len(frames),sha256=sha(path)))
 assert len({c['seed'] for c in cases})==len(cases) and len({c['run_id'] for c in cases})==len(cases)
 save(a.out/'manifest.json',dict(cases=cases,rejected_for_stratification=rejected,accepted_by_labels_only=True,sealed_before_analysis=True,generator_sha256=sha(a.source_root/'shiftlink/mes/progressive_factory.py')))
 print('DATA_READY',len(cases),dict(counts),flush=True)

def evaluate():
 verify();manifest=load(a.out/'manifest.json');binding=ActiveAdvisorySource(load(a.release/'docs/research/evidence/mes-causal-v14c-20261023/settings.json'),load(a.release/'deploy/analytics/source-config.json'),load(a.release/'deploy/analytics/normal-profile.json'))
 assert str(sys.modules[ActiveAdvisorySource.__module__].__file__).startswith(str(a.release))
 results=[];times=[];start=time.monotonic();config=binding.config_id
 with TemporaryDirectory(prefix='progressive-eval-',dir='/dev/shm') as temp:
  temp=Path(temp)
  for case in manifest['cases']:
   path=a.out/'data'/(case['id']+'.json.gz');assert sha(path)==case['sha256']
   with gzip.open(path,'rt',encoding='utf-8') as z:frames=json.load(z)
   event=None if case['kind']=='normal' else load(a.out/'private'/(case['id']+'.json'))
   session=ActiveAdvisorySession(binding,temp/(case['id']+'-checkpoint.json'));session.defer_flush=True
   raw=[];shown=[];seen=set();consecutive=0;observable=None;pause_done=False
   for frame in frames:
    tick=frame['sequence']
    if event and tick>event['repair_sequence'] and not pause_done:
     session.sync_stop(event['paused'])
     if session.detector.warm:
      session.detector._restart();session.notices.clear();session.flush()
     if session.stop_dirty:session.flush()
     pause_done=True
    before=time.perf_counter();emitted=session.feed(frame,config)
    for eq in sorted(emitted):raw.append(dict(sequence=tick,equipment_id=eq))
    if tick%3==0 or tick==frames[-1]['sequence']:
     report=session.report(frame);report_path=temp/'latest.json';report_path.write_text(json.dumps(report))
     public=read_insights(report_path,frame,config)
     for item in public.get('items',[]):
      if item['event_id'] not in seen:
       seen.add(item['event_id']);shown.append(dict(sequence=item['sequence'],display_sequence=tick,equipment_id=item['equipment_id'],event_id=item['event_id']))
    times.append(time.perf_counter()-before)
    if event and event['fault']['start']<=tick<=event['repair_sequence']:
     fault=event['fault']
     outside=any(m['equipment_id']==fault['equipment_id'] and m['signal'] in fault['signal_targets'] and m['quality']=='good' and not binding_reference[(m['equipment_id'],m['signal'])]['normal_min']<=m['value']<=binding_reference[(m['equipment_id'],m['signal'])]['normal_max'] for m in frame['measurements'])
     consecutive=consecutive+1 if outside else 0
     if consecutive>=3 and observable is None:observable=tick-2
   if event:
    fault=event['fault'];hits=[n for n in shown if n['equipment_id']==fault['equipment_id'] and fault['start']<=n['sequence']<=event['repair_sequence']]
    first=hits[0] if hits else None
    row=dict(id=case['id'],kind=case['kind'],detected=bool(hits),begin=fault['start'],repair=event['repair_sequence'],observable=observable,equipment_id=fault['equipment_id'],duplicates=max(0,len(hits)-1),unmatched=len(shown)-len(hits),latent_delay=None if first is None else first['sequence']-fault['start'],observable_delay=None if first is None or observable is None else max(0,first['sequence']-observable),display_delay=None if first is None else first['display_sequence']-fault['start'],notices=shown,raw_notices=raw)
   else:row=dict(id=case['id'],kind='normal',false_notifications=len(shown),notices=shown,raw_notices=raw)
   results.append(row);save(a.out/'progress.json',dict(completed=len(results),cases=results,elapsed=time.monotonic()-start))
   print('CASE',case['id'],'detected',row.get('detected'),'normal_fp',row.get('false_notifications'),'unmatched',row.get('unmatched'),'duplicates',row.get('duplicates'),flush=True)
 verify();positive=[r for r in results if r['kind']!='normal'];normal=[r for r in results if r['kind']=='normal']
 by_kind={k:dict(detected=sum(r['detected'] for r in positive if r['kind']==k),total=sum(r['kind']==k for r in positive),duplicates=sum(r['duplicates'] for r in positive if r['kind']==k),unmatched=sum(r['unmatched'] for r in positive if r['kind']==k)) for k in MECHANISMS}
 summary=dict(positive_cases=len(positive),detected=sum(r['detected'] for r in positive),normal_cases=len(normal),normal_frames=8*900,normal_notifications=sum(r['false_notifications'] for r in normal),duplicates=sum(r['duplicates'] for r in positive),unmatched=sum(r['unmatched'] for r in positive),p95_latent_seconds=percentile([r['latent_delay'] for r in positive if r['detected']]),p95_observable_seconds=percentile([r['observable_delay'] for r in positive if r['observable_delay'] is not None]),p95_simulated_display_seconds=percentile([r['display_delay'] for r in positive if r['detected']]),compute_p95_seconds=percentile(times),frames=len(times),elapsed_seconds=time.monotonic()-start,by_kind=by_kind,model_files_unchanged=True,latency_scope='offline feed/report/reader compute plus separately simulated three-frame polling; no real network or Chromium display timing')
 gates=dict(recall=summary['detected']/24>=.95,all_kinds_no_misses=all(v['detected']==v['total'] for v in by_kind.values()),normal_zero=summary['normal_notifications']==0,unmatched_zero=summary['unmatched']==0,duplicates_zero=summary['duplicates']==0,latent_delay=summary['p95_latent_seconds'] is not None and summary['p95_latent_seconds']<=120,observable_delay=summary['p95_observable_seconds'] is not None and summary['p95_observable_seconds']<=15,one_second_compute=summary['compute_p95_seconds']<=1)
 summary.update(gates=gates,passed=all(gates.values()));save(a.out/'result.json',dict(summary=summary,cases=results));print('FINAL',json.dumps(summary),flush=True)

binding_reference={(e['equipment_id'],s['signal']):s for e in load(a.release/'deploy/analytics/source-config.json')['equipment'] for s in e['signals']}
if not (a.out/'manifest.json').exists():generate()
evaluate()