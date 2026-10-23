"""Isolated v13 development, preservation, freeze and fresh paired evaluation."""
import argparse
import itertools
import json
from pathlib import Path
import sys
import time
import numpy as np
from scripts import mes_causal_v12_run as r
from scripts import mes_causal_v11 as baseline
from scripts import mes_causal_v13 as candidate
from scripts import mes_causal_v13_data as dataset

ROOT=r.ROOT;d=r.d;load=r.load
PREVIOUS=ROOT/'output/mes-causal-v12c-20261023'


def preserve(out):
    r.old.prior.require_lock(PREVIOUS/'candidate-lock.json')
    files=load(PREVIOUS/'candidate-lock.json')['files']
    paths=list(PREVIOUS.rglob('*'))+list((ROOT/'output/mes-causal-v13-analysis-20261023').rglob('*'))
    paths +=[ROOT/'docs/research/mes-causal-v12-result-20261023.md',ROOT/'docs/testing/mes-causal-v12-20261023.tdd.md']
    for p in paths:
        if p.is_file():files[str(p.resolve())]=d.sha(p)
    d.write_new(out/'protected.json',files)


def batches(path):
    manifest=load(path/'manifest.json');entries={e['run_id']:e for e in manifest['runs']}
    assert d.sha(path/'features.jsonl')==manifest['features_sha256'],'features changed'
    seen=set()
    with (path/'features.jsonl').open(encoding='utf-8') as stream:
        for run,group in itertools.groupby((json.loads(line) for line in stream),key=lambda f:f['run_id']):
            assert run in entries and run not in seen,'run contract'
            frames=list(group);seen.add(run)
            assert len(frames)==entries[run]['frames'],'incomplete run'
            assert all(f['sequence']==i and len(f['measurements'])==69 for i,f in enumerate(frames)),'frame contract'
            yield run,frames
    assert seen==set(entries),'missing run'


def infer(path,output,settings):
    started=time.perf_counter();rows={'v12c':{},'v13':{}};eligible=set();lite={};context=[];continuations=[]
    for run,frames in batches(path):
        args=list(r.prepare({run:frames},settings['base'])[0]);args[6]={'level':np.asarray(settings['limits'])}
        before=baseline.predict(*args);after=candidate.predict(*args)
        rows['v12c'].update(before);rows['v13'].update(after);eligible.update(args[0]['eligible_keys'])
        context.extend(candidate.associations(args,after,settings['links']))
        for i,key in enumerate(args[0]['keys']):
            for eq in sorted(before[key]-after[key]):
                ix=[j for j,c in enumerate(args[1]) if c[0]==eq and np.isfinite(args[4]['level'][i,j])
                    and args[4]['level'][i,j]>args[6]['level'][j]]
                assert ix and all('temp' in args[1][j][1] for j in ix),'nonthermal evidence suppressed'
                continuations.append(dict(run_id=run,sequence=key[1],equipment=eq,kind='thermal_continuation',
                    causal_claim=False,notification=False,signals=[args[1][j][1] for j in ix],
                    scores=[float(args[4]['level'][i,j]) for j in ix],exit_ratio=candidate.THERMAL_EXIT_RATIO))
        lite[run]=[dict(sequence=f['sequence'],line_mode=f['line_mode']) for f in frames]
    d.write_new(output/'predictions.json',r.old.serialized(rows))
    d.write_new(output/'associations.json',context);d.write_new(output/'continuations.json',continuations)
    return rows,eligible,lite,dict(batch_seconds=time.perf_counter()-started,frames=sum(map(len,lite.values())),
        timestral_loaded='timestral' in sys.modules,torch_loaded='torch' in sys.modules)


