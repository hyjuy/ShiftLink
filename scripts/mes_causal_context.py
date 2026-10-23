"""Separate fixed normal-context candidate; the original v14c core is untouched."""
import hashlib,json,math
import numpy as np
from scripts.mes_causal_v14_stream import OnlineDetector
from scripts.mes_causal_schema import signals

PAIRS={'hpu_cooler_oil_out_temp':'hpu_cooler_oil_in_temp','hpu_cooler_water_out_temp':'hpu_cooler_water_in_temp'}
MODES=[a+':'+b for a in ('slow','nominal','fast') for b in ('empty','moving','queued')]


def context(frame,capacities):
    speed=frame.get('speed');coils=frame.get('coils')
    if type(speed) not in (int,float) or not math.isfinite(speed) or not .25<=speed<=2 or not isinstance(coils,list) or len(coils)>256:return None
    found=set()
    for c in coils:
        if (not isinstance(c,dict) or not isinstance(c.get('coil_id'),str) or not 0<len(c['coil_id'])<=128 or c['coil_id'] in found
            or not isinstance(c.get('equipment_id'),str) or type(c.get('position')) not in (int,float)
            or not math.isfinite(c['position']) or not 0<=c['position']<=1):return None
        found.add(c['coil_id'])
    load='queued' if any(c['equipment_id'] in capacities and c['position']>=1 for c in coils) else 'moving' if coils else 'empty'
    return ('slow' if speed<.75 else 'fast' if speed>1.25 else 'nominal')+':'+load,coils


class ContextDetector(OnlineDetector):
    def __init__(self,settings,profile):
        self.profile=profile
        if profile.get('schema_version')!=1 or set(profile.get('offsets',{}))!=set(MODES):raise ValueError('normal profile schema')
        if not isinstance(profile.get('source_config_id'),str):raise ValueError('normal profile source')
        for values in profile['offsets'].values():
            if set(values)!=set(PAIRS) or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>20 for v in values.values()):raise ValueError('normal profile offsets')
        if not profile.get('capacities') or any(type(n) is not int or not 1<=n<=100 for n in profile['capacities'].values()):raise ValueError('normal profile capacities')
        super().__init__(settings);self.reference_center=self.center.copy();self.pending=None;self.specs=signals()
        self.lookup={c:j for j,c in enumerate(self.channels)}

    def _restart(self):
        super()._restart();self.ages={e:0 for e in self.profile['capacities']};self.previous={e:None for e in self.ages}

    def context_state(self):return dict(ages=dict(self.ages),previous=dict(self.previous))

    def load_context(self,state):
        if state is None:return
        if not isinstance(state,dict) or set(state)!={'ages','previous'} or set(state['ages'])!=set(self.ages) or set(state['previous'])!=set(self.ages):raise ValueError('context checkpoint keys')
        if any(type(v) is not int or not 0<=v<=16 for v in state['ages'].values()):raise ValueError('context checkpoint age')
        if any(v is not None and (not isinstance(v,str) or len(v)!=64) for v in state['previous'].values()):raise ValueError('context checkpoint digest')
        self.ages=dict(state['ages']);self.previous=dict(state['previous'])

    def step(self,frame):
        self.pending=frame
        return super().step(frame)

    def _scores(self,raw,reset,hold,ready):
        observed=context(self.pending,self.profile['capacities']) if self.pending.get('config_id')==self.profile['source_config_id'] else None
        if observed is None:return super()._scores(raw,reset,hold,ready)
        mode,coils=observed;expected=self.reference_center.copy();queue_normal={}
        for (eq,sig),j in self.lookup.items():
            low,high=self.specs[eq,sig]['normal_min'],self.specs[eq,sig]['normal_max']
            if not np.isfinite(raw[j]) or low is None or high is None or not low<=raw[j]<=high:continue
            if sig in PAIRS:
                k=self.lookup.get((eq,PAIRS[sig]))
                if k is not None and np.isfinite(raw[k]):expected[j]=np.clip(raw[k]+self.profile['offsets'][mode][sig],low,high)
            if sig=='cv_queue_len' and eq in self.ages:
                items=sorted((c['coil_id'],c['position']) for c in coils if c['equipment_id']==eq)
                signature=hashlib.sha256(json.dumps(items).encode()).hexdigest()
                self.ages[eq]=min(16,self.ages[eq]+1) if self.previous[eq]==signature else 0;self.previous[eq]=signature
                queued=sum(pos>=1 for _,pos in items);value=min(100.,100*queued/self.profile['capacities'][eq])
                if value<=high:
                    expected[j]=value
                    # Matching empty queues or physically moving stock are not stuck sensors.
                    queue_normal[j]=abs(raw[j]-value)<=.001 and (queued==0 or self.ages[eq]<16)
        self.center=expected
        try:level,flat,known,_=super()._scores(raw,reset,hold,ready)
        finally:self.center=self.reference_center.copy()
        for j,normal in queue_normal.items():
            if normal:flat[j]=False
        # Thermal rise and raw flat-line tests keep their original physical input.
        if not hold and self.thermal_history:self.thermal_history[-1]=(raw-self.reference_center)/self.scale
        rise=np.full(len(self.equipment),np.nan)
        if ready and not hold and len(self.thermal_history)==37:
            x=np.asarray(self.thermal_history)
            for k,ix in enumerate(self.temp_indexes):
                good=[j for j in ix if np.isfinite(x[-1,j]) and np.isfinite(x[-5:,j]).sum()>=4 and np.isfinite(x[:-5,j]).sum()>=24]
                if len(good)>=2:rise[k]=np.sort(np.nanmedian(x[-5:,good],axis=0)-np.nanmedian(x[:-5,good],axis=0))[-2]
        return level,flat,known,np.maximum(rise,0)/self.thermal_limits


def fit_profile(frames,source_config):
    capacities={e['equipment_id']:e['coil_capacity'] for e in source_config['equipment'] if e['code'].startswith('CV')}
    offsets={m:{s:[] for s in PAIRS} for m in MODES}
    for frame in frames:
        found=context(frame,capacities)
        if found is None:continue
        mode,_=found;values={(m['equipment_id'],m['signal']):m for m in frame['measurements']}
        for eq in {e for e,s in values}:
            for target,reference in PAIRS.items():
                a,b=values.get((eq,target)),values.get((eq,reference))
                if a and b and a['quality']==b['quality']=='good' and a['observed_at']==b['observed_at']==frame['simulated_at'] and all(type(v['value']) in (int,float) and math.isfinite(v['value']) for v in (a,b)):
                    offsets[mode][target].append(a['value']-b['value'])
    if any(len(v)<64 for group in offsets.values() for v in group.values()):raise ValueError('normal context needs 64 reference samples per cell')
    return dict(schema_version=1,source_config_id=source_config['config_id'],capacities=capacities,minimum_samples=64,
                offsets={m:{s:float(np.median(v)) for s,v in group.items()} for m,group in offsets.items()})
