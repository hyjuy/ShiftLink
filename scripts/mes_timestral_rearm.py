"""Causal episode rearming around the fixed preserved Timestral hybrid."""
import importlib.util
import argparse
import gc
import itertools
import json
import time
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('rearm_preserve',ROOT/'scripts/mes_timestral_preserve.py')
preserve=importlib.util.module_from_spec(spec);spec.loader.exec_module(preserve)
utils=preserve.utils;base=preserve.base


def episode_alerts(keys,raw_z,ratio,baseline,equipment,resets,desired,params):
    if (np.shape(raw_z)!=np.shape(ratio) or np.shape(raw_z)!=(len(keys),len(equipment))
            or len(resets)!=len(keys) or params['quiet'] not in (1,2,3)
            or not all(np.isfinite(params[k]) and params[k]>0 for k in ('early_scale','early_z','rearm_z'))):
        raise ValueError('invalid episode contract')
    active=np.zeros(len(equipment),dtype=bool);armed=np.ones(len(equipment),dtype=bool)
    quiet=np.zeros(len(equipment),dtype=int);output={};last=None
    for i,key in enumerate(keys):
        if key in output:raise ValueError('duplicate key')
        if resets[i] or last is None or last[0]!=key[0] or last[1]+1!=key[1]:
            active[:]=False;armed[:]=True;quiet[:]=0
        valid=np.isfinite(raw_z[i])&np.isfinite(ratio[i])
        wanted=np.array([eq in desired.get(key,set()) for eq in equipment])
        wanted |= (ratio[i]>params['early_scale'])&(raw_z[i]>=params['early_z'])
        ewma=np.array([eq in baseline.get(key,set()) for eq in equipment])
        released=active&~wanted
        waiting=(~active)&(~armed)&valid
        may_enter=armed.copy()
        normal=valid&(~ewma)&(raw_z[i]<params['rearm_z'])&(ratio[i]<=.1)
        quiet=np.where(waiting&normal,quiet+1,0)
        armed[waiting&(quiet>=params['quiet'])]=True
        active &= wanted&valid
        active |= (~active)&may_enter&wanted&valid
        armed[active|released|~valid]=False
        quiet[active|released|~valid]=0
        output[key]={eq for eq,on in zip(equipment,active) if on}
        last=key
    return output


def violations(row,current,baselines):
    failed=[]
    for i,(m,c,e,lost) in enumerate(zip(row['metrics'],current,baselines,row['lost'])):
        checks=dict(events_preserved=not lost,recall=m['detected_events']>=c['detected_events'],
            wrong=m['wrong_alert_equipment_seconds']<=c['wrong_alert_equipment_seconds'],
            duplicates=m['duplicate_alert_episodes']<=e['duplicate_alert_episodes'],
            delay=m['p95_onset_delay_seconds'] is not None and m['p95_onset_delay_seconds']<=c['p95_onset_delay_seconds'])
        if i==len(current)-1:checks['latest_strict_delay']=(m['p95_onset_delay_seconds'] is not None
            and m['p95_onset_delay_seconds']<c['p95_onset_delay_seconds'])
        failed.extend(f'{i+1}:{name}' for name,passed in checks.items() if not passed)
    return failed


def choose(rows,current,baselines):
    accepted=[row for row in rows if not violations(row,current,baselines)]
    def order(row):
        m=row['metrics'];p=row['params']
        quality=(sum(row['delayed']),sum(v['duplicate_alert_episodes'] for v in m),
            sum(v['p95_onset_delay_seconds'] if v['p95_onset_delay_seconds'] is not None else float('inf') for v in m),
            sum(v['wrong_alert_equipment_seconds'] for v in m),-sum(v['detected_events'] for v in m),
            *(p[k] for k in ('early_scale','early_z','rearm_z','quiet')))
        return quality if accepted else (bool(sum(row['lost'])),sum(row['lost']),len(violations(row,current,baselines)),*quality)
    return min(accepted or rows,key=order),bool(accepted)


CURRENT=dict(gap=3,hold_z=3.5,hold_ratio=.025,early_scale=1,early_z=2.5)


