"""Only add weak onset evidence after recently observed low deviation."""
from scripts import mes_timestral_close as close
import numpy as np

def predict(data,display,params):
    if (type(params['max_age']) is not int or params['max_age']<1 or not np.isfinite(params['normal_z'])
            or not 0<=params['normal_z']<params['z'] or not params['onset_only']):
        raise ValueError('invalid recent normal contract')
    candidate=close.augment(data,display,params)
    seen=np.full(len(data['equipment']),-1000000,dtype=int);last=None;out={}
    for i,key in enumerate(data['keys']):
        if data['resets'][i] or last is None or key[0]!=last[0] or key[1]!=last[1]+1:seen[:]=-1000000
        valid=np.isfinite(data['raw_z'][i])&np.isfinite(data['ratio'][i])
        seen[~valid]=-1000000
        seen[valid&(data['raw_z'][i]<=params['normal_z'])]=key[1]
        allowed={eq for j,eq in enumerate(data['equipment']) if valid[j] and 0<=key[1]-seen[j]<=params['max_age']}
        out[key]=set(display[key])|(candidate[key]&allowed);last=key
    return out
