"""Offline v9 retrain/development/freeze/test runner; never touches services."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
import gc
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from scripts import mes_causal_data as d
from scripts import mes_causal_train as old
from scripts import mes_causal_score as score
from scripts import mes_causal_v9 as v
from scripts.mes_causal_schema import ROOT,signals

V8=ROOT/'output/mes-causal-v8-20261022/run-final'


def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def preserve(out):
    protected=load(V8/'original-files.json')
    files=list((ROOT/'output/mes-causal-v8-20261022').rglob('*'))
    files += [ROOT/'scripts'/n for n in ('mes_causal_data.py','mes_causal_schema.py','mes_causal_source.py',
        'mes_causal_challenge.py','mes_causal_train.py','mes_causal_score.py')]
    files += list((ROOT/'docs/research').glob('mes-causal-v8-*.md'))
    files += [p for p in (ROOT/'tests').glob('test_mes_causal_*.py') if 'v9' not in p.name]
    for p in files:
        if p.is_file():protected[str(p.resolve())]=d.sha(p)
    d.write_new(out/'protected.json',protected)


def verify(out):
    protected=load(out/'protected.json')
    assert all(d.sha(ROOT/p)==h for p,h in protected.items()),'protected input changed'
    return len(protected)


def dual_forecast(model,original_head,x):
    import torch
    from scripts import mes_timestral_finetune as ft
    start=time.perf_counter()
    def work(i):
        a=ft.capture_one(x[i],model)
        cache={k:val[None] for k,val in a.items() if k!='reference'}
        with torch.inference_mode():
            before=ft.reconstruct(original_head,cache,model.config.use_asinh,model.quantile_real_cap_k).numpy()[0]
            if i<3:
                after=ft.reconstruct(model.model.head,cache,model.config.use_asinh,model.quantile_real_cap_k).numpy()[0]
                np.testing.assert_allclose(after,a['reference'],rtol=1e-5,atol=1e-5)
        return a['reference'][:,[0,10,20]],before[:,[0,10,20]]
    rows=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i,row in enumerate(pool.map(work,range(len(x)))):
            rows.append(row)
            if i%128==0:print('dual forecast',i+1,'/',len(x),flush=True)
    new,before=np.asarray([r[0] for r in rows]),np.asarray([r[1] for r in rows])
    assert np.isfinite(new).all() and np.isfinite(before).all()
    return new,before,dict(windows=len(x),seconds=time.perf_counter()-start,workers=4,torch_threads=1)


def scores(runs,channels,stats,keys,actual,q):
    from scripts.mes_timestral_comparison import channel_scores
    scales=np.array([stats[c][1] for c in channels]);center=np.array([stats[c][0] for c in channels])
    ts=old.aggregate(channel_scores(actual,q[:,:,1],q[:,:,0],q[:,:,2],scales),channels)
    x,check,_=d.windows(runs,channels);assert check==keys
    naive=old.aggregate(np.abs(actual-x[:,:,-1])/scales,channels)
    lookup={}
    for run,frames in runs.items():
        state=np.zeros(len(channels))
        for f in frames:
            if f['line_mode'] in d.INACTIVE:state[:]=0
            values=d.valid_values(f,signals())
            z=np.array([abs(values[c]-center[i])/scales[i] if c in values else np.nan for i,c in enumerate(channels)])
            state=np.where(np.isfinite(z),.4*z+.6*state,state)
            lookup[run,f['sequence']]=state.copy()
    return dict(keys=keys,actual=actual,ts=ts,naive=naive,ewma=old.aggregate(np.array([lookup[k] for k in keys]),channels))


def compute(path,runs,channels,stats,model,original_head):
    from scripts import mes_causal_v9_cache as cache
    from scripts import mes_timestral_finetune as ft
    path=Path(path).resolve()
    x,keys,actual=d.windows(runs,channels)
    digest=hashlib.sha256()
    for value in original_head.state_dict().values():digest.update(value.detach().cpu().numpy().tobytes())
    identity=ft.state_hash(model.model,False)+ft.state_hash(model.model,True)+digest.hexdigest()
    q,before,timing=cache.run_chunks(x,lambda part:dual_forecast(model,original_head,part),
                                   path.parent/(path.stem+'-parts'),identity)
    cache.archive(path,keys=np.array(keys,dtype=str),actual=actual,forecast=q,old_head=before)
    return scores(runs,channels,stats,keys,actual,q),scores(runs,channels,stats,keys,actual,before),timing


def evaluate(runs,ledger,rows,manifest,eligible):
    metrics=score.evaluate(runs,ledger,rows,eligible)
    controls={r['group_id']:r['run_id'] for r in manifest['runs'] if r['control']}
    groups={r['run_id']:r['group_id'] for r in manifest['runs']}
    matched={};previous={}
    for (run,tick),eqs in rows.items():
        for eq in eqs-previous.get(run,set()):
            candidates=[e for e in ledger[run] if e['equipment']==eq and e['start']<=tick<e['end'] and (run,e['event_id']) not in matched]
            if candidates:
                e=min(candidates,key=lambda x:(x['start'],x['event_id']));matched[run,e['event_id']]=tick-e['start']
        previous[run]=eqs
    kinds={};attributable=within=0
    for run,events in ledger.items():
        for e in events:
            hit=(run,e['event_id']) in matched
            control=controls[groups[run]]
            chance=any(e['equipment'] in rows[control,t] for t in range(e['start'],e['end']))
            credit=hit and not chance;attributable+=int(credit)
            within+=int(credit and matched[run,e['event_id']]<=10)
            cell=kinds.setdefault(e['kind'],dict(events=0,detected=0,attributable=0))
            cell['events']+=1;cell['detected']+=int(hit);cell['attributable']+=int(credit)
    metrics.update(attributable_events=attributable,attributable_within_10s=within,by_kind=kinds)
    assert sum(x['detected'] for x in kinds.values())==metrics['detected_events']
    return metrics


def choose(records):
    def key(row):
        m=row['metrics'];rate=m['pristine_normal_false_starts_per_line_hour'];p=row['params']
        return (int(rate>1),rate if rate>1 else 0,-m['attributable_events'],m['duplicate_notifications'],
                -m['attributable_within_10s'],p['patience'],p['flat'],p['q'])
    return min(records,key=key)


def train(out):
    import torch
    from timestral import TimestralForecaster
    from scripts import mes_timestral_finetune as ft
    out.mkdir(parents=True,exist_ok=False);preserve(out)
    dataset=out/'data';roles={};manifests=[]
    for role in ('fit','selection','calibration','development'):
        print('GENERATE',role,flush=True);v.generate(dataset/role,role)
        roles[role],manifest=d.read_role(dataset/role);manifests.append(manifest)
    v.check_disjoint(manifests)
    training=out/'training';training.mkdir()
    channels,stats=old.fit_statistics(roles['fit'])
    original_cal=load(V8/'training/calibration.json');assert channels==[tuple(c) for c in original_cal['channels']]
    torch.set_num_threads(1)
    model=TimestralForecaster.from_pretrained(V8/'training/checkpoint',device='cpu',local_files_only=True)
    initial_head=copy.deepcopy(model.model.head);backbone=ft.state_hash(model.model,False)
    caches={};feature_meta={}
    for role in ('fit','selection'):
        wrapped={r:[(f,dict(faults=[])) for f in frames] for r,frames in roles[role].items()}
        caches[role],_,feature_meta[role]=ft.collect(wrapped,channels,lambda f:d.valid_values(f,signals()),model,
                                                    training/(role+'-features.npz'),thin=8)
    torch.set_num_threads(4)
    head,history=ft.fit_head(model.model.head,caches['fit'],caches['selection'])
    model.model.head.load_state_dict(head.state_dict());del caches;gc.collect()
    assert ft.state_hash(model.model,False)==backbone
    d.write_new(training/'head-training.json',history)
    ft.save_checkpoint(model,training/'checkpoint');torch.set_num_threads(1)
    tolerance,variable=v.flat_reference(roles['fit'],channels)
    cal,old_cal,cal_time=compute(training/'calibration.npz',roles['calibration'],channels,stats,model,initial_head)
    development,old_dev,dev_time=compute(training/'development.npz',roles['development'],channels,stats,model,initial_head)
    finish(out,roles,manifests,channels,stats,cal,old_cal,development,history,feature_meta,cal_time,dev_time)


def finish(out,roles,manifests,channels,stats,cal,old_cal,development,history,feature_meta,cal_time,dev_time):
    training=out/'training';dataset=out/'data'
    tolerance,variable=v.flat_reference(roles['fit'],channels)
    dev_data=v.prepare(roles['development'],channels,stats,development)
    # Development labels may be used here, test material does not exist yet.
    ledger=load(dataset/'development/events.private.json');selected={};search={}
    for method in v.METHODS:
        records=[]
        for params in v.GRID:
            rows=v.predict(dev_data,channels,tolerance,variable,v.limits(cal,params['q']),params,method)
            metrics=evaluate(roles['development'],ledger,rows,manifests[-1],set(development['keys']))
            records.append(dict(params=params,metrics=metrics))
        search[method]=records;selected[method]=choose(records)
    d.write_new(training/'search.json',search)
    settings=dict(channels=channels,stats=[[*c,*stats[c]] for c in channels],tolerance=tolerance.tolist(),
        variable=variable.tolist(),selected=selected,
        limits={m:{k:a.tolist() for k,a in v.limits(cal,r['params']['q']).items()} for m,r in selected.items()},
        old_head_limits={k:a.tolist() for k,a in v.limits(old_cal,selected['full']['params']['q']).items()})
    d.write_new(training/'settings.json',settings)
    d.write_new(training/'result.json',dict(history=history,features=feature_meta,backbone_unchanged=True,
        checkpoint_sha256=d.sha(training/'checkpoint/model.safetensors'),calibration_timing=cal_time,
        development_timing=dev_time,channels=len(channels),test_rows_read=0))
    protected=load(out/'protected.json')
    files={str((ROOT/p).resolve()):h for p,h in protected.items()}
    paths=[Path(__file__),ROOT/'scripts/mes_causal_v9.py',ROOT/'scripts/mes_causal_v9_cache.py',ROOT/'docs/research/mes-causal-v9-prereg-20261023.md']
    paths+=list(training.rglob('*'))+list(dataset.rglob('*'))
    for p in paths:
        if p.is_file():files[str(p.resolve())]=d.sha(p)
    verify(out)
    d.write_new(out/'candidate-lock.json',dict(status='frozen_before_test',files=files,
        protocol='v9 paired controls; all tuning on development; test not yet generated'))
    print('FROZEN BEFORE TEST',json.dumps({m:r['params'] for m,r in selected.items()}),flush=True)


def resume(out):
    """Recover a pre-freeze interrupted development run, never an already used test."""
    import torch
    from timestral import TimestralForecaster
    from scripts import mes_timestral_finetune as ft
    assert not (out/'candidate-lock.json').exists() and not (out/'data/test').exists()
    verify(out);training=out/'training';roles={};manifests=[]
    for role in ('fit','selection','calibration','development'):
        roles[role],manifest=d.read_role(out/'data'/role);manifests.append(manifest)
    v.check_disjoint(manifests);channels,stats=old.fit_statistics(roles['fit'])
    model=TimestralForecaster.from_pretrained(training/'checkpoint',device='cpu',local_files_only=True)
    before=TimestralForecaster.from_pretrained(V8/'training/checkpoint',device='cpu',local_files_only=True)
    initial_head=copy.deepcopy(before.model.head);del before;gc.collect()
    torch.set_num_threads(4)
    with np.load(training/'fit-features.npz') as a,np.load(training/'selection-features.npz') as b:
        restored,history=ft.fit_head(initial_head,a,b)
    exact=True
    for name,value in restored.state_dict().items():
        saved=model.model.head.state_dict()[name]
        exact &= bool(np.array_equal(value.detach().numpy(),saved.detach().numpy()))
        np.testing.assert_allclose(value.detach().numpy(),saved.detach().numpy(),rtol=1e-6,atol=1e-7)
    d.write_new(training/'recovery-check.json',dict(normal_head_replay_matches_checkpoint=True,bitwise_exact=exact,
        checkpoint_sha256=d.sha(training/'checkpoint/model.safetensors'),reason='development archive creation OSError 22 before freeze'))
    d.write_new(training/'head-training.json',history)
    feature_meta={}
    for role in ('fit','selection'):
        with np.load(training/(role+'-features.npz')) as saved:count=len(saved['keys'])
        feature_meta[role]=dict(windows=count,sha256=d.sha(training/(role+'-features.npz')),reused=True)
    with np.load(training/'calibration.npz') as saved:
        keys=[(r,int(s)) for r,s in saved['keys']]
        cal=scores(roles['calibration'],channels,stats,keys,saved['actual'],saved['forecast'])
        old_cal=scores(roles['calibration'],channels,stats,keys,saved['actual'],saved['old_head'])
    torch.set_num_threads(1)
    development,_,dev_time=compute(training/'development-recovered.npz',roles['development'],channels,stats,model,initial_head)
    finish(out,roles,manifests,channels,stats,cal,old_cal,development,history,feature_meta,
           dict(windows=len(cal['keys']),reused=True,seconds=None),dev_time)


def test(out):
    import torch
    from timestral import TimestralForecaster
    torch.set_num_threads(1);lock=out/'candidate-lock.json';v.require_lock(lock)
    output=out/'evaluation';output.mkdir(exist_ok=False)
    v.generate(out/'data/test','test',lock)
    runs,manifest=d.read_role(out/'data/test')
    v.check_disjoint([load(out/'data'/r/'manifest.json') for r in v.ROLES])
    settings=load(out/'training/settings.json');channels=[tuple(c) for c in settings['channels']]
    stats={(e,s):(m,a) for e,s,m,a in settings['stats']}
    model=TimestralForecaster.from_pretrained(out/'training/checkpoint',device='cpu',local_files_only=True)
    before=TimestralForecaster.from_pretrained(V8/'training/checkpoint',device='cpu',local_files_only=True)
    assert all(np.array_equal(p.detach().numpy(),dict(before.model.named_parameters())[n].detach().numpy())
               for n,p in model.model.named_parameters() if not n.startswith('head.'))
    first_windows,_,_=d.windows(runs,channels)
    official_before,_=old.forecast(before,first_windows[:3],batch=3)
    del first_windows
    initial_head=copy.deepcopy(before.model.head);del before;gc.collect()
    computed,old_computed,timing=compute(output/'forecasts.npz',runs,channels,stats,model,initial_head)
    with np.load(output/'forecasts.npz') as saved:
        np.testing.assert_allclose(saved['old_head'][:3],official_before,rtol=1e-5,atol=1e-5)
    data=v.prepare(runs,channels,stats,computed);predictions={}
    for method in v.METHODS:
        thresholds={k:np.array(a) for k,a in settings['limits'][method].items()}
        predictions[method]=v.predict(data,channels,np.array(settings['tolerance']),np.array(settings['variable']),
                                       thresholds,settings['selected'][method]['params'],method)
    predictions['persistence']=v.predict(data,channels,np.array(settings['tolerance']),np.zeros(len(channels),bool),
        {k:np.array(a) for k,a in settings['limits']['persistence_flat'].items()},
        settings['selected']['persistence_flat']['params'],'persistence_flat')
    old_data=v.prepare(runs,channels,stats,old_computed)
    predictions['old_head']=v.predict(old_data,channels,np.array(settings['tolerance']),np.array(settings['variable']),
        {k:np.array(a) for k,a in settings['old_head_limits'].items()},settings['selected']['full']['params'],'full')
    config=load(V8/'training/calibration.json');old_stats={(e,s):(m,a) for e,s,m,a in config['stats']}
    with np.load(output/'forecasts.npz') as f:
        prior=scores(runs,channels,old_stats,computed['keys'],computed['actual'],f['old_head'])
    _,old_predictions=old.predict_policies(runs,channels,old_stats,prior,{k:np.array(a) for k,a in config['thresholds'].items()},config['settings'])
    predictions['v8']=old_predictions['timestral_ewma']
    d.write_new(output/'predictions.json',{m:[[r,s,sorted(eqs)] for (r,s),eqs in rows.items()] for m,rows in predictions.items()})
    ledger=load(out/'data/test/events.private.json')
    results={m:evaluate(runs,ledger,rows,manifest,set(computed['keys'])) for m,rows in predictions.items()}
    protected=verify(out);v.require_lock(lock)
    d.write_new(output/'result.json',dict(methods=results,timing=timing,protected_files=protected,
        frozen_unchanged=True,lock_sha256=d.sha(lock),limits='Synthetic A/B shared generator families, not field validation.'))
    print(json.dumps({m:{k:r[k] for k in ('detected_events','attributable_events','duplicate_notifications','pristine_normal_false_starts','p95_injection_delay_seconds')} for m,r in results.items()}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--phase',choices=('train','resume','test'),required=True);args=parser.parse_args()
    dict(train=train,resume=resume,test=test)[args.phase](args.out.resolve())
