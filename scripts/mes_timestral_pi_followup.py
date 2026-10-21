"""Causal alarm selection and untouched confirmation for the saved Timestral head."""
import argparse
import gc
import hashlib
import importlib.util
import json
import os
import sys
import time
from collections import deque
from pathlib import Path

os.environ['OMP_NUM_THREADS']='1'
os.environ['MKL_NUM_THREADS']='1'
os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def module(name,filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/filename)
    loaded=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


base=module('followup_comparison','mes_timestral_comparison.py')

def causal_alerts(keys, values, equipment, thresholds, scale, k, n):
    if (not np.isfinite(scale) or scale<=0 or not 1<=k<=n<=5
            or np.shape(values)!=(len(keys),len(equipment))):
        raise ValueError('invalid alarm contract')
    output={};history=deque(maxlen=n);previous=None
    limits=np.array([thresholds[eq]*scale for eq in equipment])
    if not np.isfinite(limits).all() or (limits<=0).any():
        raise ValueError('invalid thresholds')
    for key,row in zip(keys,values):
        if key in output:raise ValueError('duplicate prediction key')
        if previous is None or key[0]!=previous[0] or key[1]!=previous[1]+1:
            history.clear()
        current=np.isfinite(row)&(row>limits)
        history.append(current)
        enabled=current&(np.sum(history,axis=0)>=k)
        output[key]={eq for eq,yes in zip(equipment,enabled) if yes}
        previous=key
    return output


def choose(candidates, baseline):
    passed=[row for row in candidates if improved(baseline,row['metrics'])]
    def order(row):
        m=row['metrics'];delay=m['p95_onset_delay_seconds']
        return (-m['detected_events'],m['wrong_alert_equipment_seconds'],
                float('inf') if delay is None else delay,row['scale'],row['k'],row['n'])
    return min(passed or candidates,key=order),bool(passed)


def improved(before,after):
    return (after['detected_events']>before['detected_events'] and
            after['wrong_alert_equipment_seconds']<before['wrong_alert_equipment_seconds'])


def paths():
    output=ROOT/'output'
    return {'runtime':output/'mes-diagnostic-runtime-20261021',
            'source':output/'mes-fault-current-v7-seed2371-full-20261021',
            'normal':output/'mes-timestral-ft-normal-v7-seed35371-20261021',
            'dev':output/'mes-timestral-ft-weak-v7-seed45371-20261021',
            'ft':output/'mes-timestral-finetune-20261021',
            'reference':output/'mes-timestral-20261021/calibration.json'}


