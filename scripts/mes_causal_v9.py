"""Separate persistent/flatline candidate and paired v9 data; no runtime wiring."""
from collections import deque
import hashlib
import json
from pathlib import Path
import random
from urllib.request import Request, urlopen

import numpy as np

from scripts import mes_causal_data as d
from scripts import mes_causal_train as old
from scripts.mes_causal_schema import signals, MANUAL

ROLES={'fit':(4,320),'selection':(2,320),'calibration':(2,384),
       'development':(3,384),'test':(6,384)}
METHODS=('full','no_timestral','no_flat','ewma','persistence_flat')
GRID=[dict(q=q,patience=p,flat=n) for q in (.95,.98,.995) for p in (4,8) for n in (16,24)]


def identity(role,family,index):
    seed=901000+list(ROLES).index(role)*1000+(family=='B')*100+index
    group=f'causal-v9-{role}-{family}-{seed}'
    return group,seed


def require_lock(path):
    if path is None or not Path(path).is_file(): raise ValueError('frozen lock required')
    lock=json.loads(Path(path).read_text(encoding='utf-8'))
    if lock['status']!='frozen_before_test': raise ValueError('not frozen')
    if any(d.sha(p)!=h for p,h in lock['files'].items()): raise ValueError('frozen file changed')
    return lock


def generate(path,role,lock=None):
    if role=='test': require_lock(lock)
    path=Path(path);path.mkdir(parents=True,exist_ok=False)
    ledger,entries={},[]
    count,ticks=ROLES[role]
    specs=signals()
    with d.local_mes() as server,(path/'features.jsonl').open('x',encoding='utf-8') as target:
        base='http://127.0.0.1:'+str(server.server_address[1])
        def post(route,payload):
            with urlopen(Request(base+route,json.dumps(payload).encode(),method='POST'),timeout=30) as response:
                return json.load(response)
        for family in ('A','B'):
            for index in range(count):
                group,seed=identity(role,family,index)
                rng=random.Random(seed+19);events=[]
                if role in ('development','test') and index:
                    drive='EQ-0004' if index%2 else 'EQ-0005'
                    utility='EQ-0001' if index%2 else 'EQ-0003'
                    sensor=[('EQ-0002','bus_voltage'),('EQ-0006','rt_motor_current'),('EQ-0007','rt_vib_rms'),
                            ('EQ-0008','rt_clamp_press'),('EQ-0009','cv_motor_current')][(index-1)%5]
                    kinds=[('friction' if index%2 else 'cooling_loss',drive,None),
                           ('leak' if index%2 else 'blockage',utility,None),('sensor_stuck',*sensor)]
                    for i,((kind,eq,sig),start) in enumerate(zip(kinds,(95,165,255))):
                        at=start+rng.randint(-5,5)
                        events.append(dict(event_id=str(i),kind=kind,equipment=eq,signal=sig,start=at,
                                           end=at+rng.randint(32,50),amplitude=rng.uniform(.7,2.5)))
                for control in ([False,True] if events else [False]):
                    run=hashlib.sha256((group+str(control)).encode()).hexdigest()[:32]
                    intervention=[] if control else events
                    ledger[run]=intervention
                    post('/benchmark/reset',dict(family=family,seed=seed,run_id=run,events=intervention,pauses=False))
                    held={}
                    for tick in range(ticks):
                        frame=post('/benchmark/step',{})
                        for m in frame['measurements']:
                            key=m['equipment_id'],m['signal']
                            if m['signal'] in MANUAL or m['signal']=='rt_lift_delay' or specs[key]['unit']=='bool':continue
                            if tick==139:held[key]=m['value']
                            if 140<=tick<=151:m['value']=held[key]
                        target.write(json.dumps(frame,separators=(',',':'),allow_nan=False)+'\n')
                    entries.append(dict(run_id=run,seed=seed,nonce=group+str(control),group_id=group,
                                        family=family,control=control,frames=ticks))
    d.write_new(path/'events.private.json',ledger)
    d.write_new(path/'manifest.json',dict(role=role,runs=entries,features_sha256=d.sha(path/'features.jsonl'),
        ledger_sha256=d.sha(path/'events.private.json'),candidate_lock_sha256=d.sha(lock) if lock else None,
        acquisition_hold=[140,151],transport='isolated localhost HTTP',is_synthetic=True))