def predict(data,desired,params):
    return episode_alerts(*(data[k] for k in ('keys','raw_z','ratio','baseline','equipment','resets')),desired,params)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir',type=Path,required=True)
    args=parser.parse_args();args.out_dir.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter();p,config,specs,stats,ref,ft=utils.setup()
    from scripts.evaluate_mes_fault_models import score
    from scripts.mes_ewma_release_review import paired_events
    channels=[tuple(c) for c in ref['channels']];thresholds=ft['thresholds']['finetuned']
    prior=ROOT/'output/mes-timestral-preserve-development-20261021/result.json'
    fresh_result=ROOT/'output/mes-timestral-preserve-confirmation-retry-20261021/result.json'
    development=json.loads(prior.read_text(encoding='utf-8'))
    fresh=json.loads(fresh_result.read_text(encoding='utf-8'))
    if development['selected']!=CURRENT or fresh['selected']!=CURRENT:raise ValueError('current hybrid changed')
    if (fresh['script_sha256']!=base.sha(preserve.__file__) or fresh['helper_sha256']!=base.sha(utils.__file__)
            or fresh['checkpoint_sha256']!=ft['checkpoint_sha256'] or fresh['thresholds']!=thresholds):
        raise ValueError('current provenance changed')
    sources=[(p['dev'],p['ft']/'weak-predictions.npz',True),
        (ROOT/'output/mes-timestral-pi-confirm-v7-seed55371-20261021',ROOT/'output/mes-timestral-pi-followup-confirmation-20261021/confirmation-predictions.npz',False),
        (ROOT/'output/mes-timestral-stateful-confirm-v7-seed65371-20261021',ROOT/'output/mes-timestral-stateful-confirmation-20261021/confirmation-predictions.npz',False),
        (ROOT/'output/mes-timestral-preserve-confirm-v7-seed75371-20261021',fresh_result.parent/'confirmation-predictions.npz',False)]
    grid=[dict(params=dict(early_scale=scale,early_z=z,rearm_z=rz,quiet=q),metrics=[],lost=[],delayed=[])
        for scale,z,rz,q in itertools.product((.5,.75,1),(2,2.5),(1.5,2,2.5,3),(1,2,3))]
    current=[];ewma=[];provenance=[]
    expected=development['selected_metrics']+[fresh['metrics']['preserved_hybrid']]
    expected_ewma=development['ewma_metrics']+[fresh['metrics']['ewma']]
    expected_provenance=development['provenance']+[dict(prefix_sha256=fresh['dataset_prefix_sha256'],predictions_sha256=fresh['predictions_sha256'])]
    for index,(dataset,predictions,q21) in enumerate(sources):
        data=utils.prepare(dataset,predictions,stats,specs,channels,thresholds,q21=q21)
        if data['config_id']!=config.config_id:raise ValueError('configuration changed')
        if any(data[k]!=expected_provenance[index][k] for k in ('prefix_sha256','predictions_sha256')):
            raise ValueError('development data or predictions changed')
        desired=preserve.predict(data,CURRENT);c=score(data['runs'],desired);e=score(data['runs'],data['baseline'])
        if c!=expected[index] or e!=expected_ewma[index]:raise ValueError('reference metrics changed')
        current.append(c);ewma.append(e)
        for j,row in enumerate(grid):
            alerts=predict(data,desired,row['params'])
            row['metrics'].append(score(data['runs'],alerts))
            lost,delayed=preserve.event_changes(data['runs'],desired,alerts)
            row['lost'].append(lost);row['delayed'].append(delayed)
            if j%24==0:print(f'development {index+1}/4: {j+1}/72',flush=True)
        provenance.append(dict(dataset=str(dataset),predictions=str(predictions),q21=q21,
            prefix_sha256=data['prefix_sha256'],predictions_sha256=data['predictions_sha256']))
        if index<3:del data,desired;gc.collect()
    selected,passed=choose(grid,current,ewma)
    alerts={'ewma':data['baseline'],'preserved_hybrid':desired,
        'rearmed_hybrid':predict(data,desired,selected['params'])}
    metrics={n:score(data['runs'],a) for n,a in alerts.items()}
    snapshot=dict(metrics=metrics,alerts={n:[[r,s,sorted(v)] for (r,s),v in a.items()] for n,a in alerts.items()},
        paired_events=paired_events(data['runs'],desired,alerts['rearmed_hybrid'],metrics['preserved_hybrid'],metrics['rearmed_hybrid']),
        background={n:base.background(data['runs'],a) for n,a in alerts.items()},
        diagnostic_only=not passed,selected=selected['params'])
    result=dict(selected=selected['params'],development_passed=passed,selected_metrics=selected['metrics'],
        current_metrics=current,ewma_metrics=ewma,original_events_lost=selected['lost'],original_events_delayed=selected['delayed'],
        failed_constraints=violations(selected,current,ewma),passed_candidates=sum(not violations(row,current,ewma) for row in grid),
        grid=grid,provenance=provenance,reference_sha256={str(v):base.sha(v) for v in (prior,fresh_result)},
        script_sha256=base.sha(__file__),preserve_sha256=base.sha(preserve.__file__),helper_sha256=base.sha(utils.__file__),
        checkpoint_sha256=ft['checkpoint_sha256'],thresholds=thresholds,runtime_sha256=base.verify_runtime(p['runtime']),
        test_rows_read=0,total_seconds=time.perf_counter()-started)
    base.write_new(args.out_dir/'result.json',result);base.write_new(args.out_dir/'latest-result.json',snapshot)
    fields=('detected_events','injected_events','wrong_alert_equipment_seconds','duplicate_alert_episodes','p95_onset_delay_seconds')
    print(json.dumps(dict(selected=result['selected'],passed=passed,failed=result['failed_constraints'],
        metrics=[{k:m[k] for k in fields} for m in selected['metrics']])),flush=True)


if __name__=='__main__':main()
