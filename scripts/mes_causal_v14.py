"""Causal thermal-rise evidence; original v13 remains unchanged."""
from collections import deque
import numpy as np
from scripts import mes_causal_v13 as previous


def thermal_rise(args,window=32):
    data,channels,tolerance,variable,computed,holds,thresholds,params=args
    result=np.full((len(data['keys']),len(data['equipment'])),np.nan)
    history=deque(maxlen=window+5)
    groups=[[j for j,c in enumerate(channels) if c[0]==eq and 'temp' in c[1] and variable[j]]
            for eq in data['equipment']]
    for i,row in enumerate(data['signed_z']):
        if data['resets'][i] or holds[i]:history.clear()
        if holds[i]:continue
        history.append(row)
        if len(history)<window+5 or data['keys'][i] not in data['eligible_keys']:continue
        x=np.asarray(history)
        for k,ix in enumerate(groups):
            valid=[j for j in ix if np.isfinite(x[-1,j]) and np.isfinite(x[-5:,j]).sum()>=4
                   and np.isfinite(x[:-5,j]).sum()>=int(window*.75)]
            if len(valid)<2:continue
            change=np.nanmedian(x[-5:,valid],axis=0)-np.nanmedian(x[:-5,valid],axis=0)
            result[i,k]=np.sort(change)[-2]
    return result


def augment(args,rise=None):
    data,channels,tolerance,variable,computed,holds,thresholds,params=args
    limits=np.asarray(params['thermal_rise_limits'],float)
    if len(limits)!=len(data['equipment']) or np.any(~np.isfinite(limits)) or np.any(limits<=0):
        raise ValueError('positive finite per-equipment thermal limits required')
    rise=thermal_rise(args) if rise is None else rise
    count=len(limits);augmented=dict(data)
    augmented['values']=np.column_stack((data['values'],np.full(rise.shape,np.nan)))
    augmented['signed_z']=np.column_stack((data['signed_z'],rise))
    return (augmented,channels+[(eq,'derived_coherent_temp_rise') for eq in data['equipment']],
            np.r_[tolerance,np.zeros(count)],np.r_[variable,np.ones(count,bool)],
            {'level':np.column_stack((computed['level'],np.maximum(rise,0)/limits))},holds,
            {'level':np.r_[thresholds['level'],np.ones(count)]},params)


def predict(*args,original=None):
    rows=previous.predict(*augment(args))
    original=previous.predict(*args) if original is None else original
    process,flat,known,flat_known,indexes=previous.evidence(*args)
    thermal=np.array(['temp' in c[1] for c in args[1]])
    for i,key in enumerate(args[0]['keys']):
        for j,eq in enumerate(args[0]['equipment']):
            local=[k for k in indexes[j] if not thermal[k]]
            if eq in original[key] and (flat[i,indexes[j]].any() or process[i,local].any()):
                rows[key].add(eq)
    return rows