def evaluate(args):
    started=time.perf_counter();p=paths()
    runtime_hash=base.verify_runtime(p['runtime'])
    sys.path.insert(0,str(p['runtime']))
    from scripts.mes_validation_candidate_review import load_train_validation
    from scripts.evaluate_mes_fault_models import fit_normal,predict_ewma,score,valid_values
    from scripts.mes_training_source import prefix_hashes
    from scripts.mes_ewma_release_review import paired_events
    if not Path(sys.modules['scripts.evaluate_mes_fault_models'].__file__).resolve().is_relative_to(p['runtime']):
        raise ValueError('incorrect frozen scorer')
    original=json.loads((p['ft']/'result.json').read_text(encoding='utf-8'))
    if base.sha(p['ft']/'checkpoint/model.safetensors')!=original['checkpoint_sha256']:
        raise ValueError('checkpoint changed')
    ref=json.loads(p['reference'].read_text(encoding='utf-8'))
    config,source=load_train_validation(p['source'],profile='independent')
    specs,stats=fit_normal(source['train'],config)
    digest=hashlib.sha256(json.dumps([[*c,*stats[c]] for c in sorted(stats)]).encode()).hexdigest()
    if digest!=ref['training_provenance']['stats_sha256']:raise ValueError('normalization changed')
    del source;gc.collect()
    thresholds=original['thresholds']['finetuned']
    channels=[tuple(c) for c in ref['channels']]
    chosen=None
    if args.phase=='confirm':
        selected=json.loads(args.selection.read_text(encoding='utf-8'))
        if (selected['checkpoint_sha256']!=original['checkpoint_sha256'] or
                selected['script_sha256']!=base.sha(__file__)):
            raise ValueError('selection provenance changed')
        chosen=selected['selected']
        if selected['thresholds']!=thresholds:raise ValueError('thresholds changed')
        manifests=[json.loads((p[name]/'manifest.json').read_text(encoding='utf-8')) for name in ('source','normal','dev')]
        manifest=json.loads((args.fresh/'manifest.json').read_text(encoding='utf-8'))
        groups=[v['runs'] for v in manifests]+[manifest['runs']]
        for i,a in enumerate(groups):
            for b in groups[i+1:]:
                if any({v[field] for v in a}&{v[field] for v in b} for field in ('seed','run_id')):
                    raise ValueError('seed or run overlap')
        if (manifest['generator_version']!=7 or manifest['profile']!='independent' or
                manifest['response_scale']!=.2 or manifest['hazard']!=.003):
            raise ValueError('confirmation contract changed')
        other,normal=load_train_validation(p['normal'],profile='independent')
        fit={key:normal['train'][key] for key in list(normal['train'])[:4]}
        _,matched_stats=fit_normal(fit,config)
        del normal,fit;gc.collect()
        dataset=args.fresh
    else:dataset=p['dev']
    other,splits=load_train_validation(dataset,profile='independent')
    if other.config_id!=config.config_id:raise ValueError('configuration differs')
    runs=splits['validation'];del splits['train'];del splits;gc.collect()
    baseline=predict_ewma(runs,specs,stats,3)
    metrics={'ewma':score(runs,baseline)}
    alerts={'ewma':baseline};timing=None;verification=None
    if args.phase=='develop':
        if base.sha(p['ft']/'weak-predictions.npz')!=original['feature_meta']['weak']['sha256']:
            raise ValueError('development forecasts changed')
        with np.load(p['ft']/'weak-predictions.npz',allow_pickle=False) as cache:
            actual=cache['actual'];q=cache['adapted'][:,:,[0,10,20]]
            keys=[(str(r),int(s)) for r,s in cache['keys']]
        equipment=sorted({c[0] for c in channels})
        values=base.channel_scores(actual,q[:,:,1],q[:,:,0],q[:,:,2],np.array([stats[c][1] for c in channels]))
        values=np.stack([np.max(np.where(np.isnan(values[:,indices]),-np.inf,values[:,indices]),axis=1)
                        for eq in equipment for indices in [[i for i,c in enumerate(channels) if c[0]==eq]]],axis=1)
        if metrics['ewma']!=original['metrics']['ewma_current']:raise ValueError('development baseline differs')
    else:
        import torch
        from timestral import TimestralForecaster
        from scripts.mes_location_replay import replay_validation
        torch.set_num_threads(1);torch.set_num_interop_threads(1)
        verification=replay_validation(dataset,config,runs)['verification']
        model=TimestralForecaster.from_pretrained(p['ft']/'checkpoint',device='cpu',local_files_only=True)
        keys,values,equipment,timing=base.forecast_scores(
            {r:[f for f,_ in rows] for r,rows in runs.items()},channels,stats,
            lambda f:valid_values(f,specs),model,args.out_dir/'confirmation-predictions.npz',batch=1,workers=1)
        timing['process_peak_rss_bytes']=module('followup_resources','mes_timestral_low_resource.py').peak_rss_bytes()
        alerts['ewma_normal_refit']=predict_ewma(runs,specs,matched_stats,3)
    tick=time.perf_counter()
    default=causal_alerts(keys,values,equipment,thresholds,1,1,1)
    complete=lambda current:{(r,f['sequence']):current.get((r,f['sequence']),set()) for r,rows in runs.items() for f,_ in rows}
    alerts['finetuned_default']=complete(default)
    metrics['finetuned_default']=score(runs,alerts['finetuned_default'])
    if args.phase=='develop':
        if metrics['finetuned_default']!=original['metrics']['finetuned']:raise ValueError('development forecasts differ')
        grid=[]
        for scale in (.5,.75,1,1.25,1.5,2):
            for k,n in ((1,1),(2,3),(3,5)):
                candidate=complete(causal_alerts(keys,values,equipment,thresholds,scale,k,n))
                grid.append({'scale':scale,'k':k,'n':n,'metrics':score(runs,candidate)})
        chosen,passed=choose(grid,metrics['ewma'])
    else:grid=None;passed=selected['development_passed']
    tick=time.perf_counter()
    alerts['candidate']=complete(causal_alerts(keys,values,equipment,thresholds,chosen['scale'],chosen['k'],chosen['n']))
    alarm_seconds=time.perf_counter()-tick
    for name,current in alerts.items():metrics[name]=score(runs,current)
    manifest=json.loads((dataset/'manifest.json').read_text(encoding='utf-8'))
    result={'phase':args.phase,'selected':{key:chosen[key] for key in ('scale','k','n')},
        'development_passed':passed,'grid':grid,'metrics':metrics,'thresholds':thresholds,
        'requested_improvement_vs':{name:improved(metrics[name],metrics['candidate']) for name in metrics if name!='candidate'},
        'paired_events':{name:paired_events(runs,current,alerts['candidate'],metrics[name],metrics['candidate']) for name,current in alerts.items() if name!='candidate'},
        'background':{name:base.background(runs,current) for name,current in alerts.items()},
        'alerts':{name:[[r,s,sorted(v)] for (r,s),v in current.items()] for name,current in alerts.items()},
        'checkpoint_sha256':original['checkpoint_sha256'],'script_sha256':base.sha(__file__),
        'runtime_sha256':runtime_hash,'dataset_prefix_sha256':prefix_hashes(dataset,manifest),
        'selection_sha256':base.sha(args.selection) if args.phase=='confirm' else None,
        'replay_verification':verification,'test_rows_read':0,'timing':timing,
        'alarm_seconds':alarm_seconds,'prediction_windows':len(keys),'total_seconds':time.perf_counter()-started,
        'limits':'Synthetic running data; PC CPU1thread/worker1/batch1; Pi4 RAM/ARM speed unverified.'}
    base.verify_runtime(p['runtime'])
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('develop','confirm'),required=True)
    parser.add_argument('--out-dir',type=Path,required=True)
    parser.add_argument('--fresh',type=Path)
    parser.add_argument('--selection',type=Path)
    args=parser.parse_args()
    if args.phase=='confirm' and (args.fresh is None or args.selection is None):parser.error('confirmation requires fresh and selection')
    args.out_dir.mkdir(parents=True,exist_ok=False)
    result=evaluate(args)
    base.write_new(args.out_dir/'result.json',result)
    print(json.dumps({'selected':result['selected'],'development_passed':result['development_passed'],
        'metrics':{name:{key:m[key] for key in ('detected_events','injected_events','wrong_alert_equipment_seconds','duplicate_alert_episodes','p95_onset_delay_seconds')} for name,m in result['metrics'].items()},
        'requested_improvement_vs':result['requested_improvement_vs']}),flush=True)


if __name__=='__main__':main()
