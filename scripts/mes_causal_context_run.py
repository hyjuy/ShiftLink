"""Pi-only contextual calibration: normal fit, development, lock, fresh test."""
import argparse,copy,hashlib,json,math,random,secrets,time,sys
from datetime import datetime,timezone
from pathlib import Path
from scripts.mes_causal_context import ContextDetector,fit_profile,MODES,CONTEXT_MODES
from scripts.mes_causal_v14_stream import OnlineDetector
from shiftlink.mes.configuration import from_payload
from shiftlink.mes.contracts import Run
from shiftlink.mes.engine import MesEngine
from shiftlink.mes.signal_dynamics import SignalDynamics

ROOT=Path(__file__).resolve().parents[1]
KINDS=('oil_cooling','water_cooling','leak','friction','stuck','outlet_stuck','queue_mismatch','queue_stall')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False)
def load(p):return json.loads(Path(p).read_text())


def frames(config,role,mode,index,family,kind=None,ticks=224):
    identity=f'normal-context-v1:{role}:{mode}:{index}:{family}:{kind}';seed=int(hashlib.sha256(identity.encode()).hexdigest()[:12],16);rng=random.Random(seed)
    run_id=hashlib.sha256(identity.encode()).hexdigest()[:32];run=Run(run_id,seed,datetime(2026,10,1,tzinfo=timezone.utc),config_id=config['config_id']);engine=MesEngine(run,from_payload(config));engine.start();dynamics=SignalDynamics(engine.config,seed,identity)
    speed={'slow':.5,'nominal':1.,'fast':1.5,'unknown':1.}[mode.split(':')[0]];load_mode=mode.split(':')[1];previous=None
    for t in range(ticks):
        snap=engine.tick()
        if family=='dynamics':
            from dataclasses import replace
            snap=replace(snap,measurements=tuple(dynamics.values(snap.sequence,snap.simulated_at,snap.measurements,snap.equipment)))
        f=json.loads(json.dumps(snap.as_dict(),default=lambda x:x.isoformat()));f.update(config_id=config['config_id'],speed=speed)
        if mode.startswith('unknown:'):f.pop('speed')
        active_load=load_mode
        if kind=='normal_transition':
            active_load=('empty','moving','queued')[(t//60)%3];f['speed']=(.5,1.,1.5)[(t//60)%3]
        coils=[]
        if active_load=='moving':coils=[dict(coil_id=f'work-{t//7}',equipment_id='EQ-0006',position=(t%7)/8)]
        if active_load=='queued':coils=[dict(coil_id=f'queue-{t//5}',equipment_id='EQ-0009',position=1.)]
        if kind=='queue_mismatch' and t>=120:coils=[dict(coil_id=f'mismatch-{t//3}',equipment_id='EQ-0009',position=1.)]
        if kind=='queue_stall' and t>=120:coils=[dict(coil_id='stalled-work',equipment_id='EQ-0009',position=1.)]
        f['coils']=coils
        for m in f['measurements']:
            if m['signal']=='cv_queue_len':
                capacity=next(e['coil_capacity'] for e in config['equipment'] if e['equipment_id']==m['equipment_id'])
                m['value']=round(100*sum(c['equipment_id']==m['equipment_id'] and c['position']>=1 for c in coils)/capacity,3)
                if kind=='queue_mismatch' and t>=120 and m['equipment_id']=='EQ-0009':m['value']=0.
        if t==119:previous={(m['equipment_id'],m['signal']):m['value'] for m in f['measurements']}
        if kind and t>=120:
            strength=min(1.,(t-119)/16)
            for m in f['measurements']:
                eq,s=m['equipment_id'],m['signal']
                if kind=='oil_cooling' and eq=='EQ-0001' and 'temp' in s and 'water' not in s:m['value']+=6*strength
                if kind=='water_cooling' and eq=='EQ-0001' and 'water' in s and 'temp' in s:m['value']+=4*strength
                if kind=='leak' and eq=='EQ-0001' and ('flow' in s or 'pressure' in s):m['value']-=35*strength
                if kind=='friction' and eq=='EQ-0006' and ('current' in s or 'vib' in s):m['value']+=12*strength
                if kind=='stuck' and eq=='EQ-0006' and s=='rt_vib_rms':m['value']=previous[eq,s]
                if kind=='outlet_stuck' and eq=='EQ-0001' and s=='hpu_cooler_oil_out_temp':m['value']=previous[eq,s]
        yield f


def dataset(config,role,entries,out):
    out.mkdir(exist_ok=False);manifest=[]
    with (out/'features.jsonl').open('x') as file:
        for index,(mode,family,kind) in enumerate(entries):
            first=None
            for f in frames(config,role,mode,index,family,kind):
                if first is None:first=f
                file.write(json.dumps(f,separators=(',',':'))+'\n')
            target='EQ-0009' if kind and kind.startswith('queue') else 'EQ-0006' if kind in ('friction','stuck') else 'EQ-0001'
            identity=f'normal-context-v1:{role}:{mode}:{index}:{family}:{kind}'
            manifest.append(dict(seed=int(hashlib.sha256(identity.encode()).hexdigest()[:12],16),nonce=identity,run_id=first['run_id'],mode=mode,family=family,kind=kind,target=target,start=121,end=224,normal=kind is None or kind=='normal_transition'))
    save(out/'manifest.json',dict(role=role,runs=manifest,features_sha256=sha(out/'features.jsonl'),is_synthetic=True,normal_generator='MesEngine / SignalDynamics; queue fixture uses independent workpiece metadata',faults='separate additive/hold interventions; no PATTERNS import'))
    return manifest


def read(path):
    with Path(path).open() as f:
        for line in f:yield json.loads(line)


def evaluate(path,settings,profile):
    rows=load(path/'manifest.json')['runs'];by_run={r['run_id']:r for r in rows};events={'original':{},'candidate':{}};models={};costs=[]
    for f in read(path/'features.jsonl'):
        if not models or f['run_id']!=models['candidate'].run:
            models=dict(original=OnlineDetector(settings),candidate=ContextDetector(settings,profile))
            for d in models.values():d.config_id=profile['source_config_id']
        for name,d in models.items():
            t=time.monotonic();emitted=d.step(f)
            if name=='candidate':costs.append(time.monotonic()-t)
            if emitted:events[name].setdefault(f['run_id'],[]).extend((f['sequence'],e) for e in sorted(emitted))
    result={}
    for name,all_events in events.items():
        detected=[];delays=[];normal=duplicates=unmatched=0;per=[];normal_cases=[]
        for r in rows:
            notices=all_events.get(r['run_id'],[])
            if r['normal']:normal+=len(notices);normal_cases.append(dict(run_id=r['run_id'],mode=r['mode'],family=r['family'],notices=notices));continue
            hits=[t for t,e in notices if e==r['target'] and r['start']<=t<=r['end']]
            if hits:detected.append(r['run_id']);delays.append(min(hits)-r['start'])
            duplicates+=max(0,len(hits)-1);unmatched+=sum(not (e==r['target'] and r['start']<=t<=r['end']) for t,e in notices)
            per.append(dict(run_id=r['run_id'],mode=r['mode'],kind=r['kind'],detected=bool(hits),delay=min(hits)-r['start'] if hits else None,notices=notices))
        result[name]=dict(events=sum(not r['normal'] for r in rows),detected=len(detected),detected_runs=detected,normal_notices=normal,duplicates=duplicates,unmatched=unmatched,p95=sorted(delays)[math.ceil(.95*len(delays))-1] if delays else None,cases=per,normal_cases=normal_cases)
    a,b=result['original'],result['candidate'];common=set(a['detected_runs'])&set(b['detected_runs']);pa={r['run_id']:r['delay'] for r in a['cases']};pb={r['run_id']:r['delay'] for r in b['cases']}
    differences=sorted(pb[r]-pa[r] for r in common)
    result['checks']=dict(normal_zero=b['normal_notices']==0,no_detection_lost=set(a['detected_runs'])<=set(b['detected_runs']),sensitivity=b['detected']>=.95*b['events'],duplicates_zero=b['duplicates']==0,delay_not_worse=not differences or differences[math.ceil(.95*len(differences))-1]<=2)
    result['candidate_processing_p95']=sorted(costs)[math.ceil(.95*len(costs))-1];result['scope']='synthetic intervention replay, excludes network/UI; paired normal generators are shared'
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--phase',choices=('develop','freeze','test'),required=True);a=p.parse_args();out=a.out
    config=load(ROOT/'deploy/analytics/source-config.json');settings=load(ROOT/'docs/research/evidence/mes-causal-v14c-20261023/settings.json')
    if a.phase=='develop':
        out.mkdir(exist_ok=False);entries=[(m,f,None) for m in MODES for f in ('mes','dynamics')]
        dataset(config,'train',entries,out/'train');profile=fit_profile(read(out/'train/features.jsonl'),config,settings);profile['training_sha256']=sha(out/'train/features.jsonl');save(out/'profile.json',profile)
        modes=['slow:empty','nominal:moving','fast:queued'];entries=[(m,f,None) for m in modes for f in ('mes','dynamics')]+[(m,'dynamics',k) for m in modes for k in KINDS]
        dataset(config,'development',entries,out/'development');r=evaluate(out/'development',settings,profile);save(out/'development-result.json',r);print(json.dumps({k:v for k,v in r.items() if k not in ('original','candidate')}),flush=True)
        print('DEVELOPMENT',json.dumps({n:{k:v for k,v in r[n].items() if k not in ('cases','detected_runs')} for n in ('original','candidate')}),flush=True)
    elif a.phase=='freeze':
        r=load(out/'development-result.json');assert all(r['checks'].values()),'development failed; cannot freeze'
        for name in ('transitions','replay-development'):
            assert all(load(out/(name+'-result.json'))['checks'].values()),name+' development failed'
        files={str(p):sha(p) for p in (ROOT/'scripts/mes_causal_context.py',ROOT/'scripts/mes_causal_context_run.py',ROOT/'tests/test_mes_causal_context.py',ROOT/'scripts/mes_causal_pda_service.py',ROOT/'scripts/mes_causal_context_validate.py',out/'profile.json',ROOT/'deploy/analytics/source-config.json',ROOT/'shiftlink/mes/engine.py',ROOT/'shiftlink/mes/signal_dynamics.py',ROOT/'docs/research/evidence/mes-causal-v14c-20261023/settings.json')};save(out/'lock.json',dict(status='frozen_before_test',test_role='unused-'+secrets.token_hex(16),files=files))
    else:
        lock=load(out/'lock.json');assert all(sha(p)==v for p,v in lock['files'].items())
        assert not (out/'test').exists();entries=[(m,f,None) for m in CONTEXT_MODES for f in ('mes','dynamics')]+[(m,f,'normal_transition') for m in ('slow:empty','nominal:moving','fast:queued') for f in ('mes','dynamics')]+[(m,('mes' if i%2 else 'dynamics'),k) for m in CONTEXT_MODES for i,k in enumerate(KINDS)]
        dataset(config,lock['test_role'],entries,out/'test');r=evaluate(out/'test',settings,load(out/'profile.json'));assert all(sha(p)==v for p,v in lock['files'].items());splits={name:load(out/name/'manifest.json')['runs'] for name in ('train','development','transitions','replay-development','test')};overlap={}
        for field in ('run_id','seed','nonce'):
            sets={name:{row[field] for row in rows} for name,rows in splits.items()};overlap[field]=all(not(sets[a]&sets[b]) for i,a in enumerate(sets) for b in list(sets)[i+1:])
        assert all(overlap.values()),'split identity overlap'
        r['integrity']=dict(candidate_unchanged=True,roles_disjoint=overlap,training_sha256=sha(out/'train/features.jsonl'),test_sha256=sha(out/'test/features.jsonl'));
        save(out/'test-result.json',r);print('TEST',json.dumps({n:{k:v for k,v in r[n].items() if k not in ('cases','detected_runs')} for n in ('original','candidate')}),r['checks'],flush=True)

if __name__=='__main__':main()
