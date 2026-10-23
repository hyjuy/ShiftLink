"""Develop normal-only limits, freeze, then compare on one unused paired test."""
import argparse
import json
from pathlib import Path
import sys
import time
import shutil
import numpy as np
from scripts import mes_causal_v11_run as old
from scripts import mes_causal_v11 as baseline
from scripts import mes_causal_v12 as candidate
from scripts import mes_causal_v12_data as dataset

ROOT=old.ROOT
PREVIOUS=ROOT/'output/mes-causal-v11-20261023'
d=old.d
load=old.load


def verify(out):
    files=load(out/'protected.json')
    assert all(d.sha(p)==h for p,h in files.items()),'protected file changed'
    return len(files)


def prepare(runs,settings):
    # Per-run windows keep the original 64-frame policy without a line-sized tensor.
    return [old.prepare({run:frames},settings) for run,frames in runs.items()]


def predictions(prepared,limits):
    rows={'v11':{},'v12':{}};eligible=set()
    for args in prepared:
        rows['v11'].update(baseline.predict(*args))
        adjusted=list(args);adjusted[6]={'level':np.array(limits)}
        rows['v12'].update(candidate.predict(*adjusted));eligible.update(args[0]['eligible_keys'])
    return rows,eligible


def normal_runs(manifest):
    counts={g:sum(r['group_id']==g for r in manifest['runs']) for g in {r['group_id'] for r in manifest['runs']}}
    return {r['run_id'] for r in manifest['runs'] if r['control'] or counts[r['group_id']]==1}


def assess(out,runs,manifest,prepared,limits,ledger):
    rows,eligible=predictions(prepared,limits)
    d.write_new(out/'predictions.json',old.serialized(rows))
    # Event ledger is opened only after all prediction rows are saved.
    events=load(ledger);results=old.compare(runs,events,rows,manifest,eligible)
    delays={name:old.event_delays(events,p) for name,p in rows.items()}
    d.write_new(out/'event-delays.json',delays)
    a,b=results['v11'],results['v12']
    checks=dict(recall_not_lower=b['attributable_events']>=a['attributable_events'],
        detected_not_lower=b['detected_events']>=a['detected_events'],
        duplicate_zero=b['duplicate_notifications']==0,
        normal_not_higher=b['pristine_normal_false_starts']<=a['pristine_normal_false_starts'],
        p95_not_higher=b['p95_injection_delay_seconds']<=a['p95_injection_delay_seconds'])
    changes={k:dict(v11=v,v12=delays['v12'][k]) for k,v in delays['v11'].items() if v!=delays['v12'][k]}
    report=dict(methods=results,checks=checks,event_delay_changes=changes,
        timestral_loaded='timestral' in sys.modules,torch_loaded='torch' in sys.modules)
    d.write_new(out/'result.json',report)
    print(json.dumps(report),flush=True)
    return report


def develop(out):
    out.mkdir(parents=True,exist_ok=False);old.prior.require_lock(PREVIOUS/'candidate-lock.json')
    files=load(PREVIOUS/'candidate-lock.json')['files']
    paths=list(PREVIOUS.rglob('*'))+list((ROOT/'docs/research').glob('mes-causal-v11-*.md'))
    paths+=[ROOT/'docs/testing/mes-causal-v11-20261023.tdd.md']
    for p in paths:
        if p.is_file():files[str(p.resolve())]=d.sha(p)
    d.write_new(out/'protected.json',files)
    dataset.generate(out/'data/development','development')
    runs,manifest=d.read_role(out/'data/development');settings=load(PREVIOUS/'settings.json')
    prepared=prepare(runs,settings)
    # Normal/control status is supplied by development design, not fault ledger.
    # Explicit index-zero groups have no pair; select by declared group cardinality.
    normal=normal_runs(manifest)
    scores=np.concatenate([a[4]['level'] for a in prepared]);keys=[k for a in prepared for k in a[0]['keys']]
    limits=candidate.calibrate(scores,keys,normal,settings['selected']['no_timestral']['limits']['level'])
    d.write_new(out/'settings.json',dict(base=settings,limits=limits.tolist(),normal_runs=sorted(normal),margin=1.1))
    report=assess(out,runs,manifest,prepared,limits,out/'data/development/events.private.json')
    verify(out)
    assert all(report['checks'].values()),'development acceptance failed; do not freeze'


