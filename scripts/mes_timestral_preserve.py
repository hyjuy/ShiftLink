"""Preserve the original hybrid ON state; add only causally supported short gaps."""
import argparse
import gc
import importlib.util
import itertools
import json
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('preserve_utils',ROOT/'scripts/mes_timestral_stateful.py')
utils=importlib.util.module_from_spec(spec);spec.loader.exec_module(utils)
previous=utils.previous;base=utils.base
import numpy as np


def preserve_alerts(keys,raw_z,ratio,baseline,equipment,resets,params):
    if (np.shape(raw_z)!=np.shape(ratio) or np.shape(raw_z)!=(len(keys),len(equipment))
            or len(resets)!=len(keys) or params['gap'] not in (0,1,2,3)):
        raise ValueError('invalid preserving-alarm contract')
    anchor=np.full(len(equipment),-1,dtype=int);was_on=np.zeros(len(equipment),dtype=bool)
    output={};last=None
    for index,key in enumerate(keys):
        if key in output:raise ValueError('duplicate key')
        if resets[index] or last is None or last[0]!=key[0] or key[1]!=last[1]+1:
            anchor[:]=-1;was_on[:]=False
        ewma=np.array([eq in baseline.get(key,set()) for eq in equipment])
        original=(ewma&(ratio[index]>.1))|(ratio[index]>1.5)
        valid=np.isfinite(raw_z[index])&np.isfinite(ratio[index])
        early=(valid&(ratio[index]>params['early_scale'])&(raw_z[index]>=params['early_z'])
               if params['early_scale'] is not None else np.zeros(len(equipment),dtype=bool))
        anchor[~valid]=-1
        fill=(was_on&(anchor>=0)&((key[1]-anchor)<=params['gap'])&ewma&valid
              &(raw_z[index]>=params['hold_z'])&(ratio[index]>params['hold_ratio']))
        enabled=original|early|fill
        anchor[original&valid]=key[1]
        anchor[~enabled]=-1
        output[key]={eq for eq,yes in zip(equipment,enabled) if yes}
        was_on=enabled;last=key
    return output


def choose(rows,original):
    def eligible(row):
        return (not any(row['lost']) and not any(row['delayed']) and all(
            m['detected_events']>=b['detected_events'] and m['wrong_alert_equipment_seconds']<=b['wrong_alert_equipment_seconds']
            and m['duplicate_alert_episodes']<=b['duplicate_alert_episodes'] and m['p95_onset_delay_seconds'] is not None
            and m['p95_onset_delay_seconds']<=b['p95_onset_delay_seconds'] for m,b in zip(row['metrics'],original)))
    def tier(row):
        dup=[m['duplicate_alert_episodes']<b['duplicate_alert_episodes'] for m,b in zip(row['metrics'],original)]
        delay=[m['p95_onset_delay_seconds']<b['p95_onset_delay_seconds'] for m,b in zip(row['metrics'],original)]
        if all(dup) and all(delay):return 0
        if any(dup) and any(delay):return 1
        if any(dup) or any(delay):return 2
        return 3
    accepted=[row for row in rows if eligible(row) and tier(row)<3]
    if not accepted:return next(row for row in rows if row['params']['gap']==0 and row['params']['early_scale'] is None),False
    def order(row):
        m=row['metrics'];p=row['params']
        return (tier(row),sum(x['duplicate_alert_episodes'] for x in m),
            max(x['p95_onset_delay_seconds']/b['p95_onset_delay_seconds'] for x,b in zip(m,original)),
            sum(x['p95_onset_delay_seconds'] for x in m),-sum(x['detected_events'] for x in m),
            p['gap'],p['hold_z'],p['hold_ratio'],p['early_scale'] or 999,p['early_z'] or 999)
    return min(accepted,key=order),True


def parameters():
    choices=[(None,None)]+list(itertools.product((1,1.25),(2,2.5,3)))
    control=dict(gap=0,hold_z=3,hold_ratio=.025,early_scale=None,early_z=None)
    return [control]+[dict(gap=gap,hold_z=z,hold_ratio=r,early_scale=e,early_z=ez)
        for gap,z,r,(e,ez) in itertools.product((1,2,3),(3,3.5,4),(.025,.05),choices)]


