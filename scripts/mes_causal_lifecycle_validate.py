"""Pi-only fault lifecycle data: latent fault persists until scheduled repair, truth never enters detector."""
from pathlib import Path
import argparse,copy,hashlib,json,random,secrets
from datetime import datetime,timezone
from scripts import mes_causal_episode_validate as prior
from scripts.mes_causal_lifecycle import LifecycleSource
ROOT=Path(__file__).resolve().parents[1]
FRAMES=448
LIFECYCLES=('persistent','progressive','intermittent')
save,load,sha,zipped,unzip=prior.save,prior.load,prior.sha,prior.zipped,prior.unzip

def zipped(p,x):
    import gzip
    with gzip.open(p,'wb',compresslevel=1) as f:f.write(json.dumps(x,separators=(',',':')).encode('utf-8'))

def sensor_signature(frame):
    values=[(m['equipment_id'],m['signal'],m['value'],m['quality'],m['observed_at']==frame['simulated_at']) for m in frame['measurements']]
    return hashlib.sha256(json.dumps(values,separators=(',',':')).encode()).hexdigest()

def setup(out):
    from shiftlink.mes.configuration import from_payload
    from shiftlink.mes.contracts import Run
    from shiftlink.mes.engine import MesEngine
    config=from_payload(load(prior.RELEASE/'deploy/analytics/source-config.json'));assert config.config_id==load(prior.RELEASE/'deploy/analytics/source-config.json')['config_id']
    old=load(prior.OLD/'observed-replay.json')['snapshots']+load(out.parent/'episode-notices-20261024/fresh-source.json')['snapshots']
    prior_signatures={sensor_signature(f) for f in old};sources={};provenance={};seeds=set()
    for role in ('development','test'):
        seed=secrets.randbits(63)
        while seed in seeds:seed=secrets.randbits(63)
        seeds.add(seed);run=Run.create(seed,datetime.now(timezone.utc),config.config_id);engine=MesEngine(run,config);engine.start();frames=[]
        for tick in range(1024):
            f=json.loads(json.dumps(engine.tick().as_dict(),default=lambda x:x.isoformat()));f['config_id']=config.config_id
            assert f['scenario_id']=='normal' and not f['active_alarms'] and all(e['fault_level']=='normal' and e['operating_state']=='running' for e in f['equipment'])
            if tick>=64:frames.append(f)
        signatures={sensor_signature(f) for f in frames};assert not signatures&prior_signatures,'normal source repeats previous sensor values'
        sources[role]=frames;provenance[role]=dict(run_id=run.run_id,normal_seed=seed,source_sequences=[65,1024],discarded_initial_frames=64,exact_sensor_frame_overlap_with_prior=len(signatures&prior_signatures))
        path=out/('development-source.json.gz' if role=='development' else 'sealed-test-source.json.gz');zipped(path,frames);provenance[role]['sha256']=sha(path)
    assert not {sensor_signature(f) for f in sources['development']}&{sensor_signature(f) for f in sources['test']}
    save(out/'split.json',dict(development_run=provenance['development']['run_id'],test_run=provenance['test']['run_id'],development=[65,1024],test=[65,1024],burnin_frames_per_independent_run=64,development_sha256=provenance['development']['sha256'],test_sha256=provenance['test']['sha256'],independent_normal_seeds=True,exact_sensor_frame_overlap=0,shared_synthetic_normal_generator=True))
    files=['shiftlink/mes/engine.py','shiftlink/mes/contracts.py','shiftlink/mes/configuration.py','shiftlink/mes/signal_semantics.py','shiftlink/mes/scenarios/priority.py']
    save(out/'normal-source-provenance.json',dict(streams=provenance,engine='in-memory MesEngine on Pi; no operating MES commands or service changes',generator_files={p:sha(ROOT/p) for p in files},prior_source_frames=len(old),development_test_sensor_overlap=0,normal_generator_shared=True))
    save(out/'protocol.json',dict(frames=FRAMES,lifecycles=LIFECYCLES,latent_fault='start until repair exclusive, even when symptoms are quiet',maximum_intermittent_gap_frames=20,minimum_first_burst_frames=32,recovery_frames=32,new_distinct_evidence_after_old_recovery_frames=5,post_repair_same_sensor_gap_frames=64,no_repair_or_event_label_in_model_input=True,no_score_training=True,limitations='A sensor-only detector cannot distinguish identical same-sensor observations from an unobserved repair/new failure. Thirty-two healthy frames are observation-based recovery, not proof of repair. Normal seeds and exact sensor trajectories are disjoint, but synthetic normal generator and fault mechanisms remain shared.'))
    make_data(out,'development')

