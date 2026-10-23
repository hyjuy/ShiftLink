"""No-Timestral recovery with validity of the actual alarm source channels."""
import numpy as np
from collections import deque


def flat_evidence(values,tolerance,variable,resets):
    flat=np.zeros(values.shape,bool);known=np.zeros_like(flat);history=deque(maxlen=16)
    for i,row in enumerate(values):
        if resets[i]:history.clear()
        history.append(row);x=np.asarray(history);finite=np.isfinite(x)
        low=np.min(np.where(finite,x,np.inf),axis=0);high=np.max(np.where(finite,x,-np.inf),axis=0)
        moving=(finite.sum(axis=0)>=2) & (high-low>tolerance)
        complete=len(history)==16 and finite.all(axis=0)
        flat[i]=variable & complete & (high-low<=tolerance)
        # Observed movement proves non-flat even while missing history is being rebuilt.
        known[i]=variable & np.isfinite(row) & (flat[i] | moving)
    return flat,known


def predict(data,channels,tolerance,variable,computed,holds,thresholds,params):
    ready=np.array([key in data['eligible_keys'] for key in data['keys']]) & ~holds
    level=computed['level']
    process_known=np.isfinite(level) & variable[None,:] & ready[:,None]
    process=process_known & (level>thresholds['level'])
    values=data['values'].copy();values[holds]=np.nan
    resets=np.asarray(data['resets']) | holds
    flat,flat_known=flat_evidence(values,tolerance,variable,resets)
    flat &=ready[:,None];flat_known &=ready[:,None]
    indexes=[[j for j,c in enumerate(channels) if c[0]==eq] for eq in data['equipment']]
    notices=notifications(process,flat,process_known,flat_known,indexes,params['patience'],data['resets'],holds)
    return {key:{eq for j,eq in enumerate(data['equipment']) if notices[i,j]} for i,key in enumerate(data['keys'])}


def notifications(process,flat,process_known,flat_known,indexes,patience,resets,holds):
    count=len(indexes);on=np.zeros(count,bool);high=np.zeros(count,int);low=high.copy()
    process_sources=np.zeros((count,process.shape[1]),bool);flat_sources=process_sources.copy()
    result=np.zeros((len(process),count),bool)
    for i in range(len(process)):
        if resets[i]:
            on[:]=False;high[:]=0;low[:]=0;process_sources[:]=False;flat_sources[:]=False
        if holds[i]:high[:]=0;low[:]=0;continue
        for j,ix in enumerate(indexes):
            p=process[i,ix];f=flat[i,ix]
            high[j]=high[j]+1 if p.any() else 0
            known=process_known[i,process_sources[j]].all() and flat_known[i,flat_sources[j]].all()
            low[j]=0 if p.any() or f.any() or not known else low[j]+1
            if low[j]>=5:
                on[j]=False;process_sources[j]=False;flat_sources[j]=False
            start=not on[j] and (high[j]>=patience or f.any())
            if start:result[i,j]=True;on[j]=True
            if on[j]:
                # A different healthy sensor cannot establish recovery of an unknown alarm source.
                process_sources[j,ix] |= p;flat_sources[j,ix] |= f
    return result
