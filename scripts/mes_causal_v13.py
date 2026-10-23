"""Thermal recovery band and non-causal supply context; no generator labels."""
import numpy as np
from scripts import mes_causal_v11 as previous

THERMAL_EXIT_RATIO=2/3


def evidence(data,channels,tolerance,variable,computed,holds,thresholds,params):
    ready=np.array([key in data['eligible_keys'] for key in data['keys']]) & ~holds
    known=np.isfinite(computed['level']) & variable[None,:] & ready[:,None]
    process=known & (computed['level']>thresholds['level'])
    values=data['values'].copy();values[holds]=np.nan
    flat,flat_known=previous.flat_evidence(values,tolerance,variable,np.asarray(data['resets'])|holds)
    flat &=ready[:,None];flat_known &=ready[:,None]
    indexes=[[j for j,c in enumerate(channels) if c[0]==eq] for eq in data['equipment']]
    return process,flat,known,flat_known,indexes


def predict(data,channels,tolerance,variable,computed,holds,thresholds,params):
    process,flat,known,flat_known,indexes=evidence(data,channels,tolerance,variable,computed,holds,thresholds,params)
    thermal=np.array(['temp' in c[1] for c in channels])
    recovered=known & (~thermal[None,:] | (computed['level']<=np.asarray(thresholds['level'])*THERMAL_EXIT_RATIO))
    args=(indexes,params['patience'],data['resets'],holds)
    original=previous.notifications(process,flat,known,flat_known,*args)
    notices=previous.notifications(process,flat,recovered,flat_known,*args)
    for j,ix in enumerate(indexes):
        local=[k for k in ix if not thermal[k]]
        # A thermal tail must not hide a new flat sensor or independent nonthermal evidence.
        notices[:,j] |= original[:,j] & (flat[:,ix].any(axis=1) | process[:,local].any(axis=1))
    return {key:{eq for j,eq in enumerate(data['equipment']) if notices[i,j]} for i,key in enumerate(data['keys'])}


def associations(args,rows,links):
    data,channels,tolerance,variable,computed,holds,thresholds,params=args
    process,flat,known,flat_known,indexes=evidence(*args)
    seen=set();result=[]
    for i,key in enumerate(data['keys']):
        if data['resets'][i]:seen.clear()
        for child in sorted(rows[key]):
            pressure=[j for j,c in enumerate(channels) if c==(child,'rt_clamp_press')
                      and process[i,j] and data['signed_z'][i,j]<0]
            if not pressure:continue
            for link in links:
                parent=link['from']
                if link['to']!=child or link['relation']!='hydraulic_supply' or parent not in seen:continue
                source=[j for j,c in enumerate(channels) if c[0]==parent and 'pressure' in c[1]
                        and process[i,j] and data['signed_z'][i,j]<0]
                if not source:continue
                ix=[j for j,c in enumerate(channels) if c[0]==child]
                other=[channels[j][1] for j in ix if (process[i,j] and j not in pressure) or flat[i,j]]
                result.append(dict(run_id=key[0],sequence=key[1],equipment=child,upstream_candidate=parent,
                    relation='hydraulic_supply',kind='associated_pressure_observation',causal_claim=False,
                    notification_preserved=True,local_evidence_present=bool(other),other_signals=other,
                    observed_signals=[channels[j][1] for j in pressure],
                    upstream_low_pressure_signals=[channels[j][1] for j in source]))
        seen.update(rows[key])
    return result
