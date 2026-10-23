"""Causal sustained weak-signal entry and quiet rearmed notifications."""
import importlib.util
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('close_notification',ROOT/'scripts/mes_timestral_notifications.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)

def augment(data,display,params):
    keys=data['keys'];equipment=data['equipment'];z=data['raw_z'];ratio=data['ratio']
    if (type(params['count']) is not int or not 1<=params['count']<=8
            or not np.isfinite([params['z'],params['ratio']]).all()
            or min(params['z'],params['ratio'])<0
            or np.shape(z)!=np.shape(ratio) or np.shape(z)!=(len(keys),len(equipment))
            or len(data['resets'])!=len(keys) or len(set(keys))!=len(keys) or set(keys)!=set(display)):
        raise ValueError('invalid sustained entry contract')
    count=np.zeros(len(equipment),dtype=int);last=None;out={}
    for i,key in enumerate(keys):
        if data['resets'][i] or last is None or key[0]!=last[0] or key[1]!=last[1]+1:count[:]=0
        hit=np.isfinite(z[i])&np.isfinite(ratio[i])&(z[i]>=params['z'])&(ratio[i]>params['ratio'])
        count=np.where(hit,np.minimum(count+1,params['count']+1),0)
        ready=count==params['count'] if params.get('onset_only',False) else count>=params['count']
        out[key]=set(display[key])|{eq for j,eq in enumerate(equipment) if ready[j]}
        last=key
    return out

def pulses(data,display,params):
    return previous.notifications(data['observations'],display,**params)
