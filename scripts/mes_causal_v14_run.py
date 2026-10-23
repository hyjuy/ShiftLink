"""Isolated development, normal-only thermal calibration, freeze, unused test."""
import argparse
import json
import pickle
import sys
import time
from pathlib import Path
import numpy as np
from scripts import mes_causal_v13_run as prior
from scripts import mes_causal_v13 as baseline
from scripts import mes_causal_v14 as candidate
from scripts import mes_causal_v14_data as dataset

ROOT=prior.ROOT;d=prior.d;load=prior.load
PREVIOUS=ROOT/'output/mes-causal-v13-20261023'
ANALYSIS=ROOT/'output/mes-causal-v14-analysis-20261023'


def verify(out):return prior.r.verify(out)


def prepare(run,frames,settings):
    assert all(f['line_mode']=='running' for f in frames),'this benchmark requires running frames'
    args=list(prior.r.prepare({run:frames},settings['base'])[0])
    args[6]={'level':np.asarray(settings['limits'])}
    args[7]=dict(args[7],thermal_rise_limits=settings['thermal_rise_limits'])
    return args


def assess(path,target,settings,cache=None,reproduce=False):
    started=time.perf_counter();rows={'v13':{},'v14':{}};eligible=set();lite={};derived=[]
    source=((p.stem,pickle.loads(p.read_bytes())) for p in sorted(cache.glob('*.pkl'))) if cache else (
        (run,prepare(run,frames,settings)) for run,frames in prior.batches(path))
    for run,args in source:
        args[7]=dict(args[7],thermal_rise_limits=settings['thermal_rise_limits'])
        before=baseline.predict(*args);augmented=candidate.augment(args);after=candidate.predict(*args,original=before)
        rows['v13'].update(before);rows['v14'].update(after);eligible.update(args[0]['eligible_keys'])
        for i,key in enumerate(args[0]['keys']):
            for j,eq in enumerate(args[0]['equipment']):
                if eq in after[key] and augmented[4]['level'][i,len(args[1])+j]>1:
                    derived.append(dict(run_id=run,sequence=key[1],equipment=eq,kind='coherent_temperature_rise',
                        score=float(augmented[4]['level'][i,len(args[1])+j]),causal_claim=False))
        lite[run]=[dict(sequence=k[1],line_mode='running') for k in args[0]['keys']]
    d.write_new(target/'predictions.json',prior.r.old.serialized(rows));d.write_new(target/'thermal-evidence.json',derived)
    if reproduce:assert prior.r.old.serialized(rows)['v13']==load(PREVIOUS/'evaluation/predictions.json')['v13'],'baseline changed'
    # Never open private truth before both methods' predictions are persisted.
    manifest=load(path/'manifest.json');assert d.sha(path/'events.private.json')==manifest['ledger_sha256']
    events=load(path/'events.private.json');metrics=prior.r.old.compare(lite,events,rows,manifest,eligible)
    delays={m:prior.r.old.event_delays(events,p) for m,p in rows.items()}
    a,b=metrics['v13'],metrics['v14']
    checks=dict(detected_not_lower=b['detected_events']>=a['detected_events'],
        attributable_not_lower=b['attributable_events']>=a['attributable_events'],
        duplicate_zero=b['duplicate_notifications']==0,
        normal_not_higher=b['pristine_normal_false_starts']<=a['pristine_normal_false_starts'],
        p95_not_higher=b['p95_injection_delay_seconds']<=a['p95_injection_delay_seconds'],
        first_notice_not_later=all(delays['v14'][k] is not None and delays['v14'][k]<=v for k,v in delays['v13'].items() if v is not None))
    d.write_new(target/'event-delays.json',delays)
    thermal={m:[v[f'{run}:{e["event_id"]}'] for run,es in events.items() for e in es if e['kind']=='cooling_loss'] for m,v in delays.items()}
    thermal_stats={m:dict(events=len(v),detected=sum(x is not None for x in v),
        p95=sorted(x for x in v if x is not None)[int(np.ceil(.95*sum(x is not None for x in v)))-1] if any(x is not None for x in v) else None,
        delays=v) for m,v in thermal.items()}
    report=dict(methods=metrics,cooling=thermal_stats,checks=checks,event_delay_changes={k:dict(v13=v,v14=delays['v14'][k]) for k,v in delays['v13'].items() if v!=delays['v14'][k]},
        timing=dict(seconds=time.perf_counter()-started,timestral_loaded='timestral' in sys.modules,torch_loaded='torch' in sys.modules),
        scope='Synthetic; original injection windows; no field or end-to-end claim')
    d.write_new(target/'result.json',report)
    print(json.dumps(report),flush=True);return report


