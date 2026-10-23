"""Separate observational alarm display from bounded repeat notifications."""
import argparse
import importlib.util
import json
import gc
import time
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('notification_continuity',ROOT/'scripts/mes_timestral_continuity.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
utils=previous.utils;base=previous.base


def notifications(observations,alerts,cooldown,quiet):
    if type(cooldown) is not int or cooldown<0 or quiet is not None and (type(quiet) is not int or quiet<1):
        raise ValueError('invalid notification policy')
    keys=[(o['run'],o['sequence']) for o in observations]
    if len(set(keys))!=len(keys) or set(keys)!=set(alerts):raise ValueError('notification keys differ')
    out={};before=set();sent={};off={};last=None
    for o,key in zip(observations,keys):
        at=datetime.fromisoformat(o['at'])
        if last is None or key[0]!=last[0][0] or key[1]!=last[0][1]+1 or (at-last[1]).total_seconds()!=1 or o['inactive']:
            before=set();sent.clear();off.clear()
        current=alerts[key];emitted=set()
        if not o['inactive']:
            for eq in before-current:off[eq]=at
            for eq in current-before:
                if (eq not in sent or (at-sent[eq]).total_seconds()>=cooldown
                        or quiet is not None and eq in off and (at-off[eq]).total_seconds()>=quiet):
                    emitted.add(eq);sent[eq]=at
            for eq in current:off.pop(eq,None)
            before=set(current)
        out[key]=emitted;last=(key,at)
    return out


def choose(rows):
    accepted=[r for r in rows if not any(v for k in ('lost','gained','delayed','duplicate_excess','p95_worse') for v in r[k])]
    return min(accepted,key=lambda r:(r['params']['cooldown'],0 if r['params']['quiet'] is None else 1,-(r['params']['quiet'] or 0))) if accepted else None


def observations(runs):
    return [dict(run=r,sequence=f['sequence'],at=f['simulated_at'],inactive=f.get('line_mode') in base.INACTIVE)
        for r,rows in runs.items() for f,_ in rows]


def assess(runs,display,pulses,before,ewma):
    from scripts.evaluate_mes_fault_models import score
    from scripts.mes_ewma_release_review import event_starts
    after=score(runs,pulses);old=event_starts(runs,display);new=event_starts(runs,pulses)
    changes=[dict(run_id=k[0],fault_id=k[1],before_delay=v['delay_seconds'],after_delay=new[k]['delay_seconds'])
        for k,v in old.items() if v['delay_seconds']!=new[k]['delay_seconds']]
    count=sum(len(v) for v in pulses.values())
    return dict(metrics={k:after[k] for k in ('detected_events','injected_events','duplicate_alert_episodes','p95_onset_delay_seconds')},
        notifications=count,unmatched_starts=count-after['detected_events'],changes=changes,
        lost=sum(v['detected'] is not None and new[k]['detected'] is None for k,v in old.items()),
        gained=sum(v['detected'] is None and new[k]['detected'] is not None for k,v in old.items()),
        delayed=sum(v['delay_seconds'] is not None and new[k]['delay_seconds'] is not None and new[k]['delay_seconds']>v['delay_seconds'] for k,v in old.items()),
        duplicate_excess=max(0,after['duplicate_alert_episodes']-ewma['duplicate_alert_episodes']),
        p95_worse=after['p95_onset_delay_seconds'] is None and before['p95_onset_delay_seconds'] is not None or
            after['p95_onset_delay_seconds'] is not None and before['p95_onset_delay_seconds'] is not None and after['p95_onset_delay_seconds']>before['p95_onset_delay_seconds'])


def model_context():
    p,config,specs,stats,ref,ft=utils.setup()
    path=ROOT/'output/mes-timestral-ablation-development-20261021/result.json'
    if base.sha(path)!='0fdcf7c8cc73f10d58c37b93745e6893ee4f304d1fddd86c3e6273e8fac8371a':raise ValueError('ablation reference changed')
    prior=json.loads(path.read_text(encoding='utf-8'))
    if prior['checkpoint_sha256']!=ft['checkpoint_sha256'] or prior['runtime_sha256']!=base.verify_runtime(p['runtime']):raise ValueError('model or runtime changed')
    for filename,expected in prior['helper_sha256'].items():
        if base.sha(ROOT/'scripts'/filename)!=expected:raise ValueError('alarm helper changed')
    return p,config,specs,stats,ref,ft,prior


def write_dataset(out,index,runs,alerts,metrics,policy,provenance):
    data=dict(metrics=metrics,background={n:base.background(runs,a) for n,a in alerts.items()},provenance=provenance,
        notification_results={},display_unchanged=True)
    obs=observations(runs)
    for name,a in alerts.items():
        pulses=notifications(obs,a,**policy)
        data['notification_results'][name]=assess(runs,a,pulses,metrics[name],metrics['ewma'])
        zero=assess(runs,a,notifications(obs,a,0,None),metrics[name],metrics['ewma'])
        assert zero['metrics']=={k:metrics[name][k] for k in zero['metrics']} and not zero['changes']
        base.write_new(out/f'dataset-{index}-{name}-notifications.json',[[r,s,sorted(v)] for (r,s),v in pulses.items()])
    base.write_new(out/f'dataset-{index}-observations.json',obs)
    base.write_new(out/f'dataset-{index}-displays.json',{n:[[r,s,sorted(v)] for (r,s),v in a.items()] for n,a in alerts.items()})
    return data


def develop(args,context):
    p,config,specs,stats,ref,ft,prior=context
    from scripts.mes_validation_candidate_review import load_train_validation
    from scripts.evaluate_mes_fault_models import score
    policies=[dict(cooldown=0,quiet=None)]+[dict(cooldown=c,quiet=q) for c in (5,10,15,20,25,30,40,60) for q in (None,3,6,10)]
    rows=[dict(params=policy,metrics=[],lost=[],gained=[],delayed=[],duplicate_excess=[],p95_worse=[]) for policy in policies]
    for i,d in enumerate(prior['datasets']):
        _,splits=load_train_validation(Path(d['provenance']['dataset']),profile='independent');runs=splits['validation'];del splits
        saved=json.loads((ROOT/f'output/mes-timestral-ablation-development-20261021/dataset-{i+1}-alerts.json').read_text(encoding='utf-8'))
        alerts={n:{(r,s):set(v) for r,s,v in saved[n]} for n in ('full','no_timestral','ewma')}
        for n,a in alerts.items():assert score(runs,a)==d['metrics'][n]
        obs=observations(runs)
        for row in rows:
            assessment=assess(runs,alerts['full'],notifications(obs,alerts['full'],**row['params']),d['metrics']['full'],d['metrics']['ewma'])
            row['metrics'].append(assessment['metrics'])
            for key in ('lost','gained','delayed','duplicate_excess','p95_worse'):row[key].append(assessment[key])
        print(f'development {i+1}/4: 33 policies scored',flush=True)
        del runs,alerts,obs;gc.collect()
    selected=choose(rows);datasets=[]
    if selected is not None:
        for i,d in enumerate(prior['datasets']):
            _,splits=load_train_validation(Path(d['provenance']['dataset']),profile='independent');runs=splits['validation'];del splits
            saved=json.loads((ROOT/f'output/mes-timestral-ablation-development-20261021/dataset-{i+1}-alerts.json').read_text(encoding='utf-8'))
            alerts={n:{(r,s):set(v) for r,s,v in saved[n]} for n in ('full','no_timestral','ewma')}
            datasets.append(write_dataset(args.out_dir,i+1,runs,alerts,{n:d['metrics'][n] for n in alerts},selected['params'],d['provenance']))
            del runs,alerts;gc.collect()
    return dict(phase='develop',selected=selected['params'] if selected else None,development_passed=selected is not None,
        grid=rows,datasets=datasets,reference_sha256='0fdcf7c8cc73f10d58c37b93745e6893ee4f304d1fddd86c3e6273e8fac8371a')


def confirm(args,context):
    p,config,specs,stats,ref,ft,prior=context
    selection=json.loads(args.selection.read_text(encoding='utf-8'))
    if (not selection['development_passed'] or selection['script_sha256']!=base.sha(__file__)
            or selection['checkpoint_sha256']!=ft['checkpoint_sha256']):raise ValueError('selection changed')
    from scripts.build_mes_fault_dataset import build_dataset
    from scripts.mes_validation_candidate_review import load_train_validation
    from scripts.evaluate_mes_fault_models import valid_values,score
    from scripts.mes_training_source import prefix_hashes
    old_seeds=set();old_ids=set()
    for path in (ROOT/'output').glob('mes-*/manifest.json'):
        manifest=json.loads(path.read_text(encoding='utf-8'))
        old_seeds.update(r['seed'] for r in manifest.get('runs',[]) if 'seed' in r)
        old_ids.update(r['run_id'] for r in manifest.get('runs',[]) if 'run_id' in r)
    if set(range(85371,85395))&old_seeds:raise ValueError('confirmation seed already used')
    fresh=ROOT/'output/mes-timestral-notify-confirm-v7-seed85371-20261022'
    if fresh.exists():raise FileExistsError(fresh)
    manifest=build_dataset(fresh,runs_per_split=8,ticks=300,seed=85371,hazard=.003,profile='independent',warmup_ticks=60,response_scale=.2)
    if old_ids&{r['run_id'] for r in manifest['runs']}:raise ValueError('confirmation run overlap')
    other,splits=load_train_validation(fresh,profile='independent');runs=splits['validation'];del splits
    if other.config_id!=config.config_id:raise ValueError('confirmation config changed')
    print('fresh validation locked; running CPU1/worker1/batch1 forecasts',flush=True)
    import torch
    from timestral import TimestralForecaster
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.use_deterministic_algorithms(True)
    model=TimestralForecaster.from_pretrained(p['ft']/'checkpoint',device='cpu',local_files_only=True)
    channels=[tuple(c) for c in ref['channels']]
    predictions=args.out_dir/'confirmation-predictions.npz'
    _,_,_,timing=base.forecast_scores({r:[f for f,_ in rows] for r,rows in runs.items()},channels,stats,
        lambda f:valid_values(f,specs),model,predictions,batch=1,workers=1)
    del model,runs;gc.collect()
    data=utils.prepare(fresh,predictions,stats,specs,channels,ft['thresholds']['finetuned'])
    import numpy as np
    original=previous.preserve.predict(data,previous.previous.CURRENT)
    alerts=dict(full=previous.predict(data,original,prior['fast_params']),ewma=data['baseline'])
    alerts['no_timestral']={key:{eq for j,eq in enumerate(data['equipment']) if np.isfinite(data['ratio'][i,j]) and
        (eq in data['baseline'][key] or np.isfinite(data['raw_z'][i,j]) and data['raw_z'][i,j]>=2.5)} for i,key in enumerate(data['keys'])}
    metrics={n:score(data['runs'],a) for n,a in alerts.items()}
    provenance=dict(dataset=str(fresh),predictions=str(predictions),prefix_sha256=prefix_hashes(fresh,manifest),predictions_sha256=base.sha(predictions))
    result=write_dataset(args.out_dir,1,data['runs'],alerts,metrics,selection['selected'],provenance)
    notice=result['notification_results']['full']
    passed=not any(notice[k] for k in ('lost','gained','delayed','duplicate_excess','p95_worse'))
    return dict(phase='confirm',selected=selection['selected'],confirmation_passed=passed,datasets=[result],
        selection_sha256=base.sha(args.selection),forecast_timing_pc=timing,new_neural_calls=timing['windows']+len(timing['single_window_seconds']))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=('develop','confirm'),required=True)
    parser.add_argument('--out-dir',type=Path,required=True);parser.add_argument('--selection',type=Path)
    args=parser.parse_args()
    if args.phase=='confirm' and args.selection is None:parser.error('confirm requires selection')
    args.out_dir.mkdir(parents=True,exist_ok=False);started=time.perf_counter();context=model_context()
    result=develop(args,context) if args.phase=='develop' else confirm(args,context)
    result.update(script_sha256=base.sha(__file__),checkpoint_sha256=context[5]['checkpoint_sha256'],
        runtime_sha256=base.verify_runtime(context[0]['runtime']),test_rows_read=0,total_seconds=time.perf_counter()-started)
    base.write_new(args.out_dir/'result.json',result)
    print(json.dumps(dict(selected=result['selected'],passed=result.get('development_passed',result.get('confirmation_passed')),
        datasets=[dict(display={n:{k:v for k,v in m.items() if k in ('detected_events','injected_events','wrong_alert_equipment_seconds','duplicate_alert_episodes','p95_onset_delay_seconds')} for n,m in d['metrics'].items()},
            notifications=d['notification_results']) for d in result['datasets']])),flush=True)


if __name__=='__main__':
    main()
