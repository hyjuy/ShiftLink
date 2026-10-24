"""Pi-only development/freeze/unseen comparison for notice-episode candidate."""
from pathlib import Path
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,gzip,hashlib,importlib.util,json,math,random,secrets,time
from datetime import datetime,timezone
from scripts.mes_causal_pda_service import AdvisorySession,BoundSource
from scripts.mes_causal_episode import EpisodeSource
ROOT=Path(__file__).resolve().parents[1]
OLD=Path('/home/pi/shiftlink/analytics/validation/random-injection-20261024')
RELEASE=Path('/home/pi/shiftlink/analytics/releases/normal-context-v1-pda-20261024-r5-manual-stop')

def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,allow_nan=False))
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def zipped(p,x):
 with gzip.open(p,'wt') as f:json.dump(x,f,separators=(',',':'))
def unzip(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def p95(x):return sorted(x)[math.ceil(.95*len(x))-1] if x else None

def source_generator():
 assert sha(OLD/'random_test.py')==load(OLD/'freeze.json')['script_sha256']
 spec=importlib.util.spec_from_file_location('frozen_intervention_generator',OLD/'random_test.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def setup(out):
 raw=load(out/'fresh-source.json')['snapshots'];assert len(raw)>=704
 assert all(f['line_mode']=='running' and not f['active_alarms'] for f in raw)
 assert all(b['sequence']==a['sequence']+1 for a,b in zip(raw,raw[1:]))
 cut=(len(raw)-64)//2;dev=raw[:cut];test=raw[cut+64:];zipped(out/'development-source.json.gz',dev);zipped(out/'sealed-test-source.json.gz',test)
 save(out/'split.json',dict(source_run=raw[0]['run_id'],development=[dev[0]['sequence'],dev[-1]['sequence']],purge_frames=64,test=[test[0]['sequence'],test[-1]['sequence']],development_sha256=sha(out/'development-source.json.gz'),test_sha256=sha(out/'sealed-test-source.json.gz'),shared_source_run=True,disjoint_source_times=True,previous_test_source_max_sequence=1724))
 make_data(out,'development')

def make_data(out,role):
 if role=='test':verify_freeze(out)
 split=load(out/'split.json');source=out/('development-source.json.gz' if role=='development' else 'sealed-test-source.json.gz');assert sha(source)==split['development_sha256' if role=='development' else 'test_sha256'];base=unzip(source)
 folder=out/role;folder.mkdir(exist_ok=False);(folder/'cases').mkdir();g=source_generator();seed=secrets.randbits(63);rng=random.Random(seed);nonce=secrets.token_hex(16);epoch=datetime.now(timezone.utc);config=load(RELEASE/'deploy/analytics/source-config.json');cases=[]
 schedule=[]
 for kind in g.KINDS:
  for rep in (range(4) if role=='test' or kind in ('friction','variance') else [1,3]):schedule.append((kind,rep))
 for kind in ('normal','spike','bad_quality'):
  for rep in range((8 if kind!='bad_quality' else 4) if role=='test' else 4):schedule.append((kind,rep))
 for rep in range(8 if role=='test' else 4):schedule.append(('nearby',rep))
 for index,(kind,rep) in enumerate(schedule):
  ident=f'{kind}-{rep:02}';rid=hashlib.sha256((nonce+ident).encode()).hexdigest()[:32];offset=rng.randrange(0,len(base)-320+1);frames=g.frames_from(base,offset,rid,epoch,config['config_id']);events=[]
  if kind=='nearby':
   gap=([5,12,24,5] if role=='development' else [5,12,24,48,5,12,24,48])[rep]
   first=g.make_event('friction',2,rng,96);first.update(equipment_id='EQ-0004',end=132)
   second=g.make_event('sensor_bias',2,rng,132+gap);second.update(equipment_id='EQ-0005' if rep%4==3 else 'EQ-0004',signal='gr_oil_level',sign=-1,end=168+gap)
   events=[first,second]
  elif kind!='normal':
   start=rng.randint(112,144);event=g.make_event(kind if kind not in ('spike','bad_quality') else 'sensor_bias',min(rep,3),rng,start);event['kind']=kind
   if kind=='spike':event['end']=start+1
   events=[event]
  for event in events:g.inject(frames,event)
  path=folder/'cases'/(ident+'.json.gz');zipped(path,frames)
  cases.append(dict(id=ident,kind=kind,run_id=rid,source_offset=offset,events=events,sha256=sha(path),positive=kind in g.KINDS or kind=='nearby'))
 previous=load(OLD/'plan.json');previous_ids={c['run_id'] for c in previous['cases']}
 assert not previous_ids.intersection(c['run_id'] for c in cases)
 if role=='test':
  dev=load(out/'development/manifest.json');assert seed!=dev['seed'] and nonce!=dev['nonce'] and not {c['run_id'] for c in cases}&{c['run_id'] for c in dev['cases']}
 save(folder/'manifest.json',dict(role=role,seed=seed,nonce=nonce,cases=cases,source_sha256=sha(source),generator_sha256=sha(OLD/'random_test.py'),context='new random interventions on disjoint time blocks from one shared synthetic source run; not an independent field domain'))
 print('DATA_READY',role,len(cases),flush=True)

def freeze(out):
 comparison=load(out/'development/comparison.json');assert comparison['passed'],'development gates must pass before freeze'
 paths=['scripts/mes_causal_episode.py','scripts/mes_causal_episode_validate.py','scripts/mes_causal_context.py','scripts/mes_causal_v14_stream.py','scripts/mes_causal_pda_service.py','tests/test_mes_causal_episode.py']
 pinned={p:sha(ROOT/p) for p in paths};save(out/'candidate-lock.json',dict(files=pinned,development_manifest_sha256=sha(out/'development/manifest.json'),split_sha256=sha(out/'split.json'),before_unseen_data_generation=True,selection='fixed score model; one equipment episode; five valid healthy frames at two-thirds exit bound; no fault-score retraining',criteria='no previously detected incident lost; identical first frame for common detections; normal/spike/quality and unmatched counts not increased; duplicates zero; paired delay p95 not increased'))
 print('CANDIDATE_FROZEN',flush=True)

def verify_freeze(out):
 lock=load(out/'candidate-lock.json');assert all(sha(ROOT/p)==h for p,h in lock['files'].items());assert sha(out/'split.json')==lock['split_sha256'];assert sha(out/'development/manifest.json')==lock['development_manifest_sha256']

def evaluate(out,role,model):
 if role=='test':verify_freeze(out)
 manifest=load(out/role/'manifest.json');folder=out/role/model;folder.mkdir(exist_ok=False);settings=load(RELEASE/'docs/research/evidence/mes-causal-v14c-20261023/settings.json');config=load(RELEASE/'deploy/analytics/source-config.json');profile=load(RELEASE/'deploy/analytics/normal-profile.json');binding=(EpisodeSource if model=='candidate' else BoundSource)(settings,config,profile);rows=[]
 for case in manifest['cases']:
  path=out/role/'cases'/(case['id']+'.json.gz');assert sha(path)==case['sha256'];frames=unzip(path);session=AdvisorySession(binding,folder/(case['id']+'-checkpoint.json'));session.defer_flush=True;notices=[]
  for frame in frames:
   for eq in sorted(session.feed(frame,binding.config_id)):notices.append(dict(sequence=frame['sequence'],equipment_id=eq))
  session.flush();incidents=[];matched=0
  if case['positive']:
   for i,event in enumerate(case['events']):
    hits=[n for n in notices if n['equipment_id']==event['equipment_id'] and event['start']<=n['sequence']-1<event['end']];matched+=len(hits)
    incidents.append(dict(key=case['id']+':'+str(i),kind=event['kind'],detected=bool(hits),first=hits[0]['sequence'] if hits else None,delay=hits[0]['sequence']-1-event['start'] if hits else None,duplicates=max(0,len(hits)-1)))
  row=dict(id=case['id'],kind=case['kind'],positive=case['positive'],incidents=incidents,unmatched=len(notices)-matched,notices=notices);rows.append(row);save(folder/'progress.json',rows);print('CASE',role,model,case['id'],[x['detected'] for x in incidents],'notices',len(notices),flush=True)
 events=[e for r in rows for e in r['incidents']];result=dict(model=model,cases=len(rows),frames=len(rows)*320,detected=sum(e['detected'] for e in events),total=len(events),duplicates=sum(e['duplicates'] for e in events),unmatched=sum(r['unmatched'] for r in rows if r['positive']),normal=sum(len(r['notices']) for r in rows if r['kind']=='normal'),spike=sum(len(r['notices']) for r in rows if r['kind']=='spike'),quality=sum(len(r['notices']) for r in rows if r['kind']=='bad_quality'),delay_p95_frames=p95([e['delay'] for e in events if e['detected']]),rows=rows)
 save(folder/'result.json',result);print('EVALUATION_DONE',role,model,{k:v for k,v in result.items() if k!='rows'},flush=True)

def compare(out,role):
 original=load(out/role/'original/result.json');candidate=load(out/role/'candidate/result.json');a={e['key']:e for r in original['rows'] for e in r['incidents']};b={e['key']:e for r in candidate['rows'] for e in r['incidents']};assert set(a)==set(b)
 lost=[k for k in a if a[k]['detected'] and not b[k]['detected']];deltas={k:b[k]['first']-a[k]['first'] for k in a if a[k]['detected'] and b[k]['detected']};gates=dict(no_detection_loss=not lost,first_notices_unchanged=all(x==0 for x in deltas.values()),duplicates_zero=candidate['duplicates']==0,normal_zero=candidate['normal']==0,spike_zero=candidate['spike']==0,quality_not_increased=candidate['quality']<=original['quality'],unmatched_not_increased=candidate['unmatched']<=original['unmatched'],p95_not_increased=candidate['delay_p95_frames'] is not None and candidate['delay_p95_frames']<=original['delay_p95_frames'])
 result=dict(role=role,passed=all(gates.values()),gates=gates,lost=lost,common_first_deltas=deltas,original={k:v for k,v in original.items() if k!='rows'},candidate={k:v for k,v in candidate.items() if k!='rows'});save(out/role/'comparison.json',result);print('COMPARISON',json.dumps(result),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--phase',choices=['setup','freeze','make-test','evaluate','compare'],required=True);p.add_argument('--role',choices=['development','test'],default='development');p.add_argument('--model',choices=['original','candidate'],default='candidate');a=p.parse_args()
 if a.phase=='setup':setup(a.out)
 elif a.phase=='freeze':freeze(a.out)
 elif a.phase=='make-test':make_data(a.out,'test')
 elif a.phase=='evaluate':evaluate(a.out,a.role,a.model)
 else:compare(a.out,a.role)
