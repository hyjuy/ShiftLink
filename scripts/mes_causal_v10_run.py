"""Separate v10 development/freeze/first-use evaluation; no service operations."""
import argparse
import copy
import json
from pathlib import Path

import numpy as np
from scripts import mes_causal_data as d
from scripts import mes_causal_train as old
from scripts import mes_causal_v9 as v9
from scripts import mes_causal_v9_run as prior
from scripts import mes_causal_v10 as v
from scripts.mes_causal_schema import ROOT

PREVIOUS=ROOT/'output/mes-causal-v9-20261023'
METHODS=('full','no_timestral','timestral','persistence','no_flat')
GRID=[dict(width=w,q=q,patience=p) for w in (5,9) for q in (.98,.995) for p in (4,8)]


def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def protect(out):
    files=load(PREVIOUS/'protected.json')
    paths=list(PREVIOUS.rglob('*'))+[ROOT/'scripts'/n for n in (
        'mes_causal_v9.py','mes_causal_v9_run.py','mes_causal_v9_cache.py')]
    paths+=list((ROOT/'docs/research').glob('mes-causal-v9-*.md'))
    for p in paths:
        if p.is_file():files[str(p.resolve())]=d.sha(p)
    d.write_new(out/'protected.json',files)


def verify(out):
    files=load(out/'protected.json')
    assert all(d.sha(ROOT/p)==h for p,h in files.items()),'protected original changed'
    return len(files)


def forecast(path,runs,channels,stats):
    import torch
    from timestral import TimestralForecaster
    torch.set_num_threads(1)
    model=TimestralForecaster.from_pretrained(PREVIOUS/'training/checkpoint',device='cpu',local_files_only=True)
    head=copy.deepcopy(model.model.head)
    result,_,timing=prior.compute(path,runs,channels,stats,model,head)
    return result,timing


def prepare(path,runs,channels,stats):
    from scripts.mes_timestral_comparison import channel_scores
    with np.load(path) as saved:
        keys=[(r,int(s)) for r,s in saved['keys']];actual=saved['actual'];q=saved['forecast']
        computed=prior.scores(runs,channels,stats,keys,actual,q)
        scale=np.array([stats[c][1] for c in channels])
        ts=channel_scores(actual,q[:,:,1],q[:,:,0],q[:,:,2],scale)
        x,check,_=d.windows(runs,channels);assert check==keys
        naive=np.abs(actual-x[:,:,-1])/scale
    data=v9.prepare(runs,channels,stats,computed);lookup={k:i for i,k in enumerate(keys)}
    def expand(a):return np.asarray([a[lookup[k]] if k in lookup else np.full(len(channels),np.nan) for k in data['keys']])
    return data,expand(ts),expand(naive)


def variants(data,ts,naive,stats,channels,variable):
    return {w:v.process_scores(data,stats,channels,variable,w,ts,naive) for w in (5,9)}


def thresholds(computed,q):return {name:v.channel_limits(a,q) for name,a in computed.items()}


def gate_ablation(data,stats,channels,variable,holds):
    z=np.abs((data['values']-np.array([stats[c][0] for c in channels]))/np.array([stats[c][1] for c in channels]))
    a=v.smooth_signed(z,data['resets'],holds)
    a[~np.array([k in data['eligible_keys'] for k in data['keys']])]=np.nan
    a[:,~variable]=0.
    return a


def ablation_limits(a,channels,q,channel):
    if channel:return v.channel_limits(a,q)
    equipment=sorted({c[0] for c in channels});maxima=old.aggregate(a,channels)
    limits=v.channel_limits(np.where(np.isfinite(maxima),maxima,np.nan),q)
    return np.asarray([limits[equipment.index(c[0])] for c in channels])


def predict(data,channels,tolerance,variable,versions,params,limits,method):
    computed,holds=versions[params['width']]
    return v.predict(data,channels,tolerance,variable,computed,holds,
                     {n:np.asarray(a) for n,a in limits.items()},params,method)


def healthy_quality(runs,manifest,data,holds):
    return dict(acquisition_repeat_frames=int(holds.sum()),frames=len(data['keys']),
                ready_frames=len(data['eligible_keys']),
                ready_repeat_frames=sum(bool(holds[i]) for i,k in enumerate(data['keys']) if k in data['eligible_keys']))


