"""Preserve v14b; duration-aligned normal calibration, then one new test."""
import argparse
import json
import pickle
import shutil
from pathlib import Path
import numpy as np
from scripts import mes_causal_v14_run as r
from scripts import mes_causal_v14c as calibration
from scripts import mes_causal_v14c_data as dataset

ROOT=r.ROOT;BASE=ROOT/'output/mes-causal-v14b-20261023';d=r.d;load=r.load


def known_cases(out,settings):
    cases=[('development','a715b2bc6b86b8f98cc39f3ab18b695a',102,140),
           ('test','1bd4f2fa4967cdc82b2a2f87620a4e07',104,138)]
    results=[]
    for role,run,start,end in cases:
        path=r.PREVIOUS/'data'/role;manifest=load(path/'manifest.json')
        entry=next(e for e in manifest['runs'] if e['run_id']==run)
        control=next(e['run_id'] for e in manifest['runs'] if e['group_id']==entry['group_id'] and e['control'])
        found={}
        if role=='development':
            for rid in (run,control):found[rid]=pickle.loads((r.ANALYSIS/(rid+'.pkl')).read_bytes())
        else:
            for rid,frames in r.prior.batches(path):
                if rid in (run,control):found[rid]=r.prepare(rid,frames,settings)
        predictions={}
        for rid,args in found.items():
            args[7]=dict(args[7],thermal_rise_limits=settings['thermal_rise_limits'])
            predictions[rid]=r.candidate.predict(*args)
        ticks=[t for (rid,t),eqs in predictions[run].items() if 'EQ-0005' in eqs]
        normal=sum(map(len,predictions[control].values()))
        results.append(dict(role=role,run_id=run,interval=[start,end],notice_ticks=ticks,
            detected_inside=any(start<=t<end for t in ticks),paired_normal_notices=normal))
    d.write_new(out/'known-cases.json',results)
    assert all(x['detected_inside'] and x['paired_normal_notices']==0 for x in results),'known cases failed'


def develop(out):
    out.mkdir(parents=True,exist_ok=False)
    r.prior.r.old.prior.require_lock(BASE/'candidate-lock.json')
    assert load(BASE/'final-audit.json')['passed'],'previous audit incomplete'
    files=load(BASE/'candidate-lock.json')['files']
    for p in BASE.rglob('*'):
        if p.is_file() and str(p.resolve()) not in files:files[str(p.resolve())]=d.sha(p)
    d.write_new(out/'protected.json',files)
    shutil.copytree(BASE/'data/development',out/'data/development');shutil.copytree(BASE/'prepared',out/'prepared')
    settings=load(BASE/'settings.json');batches=[];references=[]
    for path,cache in ((r.PREVIOUS/'data/development',r.ANALYSIS),(out/'data/development',out/'prepared')):
        for run in sorted(r.prior.r.normal_runs(load(path/'manifest.json'))):
            args=pickle.loads((cache/(run+'.pkl')).read_bytes())
            assert args[7]['patience']==4
            flags=(args[4]['level']>args[6]['level']) & args[3][None,:]
            background=np.column_stack([flags[:,[j for j,c in enumerate(args[1]) if c[0]==eq]].any(axis=1) for eq in args[0]['equipment']])
            batches.append((r.candidate.thermal_rise(args),background));references.append(run)
    settings['previous_thermal_rise_limits']=settings['thermal_rise_limits']
    settings['thermal_rise_limits']=calibration.calibrate(batches).tolist()
    settings['thermal_calibration']='normal four-frame minimum maximum x1.1; baseline flags included; floor .5'
    settings['thermal_reference_runs']=references;d.write_new(out/'settings.json',settings)
    target=out/'development';target.mkdir();report=r.assess(out/'data/development',target,settings,out/'prepared')
    assert all(report['checks'].values()),'development failed; no freeze'
    known_cases(out,settings);r.verify(out)


def freeze(out):
    assert all(load(out/'development/result.json')['checks'].values())
    assert all(x['detected_inside'] and x['paired_normal_notices']==0 for x in load(out/'known-cases.json'))
    check=load(out/'regression.json');assert check['passed'] and check['calibration_sha256']==d.sha(ROOT/'scripts/mes_causal_v14c.py')
    assert not (out/'data/test').exists();r.verify(out);files=load(out/'protected.json')
    paths=list(out.rglob('*'))+[ROOT/'scripts'/n for n in ('mes_causal_v14c.py','mes_causal_v14c_data.py','mes_causal_v14c_run.py','mes_causal_v14c_audit.py')]
    paths +=[ROOT/'tests/test_mes_causal_v14c.py',ROOT/'docs/research/mes-causal-v14c-prereg-20261023.md']
    for p in paths:
        if p.is_file():files[str(p.resolve())]=d.sha(p)
    d.write_new(out/'candidate-lock.json',dict(status='frozen_before_test',files=files,protocol=settings_protocol(out)))
    print('FROZEN',len(files),flush=True)


def settings_protocol(out):return load(out/'settings.json')['thermal_calibration']


def evaluate(out):
    lock=out/'candidate-lock.json'
    # The generator verifies the entire lock before creating its output directory.
    dataset.generate(out/'data/test','test',lock)
    manifests=[load(out/'data'/role/'manifest.json') for role in dataset.ROLES]
    manifests.append(load(BASE/'data/test/manifest.json'))
    for root in (r.PREVIOUS,r.prior.PREVIOUS,r.prior.r.PREVIOUS):
        manifests.extend(load(root/'data'/role/'manifest.json') for role in dataset.ROLES)
    r.prior.r.old.prior.check_disjoint(manifests)
    target=out/'evaluation';target.mkdir();r.assess(out/'data/test',target,load(out/'settings.json'))
    r.prior.r.old.prior.require_lock(lock)
    d.write_new(target/'integrity.json',dict(protected_files=len(load(out/'protected.json')),frozen_files=len(load(lock)['files']),
        frozen_unchanged=True,roles_disjoint=True,includes_previous_v14b_test=True,lock_sha256=d.sha(lock)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--phase',choices=('develop','freeze','test'),required=True);a=p.parse_args()
    dict(develop=develop,freeze=freeze,test=evaluate)[a.phase](a.out.resolve())
