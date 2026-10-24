"""Pi-only split generation and paired fixed-profile qualification.

Truth stays separate from sensor inputs. Generating a split does not import a detector.
"""
import argparse,copy,gzip,hashlib,json,math,secrets,time,uuid
from collections import Counter
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
from tempfile import TemporaryDirectory

def load(p):return json.loads(p.read_text())
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def p95(xs):return sorted(xs)[math.ceil(.95*len(xs))-1] if xs else None

def generate(a):
 from shiftlink.mes.progressive_factory import ProgressiveFactoryEngine,MECHANISMS
 from shiftlink.mes.configuration import from_payload
 from shiftlink.mes.contracts import Run
 cfg=from_payload(load(a.root/'deploy/analytics/source-config.json'));cases=[];used=set();counts=Counter();rejected=[]
 for previous in a.exclude:
  for c in load(previous/'manifest.json')['cases']:used.add(c['seed'])
 def engine(healthy=False):
  while True:
   seed=secrets.randbits(63)
   if seed not in used:used.add(seed);break
  nonce=uuid.uuid4().hex;e=ProgressiveFactoryEngine(Run.create(seed,datetime.now(timezone.utc),cfg.config_id),cfg,run_nonce=nonce)
  if healthy:e.scheduler.next_fault=10**12
  e.start();return e,seed,nonce
 def snap(e):
  f=json.loads(json.dumps(asdict(e.snapshot),default=lambda x:x.isoformat()));f['config_id']=cfg.config_id
  assert len(f['measurements'])==69 and not {'faults','truth','intensity','signal_targets'}&f.keys();return f
 def write(ident,kind,e,seed,nonce,frames,truth=None):
  path=a.out/'data'/(ident+'.json.gz');path.parent.mkdir(parents=True,exist_ok=True)
  with gzip.open(path,'wt',compresslevel=1) as z:json.dump(frames,z,separators=(',',':'))
  if truth:save(a.out/'private'/(ident+'.json'),truth)
  cases.append(dict(id=ident,kind=kind,seed=seed,nonce=nonce,run_id=e.run.run_id,frames=len(frames),sha256=sha(path)))
 quota=1 if a.split=='development' else 6
 for attempt in range(256):
  if all(counts[k]>=quota for k in MECHANISMS):break
  e,seed,nonce=engine();frames=[]
  while e.scheduler.active is None:e.tick();frames.append(snap(e))
  fault=copy.deepcopy(e.scheduler.active);kind=fault['kind']
  if counts[kind]>=quota:rejected.append(dict(seed=seed,nonce=nonce,kind=kind));continue
  begin=fault['start']
  while e.snapshot.sequence<begin+300:e.tick();frames.append(snap(e))
  end=e.snapshot.sequence;e.pause();paused=snap(e);e.repair_fault(fault['equipment_id']);e.resume()
  for _ in range(160):e.tick();frames.append(snap(e))
  counts[kind]+=1;write(f'{kind}-{counts[kind]:02d}',kind,e,seed,nonce,frames,dict(equipment_id=fault['equipment_id'],begin=begin,end=end,targets=list(fault['signal_targets']),paused=paused))
 else:raise RuntimeError('stratification quota')
 for n in range(4 if a.split=='development' else 16):
  e,seed,nonce=engine(True);frames=[]
  for _ in range(900):e.tick();frames.append(snap(e))
  write(f'normal-{n+1:02d}','normal',e,seed,nonce,frames)
 channels=[(e['equipment_id'],s) for e in load(a.root/'deploy/analytics/source-config.json')['equipment'] for s in e['signals'] if 'vib_rms' in s['signal']]
 for eq,spec in channels:
  for where in ('inside','outside'):
   e,seed,nonce=engine(True);frames=[];begin=secrets.randbelow(61)+180;end=begin+180;value=None
   for _ in range(end+100):
    e.tick();f=snap(e)
    if f['sequence']==begin:
     m=next(m for m in f['measurements'] if (m['equipment_id'],m['signal'])==(eq,spec['signal']))
     value=m['value'] if where=='inside' else spec['normal_max']+(spec['normal_max']-spec['normal_min'])*.5
    if begin<=f['sequence']<=end:
     m=next(m for m in f['measurements'] if (m['equipment_id'],m['signal'])==(eq,spec['signal']))
     m.update(value=value,quality='good',observed_at=f['simulated_at'])
    frames.append(f)
   write(f'stuck-{eq}-{where}','stuck_'+where,e,seed,nonce,frames,dict(equipment_id=eq,begin=begin,end=end,targets=[spec['signal']],value=value))
 assert len({c['run_id'] for c in cases})==len(cases)
 save(a.out/'manifest.json',dict(split=a.split,cases=cases,rejected_for_labels_only=rejected,sealed_before_analysis=True,exclude=[str(x) for x in a.exclude],generator_sha256=sha(a.root/'shiftlink/mes/progressive_factory.py')))
 print('GENERATED',a.split,len(cases),flush=True)