def develop(out,resume=False):
    if resume:
        assert not (out/'candidate-lock.json').exists() and not (out/'data/test').exists()
        verify(out)
    else:out.mkdir(parents=True,exist_ok=False);protect(out)
    roles={};manifests=[]
    for role in ('fit','calibration','development'):
        if not resume:print('GENERATE',role,flush=True);v.generate(out/'data'/role,role)
        roles[role],manifest=d.read_role(out/'data'/role);manifests.append(manifest)
    v9.check_disjoint(manifests+[load(PREVIOUS/'data'/r/'manifest.json') for r in v9.ROLES])
    channels,stats=old.fit_statistics(roles['fit']);tolerance,variable=v9.flat_reference(roles['fit'],channels)
    training=out/'development';training.mkdir(exist_ok=resume)
    timings={}
    for role in ('calibration','development'):
        path=training/(role+'.npz')
        if resume and path.exists():
            with np.load(path) as saved:count=len(saved['keys'])
            timings[role]=dict(reused_archive=True,windows=count)
        else:_,timings[role]=forecast(path,roles[role],channels,stats)
    cal,ct,cn=prepare(training/'calibration.npz',roles['calibration'],channels,stats)
    dev,dt,dn=prepare(training/'development.npz',roles['development'],channels,stats)
    cv=variants(cal,ct,cn,stats,channels,variable);dv=variants(dev,dt,dn,stats,channels,variable)
    ledger=load(out/'data/development/events.private.json');selected={};search={}
    for method in METHODS:
        records=[]
        for params in GRID:
            limits=thresholds(cv[params['width']][0],params['q'])
            rows=predict(dev,channels,tolerance,variable,dv,params,limits,method)
            metrics=prior.evaluate(roles['development'],ledger,rows,manifests[-1],dev['eligible_keys'])
            records.append(dict(params=params,metrics=metrics,limits={k:a.tolist() for k,a in limits.items()}))
        # Same normal-budget/event/duplicate/latency rule as v9; substitute width for the flat tie-breaker.
        def key(r):
            m=r['metrics'];p=r['params'];rate=m['pristine_normal_false_starts_per_line_hour']
            return (int(rate>1),rate if rate>1 else 0,-m['attributable_events'],m['duplicate_notifications'],
                    -m['attributable_within_10s'],p['patience'],p['width'],p['q'])
        search[method]=records;selected[method]=min(records,key=key)
    settings=dict(channels=channels,stats=[[*c,*stats[c]] for c in channels],tolerance=tolerance.tolist(),
                  variable=variable.tolist(),selected=selected,checkpoint=str(PREVIOUS/'training/checkpoint'),
                  checkpoint_sha256=d.sha(PREVIOUS/'training/checkpoint/model.safetensors'),retrained=False)
    raw=gate_ablation(cal,stats,channels,variable,cv[5][1]);fixed=selected['no_timestral']['params']
    settings['ablation_limits']={name:ablation_limits(raw,channels,fixed['q'],channel).tolist()
                                 for name,channel in (('gate_only',False),('gate_channel',True))}
    d.write_new(training/'settings.json',settings);d.write_new(training/'search.json',search)
    d.write_new(training/'quality.json',dict(calibration=healthy_quality(roles['calibration'],manifests[1],cal,cv[5][1]),
                    development=healthy_quality(roles['development'],manifests[-1],dev,dv[5][1]),timings=timings))
    files={str((ROOT/p).resolve()):h for p,h in load(out/'protected.json').items()}
    paths=[Path(__file__),ROOT/'scripts/mes_causal_v10.py',ROOT/'tests/test_mes_causal_v10.py',
           ROOT/'docs/research/mes-causal-v10-prereg-20261023.md']+list(training.rglob('*'))+list((out/'data').rglob('*'))
    for p in paths:
        if p.is_file():files[str(p.resolve())]=d.sha(p)
    verify(out)
    d.write_new(out/'candidate-lock.json',dict(status='frozen_before_test',files=files,
                                             protocol='v10 normal-only channel calibration; no model retraining; fresh test not generated'))
    print('FROZEN',json.dumps({m:dict(params=r['params'],detected=r['metrics']['detected_events'],
        normal=r['metrics']['pristine_normal_false_starts'],leak=r['metrics']['by_kind']['leak']) for m,r in selected.items()}),flush=True)