def frames_from(g,base,offset,rid,epoch,config_id):
    # Existing frozen helper rebases the first 320 frames. Apply identical time mapping to the rest.
    selected=copy.deepcopy(base[offset:offset+FRAMES]);assert len(selected)==FRAMES
    from datetime import timedelta
    for i,f in enumerate(selected):
        old=datetime.fromisoformat(f['simulated_at'].replace('Z','+00:00'));new=epoch+timedelta(seconds=i)
        f.update(run_id=rid,sequence=i+1,simulated_at=new.isoformat(),config_id=config_id)
        for m in f['measurements']:
            if m.get('observed_at') is not None:m['observed_at']=(datetime.fromisoformat(m['observed_at'].replace('Z','+00:00'))+(new-old)).isoformat()
    return selected

def apply_lifecycle(g,frames,event,rng):
    start,end=event['start'],event['repair'];mode=event['lifecycle'];assert 0<start<end<=len(frames)
    segments=[]
    if mode=='intermittent':
        cursor=start;first=True
        while cursor<end:
            finish=min(end,cursor+(32 if first else rng.randint(18,32)));segments.append([cursor,finish]);first=False
            cursor=finish+rng.randint(4,20)
    else:segments=[[start,end]]
    pristine=copy.deepcopy(frames) if mode=='progressive' else None
    for a,b in segments:
        patch=dict(event,start=a,end=b,ramp=1 if mode=='progressive' else min(event['ramp'],3) if mode=='intermittent' else event['ramp'])
        g.inject(frames,patch)
    if mode=='progressive':
        span=end-start
        for i in range(start,end):
            factor=min(1.,(i-start+1)/max(1,span-32))
            for before,after in zip(pristine[i]['measurements'],frames[i]['measurements']):
                if before['equipment_id']==event['equipment_id'] and before['quality']=='good':after['value']=round(before['value']+factor*(after['value']-before['value']),6)
        if event['kind']=='sensor_stuck':
            # Growing sample-and-hold intervals simulate worsening acquisition stalls; final 32 frames are stuck.
            signal=event['signal'];frozen=None;release=start
            for i in range(start,end):
                before=next(m for m in pristine[i]['measurements'] if m['equipment_id']==event['equipment_id'] and m['signal']==signal)
                after=next(m for m in frames[i]['measurements'] if m['equipment_id']==event['equipment_id'] and m['signal']==signal)
                if i==end-32:frozen=before['value'];release=end
                elif i>=release:
                    frozen=before['value'];release=end if i>=end-32 else i+max(1,int(1+24*(i-start)/span))
                after['value']=frozen
    event['symptom_segments']=segments
    event['end']=end
    return event