def develop(out):
    out.mkdir(parents=True,exist_ok=False)
    prior.r.old.prior.require_lock(PREVIOUS/'candidate-lock.json')
    files=load(ANALYSIS/'protected.json')
    for p in ANALYSIS.rglob('*'):
        if p.is_file():files[str(p.resolve())]=d.sha(p)
    d.write_new(out/'protected.json',files)
    settings=load(PREVIOUS/'settings.json');settings['thermal_rise_limits']=[1e6]*10
    dataset.generate(out/'data/development','development')
    cache=out/'prepared';cache.mkdir();normal_scores=[];calibration_runs=[]
    for path in (PREVIOUS/'data/development',out/'data/development'):
        normals=prior.r.normal_runs(load(path/'manifest.json'))
        for run,frames in prior.batches(path):
            if path==PREVIOUS/'data/development':
                if run not in normals:continue
                args=pickle.loads((ANALYSIS/(run+'.pkl')).read_bytes())
            else:
                args=prepare(run,frames,settings)
                with (cache/(run+'.pkl')).open('xb') as stream:pickle.dump(args,stream)
            if run in normals:normal_scores.append(candidate.thermal_rise(args));calibration_runs.append(run)
    values=np.concatenate(normal_scores);limits=[]
    for col in values.T:
        good=col[np.isfinite(col)];limits.append(max(.5,float(good.max())*1.1) if len(good) else 1e6)
    settings.update(thermal_rise_limits=limits,thermal_reference_runs=calibration_runs,thermal_window=32,thermal_current_width=5)
    d.write_new(out/'settings.json',settings)
    target=out/'development';target.mkdir();report=assess(out/'data/development',target,settings,cache)
    target=out/'diagnostic-v13';target.mkdir();diagnostic=assess(PREVIOUS/'data/test',target,settings,reproduce=True)
    verify(out)
    assert all(report['checks'].values()),'development failed; no freeze'
    assert all(diagnostic['checks'].values()),'consumed regression failed; no freeze'
    assert diagnostic['methods']['v14']['detected_events']==42,'known cooling miss remains; no freeze'



def revise(out):
    import shutil
    initial=ROOT/'output/mes-causal-v14-20261023'
    assert (initial/'diagnostic-v13/result.json').exists(),'initial diagnostic must finish'
    out.mkdir(parents=True,exist_ok=False);files=load(initial/'protected.json')
    for p in initial.rglob('*'):
        if p.is_file():files[str(p.resolve())]=d.sha(p)
    d.write_new(out/'protected.json',files)
    shutil.copytree(initial/'data/development',out/'data/development')
    shutil.copytree(initial/'prepared',out/'prepared')
    settings=load(initial/'settings.json');d.write_new(out/'settings.json',settings)
    for name,path,cache,reproduce in (
        ('development',out/'data/development',out/'prepared',False),
        ('diagnostic-v13',PREVIOUS/'data/test',None,True)):
        target=out/name;target.mkdir();report=assess(path,target,settings,cache,reproduce)
        assert all(report['checks'].values()),'revised regression failed'
    assert report['methods']['v14']['detected_events']==42,'known cooling miss remains'
    verify(out)


def freeze(out):
    for name in ('development','diagnostic-v13'):assert all(load(out/name/'result.json')['checks'].values()),'regression failed'
    assert not (out/'data/test').exists(),'test already exists'
    assert load(out/'regression.json')['passed'],'regressions required'
    assert load(out/'diagnostic-v13/result.json')['methods']['v14']['detected_events']==42,'known cooling miss remains'
    verify(out);files=load(out/'protected.json')
    paths=list(out.rglob('*'))+[ROOT/'scripts'/n for n in ('mes_causal_v14.py','mes_causal_v14_data.py','mes_causal_v14_run.py','mes_causal_v14_audit.py')]
    paths +=[ROOT/'tests/test_mes_causal_v14.py',ROOT/'docs/research/mes-causal-v14-prereg-20261023.md']
    for p in paths:
        if p.is_file():files[str(p.resolve())]=d.sha(p)
    d.write_new(out/'candidate-lock.json',dict(status='frozen_before_test',files=files,protocol='v13 + causal normal-calibrated coherent thermal rise; fixed 42 new events'))
    print('FROZEN',len(files),flush=True)


def evaluate(out):
    lock=out/'candidate-lock.json';prior.r.old.prior.require_lock(lock)
    dataset.generate(out/'data/test','test',lock)
    manifests=[load(out/'data'/role/'manifest.json') for role in dataset.ROLES]
    for root in (PREVIOUS,prior.PREVIOUS,prior.r.PREVIOUS):
        manifests.extend(load(root/'data'/role/'manifest.json') for role in dataset.ROLES)
    prior.r.old.prior.check_disjoint(manifests)
    target=out/'evaluation';target.mkdir();assess(out/'data/test',target,load(out/'settings.json'))
    prior.r.old.prior.require_lock(lock)
    d.write_new(target/'integrity.json',dict(protected_files=verify(out),frozen_files=len(load(lock)['files']),frozen_unchanged=True,roles_disjoint=True,lock_sha256=d.sha(lock)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);p.add_argument('--phase',required=True,choices=('develop','revise','freeze','test'));a=p.parse_args()
    dict(develop=develop,revise=revise,freeze=freeze,test=evaluate)[a.phase](a.out.resolve())