def evaluate(a):
 from scripts.mes_causal_active_advisory import ActiveAdvisorySource,ActiveAdvisorySession
 from shiftlink.pda.ai_insights import read_insights
 lock=load(a.out/'candidate-lock.json')
 def verify():assert all(sha(Path(p))==h for p,h in lock['files'].items())
 verify();manifest=load(a.out/'manifest.json');binding=ActiveAdvisorySource(load(a.root/'docs/research/evidence/mes-causal-v14c-20261023/settings.json'),load(a.root/'deploy/analytics/source-config.json'),load(a.profile));results=[];times=[];started=time.monotonic()
 with TemporaryDirectory(prefix='rms-qualify-',dir='/dev/shm') as tmp:
  for case in manifest['cases']:
   path=a.out/'data'/(case['id']+'.json.gz');assert sha(path)==case['sha256']
   with gzip.open(path,'rt') as z:frames=json.load(z)
   truth=None if case['kind']=='normal' else load(a.out/'private'/(case['id']+'.json'));session=ActiveAdvisorySession(binding,Path(tmp)/(case['id']+'.json'));session.defer_flush=True
   notices=[];seen=set();pause_done=False
   for f in frames:
    tick=f['sequence']
    if truth and truth.get('paused') and tick>truth['end'] and not pause_done:
     session.sync_stop(truth['paused'])
     if session.detector.warm:session.detector._restart();session.notices.clear();session.flush()
     if session.stop_dirty:session.flush()
     pause_done=True
    before=time.perf_counter();session.feed(f,binding.config_id)
    if tick%3==0 or tick==frames[-1]['sequence']:
     report=session.report(f);p=Path(tmp)/'latest.json';p.write_text(json.dumps(report));public=read_insights(p,f,binding.config_id)
     for item in public.get('items',[]):
      if item['event_id'] not in seen:seen.add(item['event_id']);notices.append(dict(sequence=item['sequence'],display_sequence=tick,equipment_id=item['equipment_id'],event_id=item['event_id']))
    times.append(time.perf_counter()-before)
   hits=[] if truth is None else [n for n in notices if n['equipment_id']==truth['equipment_id'] and truth['begin']<=n['sequence']<=truth['end']]
   row=dict(id=case['id'],kind=case['kind'],detected=bool(hits),duplicates=max(0,len(hits)-1),false_notifications=len(notices)-len(hits),delay=hits[0]['sequence']-truth['begin'] if hits else None,display_delay=hits[0]['display_sequence']-truth['begin'] if hits else None,notices=notices)
   results.append(row);save(a.out/(a.label+'-progress.json'),dict(completed=len(results),cases=results));print('CASE',a.label,case['id'],row['detected'],'fp',row['false_notifications'],'dup',row['duplicates'],'delay',row['delay'],flush=True)
 verify();positive=[r for r in results if r['kind']!='normal'];kinds=sorted({r['kind'] for r in positive})
 by_kind={k:dict(detected=sum(r['detected'] for r in positive if r['kind']==k),total=sum(r['kind']==k for r in positive),p95_delay=p95([r['delay'] for r in positive if r['kind']==k and r['detected']])) for k in kinds}
 summary=dict(profile_sha256=sha(a.profile),positive=len(positive),detected=sum(r['detected'] for r in positive),false_notifications=sum(r['false_notifications'] for r in results),normal_notifications=sum(r['false_notifications'] for r in results if r['kind']=='normal'),duplicates=sum(r['duplicates'] for r in positive),p95_delay=p95([r['delay'] for r in positive if r['detected']]),p95_simulated_display_delay=p95([r['display_delay'] for r in positive if r['detected']]),compute_p95_seconds=p95(times),frames=len(times),elapsed_seconds=time.monotonic()-started,by_kind=by_kind,latency_scope='offline Pi feed/report/reader; simulated three-frame display polling, excludes actual transport and rendering')
 gates=dict(no_misses=summary['detected']==summary['positive'],zero_false=summary['false_notifications']==0,zero_duplicates=summary['duplicates']==0,delay=summary['p95_delay'] is not None and summary['p95_delay']<=120,stuck_inside_delay=by_kind['stuck_inside']['p95_delay'] is not None and by_kind['stuck_inside']['p95_delay']<=15,one_second_compute=summary['compute_p95_seconds']<1)
 summary.update(gates=gates,passed=all(gates.values()));save(a.out/(a.label+'-result.json'),dict(summary=summary,cases=results));print('FINAL',json.dumps(summary),flush=True)

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['generate','evaluate']);p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--split',choices=['development','holdout']);p.add_argument('--exclude',action='append',type=Path,default=[]);p.add_argument('--profile',type=Path);p.add_argument('--label',default='candidate');a=p.parse_args()
 if a.action=='generate':
  assert a.split and not (a.out/'manifest.json').exists();generate(a)
 else:assert a.profile;evaluate(a)
if __name__=='__main__':main()
