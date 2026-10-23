"""Frozen no-Timestral comparison, with no model loading or threshold selection."""
import argparse
import json
from pathlib import Path
import sys
import time
import numpy as np
from scripts import mes_causal_data as d
from scripts import mes_causal_v9 as prior
from scripts import mes_causal_v9_run as scoring
from scripts import mes_causal_v10 as baseline
from scripts import mes_causal_v11 as candidate
from scripts import mes_causal_v11_data as dataset
from scripts.mes_causal_schema import ROOT

PREVIOUS=ROOT/'output/mes-causal-v10b-20261023'


def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def protect(out):
    prior.require_lock(PREVIOUS/'candidate-lock.json');files=load(PREVIOUS/'candidate-lock.json')['files']
    paths=list(PREVIOUS.rglob('*'))+[ROOT/'docs/research/mes-causal-v10b-result-20261023.md',
        ROOT/'docs/research/mes-causal-v10-result-20261023.md',ROOT/'docs/testing/mes-causal-v10-20261023.tdd.md']
    for p in paths:
        if p.is_file():files[str(p.resolve())]=d.sha(p)
    d.write_new(out/'protected.json',files)


def verify(out):
    files=load(out/'protected.json');assert all(d.sha(p)==h for p,h in files.items()),'protected file changed'
    return len(files)


def prepare(runs,settings):
    channels=[tuple(c) for c in settings['channels']];stats={(e,s):(m,a) for e,s,m,a in settings['stats']}
    x,keys,_=d.windows(runs,channels);del x
    zeros=np.zeros((len(keys),len({c[0] for c in channels})))
    stub=dict(keys=keys,ts=zeros,ewma=zeros,naive=zeros)
    data=prior.prepare(runs,channels,stats,stub)
    fixed=settings['selected']['no_timestral'];variable=np.array(settings['variable']);tolerance=np.array(settings['tolerance'])
    computed,holds=baseline.process_scores(data,stats,channels,variable,fixed['params']['width'])
    args=(data,channels,tolerance,variable,computed,holds,{'level':np.array(fixed['limits']['level'])},fixed['params'])
    return args


def predict(runs,settings):
    started=time.perf_counter();args=prepare(runs,settings)
    rows=dict(baseline=baseline.predict(*args,'no_timestral'),candidate=candidate.predict(*args))
    return rows,args[0]['eligible_keys'],dict(seconds=time.perf_counter()-started,frames=len(args[0]['keys']),
        acquisition_repeat_frames=int(args[5].sum()),timestral_loaded='timestral' in sys.modules,torch_loaded='torch' in sys.modules)


def compare(runs,ledger,rows,manifest,eligible):
    return {name:scoring.evaluate(runs,ledger,alerts,manifest,eligible) for name,alerts in rows.items()}


def serialized(rows):return {m:[[r,t,sorted(e)] for (r,t),e in p.items()] for m,p in rows.items()}


def event_delays(ledger,alerts):
    return {f'{r}:{e["event_id"]}':next((t-e['start'] for t in range(e['start'],e['end']) if e['equipment'] in alerts[r,t]),None)
            for r,events in ledger.items() for e in events}


def replay(out,settings):
    runs,manifest=d.read_role(PREVIOUS/'data/test');rows,eligible,timing=predict(runs,settings)
    assert serialized(rows)['baseline']==load(PREVIOUS/'evaluation/predictions.json')['no_timestral'],'baseline reproduction changed'
    ledger=load(PREVIOUS/'data/test/events.private.json');results=compare(runs,ledger,rows,manifest,eligible)
    assert event_delays(ledger,rows['baseline'])==event_delays(ledger,rows['candidate']),'old first notices changed'
    assert results['candidate']['duplicate_notifications']==0,'old duplicate remains'
    key='f6c5ce73a701551bd37bd3bf48d734ab'
    case={name:[t for (r,t),eqs in alerts.items() if r==key and 'EQ-0006' in eqs] for name,alerts in rows.items()}
    assert case==dict(baseline=[391,422],candidate=[391]),case
    d.write_new(out/'diagnostic-replay.json',dict(methods=results,timing=timing,case=case,
        original_baseline_rows_identical=True,first_event_delays_identical=True,
        note='Consumed v10b test, diagnostic only; not fresh evaluation.'))


def develop(out):
    out.mkdir(parents=True,exist_ok=False);protect(out);settings=load(PREVIOUS/'development/settings.json')
    replay(out,settings)
    dataset.generate(out/'data/development','development');runs,manifest=d.read_role(out/'data/development')
    rows,eligible,timing=predict(runs,settings)
    d.write_new(out/'development-predictions.json',serialized(rows))
    results=compare(runs,load(out/'data/development/events.private.json'),rows,manifest,eligible)
    assert results['candidate']['duplicate_notifications']==0,'development duplicate remains'
    assert results['candidate']['attributable_events']>=results['baseline']['attributable_events'],'development recall regression'
    assert not timing['timestral_loaded'] and not timing['torch_loaded'],'model unexpectedly loaded'
    d.write_new(out/'settings.json',settings);d.write_new(out/'development-result.json',dict(methods=results,timing=timing))
    files=load(out/'protected.json')
    paths=[ROOT/'scripts'/name for name in ('mes_causal_v11.py','mes_causal_v11_data.py','mes_causal_v11_run.py')]
    paths+=[ROOT/'tests/test_mes_causal_v11.py',ROOT/'docs/research/mes-causal-v11-prereg-20261023.md']
    paths+=list(out.rglob('*'))
    for p in paths:
        if p.is_file():files[str(p.resolve())]=d.sha(p)
    verify(out)
    d.write_new(out/'candidate-lock.json',dict(status='frozen_before_test',files=files,
        protocol='v11 provenance recovery; unchanged v10b no-Timestral settings; test not generated'))
    print('FROZEN',json.dumps(results),flush=True)


def evaluate(out):
    lock=out/'candidate-lock.json';prior.require_lock(lock);output=out/'evaluation';output.mkdir(exist_ok=False)
    dataset.generate(out/'data/test','test',lock);runs,manifest=d.read_role(out/'data/test')
    manifests=[load(out/'data'/role/'manifest.json') for role in dataset.ROLES]
    manifests +=[load(PREVIOUS/'data'/role/'manifest.json') for role in ('fit','calibration','development','test')]
    prior.check_disjoint(manifests)
    rows,eligible,timing=predict(runs,load(out/'settings.json'))
    d.write_new(output/'predictions.json',serialized(rows))
    ledger=load(out/'data/test/events.private.json');results=compare(runs,ledger,rows,manifest,eligible)
    delays={name:event_delays(ledger,alerts) for name,alerts in rows.items()}
    d.write_new(output/'event-delays.json',delays)
    prior.require_lock(lock);count=verify(out)
    d.write_new(output/'result.json',dict(methods=results,timing=timing,protected_files=count,frozen_unchanged=True,
        first_event_delays_identical=delays['baseline']==delays['candidate'],lock_sha256=d.sha(lock),
        limits='Known synthetic A/B, explicit quality stress, not field validation. Injection time excludes end-to-end latency.'))
    print(json.dumps(results),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--phase',choices=('develop','test'),required=True);args=parser.parse_args()
    (develop if args.phase=='develop' else evaluate)(args.out.resolve())
