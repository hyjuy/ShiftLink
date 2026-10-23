"""Isolated v10: acquisition-repeat quality gate and robust channel calibration."""
from collections import deque
import hashlib
import json
from pathlib import Path
import random
from urllib.request import Request, urlopen

import numpy as np
from scripts import mes_causal_data as d
from scripts import mes_causal_v9 as v9
from scripts.mes_causal_schema import signals, MANUAL

ROLES={'fit':(4,384),'calibration':(2,384),'development':(3,512),'test':(7,512)}


def identity(role,family,index):
    seed=1001000+list(ROLES).index(role)*1000+(family=='B')*100+index
    return f'causal-v10-{role}-{family}-{seed}',seed


def generate(path,role,lock=None):
    if role=='test':v9.require_lock(lock)
    path=Path(path);path.mkdir(parents=True,exist_ok=False)
    ledger,entries={},[];count,ticks=ROLES[role];specs=signals()
    with d.local_mes() as server,(path/'features.jsonl').open('x',encoding='utf-8') as target:
        base='http://127.0.0.1:'+str(server.server_address[1])
        def post(route,payload):
            with urlopen(Request(base+route,json.dumps(payload).encode(),method='POST'),timeout=30) as response:return json.load(response)
        for family in ('A','B'):
            for index in range(count):
                group,seed=identity(role,family,index);rng=random.Random(seed+31);events=[]
                if role in ('development','test') and index:
                    drive='EQ-0004' if index%2 else 'EQ-0005'
                    utility='EQ-0001' if index%2 else 'EQ-0003'
                    sensor=[('EQ-0002','bus_voltage'),('EQ-0006','rt_motor_current'),('EQ-0007','rt_vib_rms'),
                            ('EQ-0008','rt_clamp_press'),('EQ-0009','cv_motor_current')][(index-1)%5]
                    kinds=[('friction' if index%2 else 'cooling_loss',drive,None),
                           ('leak' if index%2 else 'blockage',utility,None),('sensor_stuck',*sensor)]
                    for i,((kind,eq,sig),start) in enumerate(zip(kinds,(100,230,370))):
                        at=start+rng.randint(-12,12)
                        events.append(dict(event_id=str(i),kind=kind,equipment=eq,signal=sig,start=at,
                                           end=at+rng.randint(32,60),amplitude=rng.uniform(.5,2.5)))
                # Hold timing/length vary independently of intervention labels, identical in paired runs.
                hold_start=rng.randint(140,180);hold_length=rng.randint(6,14)
                for control in ([False,True] if events else [False]):
                    run=hashlib.sha256((group+str(control)).encode()).hexdigest()[:32]
                    intervention=[] if control else events;ledger[run]=intervention
                    post('/benchmark/reset',dict(family=family,seed=seed,run_id=run,events=intervention,pauses=False))
                    held={}
                    for tick in range(ticks):
                        frame=post('/benchmark/step',{})
                        for m in frame['measurements']:
                            key=m['equipment_id'],m['signal']
                            if m['signal'] in MANUAL or m['signal']=='rt_lift_delay' or specs[key]['unit']=='bool':continue
                            if tick==hold_start-1:held[key]=m['value']
                            if hold_start<=tick<hold_start+hold_length:m['value']=held[key]
                        target.write(json.dumps(frame,separators=(',',':'),allow_nan=False)+'\n')
                    entries.append(dict(run_id=run,seed=seed,nonce=group+str(control),group_id=group,
                                        family=family,control=control,frames=ticks,hold=[hold_start,hold_length]))
    d.write_new(path/'events.private.json',ledger)
    d.write_new(path/'manifest.json',dict(role=role,runs=entries,features_sha256=d.sha(path/'features.jsonl'),
        ledger_sha256=d.sha(path/'events.private.json'),candidate_lock_sha256=d.sha(lock) if lock else None,
        transport='isolated localhost HTTP',is_synthetic=True))


def acquisition_repeats(values,variable,resets):
    flags=np.zeros(len(values),bool);previous=None
    for i,row in enumerate(values):
        if resets[i]:previous=None
        if previous is not None:
            valid=variable & np.isfinite(row) & np.isfinite(previous)
            # Exact common freeze of >=80% of normally variable channels, minimum 4.
            flags[i]=valid.sum()>=4 and np.sum(valid & (row==previous))>=.8*valid.sum()
        previous=row
    return flags


