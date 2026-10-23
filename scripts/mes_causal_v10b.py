"""Pre-test v10 calibration revision; preserves the rejected development candidate."""
import argparse
from pathlib import Path
import shutil
import numpy as np

from scripts import mes_causal_v10_run as r
from scripts import mes_causal_v9 as v9
from scripts import mes_causal_data as d

FIRST=r.ROOT/'output/mes-causal-v10-20261023'
GRID=[dict(width=w,q=q,patience=p,multiplier=m) for w in (5,9) for q in (.98,.995)
      for p in (4,8) for m in (1.,1.5,2.,3.)]


def choose(records):
    def key(row):
        x=row['metrics'];p=row['params'];rate=x['pristine_normal_false_starts_per_line_hour']
        return (int(rate>1),rate if rate>1 else 0,-x['attributable_events'],x['duplicate_notifications'],
                -x['attributable_within_10s'],p['patience'],p['width'],p['q'],p['multiplier'])
    return min(records,key=key)


def develop(out):
    assert not (FIRST/'data/test').exists(),'first candidate must not have consumed test'
    v9.require_lock(FIRST/'candidate-lock.json')
    out.mkdir(parents=True,exist_ok=False)
    files=r.load(FIRST/'candidate-lock.json')['files']
    for p in FIRST.rglob('*'):
        if p.is_file():files[str(p.resolve())]=d.sha(p)
    d.write_new(out/'protected.json',files)
    (out/'data').mkdir();training=out/'development';training.mkdir()
    for role in ('fit','calibration','development'):shutil.copytree(FIRST/'data'/role,out/'data'/role)
    for name in ('calibration.npz','development.npz'):shutil.copyfile(FIRST/'development'/name,training/name)
    initial=r.load(FIRST/'development/settings.json');channels=[tuple(c) for c in initial['channels']]
    stats={(e,s):(m,a) for e,s,m,a in initial['stats']}
    variable=np.array(initial['variable']);tolerance=np.array(initial['tolerance'])
    cr,_=d.read_role(out/'data/calibration');dr,manifest=d.read_role(out/'data/development')
    cal,ct,cn=r.prepare(training/'calibration.npz',cr,channels,stats)
    dev,dt,dn=r.prepare(training/'development.npz',dr,channels,stats)
    cv=r.variants(cal,ct,cn,stats,channels,variable);dv=r.variants(dev,dt,dn,stats,channels,variable)
    ledger=r.load(out/'data/development/events.private.json');search={};selected={}
    for method in r.METHODS:
        records=[]
        for params in GRID:
            limits={k:a*params['multiplier'] for k,a in r.thresholds(cv[params['width']][0],params['q']).items()}
            rows=r.predict(dev,channels,tolerance,variable,dv,params,limits,method)
            metrics=r.prior.evaluate(dr,ledger,rows,manifest,dev['eligible_keys'])
            records.append(dict(params=params,metrics=metrics,limits={k:a.tolist() for k,a in limits.items()}))
        search[method]=records;selected[method]=choose(records)
        print('SELECTED',method,selected[method]['params'],selected[method]['metrics']['detected_events'],
              selected[method]['metrics']['pristine_normal_false_starts'],flush=True)
    settings=dict(initial,selected=selected)
    raw=r.gate_ablation(cal,stats,channels,variable,cv[5][1]);fixed=selected['no_timestral']['params']
    settings['ablation_limits']={name:(r.ablation_limits(raw,channels,fixed['q'],channel)*fixed['multiplier']).tolist()
                                 for name,channel in (('gate_only',False),('gate_channel',True))}
    d.write_new(training/'settings.json',settings);d.write_new(training/'search.json',search)
    d.write_new(training/'revision.json',dict(source=str(FIRST),source_test_rows_read=0,retrained=False,
        rejected_development_normal_starts=19,equal_search_budget=len(GRID),
        reason='Simultaneous monitoring and normal load variation exceeded per-channel quantiles by ratios 1.004..1.260.'))
    files={str(Path(p).resolve()):h for p,h in r.load(out/'protected.json').items()}
    paths=[Path(__file__),r.ROOT/'tests/test_mes_causal_v10b.py',
           r.ROOT/'docs/research/mes-causal-v10b-prereg-20261023.md']
    paths+=list(training.rglob('*'))+list((out/'data').rglob('*'))
    for p in paths:
        if p.is_file():files[str(p.resolve())]=d.sha(p)
    r.verify(out)
    d.write_new(out/'candidate-lock.json',dict(status='frozen_before_test',files=files,
        protocol='v10b revised on development only; same normal budget; no test generated'))
    print('FROZEN v10b',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--phase',choices=('develop','test'),required=True);args=parser.parse_args()
    (develop if args.phase=='develop' else r.evaluate)(args.out.resolve())