def make_data(out,role):
    if role=='test':verify_freeze(out)
    split=load(out/'split.json');source=out/('development-source.json.gz' if role=='development' else 'sealed-test-source.json.gz')
    assert sha(source)==split['development_sha256' if role=='development' else 'test_sha256']
    base=unzip(source);folder=out/role;folder.mkdir(exist_ok=False);(folder/'cases').mkdir();g=prior.source_generator();seed=secrets.randbits(63);nonce=secrets.token_hex(16);rng=random.Random(seed);epoch=datetime.now(timezone.utc);cases=[];schedule=[]
    for kind in g.KINDS:
        for mode in LIFECYCLES:
            for severity in ([2] if role=='development' else [1,3]):schedule.append((kind,mode,severity))
    for kind,count in [('normal',3 if role=='development' else 5),('spike',3 if role=='development' else 5),('bad_quality',2)]:
        for rep in range(count):schedule.append((kind,'control',rep))
    for kind in ['post_repair','nearby']:
        for rep in range(4):schedule.append((kind,'persistent',rep))
    config=load(prior.RELEASE/'deploy/analytics/source-config.json')
    for index,(kind,mode,severity) in enumerate(schedule):
        ident=f'{index:03}-{kind}-{mode}-{severity}';rid=hashlib.sha256((nonce+ident).encode()).hexdigest()[:32];offset=rng.randrange(len(base)-FRAMES+1)
        frames=frames_from(g,base,offset,rid,epoch,config['config_id']);events=[]
        if kind=='post_repair':
            mechanism=['friction','variance','sensor_bias','sensor_stuck'][severity];a=g.make_event(mechanism,2,rng,96);a.update(repair=168,lifecycle='persistent');b=copy.deepcopy(a);b.update(start=232,repair=344,seed=rng.getrandbits(63));events=[a,b]
        elif kind=='nearby':
            gap=[5,12,24,48][severity];a=g.make_event('friction',2,rng,96);a.update(equipment_id='EQ-0004',repair=132,lifecycle='persistent')
            b=g.make_event('sensor_bias',2,rng,132+gap);b.update(equipment_id='EQ-0005' if severity==3 else 'EQ-0004',signal='gr_oil_level',sign=-1,repair=220+gap,lifecycle='persistent');events=[a,b]
        elif kind not in ('normal','spike','bad_quality'):
            a=g.make_event(kind,severity,rng,rng.randint(96,120));a.update(repair=rng.randint(272,304),lifecycle=mode);events=[a]
        elif kind!='normal':
            a=g.make_event('sensor_bias',2,rng,128);a.update(kind=kind,end=129 if kind=='spike' else 176);g.inject(frames,a)
        for n,e in enumerate(events):e['incident_id']=rid+':'+str(n);apply_lifecycle(g,frames,e,rng)
        assert all(not f['active_alarms'] and 'repair' not in f and 'incident_id' not in f and 'lifecycle' not in f for f in frames)
        path=folder/'cases'/(ident+'.json.gz');zipped(path,frames)
        cases.append(dict(id=ident,kind=kind,lifecycle=mode,run_id=rid,source_offset=offset,positive=bool(events),events=events,sha256=sha(path)))
    manifests=[load(prior.OLD/'plan.json'),load(out.parent/'episode-notices-20261024/development/manifest.json'),load(out.parent/'episode-notices-20261024/test/manifest.json')]
    if role=='test':manifests.append(load(out/'development/manifest.json'))
    for m in manifests:
        assert seed!=m['seed'] and nonce!=m['nonce'] and not {c['run_id'] for c in cases}&{c['run_id'] for c in m['cases']}
    save(folder/'manifest.json',dict(role=role,seed=seed,nonce=nonce,cases=cases,source_sha256=sha(source),generator_sha256=sha(prior.OLD/'random_test.py'),protocol_sha256=sha(out/'protocol.json'),frames_per_case=FRAMES,truth_not_in_frames=True))
    print('DATA_READY',role,len(cases),'incidents',sum(len(c['events']) for c in cases),flush=True)

def freeze(out):
    assert load(out/'development/comparison.json')['passed'],'development must pass first'
    assert load(out/'model-input-overlap-audit.json')['passed'],'model input overlap audit must pass'
    paths=['scripts/mes_causal_lifecycle.py','scripts/mes_causal_lifecycle_validate.py','scripts/mes_causal_episode.py','scripts/mes_causal_episode_validate.py','scripts/mes_causal_context.py','scripts/mes_causal_v14_stream.py','scripts/mes_causal_schema.py','scripts/mes_causal_pda_service.py','tests/test_mes_causal_lifecycle.py','tests/test_mes_causal_lifecycle_data.py','docs/research/mes-causal-lifecycle-prereg-20261024.md','deploy/analytics/normal-profile.json','deploy/analytics/source-config.json','docs/research/evidence/mes-causal-v14c-20261023/settings.json']
    save(out/'candidate-lock.json',dict(files={p:sha(ROOT/p) for p in paths},development_manifest_sha256=sha(out/'development/manifest.json'),split_sha256=sha(out/'split.json'),normal_source_provenance_sha256=sha(out/'normal-source-provenance.json'),model_input_overlap_sha256=sha(out/'model-input-overlap-audit.json'),protocol_sha256=sha(out/'protocol.json'),before_unseen_generation=True,selection='first development-passing candidate, no score fitting'))

def verify_freeze(out):
    lock=load(out/'candidate-lock.json');assert all(sha(ROOT/p)==h for p,h in lock['files'].items())
    for name,key in [('development/manifest.json','development_manifest_sha256'),('split.json','split_sha256'),('normal-source-provenance.json','normal_source_provenance_sha256'),('model-input-overlap-audit.json','model_input_overlap_sha256'),('protocol.json','protocol_sha256')]:assert sha(out/name)==lock[key]

    assert all(sha(ROOT/p)==h for p,h in load(out/'normal-source-provenance.json')['generator_files'].items())