def assess(path,output,settings,reproduce=False):
    rows,eligible,lite,timing=infer(path,output,settings)
    if reproduce:
        assert r.old.serialized(rows)['v12c']==load(PREVIOUS/'evaluation/predictions.json')['v12'],'baseline reproduction changed'
    # Truth is opened after predictions and context are persisted.
    events=load(path/'events.private.json');manifest=load(path/'manifest.json')
    assert d.sha(path/'events.private.json')==manifest['ledger_sha256'],'ledger changed'
    metrics=r.old.compare(lite,events,rows,manifest,eligible)
    delays={m:r.old.event_delays(events,p) for m,p in rows.items()}
    changes={k:dict(v12c=v,v13=delays['v13'][k]) for k,v in delays['v12c'].items() if v!=delays['v13'][k]}
    a,b=metrics['v12c'],metrics['v13']
    checks=dict(detected_not_lower=b['detected_events']>=a['detected_events'],
        attributable_not_lower=b['attributable_events']>=a['attributable_events'],
        duplicate_zero=b['duplicate_notifications']==0,
        normal_not_higher=b['pristine_normal_false_starts']<=a['pristine_normal_false_starts'],
        p95_not_higher=b['p95_injection_delay_seconds']<=a['p95_injection_delay_seconds'],
        first_notice_not_later=all(delays['v13'][k] is not None and delays['v13'][k]<=v
                                  for k,v in delays['v12c'].items() if v is not None))
    assert not timing['timestral_loaded'] and not timing['torch_loaded'],'unexpected model load'
    d.write_new(output/'event-delays.json',delays)
    report=dict(methods=metrics,checks=checks,event_delay_changes=changes,timing=timing,
        associations=len(load(output/'associations.json')),continuations=len(load(output/'continuations.json')),
        truth_scope='Injection windows unchanged. Associated impacts remain strict unmatched; no oracle labels enter detector.')
    d.write_new(output/'result.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='methods'}),flush=True)
    return report


def develop(out):
    out.mkdir(parents=True,exist_ok=False);preserve(out)
    settings=load(PREVIOUS/'settings.json')
    source=ROOT/'docs/data/reference/00_plant_and_relations.json'
    settings['links']=[dict(from_=e['from_id'],to=e['to_id'],relation=e['relation_type'])
                      for e in load(source)['relations'] if e['relation_type']=='hydraulic_supply']
    for e in settings['links']:e['from']=e.pop('from_')
    settings['relation_source_sha256']=d.sha(source)
    settings['thermal_exit_ratio']=candidate.THERMAL_EXIT_RATIO
    d.write_new(out/'settings.json',settings)
    diagnostic=out/'diagnostic';diagnostic.mkdir()
    old=assess(PREVIOUS/'data/test',diagnostic,settings,True)
    assert all(old['checks'].values()),'consumed replay regressed'
    assert old['methods']['v13']['unmatched_starts_including_duplicates']==12,'known residual not resolved'
    assert old['associations']==12 and old['continuations']==1,'known explanation incomplete'
    dataset.generate(out/'data/development','development')
    target=out/'development';target.mkdir()
    report=assess(out/'data/development',target,settings)
    r.verify(out);assert all(report['checks'].values()),'development failed; do not freeze'


def freeze(out):
    assert all(load(out/'development/result.json')['checks'].values()),'development failed'
    assert not (out/'data/test').exists(),'test already generated'
    r.verify(out);files=load(out/'protected.json')
    paths=[ROOT/'scripts'/n for n in ('mes_causal_v13.py','mes_causal_v13_data.py','mes_causal_v13_run.py')]
    paths +=[ROOT/'tests/test_mes_causal_v13.py',ROOT/'docs/research/mes-causal-v13-prereg-20261023.md']
    paths +=list(out.rglob('*'))
    for p in paths:
        if p.is_file():files[str(p.resolve())]=d.sha(p)
    d.write_new(out/'candidate-lock.json',dict(status='frozen_before_test',files=files,
        protocol='v12c fixed input/limits; thermal exit 2/3; independent evidence retained; context is not cause classification'))
    print('FROZEN',len(files),flush=True)


def evaluate(out):
    lock=out/'candidate-lock.json';r.old.prior.require_lock(lock)
    target=out/'evaluation';target.mkdir(exist_ok=False);dataset.generate(out/'data/test','test',lock)
    manifests=[load(out/'data'/role/'manifest.json') for role in dataset.ROLES]
    manifests +=[load(PREVIOUS/'data'/role/'manifest.json') for role in dataset.ROLES]
    manifests +=[load(r.PREVIOUS/'data'/role/'manifest.json') for role in dataset.ROLES]
    r.old.prior.check_disjoint(manifests)
    assess(out/'data/test',target,load(out/'settings.json'))
    r.old.prior.require_lock(lock)
    d.write_new(target/'integrity.json',dict(protected_files=r.verify(out),frozen_files=len(load(lock)['files']),
        frozen_unchanged=True,roles_disjoint=True,lock_sha256=d.sha(lock)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--phase',required=True,choices=('develop','freeze','test'));args=parser.parse_args()
    dict(develop=develop,freeze=freeze,test=evaluate)[args.phase](args.out.resolve())
