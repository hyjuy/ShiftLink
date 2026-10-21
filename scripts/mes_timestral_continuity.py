"""Observation-only continuity filters with framewise source-display preservation."""
import importlib.util
import argparse
import gc
import itertools
import json
import time
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('continuity_previous',ROOT/'scripts/mes_timestral_rearm.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
preserve=previous.preserve;utils=previous.utils;base=previous.base


def continuity_alerts(keys,raw_z,ratio,baseline,equipment,resets,current,params):
    if (np.shape(raw_z)!=np.shape(ratio) or np.shape(raw_z)!=(len(keys),len(equipment))
            or len(resets)!=len(keys) or not 0<params['peak_fraction']<=1
            or not 0<=params['gap']<=12 or params['clean_z']<0 or params['hold_z']<0):
        raise ValueError('invalid continuity contract')
    anchor=np.full(len(equipment),-1,dtype=int);peak=np.zeros(len(equipment))
    was_on=np.zeros(len(equipment),dtype=bool);last_clean=was_on.copy();output={};last=None
    for i,key in enumerate(keys):
        if key in output:raise ValueError('duplicate key')
        if resets[i] or last is None or last[0]!=key[0] or last[1]+1!=key[1]:
            anchor[:]=-1;peak[:]=0;was_on[:]=False;last_clean[:]=False
        old=np.array([eq in current.get(key,set()) for eq in equipment])
        if params.get('control'):
            output[key]=set(current.get(key,set()));last=key;continue
        valid=np.isfinite(raw_z[i])&np.isfinite(ratio[i])
        clean=old if params['clean_z']==0 else old&np.isfinite(raw_z[i])&(raw_z[i]>=params['clean_z'])
        ewma=np.array([eq in baseline.get(key,set()) for eq in equipment])
        anchor[~valid]=-1;peak[~valid]=0
        bridge=(was_on&(anchor>=0)&((key[1]-anchor)<=params['gap'])&ewma&valid
            &(ratio[i]>.025)&(raw_z[i]>=params['hold_z'])&(raw_z[i]>=peak*params['peak_fraction']))
        early=(valid&(ratio[i]>params['early_scale'])&(raw_z[i]>=params['early_z'])
            if params['early_scale'] is not None else np.zeros(len(equipment),dtype=bool))
        enabled=clean|bridge|early
        clean_valid=clean&valid
        peak=np.where(clean_valid,np.where(last_clean,np.maximum(peak,raw_z[i]),raw_z[i]),peak)
        anchor[clean_valid]=key[1]
        anchor[~enabled]=-1;peak[~enabled]=0
        output[key]={eq for eq,on in zip(equipment,enabled) if on}
        was_on=enabled;last_clean=clean_valid;last=key
    return output


def coverage_loss(keys,positive,before,after):
    return sum(len((before.get(key,set())-after.get(key,set()))&positive[key]) for key in keys)


def violations(row,current,baselines):
    return previous.violations(row,current,baselines)+[
        f'{i+1}:display' for i,removed in enumerate(row['removed_active']) if removed]


def choose(rows,current,baselines):
    accepted=[row for row in rows if not violations(row,current,baselines)]
    preserving=[row for row in rows if not any(tag.rsplit(':',1)[1] not in ('duplicates','latest_strict_delay')
        for tag in violations(row,current,baselines))]
    def order(row):
        m=row['metrics'];p=row['params']
        tie=tuple(p[k] if p[k] is not None else 999 for k in ('clean_z','gap','hold_z','peak_fraction','early_scale','early_z'))
        dup=sum(v['duplicate_alert_episodes'] for v in m);wrong=sum(v['wrong_alert_equipment_seconds'] for v in m)
        if accepted:return (sum(row['delayed']),dup,sum(v['p95_onset_delay_seconds'] for v in m),wrong,-sum(v['detected_events'] for v in m),*tie)
        if preserving:return (max(v['duplicate_alert_episodes']/max(e['duplicate_alert_episodes'],1) for v,e in zip(m,baselines)),
            m[-1]['p95_onset_delay_seconds'],dup,sum(row['delayed']),wrong,*tie)
        return (sum(row['removed_active']),sum(row['lost']),len(violations(row,current,baselines)),*tie)
    return min(accepted or preserving or rows,key=order),bool(accepted)


def predict(data,current,params):
    return continuity_alerts(*(data[k] for k in ('keys','raw_z','ratio','baseline','equipment','resets')),current,params)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir',type=Path,required=True)
    args=parser.parse_args();args.out_dir.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter();p,config,specs,stats,ref,ft=utils.setup()
    from scripts.evaluate_mes_fault_models import score
    from scripts.mes_ewma_release_review import paired_events,alarm_changes
    reference=ROOT/'output/mes-timestral-rearm-development-20261021/result.json'
    prior=json.loads(reference.read_text(encoding='utf-8'))
    if (len(prior['provenance'])!=4 or prior['script_sha256']!=base.sha(previous.__file__)
            or prior['preserve_sha256']!=base.sha(preserve.__file__) or prior['helper_sha256']!=base.sha(utils.__file__)
            or prior['checkpoint_sha256']!=ft['checkpoint_sha256'] or prior['thresholds']!=ft['thresholds']['finetuned']):
        raise ValueError('fixed references changed')
    channels=[tuple(c) for c in ref['channels']];thresholds=ft['thresholds']['finetuned']
    control=dict(control=True,clean_z=0,gap=0,hold_z=0,peak_fraction=1,early_scale=None,early_z=None)
    parameters=[control]+[dict(clean_z=clean,gap=gap,hold_z=hold,peak_fraction=fraction,early_scale=early,early_z=z)
        for clean,gap,hold,fraction,early,z in itertools.product((0,2,3),(3,6,12),(2.5,3.5),(.75,.9),(.1,.25,.5),(2.5,3))]
    grid=[dict(params=params,metrics=[],lost=[],delayed=[],removed_active=[]) for params in parameters]
    current_metrics=[];ewma_metrics=[];provenance=[]
    for i,source in enumerate(prior['provenance']):
        data=utils.prepare(Path(source['dataset']),Path(source['predictions']),stats,specs,channels,thresholds,q21=source['q21'])
        if data['config_id']!=config.config_id or any(data[k]!=source[k] for k in ('prefix_sha256','predictions_sha256')):
            raise ValueError('development data or predictions changed')
        current=preserve.predict(data,previous.CURRENT)
        c=score(data['runs'],current);e=score(data['runs'],data['baseline'])
        if c!=prior['current_metrics'][i] or e!=prior['ewma_metrics'][i]:raise ValueError('current metric changed')
        current_metrics.append(c);ewma_metrics.append(e)
        positive={(r,f['sequence']):{fault['equipment_id'] for fault in label['faults'] if fault['intensity']>0}
            for r,rows in data['runs'].items() for f,label in rows}
        for j,row in enumerate(grid):
            new=predict(data,current,row['params'])
            row['metrics'].append(score(data['runs'],new))
            lost,delayed=preserve.event_changes(data['runs'],current,new)
            row['lost'].append(lost);row['delayed'].append(delayed)
            row['removed_active'].append(coverage_loss(data['keys'],positive,current,new))
            if j%48==0:print(f'development {i+1}/4: {j+1}/217',flush=True)
        provenance.append(source)
        if i<3:del data,current,positive;gc.collect()
    selected,passed=choose(grid,current_metrics,ewma_metrics)
    alerts={'ewma':data['baseline'],'preserved_hybrid':current,'continuity_hybrid':predict(data,current,selected['params'])}
    metrics={name:score(data['runs'],a) for name,a in alerts.items()}
    snapshot=dict(metrics=metrics,alerts={name:[[r,s,sorted(v)] for (r,s),v in a.items()] for name,a in alerts.items()},
        paired_events={name:paired_events(data['runs'],a,alerts['continuity_hybrid'],metrics[name],metrics['continuity_hybrid'])
            for name,a in alerts.items() if name!='continuity_hybrid'},
        background={name:base.background(data['runs'],a) for name,a in alerts.items()},
        change_accounting=alarm_changes(data['runs'],current,alerts['continuity_hybrid']),
        diagnostic_only=not passed,selected=selected['params'])
    preserving=lambda row:not any(tag.rsplit(':',1)[1] not in ('duplicates','latest_strict_delay')
        for tag in violations(row,current_metrics,ewma_metrics))
    result=dict(selected=selected['params'],development_passed=passed,selected_metrics=selected['metrics'],
        current_metrics=current_metrics,ewma_metrics=ewma_metrics,original_events_lost=selected['lost'],
        original_events_delayed=selected['delayed'],removed_active=selected['removed_active'],
        failed_constraints=violations(selected,current_metrics,ewma_metrics),
        passed_candidates=sum(not violations(row,current_metrics,ewma_metrics) for row in grid),
        preservation_candidates=sum(preserving(row) for row in grid),grid=grid,provenance=provenance,
        script_sha256=base.sha(__file__),previous_sha256=base.sha(previous.__file__),preserve_sha256=base.sha(preserve.__file__),
        helper_sha256=base.sha(utils.__file__),checkpoint_sha256=ft['checkpoint_sha256'],thresholds=thresholds,
        reference_sha256=base.sha(reference),runtime_sha256=base.verify_runtime(p['runtime']),test_rows_read=0,
        total_seconds=time.perf_counter()-started)
    base.write_new(args.out_dir/'result.json',result);base.write_new(args.out_dir/'latest-result.json',snapshot)
    fields=('detected_events','injected_events','wrong_alert_equipment_seconds','duplicate_alert_episodes','p95_onset_delay_seconds')
    print(json.dumps(dict(selected=selected['params'],passed=passed,failed=result['failed_constraints'],
        removed_active=selected['removed_active'],metrics=[{k:m[k] for k in fields} for m in selected['metrics']])),flush=True)


if __name__=='__main__':main()
