"""Causal evidence aggregation and observation-confirmed notification rearming."""
from scripts import mes_timestral_recent_entry as previous
from collections import deque
from datetime import datetime
import numpy as np

def validate(data,display):
    keys=data['keys'];equipment=data['equipment']
    if (np.shape(data['raw_z'])!=np.shape(data['ratio']) or np.shape(data['raw_z'])!=(len(keys),len(equipment))
            or len(data['resets'])!=len(keys) or len(set(keys))!=len(keys) or set(keys)!=set(display)):
        raise ValueError('invalid evidence data')
    return keys,equipment

def predict(data,display,params):
    keys,equipment=validate(data,display);k=params['raw_count']
    if (type(k) is not int or not 1<=k<=8 or not np.isfinite(params['fraction']) or not 0<=params['fraction']<=1
            or type(params['max_age']) is not int or params['max_age']<1):raise ValueError('invalid evidence parameters')
    streak=np.zeros(len(equipment),int);normal=np.full(len(equipment),-1000000,int);fired=np.zeros(len(equipment),bool)
    history=deque(maxlen=k);out={};evidence={};last=None
    for i,key in enumerate(keys):
        if data['resets'][i] or last is None or key[0]!=last[0] or key[1]!=last[1]+1:
            streak[:]=0;normal[:]=-1000000;fired[:]=False;history.clear()
        z=data['raw_z'][i];r=data['ratio'][i];valid=np.isfinite(z)&np.isfinite(r)
        normal[~valid]=-1000000;normal[valid&(z<=1.5)]=key[1]
        raw=valid&(z>=2.5);streak=np.where(raw,np.minimum(streak+1,k),0);fired[~raw]=False
        history.append(valid&(r>.1));votes=np.sum(history,axis=0)
        trigger=raw&(streak>=k)&(votes>=params['fraction']*k)&(key[1]-normal<=params['max_age'])&~fired
        evidence[key]={eq for j,eq in enumerate(equipment) if trigger[j]};fired|=trigger
        out[key]=set(display[key])|evidence[key];last=key
    return out,evidence

def notifications(data,display,evidence,params):
    keys,equipment=validate(data,display);k=params['normal_count'];cooldown=params['cooldown'];obs=data['observations']
    if (type(k) is not int or not 1<=k<=12 or type(cooldown) is not int or cooldown<1
            or [(o['run'],o['sequence']) for o in obs]!=keys or set(evidence)!=set(keys)
            or any(not evidence[key]<=display[key] for key in keys)):raise ValueError('invalid notification parameters')
    count=np.zeros(len(equipment),int);armed=set();sent={};before=set();last=None;out={}
    for i,(key,o) in enumerate(zip(keys,obs)):
        now=datetime.fromisoformat(o['at'])
        if data['resets'][i] or last is None or key[0]!=last[0][0] or key[1]!=last[0][1]+1 or (now-last[1]).total_seconds()!=1 or o['inactive']:
            count[:]=0;armed.clear();sent.clear();before=set()
        emitted=set();current=display[key]
        if not o['inactive']:
            normal=np.isfinite(data['raw_z'][i])&np.isfinite(data['ratio'][i])&(data['raw_z'][i]<=1.5)
            count=np.where(normal,np.minimum(count+1,k),0)
            armed.update(eq for j,eq in enumerate(equipment) if count[j]>=k)
            for eq in (current-before)|evidence[key]:
                if eq not in sent or eq in armed or (now-sent[eq]).total_seconds()>=cooldown:
                    emitted.add(eq);sent[eq]=now;armed.discard(eq)
            before=set(current)
        out[key]=emitted;last=key,now
    return out