def evaluate(out):
    lock=out/'candidate-lock.json';v9.require_lock(lock)
    folder=out/'evaluation';folder.mkdir(exist_ok=False)
    v.generate(out/'data/test','test',lock)
    runs,manifest=d.read_role(out/'data/test')
    v9.check_disjoint([load(out/'data'/r/'manifest.json') for r in v.ROLES]+[load(PREVIOUS/'data'/r/'manifest.json') for r in v9.ROLES])
    settings=load(out/'development/settings.json');channels=[tuple(c) for c in settings['channels']]
    stats={(e,s):(m,a) for e,s,m,a in settings['stats']}
    tolerance=np.asarray(settings['tolerance']);variable=np.asarray(settings['variable'])
    _,timing=forecast(folder/'forecasts.npz',runs,channels,stats)
    data,ts,naive=prepare(folder/'forecasts.npz',runs,channels,stats)
    versions=variants(data,ts,naive,stats,channels,variable);predictions={}
    for method in METHODS:
        fixed=settings['selected'][method]
        predictions[method]=predict(data,channels,tolerance,variable,versions,fixed['params'],fixed['limits'],method)
    full=settings['selected']['full']
    predictions['remove_ts_fixed']=predict(data,channels,tolerance,variable,versions,full['params'],full['limits'],'no_timestral')
    raw=gate_ablation(data,stats,channels,variable,versions[5][1])
    for method,limits in settings['ablation_limits'].items():
        predictions[method]=v.predict(data,channels,tolerance,variable,{'level':raw},versions[5][1],
            {'level':np.asarray(limits)},settings['selected']['no_timestral']['params'],'no_timestral')
    previous=load(PREVIOUS/'training/settings.json');ps={(e,s):(m,a) for e,s,m,a in previous['stats']}
    with np.load(folder/'forecasts.npz') as saved:
        pc=prior.scores(runs,channels,ps,[(r,int(s)) for r,s in saved['keys']],saved['actual'],saved['forecast'])
    pd=v9.prepare(runs,channels,ps,pc)
    predictions['v9']=v9.predict(pd,channels,np.asarray(previous['tolerance']),np.asarray(previous['variable']),
        {k:np.asarray(a) for k,a in previous['limits']['full'].items()},previous['selected']['full']['params'],'full')
    # All predictions are committed to disk before reading test event labels.
    d.write_new(folder/'predictions.json',{m:[[r,t,sorted(eqs)] for (r,t),eqs in rows.items()] for m,rows in predictions.items()})
    ledger=load(out/'data/test/events.private.json')
    results={m:prior.evaluate(runs,ledger,rows,manifest,data['eligible_keys']) for m,rows in predictions.items()}
    holds=versions[5][1];healthy={r for r in runs if not ledger[r]}
    normal_holds=sum(bool(holds[i]) for i,(r,t) in enumerate(data['keys']) if r in healthy and (r,t) in data['eligible_keys'])
    quality=healthy_quality(runs,manifest,data,holds)
    quality.update(normal_ready_repeat_seconds=normal_holds,
        normal_hold_excluded_seconds=results['full']['pristine_normal_run_seconds']-normal_holds,
        events_overlapping_hold=sum(any(holds[i] and e['start']<=t<e['end'] for i,(rr,t) in enumerate(data['keys']) if rr==r)
                                    for r in runs for e in ledger[r]))
    hits={}
    for method,rows in predictions.items():
        hits[method]={f'{r}:{e["event_id"]}':next((t-e['start'] for t in range(e['start'],e['end']) if e['equipment'] in rows[r,t]),None)
                      for r in runs for e in ledger[r]}
    d.write_new(folder/'event-delays.json',hits)
    quality['full_only_events']=[k for k in hits['full'] if hits['full'][k] is not None and hits['remove_ts_fixed'][k] is None]
    quality['removed_only_events']=[k for k in hits['full'] if hits['full'][k] is None and hits['remove_ts_fixed'][k] is not None]
    verify(out);v9.require_lock(lock)
    d.write_new(folder/'result.json',dict(methods=results,quality=quality,timing=timing,
        protected_files=verify(out),frozen_unchanged=True,lock_sha256=d.sha(lock),retrained=False,
        limits='Synthetic known A/B families. Injection delay excludes inference/network/UI. Not field validation.'))
    print(json.dumps({m:{k:x[k] for k in ('detected_events','duplicate_notifications','pristine_normal_false_starts',
          'p95_injection_delay_seconds','by_kind')} for m,x in results.items()}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--phase',choices=('develop','resume','test'),required=True);args=parser.parse_args()
    if args.phase=='test':evaluate(args.out.resolve())
    else:develop(args.out.resolve(),resume=args.phase=='resume')