def evaluate(out,role,model):
    if role=='test':verify_freeze(out)
    folder=out/role/model;folder.mkdir(exist_ok=False)
    binding=(LifecycleSource if model=='candidate' else prior.BoundSource)(load(prior.RELEASE/'docs/research/evidence/mes-causal-v14c-20261023/settings.json'),load(prior.RELEASE/'deploy/analytics/source-config.json'),load(prior.RELEASE/'deploy/analytics/normal-profile.json'));rows=[]
    for case in load(out/role/'manifest.json')['cases']:
        path=out/role/'cases'/(case['id']+'.json.gz');assert sha(path)==case['sha256'];frames=unzip(path);assert len(frames)==FRAMES
        session=prior.AdvisorySession(binding,folder/(case['id']+'-checkpoint.json'));session.defer_flush=True;notices=[]
        for frame in frames:
            for eq in sorted(session.feed(frame,binding.config_id)):notices.append(dict(sequence=frame['sequence'],equipment_id=eq))
        session.flush();incidents=[];matched=0
        for n,event in enumerate(case['events']):
            hits=[x for x in notices if x['equipment_id']==event['equipment_id'] and event['start']<=x['sequence']-1<event['repair']];matched+=len(hits)
            incidents.append(dict(key=case['id']+':'+str(n),kind=event['kind'],lifecycle=event['lifecycle'],detected=bool(hits),first=hits[0]['sequence'] if hits else None,delay=hits[0]['sequence']-1-event['start'] if hits else None,duplicates=max(0,len(hits)-1)))
        rows.append(dict(id=case['id'],kind=case['kind'],positive=case['positive'],incidents=incidents,unmatched=len(notices)-matched,notices=notices));save(folder/'progress.json',rows)
        print('CASE',role,model,case['id'],[e['detected'] for e in incidents],'notices',len(notices),flush=True)
    events=[e for r in rows for e in r['incidents']]
    result=dict(model=model,cases=len(rows),frames=len(rows)*FRAMES,detected=sum(e['detected'] for e in events),total=len(events),duplicates=sum(e['duplicates'] for e in events),unmatched=sum(r['unmatched'] for r in rows if r['positive']),normal=sum(len(r['notices']) for r in rows if r['kind']=='normal'),spike=sum(len(r['notices']) for r in rows if r['kind']=='spike'),quality=sum(len(r['notices']) for r in rows if r['kind']=='bad_quality'),delay_p95_frames=prior.p95([e['delay'] for e in events if e['detected']]),rows=rows)
    save(folder/'result.json',result);print('EVALUATION_DONE',role,model,{k:v for k,v in result.items() if k!='rows'},flush=True)

def compare(out,role):
    prior.compare(out,role)
    a=load(out/role/'original/result.json');b=load(out/role/'candidate/result.json');m=load(out/role/'manifest.json');groups={}
    for label in (*LIFECYCLES,'post_repair','nearby'):
        ids={c['id'] for c in m['cases'] if (c['kind']==label if label in ('post_repair','nearby') else c['lifecycle']==label and c['kind'] not in ('post_repair','nearby'))};groups[label]={}
        for name,r in [('original',a),('candidate',b)]:
            events=[e for row in r['rows'] if row['id'] in ids for e in row['incidents']]
            groups[label][name]=dict(detected=sum(e['detected'] for e in events),total=len(events),duplicates=sum(e['duplicates'] for e in events),p95_frames=prior.p95([e['delay'] for e in events if e['detected']]))
    p=out/role/'comparison.json';r=load(p);r['by_scenario']=groups;save(p,r)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--phase',choices=['setup','freeze','make-test','evaluate','compare'],required=True);p.add_argument('--role',choices=['development','test'],default='development');p.add_argument('--model',choices=['original','candidate'],default='candidate');a=p.parse_args()
    if a.phase=='setup':setup(a.out)
    elif a.phase=='freeze':freeze(a.out)
    elif a.phase=='make-test':make_data(a.out,'test')
    elif a.phase=='evaluate':evaluate(a.out,a.role,a.model)
    else:compare(a.out,a.role)