def predict(data,params):
    return preserve_alerts(*(data[k] for k in ('keys','raw_z','ratio','baseline','equipment','resets')),params)


def event_changes(runs,old,new):
    from scripts.mes_ewma_release_review import event_starts
    before=event_starts(runs,old);after=event_starts(runs,new)
    lost=sum(v['detected'] is not None and after[key]['detected'] is None for key,v in before.items())
    delayed=sum(v['delay_seconds'] is not None and after[key]['delay_seconds'] is not None
                and after[key]['delay_seconds']>v['delay_seconds'] for key,v in before.items())
    return lost,delayed


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('develop','confirm'),required=True)
    parser.add_argument('--out-dir',type=Path,required=True)
    parser.add_argument('--fresh',type=Path)
    parser.add_argument('--selection',type=Path)
    args=parser.parse_args();args.out_dir.mkdir(parents=True,exist_ok=False)
    tick=time.perf_counter();p,config,specs,stats,ref,ft=utils.setup()
    from scripts.evaluate_mes_fault_models import score
    from scripts.mes_ewma_release_review import paired_events
    channels=[tuple(c) for c in ref['channels']];thresholds=ft['thresholds']['finetuned']
    if args.phase=='develop':
        grid=[dict(params=params,metrics=[],lost=[],delayed=[]) for params in parameters()]
        originals=[];baselines=[];provenance=[]
        sources=[(p['dev'],p['ft']/'weak-predictions.npz',True,ROOT/'output/mes-timestral-pi-hybrid-development-20261021/result.json','candidate'),
            (ROOT/'output/mes-timestral-pi-confirm-v7-seed55371-20261021',ROOT/'output/mes-timestral-pi-followup-confirmation-20261021/confirmation-predictions.npz',False,ROOT/'output/mes-timestral-pi-followup-confirmation-20261021/result.json','candidate'),
            (ROOT/'output/mes-timestral-stateful-confirm-v7-seed65371-20261021',ROOT/'output/mes-timestral-stateful-confirmation-20261021/confirmation-predictions.npz',False,ROOT/'output/mes-timestral-stateful-confirmation-20261021/result.json','previous_hybrid')]
        for dataset,prediction,q21,reference,method in sources:
            data=utils.prepare(dataset,prediction,stats,specs,channels,thresholds,q21=q21)
            if data['config_id']!=config.config_id:raise ValueError('configuration differs')
            old=predict(data,grid[0]['params']);m=score(data['runs'],old)
            expected=json.loads(reference.read_text(encoding='utf-8'))
            if m!=expected['metrics'][method]:raise ValueError('original hybrid changed')
            originals.append(m);baselines.append(score(data['runs'],data['baseline']))
            for index,row in enumerate(grid):
                new=predict(data,row['params'])
                assert all(old[key]<=new[key] for key in old)
                metrics=score(data['runs'],new)
                assert metrics['wrong_alert_equipment_seconds']>=m['wrong_alert_equipment_seconds']
                lost,delayed=event_changes(data['runs'],old,new)
                row['metrics'].append(metrics);row['lost'].append(lost);row['delayed'].append(delayed)
                if index%32==0:print(f'development {len(originals)}/3: {index+1}/127',flush=True)
            provenance.append({k:data[k] for k in ('prefix_sha256','predictions_sha256')})
            del data;gc.collect()
        selected,passed=choose(grid,originals)
        result=dict(selected=selected['params'],development_passed=passed,selected_metrics=selected['metrics'],
            original_metrics=originals,ewma_metrics=baselines,grid=grid,provenance=provenance)
    else:
        if args.selection is None or args.fresh is None:parser.error('confirmation requires selection and fresh')
        selected=json.loads(args.selection.read_text(encoding='utf-8'))
        if (not selected['development_passed'] or selected['script_sha256']!=base.sha(__file__)
                or selected['checkpoint_sha256']!=ft['checkpoint_sha256'] or selected['thresholds']!=thresholds):raise ValueError('selection differs or is not improved')
        manifest=json.loads((args.fresh/'manifest.json').read_text(encoding='utf-8'))
        known=[p['source'],p['normal'],p['dev'],ROOT/'output/mes-timestral-pi-confirm-v7-seed55371-20261021',ROOT/'output/mes-timestral-stateful-confirm-v7-seed65371-20261021',ROOT/'output/mes-fault-timestral-v7-seed15371-weak-20261021']
        for path in known:
            prior=json.loads((path/'manifest.json').read_text(encoding='utf-8'))
            if any({r[field] for r in prior['runs']}&{r[field] for r in manifest['runs']} for field in ('seed','run_id')):raise ValueError('confirmation overlaps')
        old=previous.evaluate(argparse.Namespace(phase='confirm',fresh=args.fresh,out_dir=args.out_dir,
            selection=ROOT/'output/mes-timestral-pi-hybrid-development-20261021/result.json',hybrid=False))
        data=utils.prepare(args.fresh,args.out_dir/'confirmation-predictions.npz',stats,specs,channels,thresholds)
        alerts={name:{(r,int(s)):set(v) for r,s,v in rows} for name,rows in old['alerts'].items() if name!='standalone_diagnostic'}
        alerts['original_hybrid']=alerts.pop('candidate')
        start=time.perf_counter();alerts['preserved_hybrid']=predict(data,selected['selected']);alarm_seconds=time.perf_counter()-start
        assert all(alerts['original_hybrid'][key]<=alerts['preserved_hybrid'][key] for key in data['keys'])
        metrics={name:score(data['runs'],a) for name,a in alerts.items()}
        lost,delayed=event_changes(data['runs'],alerts['original_hybrid'],alerts['preserved_hybrid'])
        before=metrics['original_hybrid'];after=metrics['preserved_hybrid']
        preserved=(not lost and not delayed and after['wrong_alert_equipment_seconds']<=before['wrong_alert_equipment_seconds']
                   and after['duplicate_alert_episodes']<=before['duplicate_alert_episodes'] and after['p95_onset_delay_seconds']<=before['p95_onset_delay_seconds'])
        result=dict(selected=selected['selected'],metrics=metrics,
            alerts={name:[[r,s,sorted(v)] for (r,s),v in a.items()] for name,a in alerts.items()},
            original_preserved=preserved,original_events_lost=lost,original_events_delayed=delayed,
            paired_events={name:paired_events(data['runs'],a,alerts['preserved_hybrid'],metrics[name],after) for name,a in alerts.items() if name!='preserved_hybrid'},
            requested_improvement_vs_ewma=previous.improved(metrics['ewma'],after),
            background={name:base.background(data['runs'],a) for name,a in alerts.items()},
            selection_sha256=base.sha(args.selection),dataset_prefix_sha256=data['prefix_sha256'],
            predictions_sha256=data['predictions_sha256'],timing=old['timing'],alarm_seconds=alarm_seconds,
            replay_verification=old['replay_verification'],grid=None)
    result.update(script_sha256=base.sha(__file__),checkpoint_sha256=ft['checkpoint_sha256'],thresholds=thresholds,
        runtime_sha256=base.verify_runtime(p['runtime']),helper_sha256=base.sha(utils.__file__),previous_script_sha256=base.sha(previous.__file__),
        test_rows_read=0,total_seconds=time.perf_counter()-tick)
    base.write_new(args.out_dir/'result.json',result)
    fields=('detected_events','injected_events','wrong_alert_equipment_seconds','duplicate_alert_episodes','p95_onset_delay_seconds')
    if args.phase=='develop':print(json.dumps(dict(selected=result['selected'],development_passed=result['development_passed'],
        metrics=[{k:m[k] for k in fields} for m in result['selected_metrics']])),flush=True)
    else:print(json.dumps({name:{k:m[k] for k in fields} for name,m in result['metrics'].items()}),flush=True)


if __name__=='__main__':main()