def robust_levels(values,width,resets,holds):
    result=np.full(values.shape,np.nan);history=deque(maxlen=width)
    for i,row in enumerate(values):
        if resets[i] or holds[i]:history.clear()
        if holds[i]:continue
        history.append(row)
        if len(history)==width:
            x=np.asarray(history);valid=np.isfinite(x).all(axis=0)
            result[i,valid]=np.median(x[:,valid],axis=0)
    return result


def channel_limits(values,q):
    limits=[]
    for column in values.T:
        good=column[np.isfinite(column)]
        if not len(good):raise ValueError('empty channel calibration')
        limits.append(max(1.,float(np.quantile(np.abs(good),q,method='higher'))))
    return np.asarray(limits)


def smooth_signed(values,resets,holds):
    result=np.full(values.shape,np.nan);state=np.zeros(values.shape[1]);valid=np.zeros(values.shape[1],bool)
    for i,row in enumerate(values):
        if resets[i] or holds[i]:state[:]=0;valid[:]=False
        current=np.isfinite(row) & ~holds[i]
        state=np.where(current,np.where(valid,.4*row+.6*state,row),0.)
        valid=current
        result[i,current]=state[current]
    return result


def process_scores(data,stats,channels,variable,width,ts=None,naive=None):
    center=np.array([stats[c][0] for c in channels]);scale=np.array([stats[c][1] for c in channels])
    holds=acquisition_repeats(data['values'],variable,data['resets'])
    z=(data['values']-center)/scale
    level=np.abs(smooth_signed(robust_levels(z,width,data['resets'],holds),data['resets'],holds))
    result={'level':level}
    for name,source in (('ts',ts),('naive',naive)):
        if source is not None:result[name]=robust_levels(source,width,data['resets'],holds)
    ready=np.array([k in data['eligible_keys'] for k in data['keys']]) & ~holds
    for scores in result.values():
        scores[~ready]=np.nan;scores[:,~variable]=0.
    return result,holds


def predict(data,channels,tolerance,variable,computed,holds,thresholds,params,method):
    names=('level','ts') if method=='full' else ('ts',) if method=='timestral' else ('naive',) if method=='persistence' else ('level',)
    evidence=np.zeros((len(data['keys']),len(data['equipment'])),bool)
    for name in names:
        flags=np.isfinite(computed[name]) & (computed[name]>thresholds[name]) & variable[None,:]
        for j,e in enumerate(data['equipment']):evidence[:,j]|=flags[:,[i for i,c in enumerate(channels) if c[0]==e]].any(axis=1)
    resets=np.asarray(data['resets']) | holds
    flat_values=data['values'].copy();flat_values[holds]=np.nan
    flat=v9.flatlines(flat_values,tolerance,variable,16,resets)
    ready=np.array([k in data['eligible_keys'] for k in data['keys']]) & ~holds
    flat &= ready[:,None];evidence &= ready[:,None]
    direct=np.zeros_like(evidence)
    if method!='no_flat':
        for j,e in enumerate(data['equipment']):direct[:,j]=flat[:,[i for i,c in enumerate(channels) if c[0]==e]].any(axis=1)
    # Missing/rebuilding evidence cannot prove that an active alarm recovered.
    age=16;recovery_ready=np.zeros_like(evidence)
    for i in range(len(holds)):
        if holds[i]:age=0
        else:age+=1
        for j,e in enumerate(data['equipment']):
            ix=[k for k,c in enumerate(channels) if c[0]==e and variable[k]]
            recovery_ready[i,j]=age>=16 and ready[i] and np.isfinite(data['values'][i,ix]).any()
    notices=notifications(evidence,params['patience'],data['resets'],holds,direct,recovery_ready)
    return {k:{e for j,e in enumerate(data['equipment']) if notices[i,j]} for i,k in enumerate(data['keys'])}


def notifications(evidence,patience,resets,holds,direct,recovery_ready=None):
    result=np.zeros_like(evidence);on=np.zeros(evidence.shape[1],bool)
    high=np.zeros(evidence.shape[1],int);low=high.copy()
    for i,row in enumerate(evidence):
        if resets[i]:on[:]=False;high[:]=0;low[:]=0
        if holds[i]:high[:]=0;low[:]=0;continue
        high=np.where(row,high+1,0)
        recover=np.ones_like(on) if recovery_ready is None else recovery_ready[i]
        low=np.where(row|direct[i],0,np.where(recover,low+1,0))
        on[low>=5]=False
        result[i]=~on & ((high>=patience)|direct[i]);on|=result[i]
    return result
