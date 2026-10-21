"""Bounded causal state-machine experiment around a fixed Timestral checkpoint."""
import argparse
import gc
import itertools
import json
import sys
import time
from datetime import datetime
from pathlib import Path
import importlib.util

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('stateful_previous',ROOT/'scripts/mes_timestral_pi_followup.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
base=previous.base
import numpy as np


def stateful_alerts(keys, raw_z, ratio, baseline, equipment, resets, params, *, use_timestral=True):
    gate,on_scale,on_z,off_z,release=(params[k] for k in ('gate','on_scale','on_z','off_z','release'))
    if (not 0<=gate or not 0<on_scale or not 0<off_z<=on_z or release not in (1,2)
            or raw_z.shape!=ratio.shape or raw_z.shape!=(len(keys),len(equipment)) or len(resets)!=len(keys)):
        raise ValueError('invalid state-machine contract')
    active=np.zeros(len(equipment),dtype=bool);low=np.zeros(len(equipment),dtype=int)
    output={};last=None
    for i,key in enumerate(keys):
        if key in output:raise ValueError('duplicate key')
        if resets[i] or last is None or last[0]!=key[0] or last[1]+1!=key[1]:
            active[:]=False;low[:]=0
        valid=np.isfinite(raw_z[i])
        above=valid&(raw_z[i]>=off_z)
        entered=active.copy()
        low=np.where(above,0,low+1)
        active &= valid&(low<release)
        accepted=(ratio[i]>gate) if use_timestral and gate else np.ones(len(equipment),dtype=bool)
        ewma=np.array([eq in baseline.get(key,set()) for eq in equipment])
        extra=(ratio[i]>on_scale)&(raw_z[i]>=on_z) if use_timestral else np.zeros(len(equipment),dtype=bool)
        start=(~entered)&above&((ewma&accepted)|extra)
        active |= start;low[start]=0
        output[key]={eq for eq,enabled in zip(equipment,active) if enabled}
        last=key
    return output


def choose(candidates, baselines):
    def violations(row):
        return sum(sum((m['detected_events']<=b['detected_events'],
            m['wrong_alert_equipment_seconds']>=b['wrong_alert_equipment_seconds'],
            m['duplicate_alert_episodes']>b['duplicate_alert_episodes'],
            m['p95_onset_delay_seconds'] is None or m['p95_onset_delay_seconds']>b['p95_onset_delay_seconds']))
            for m,b in zip(row['metrics'],baselines))
    def order(row,passed):
        metrics=row['metrics'];p=row['params']
        events=sum(m['detected_events'] for m in metrics)
        wrong=sum(m['wrong_alert_equipment_seconds'] for m in metrics)
        duplicate=sum(m['duplicate_alert_episodes'] for m in metrics)
        delay=max(float('inf') if m['p95_onset_delay_seconds'] is None else m['p95_onset_delay_seconds'] for m in metrics)
        tie=tuple(p[k] for k in ('gate','on_scale','on_z','off_z','release'))
        if passed:return (-events,wrong,duplicate,delay,*tie)
        return (violations(row),max(m['duplicate_alert_episodes']/max(b['duplicate_alert_episodes'],1) for m,b in zip(metrics,baselines)),
            max((float('inf') if m['p95_onset_delay_seconds'] is None else m['p95_onset_delay_seconds'])/max(b['p95_onset_delay_seconds'],1) for m,b in zip(metrics,baselines)),wrong,-events,*tie)
    passed=[row for row in candidates if violations(row)==0]
    return min(passed or candidates,key=lambda row:order(row,bool(passed))),bool(passed)


def setup():
    p=previous.paths();base.verify_runtime(p['runtime']);sys.path.insert(0,str(p['runtime']))
    from scripts.mes_validation_candidate_review import load_train_validation
    from scripts.evaluate_mes_fault_models import fit_normal
    ref=json.loads(p['reference'].read_text(encoding='utf-8'))
    config,splits=load_train_validation(p['source'],profile='independent')
    specs,stats=fit_normal(splits['train'],config)
    del splits;gc.collect()
    import hashlib
    digest=hashlib.sha256(json.dumps([[*c,*stats[c]] for c in sorted(stats)]).encode()).hexdigest()
    if digest!=ref['training_provenance']['stats_sha256']:raise ValueError('normalization changed')
    ft=json.loads((p['ft']/'result.json').read_text(encoding='utf-8'))
    if base.sha(p['ft']/'checkpoint/model.safetensors')!=ft['checkpoint_sha256']:raise ValueError('checkpoint changed')
    return p,config,specs,stats,ref,ft


def prepare(dataset,predictions,stats,specs,channels,thresholds,*,q21=False):
    from scripts.mes_validation_candidate_review import load_train_validation
    from scripts.evaluate_mes_fault_models import predict_ewma,valid_values
    from scripts.mes_training_source import prefix_hashes
    config,splits=load_train_validation(dataset,profile='independent')
    runs=splits['validation'];del splits['train'];del splits;gc.collect()
    with np.load(predictions,allow_pickle=False) as cache:
        if [tuple(c) for c in cache['channels']]!=channels:raise ValueError('channels changed')
        if q21:
            q=cache['adapted'][:,:,[0,10,20]];actual=cache['actual']
            values=base.channel_scores(actual,q[:,:,1],q[:,:,0],q[:,:,2],np.array([stats[c][1] for c in channels]))
            equipment=sorted({c[0] for c in channels})
            values=np.stack([np.max(np.where(np.isnan(values[:,idx]),-np.inf,values[:,idx]),axis=1)
                for eq in equipment for idx in [[i for i,c in enumerate(channels) if c[0]==eq]]],axis=1)
            prediction_keys=[(str(r),int(s)) for r,s in cache['keys']]
        else:
            equipment=sorted({c[0] for c in channels});values=cache['equipment_scores']
            prediction_keys=[(str(r),int(s)) for r,s in cache['context_keys']]
    lookup={key:row for key,row in zip(prediction_keys,values)}
    expected=base.causal_windows({r:[f for f,_ in rows] for r,rows in runs.items()},channels,lambda f:valid_values(f,specs))[1]
    if prediction_keys!=expected:raise ValueError('prediction keys differ')
    keys=[];raw=[];ratios=[];resets=[]
    for r,rows in runs.items():
        last=None;was_ready=None
        for f,_ in rows:
            key=(r,f['sequence']);at=datetime.fromisoformat(f['simulated_at']);ready=key in lookup
            inactive=f.get('line_mode') in base.INACTIVE
            resets.append(last is None or (at-last).total_seconds()!=1 or inactive or (was_ready is not None and ready!=was_ready))
            current=valid_values(f,specs);by_eq={eq:[] for eq in equipment}
            for channel in channels:
                if channel in current:
                    center,scale=stats[channel];by_eq[channel[0]].append(abs(current[channel]-center)/scale)
            raw.append([max(by_eq[eq]) if by_eq[eq] and not inactive else np.nan for eq in equipment])
            value=lookup.get(key,np.full(len(equipment),np.nan))
            ratios.append([v/thresholds[eq] for eq,v in zip(equipment,value)])
            keys.append(key);last=at;was_ready=ready
    baseline=predict_ewma(runs,specs,stats,3)
    manifest=json.loads((dataset/'manifest.json').read_text(encoding='utf-8'))
    return dict(runs=runs,keys=keys,raw_z=np.array(raw),ratio=np.array(ratios),baseline=baseline,
        equipment=equipment,resets=resets,config_id=config.config_id,
        prefix_sha256=prefix_hashes(dataset,manifest),predictions_sha256=base.sha(predictions))


def predict(data,params,*,use_timestral=True):
    return stateful_alerts(*(data[k] for k in ('keys','raw_z','ratio','baseline','equipment','resets')),params,use_timestral=use_timestral)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('develop','confirm'),required=True)
    parser.add_argument('--out-dir',type=Path,required=True)
    parser.add_argument('--selection',type=Path)
    parser.add_argument('--fresh',type=Path)
    args=parser.parse_args();args.out_dir.mkdir(parents=True,exist_ok=False)
    p,config,specs,stats,ref,ft=setup();channels=[tuple(c) for c in ref['channels']]
    from scripts.evaluate_mes_fault_models import score
    from scripts.mes_ewma_release_review import paired_events
    thresholds=ft['thresholds']['finetuned'];started=time.perf_counter()
    if args.phase=='develop':
        prior_path=ROOT/'output/mes-timestral-pi-followup-confirmation-20261021'
        prior=json.loads((prior_path/'result.json').read_text(encoding='utf-8'))
        datasets=[]
        for dataset,predictions,q21,reference in (
            (p['dev'],p['ft']/'weak-predictions.npz',True,ft['metrics']['ewma_current']),
            (ROOT/'output/mes-timestral-pi-confirm-v7-seed55371-20261021',prior_path/'confirmation-predictions.npz',False,prior['metrics']['ewma'])):
            d=prepare(dataset,predictions,stats,specs,channels,thresholds,q21=q21)
            if d['config_id']!=config.config_id or score(d['runs'],d['baseline'])!=reference:raise ValueError('development differs')
            datasets.append(d)
        grid=[];baselines=[score(d['runs'],d['baseline']) for d in datasets]
        for index,values in enumerate(itertools.product((0,.1),(.75,1,1.5),(2.5,3,3.5),(1.5,2,2.5),(1,2))):
            params=dict(zip(('gate','on_scale','on_z','off_z','release'),values))
            metrics=[score(d['runs'],predict(d,params)) for d in datasets]
            grid.append({'params':params,'metrics':metrics})
            if index%18==0:print(f'development: {index+1}/108',flush=True)
        chosen,passed=choose(grid,baselines)
        result={'selected':chosen['params'],'development_passed':passed,'selected_metrics':chosen['metrics'],
            'baselines':baselines,'grid':grid,'script_sha256':base.sha(__file__),
            'checkpoint_sha256':ft['checkpoint_sha256'],'thresholds':thresholds,
            'provenance':[{k:d[k] for k in ('prefix_sha256','predictions_sha256')} for d in datasets]}
    else:
        if args.selection is None or args.fresh is None:parser.error('confirmation requires selection and fresh')
        selected=json.loads(args.selection.read_text(encoding='utf-8'))
        if selected['script_sha256']!=base.sha(__file__) or selected['checkpoint_sha256']!=ft['checkpoint_sha256'] or selected['thresholds']!=thresholds:
            raise ValueError('selection changed')
        manifest=json.loads((args.fresh/'manifest.json').read_text(encoding='utf-8'))
        known=[json.loads((path/'manifest.json').read_text(encoding='utf-8'))['runs'] for path in
            (p['source'],p['normal'],p['dev'],ROOT/'output/mes-timestral-pi-confirm-v7-seed55371-20261021')]
        for runs in known:
            if any({r[field] for r in runs}&{r[field] for r in manifest['runs']} for field in ('run_id','seed')):raise ValueError('fresh overlaps')
        # Reuse the fixed official inference/scoring pipeline without changing its code.
        old=previous.evaluate(argparse.Namespace(phase='confirm',selection=ROOT/'output/mes-timestral-pi-hybrid-development-20261021/result.json',
            fresh=args.fresh,out_dir=args.out_dir,hybrid=False))
        data=prepare(args.fresh,args.out_dir/'confirmation-predictions.npz',stats,specs,channels,thresholds)
        alerts={name:{(r,int(s)):set(v) for r,s,v in rows} for name,rows in old['alerts'].items() if name!='standalone_diagnostic'}
        alerts['previous_hybrid']=alerts.pop('candidate')
        tick=time.perf_counter();alerts['stateful']=predict(data,selected['selected']);alarm_seconds=time.perf_counter()-tick
        alerts['ewma_stateful_ablation']=predict(data,selected['selected'],use_timestral=False)
        metrics={name:score(data['runs'],a) for name,a in alerts.items()}
        result={'selected':selected['selected'],'development_passed':selected['development_passed'],
            'metrics':metrics,'alerts':{name:[[r,s,sorted(v)] for (r,s),v in a.items()] for name,a in alerts.items()},
            'paired_events':{name:paired_events(data['runs'],a,alerts['stateful'],metrics[name],metrics['stateful']) for name,a in alerts.items() if name!='stateful'},
            'background':{name:base.background(data['runs'],a) for name,a in alerts.items()},
            'requested_improvement_vs':{name:previous.improved(m,metrics['stateful']) for name,m in metrics.items() if name!='stateful'},
            'all_four_failures_vs':{name:base.aggregate_failures(m,metrics['stateful']) for name,m in metrics.items() if name!='stateful'},
            'selection_sha256':base.sha(args.selection),'script_sha256':base.sha(__file__),
            'checkpoint_sha256':ft['checkpoint_sha256'],'thresholds':thresholds,
            'dataset_prefix_sha256':data['prefix_sha256'],'predictions_sha256':data['predictions_sha256'],
            'runtime_sha256':base.verify_runtime(p['runtime']),'previous_script_sha256':base.sha(previous.__file__),
            'test_rows_read':0,'replay_verification':old['replay_verification'],'timing':old['timing'],
            'alarm_seconds':alarm_seconds,'grid':None}
    result['total_seconds']=time.perf_counter()-started
    base.write_new(args.out_dir/'result.json',result)
    if args.phase=='develop':print(json.dumps({k:result[k] for k in ('selected','development_passed','selected_metrics','baselines')}),flush=True)
    else:print(json.dumps({name:{key:m[key] for key in ('detected_events','injected_events','wrong_alert_equipment_seconds','duplicate_alert_episodes','p95_onset_delay_seconds')} for name,m in result['metrics'].items()}),flush=True)


if __name__=='__main__':main()