def revise(out):
    initial=ROOT/'output/mes-causal-v12-20261023'
    out.mkdir(parents=True,exist_ok=False);files=load(initial/'protected.json')
    for p in initial.rglob('*'):
        if p.is_file():files[str(p.resolve())]=d.sha(p)
    intermediate=ROOT/'output/mes-causal-v12b-20261023'
    if intermediate.exists() and intermediate.resolve()!=out.resolve():
        for p in intermediate.rglob('*'):
            if p.is_file():files[str(p.resolve())]=d.sha(p)
    d.write_new(out/'protected.json',files)
    shutil.copytree(initial/'data/development',out/'data/development')
    settings=load(PREVIOUS/'settings.json')
    runs,manifest=d.read_role(out/'data/development');prepared=prepare(runs,settings)
    anchor_runs,anchor_manifest=d.read_role(PREVIOUS/'data/test')
    anchor_ids=normal_runs(anchor_manifest)
    anchor_runs={k:v for k,v in anchor_runs.items() if k in anchor_ids}
    anchors=prepare(anchor_runs,settings);all_prepared=prepared+anchors
    normal=normal_runs(manifest)
    scores=np.concatenate([a[4]['level'] for a in all_prepared]);keys=[k for a in all_prepared for k in a[0]['keys']]
    limits=candidate.calibrate(scores,keys,normal|anchor_ids,settings['selected']['no_timestral']['limits']['level'])
    d.write_new(out/'settings.json',dict(base=settings,limits=limits.tolist(),normal_runs=sorted(normal),margin=1.1,
        consumed_v11_normal_reference=sorted(anchor_ids),anchor_manifest_sha256=d.sha(PREVIOUS/'data/test/manifest.json'),
        calibration='normal four-consecutive exceedance channels only'))
    report=assess(out,runs,manifest,prepared,limits,out/'data/development/events.private.json')
    verify(out);assert all(report['checks'].values()),'revised development failed'


def freeze(out):
    assert all(load(out/'result.json')['checks'].values()),'development failed'
    assert not (out/'data/test').exists(),'test already exists'
    replay=load(out/'diagnostic-v11-replay.json')
    assert replay['case']['v11']==[668,718] and replay['case']['v12']==[],'known normal regressions remain'
    verify(out);files=load(out/'protected.json')
    paths=[ROOT/'scripts'/n for n in ('mes_causal_v12.py','mes_causal_v12_data.py','mes_causal_v12_run.py')]
    paths +=[ROOT/'tests/test_mes_causal_v12.py',ROOT/'docs/research/mes-causal-v12-prereg-20261023.md']
    paths +=list(out.rglob('*'))
    for p in paths:
        if p.is_file():files[str(p.resolve())]=d.sha(p)
    d.write_new(out/'candidate-lock.json',dict(status='frozen_before_test',files=files,
        protocol='normal sustained channels only, max x1.1 with prior floor; v11 state unchanged; no test generated'))
    print('FROZEN',len(files),flush=True)


def evaluate(out):
    lock=out/'candidate-lock.json';old.prior.require_lock(lock)
    target=out/'evaluation';target.mkdir(exist_ok=False)
    dataset.generate(out/'data/test','test',lock)
    runs,manifest=d.read_role(out/'data/test')
    manifests=[load(out/'data'/role/'manifest.json') for role in dataset.ROLES]
    manifests +=[load(PREVIOUS/'data'/role/'manifest.json') for role in dataset.ROLES]
    manifests +=[load(old.PREVIOUS/'data'/role/'manifest.json') for role in ('fit','calibration','development','test')]
    old.prior.check_disjoint(manifests)
    settings=load(out/'settings.json');started=time.perf_counter()
    prepared=prepare(runs,settings['base'])
    assess(target,runs,manifest,prepared,settings['limits'],out/'data/test/events.private.json')
    old.prior.require_lock(lock)
    d.write_new(target/'integrity.json',dict(protected_files=verify(out),frozen_files=len(load(lock)['files']),
        frozen_unchanged=True,roles_disjoint=True,seconds=time.perf_counter()-started,
        lock_sha256=d.sha(lock),synthetic_only=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--phase',choices=('develop','revise','freeze','test'),required=True);args=parser.parse_args()
    dict(develop=develop,revise=revise,freeze=freeze,test=evaluate)[args.phase](args.out.resolve())
