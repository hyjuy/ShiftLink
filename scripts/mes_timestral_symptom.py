"""Bounded symptom memory for causal, equipment-level notifications."""
from scripts import mes_timestral_evidence_entry as previous
from datetime import datetime
import numpy as np

def notifications(data,display,params):
    keys,equipment=previous.evidence.validate(data,display)
    z=params['z'];stable=params['stable'];normal_count=params['normal_count'];cooldown=params['cooldown']
    if (type(stable) is not int or not 1<=stable<=2 or type(normal_count) is not int or not 1<=normal_count<=12
            or type(cooldown) is not int or cooldown<1 or not np.isfinite(z) or z<=1.5
            or np.shape(data['signed_z'])!=(len(keys),len(data['channels']))
            or [(o['run'],o['sequence']) for o in data['observations']]!=keys):raise ValueError('invalid symptom contract')
    signatures=[];magnitudes=[]
    for eq in equipment:
        ix=np.array([j for j,c in enumerate(data['channels']) if c[0]==eq])
        if not len(ix):raise ValueError('equipment channels missing')
        values=data['signed_z'][:,ix];absolute=np.where(np.isfinite(values),np.abs(values),-np.inf)
        dom=np.argmax(absolute,axis=1);signed=values[np.arange(len(keys)),dom]
        signatures.append(ix[dom]*2+(signed<0));magnitudes.append(absolute[np.arange(len(keys)),dom])
    signatures=np.array(signatures).T;magnitudes=np.array(magnitudes).T
    state={};last=None;out={}
    for i,(key,o) in enumerate(zip(keys,data['observations'])):
        at=datetime.fromisoformat(o['at']);emitted=set()
        if data['resets'][i] or last is None or key[0]!=last[0][0] or key[1]!=last[0][1]+1 or (at-last[1]).total_seconds()!=1 or o['inactive']:state={}
        if not o['inactive']:
            for j,eq in enumerate(equipment):
                s=state.setdefault(eq,dict(seen=set(),normal=0,armed=False,sent=None,on=False,dominant=None,stable=0))
                valid=np.isfinite(data['raw_z'][i,j]) and np.isfinite(data['ratio'][i,j])
                normal=valid and data['raw_z'][i,j]<=1.5
                s['normal']=min(s['normal']+1,normal_count+1) if normal else 0
                if s['normal']==normal_count:s['armed']=True;s['seen'].clear()
                sig=int(signatures[i,j]) if magnitudes[i,j]>=z and np.isfinite(data['raw_z'][i,j]) else None
                s['stable']=min(s['stable']+1,stable) if sig is not None and sig==s['dominant'] else int(sig is not None)
                s['dominant']=sig;current=eq in display[key]
                novel=sig is not None and s['stable']>=stable and sig not in s['seen']
                candidate=current and not s['on']
                if candidate and (s['sent'] is None or s['armed'] or novel or (at-s['sent']).total_seconds()>=cooldown):
                    emitted.add(eq);s['sent']=at;s['armed']=False
                    if sig is not None:s['seen'].add(sig)
                if not current and sig is not None and s['sent'] is not None and (at-s['sent']).total_seconds()<=8:s['seen'].add(sig)
                s['on']=current
        out[key]=emitted;last=key,at
    return out