def check_disjoint(manifests):
    prior=set();runs=set();nonces=set()
    for manifest in manifests:
        for r in manifest['runs']:
            if r['run_id'] in runs or r['nonce'] in nonces:raise ValueError('run/nonce overlap')
            runs.add(r['run_id']);nonces.add(r['nonce'])
        groups={r['group_id'] for r in manifest['runs']}
        if prior & groups: raise ValueError('group overlap')
        prior |= groups
    # Same seed only belongs to one role/group, including its intentional control.
    ownership={}
    for manifest in manifests:
        for r in manifest['runs']:
            if r['seed'] in ownership and ownership[r['seed']]!=r['group_id']:raise ValueError('seed overlap')
            ownership[r['seed']]=r['group_id']


def flatlines(values,tolerance,eligible,patience,resets=None):
    result=np.zeros(values.shape,bool);history=deque(maxlen=patience)
    for i,row in enumerate(values):
        if resets is not None and resets[i]:history.clear()
        history.append(row)
        if len(history)==patience:
            x=np.asarray(history)
            valid=np.isfinite(x).all(axis=0)
            result[i]=eligible & valid & ((np.max(x,axis=0)-np.min(x,axis=0))<=tolerance)
    return result


def transitions(evidence,patience,recovery,resets=None,immediate=None):
    emitted=np.zeros(evidence.shape,bool);on=np.zeros(evidence.shape[1],bool)
    high=np.zeros(evidence.shape[1],int);low=high.copy()
    for i,row in enumerate(evidence):
        if resets is not None and resets[i]:on[:]=False;high[:]=0;low[:]=0
        high=np.where(row,high+1,0)
        direct=np.zeros_like(on) if immediate is None else immediate[i]
        low=np.where(row|direct,0,low+1)
        on[low>=recovery]=False
        starts=~on & ((high>=patience)|direct)
        emitted[i]=starts;on|=starts
    return emitted


def flat_reference(runs,channels):
    deltas=[[] for _ in channels]
    for frames in runs.values():
        prior={}
        for f in frames:
            current=d.valid_values(f,signals())
            for j,c in enumerate(channels):
                if c in prior and c in current:deltas[j].append(abs(current[c]-prior[c]))
            prior=current
    tolerance=[];eligible=[]
    for c,values in zip(channels,deltas):
        x=np.asarray(values);positive=x[x>0]
        spec=signals()[c];band=(spec['normal_max'] or 0)-(spec['normal_min'] or 0)
        tolerance.append(max(1e-9*max(band,1),float(np.quantile(positive,.01))*.01 if len(positive) else 0))
        eligible.append(spec['unit']!='bool' and len(x)>0 and np.median(x)>max(band,1)*1e-7)
    return np.array(tolerance),np.array(eligible)


def prepare(runs,channels,stats,computed):
    unit_limits={k:np.ones(len(computed['ts'][0])) for k in ('timestral','ewma')}
    data=old.policy_data(runs,channels,stats,computed,unit_limits)
    lookup={key:i for i,key in enumerate(computed['keys'])}
    for name in ('ts','ewma','naive'):
        data[name]=np.asarray([computed[name][lookup[k]] if k in lookup else np.full(len(data['equipment']),np.nan) for k in data['keys']])
    values=[]
    for frames in runs.values():
        for f in frames:
            current=d.valid_values(f,signals())
            values.append([current.get(c,np.nan) for c in channels])
    data['values']=np.asarray(values)
    data['eligible_keys']=set(computed['keys'])
    return data


def limits(computed,q):
    out={}
    for name in ('ts','ewma','naive'):
        out[name]=np.array([max(1.,float(np.quantile(c[np.isfinite(c)],q,method='higher'))) for c in computed[name].T])
    return out


def predict(data,channels,tolerance,variable,thresholds,params,method):
    evidence=np.zeros(data['raw_z'].shape,bool)
    for name in (('ewma','ts') if method in ('full','no_flat') else ('naive',) if method=='persistence_flat' else ('ewma',)):
        evidence |= data[name]>thresholds[name]
    flat=np.zeros_like(evidence)
    if method in ('full','no_timestral','persistence_flat'):
        flags=flatlines(data['values'],tolerance,variable,params['flat'],data['resets'])
        for j,e in enumerate(data['equipment']):flat[:,j]=flags[:,[i for i,c in enumerate(channels) if c[0]==e]].any(axis=1)
    ready=np.array([k in data['eligible_keys'] for k in data['keys']])
    flat &= ready[:,None];evidence &=ready[:,None] & np.isfinite(data['raw_z'])
    notices=transitions(evidence,params['patience'],5,data['resets'],flat)
    return {k:{e for j,e in enumerate(data['equipment']) if notices[i,j]} for i,k in enumerate(data['keys'])}
