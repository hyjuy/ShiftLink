"""Separate fixed normal-context candidate; the original v14c core is untouched."""
import hashlib,json,math
from collections import deque
import numpy as np
from scripts.mes_causal_v14_stream import OnlineDetector
from scripts.mes_causal_schema import signals

PAIRS={'hpu_cooler_oil_out_temp':'hpu_cooler_oil_in_temp','hpu_cooler_water_out_temp':'hpu_cooler_water_in_temp'}
MODES=[a+':'+b for a in ('slow','nominal','fast') for b in ('empty','moving','queued')]
# Fixture speed groups are replay-clock labels, not physical load features.
CONTEXT_MODES=['unknown:'+b for b in ('empty','moving','queued')]


def context(frame,capacities):
    coils=frame.get('coils')
    if not isinstance(coils,list) or len(coils)>256:return None
    found=set()
    for c in coils:
        if (not isinstance(c,dict) or not isinstance(c.get('coil_id'),str) or not 0<len(c['coil_id'])<=128 or c['coil_id'] in found
            or not isinstance(c.get('equipment_id'),str) or type(c.get('position')) not in (int,float)
            or not math.isfinite(c['position']) or not 0<=c['position']<=1):return None
        found.add(c['coil_id'])
    load='queued' if any(c['equipment_id'] in capacities and c['position']>=1 for c in coils) else 'moving' if coils else 'empty'
    return 'unknown:'+load,coils


class ContextDetector(OnlineDetector):
    def __init__(self,settings,profile):
        self.profile=profile
        if profile.get('schema_version')!=1 or set(profile.get('offsets',{}))!=set(CONTEXT_MODES):raise ValueError('normal profile schema')
        if not isinstance(profile.get('source_config_id'),str):raise ValueError('normal profile source')
        for values in profile['offsets'].values():
            if set(values)!=set(PAIRS) or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>20 for v in values.values()):raise ValueError('normal profile offsets')
        if not profile.get('capacities') or any(type(n) is not int or not 1<=n<=100 for n in profile['capacities'].values()):raise ValueError('normal profile capacities')
        super().__init__(settings);self.reference_center=self.center.copy();self.reference_scale=self.scale.copy();self.pending=None;self.specs=signals()
        self.normal_stats=profile.get('normal_stats',{})
        if self.normal_stats and set(self.normal_stats)!=set(CONTEXT_MODES):raise ValueError('normal statistics modes')
        for values in self.normal_stats.values():
            if len(values)!=len(self.channels) or any(len(v)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) for x in v) or v[1]<=0 for v in values):raise ValueError('normal statistics values')
        self.lookup={c:j for j,c in enumerate(self.channels)}
        self.context_thermal=np.asarray(profile.get('thermal_limits',self.thermal_limits),float)
        if self.context_thermal.shape!=self.thermal_limits.shape or not np.isfinite(self.context_thermal).all() or np.any(self.context_thermal<self.thermal_limits):raise ValueError('normal thermal limits')
        self.flat_windows=profile.get('flat_windows',[5 if v else 16 for v in profile.get('fast_flat',[False for _ in self.channels])])
        if len(self.flat_windows)!=len(self.channels) or any(type(v) is not int or not 5<=v<=16 for v in self.flat_windows):raise ValueError('normal flat windows')
        self.plateaus=profile.get('normal_plateaus',[[] for _ in self.channels])
        self.fast_flat=np.asarray(profile.get('fast_flat',[False for _ in self.channels]),bool)
        self.plateau_bounds=profile.get('normal_plateau_bounds',[None for _ in self.channels])
        if len(self.plateau_bounds)!=len(self.channels) or any(b is not None and (len(b)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) for x in b) or b[0]>b[1]) for b in self.plateau_bounds):raise ValueError('normal plateau bounds')
        if len(self.plateaus)!=len(self.channels) or self.fast_flat.shape!=(len(self.channels),):raise ValueError('normal plateau shape')
        if any(len(v)>1024 or any(type(x) not in (int,float) or not math.isfinite(x) for x in v) for v in self.plateaus):raise ValueError('normal plateau values')

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
        if observed is not None and any(c['equipment_id'] not in self.equipment for c in observed[1]):observed=None
        if observed is None:return super()._scores(raw,reset,hold,ready)
        mode,coils=observed;expected=self.reference_center.copy();scales=self.reference_scale.copy();queue_flat_suppressed={}
        if mode in self.normal_stats:
            expected,scales=np.asarray(self.normal_stats[mode],float).T.copy()
        for (eq,sig),j in self.lookup.items():
            low,high=self.specs[eq,sig]['normal_min'],self.specs[eq,sig]['normal_max']
            if sig=='cv_queue_len':low,high=0.,100.
            if not np.isfinite(raw[j]) or low is None or high is None or not low<=raw[j]<=high:
                expected[j]=self.reference_center[j];scales[j]=self.reference_scale[j];continue
            if sig in PAIRS:
                scales[j]=self.reference_scale[j]
                k=self.lookup.get((eq,PAIRS[sig]));expected[j]=self.reference_center[j]
                reference=self.specs.get((eq,PAIRS[sig]),{})
                if k is not None and np.isfinite(raw[k]) and reference['normal_min']<=raw[k]<=reference['normal_max']:expected[j]=np.clip(raw[k]+self.profile['offsets'][mode][sig],low,high)
            if sig=='cv_queue_len' and eq in self.ages:
                items=sorted((c['coil_id'],c['position']) for c in coils if c['equipment_id']==eq)
                signature=hashlib.sha256(json.dumps(items).encode()).hexdigest()
                self.ages[eq]=min(16,self.ages[eq]+1) if self.previous[eq]==signature else 0;self.previous[eq]=signature
                queued=sum(pos>=1 for _,pos in items);value=min(100.,100*queued/self.profile['capacities'][eq])
                if value<=high:
                    expected[j]=raw[j] if abs(raw[j]-value)<=.001 else value
                    # New stock/reading mismatch requires process persistence; prior empty history is not stuck evidence.
                    queue_flat_suppressed[j]=abs(raw[j]-value)>.001 or queued==0 or self.ages[eq]<16
        self.center=expected;self.scale=scales
        try:level,flat,known,_=super()._scores(raw,reset,hold,ready)
        finally:self.center=self.reference_center.copy();self.scale=self.reference_scale.copy()
        if ready and not hold and self.plateaus:
            x=np.asarray(self.flat)
            for j,values in enumerate(self.plateaus):
                # A healthy regulated plateau alone cannot identify sensor failure.
                bounds=self.plateau_bounds[j]
                normal_plateau=(bounds[0]-self.tolerance[j]<=raw[j]<=bounds[1]+self.tolerance[j]) if bounds is not None else any(abs(raw[j]-v)<=self.tolerance[j] for v in values)
                if flat[j] and self.channels[j][1]!='cv_queue_len' and normal_plateau:flat[j]=False
                width=self.flat_windows[j]
                if width<16 and len(x)>=width and np.isfinite(x[-width:,j]).all() and np.ptp(x[-width:,j])<=self.tolerance[j]:flat[j]=known[j]=True
        for j,normal in queue_flat_suppressed.items():
            if normal:flat[j]=False
        # Thermal rise and raw flat-line tests keep their original physical input.
        if not hold and self.thermal_history:self.thermal_history[-1]=(raw-self.reference_center)/self.reference_scale
        rise=np.full(len(self.equipment),np.nan)
        if ready and not hold and len(self.thermal_history)==37:
            x=np.asarray(self.thermal_history)
            for k,ix in enumerate(self.temp_indexes):
                good=[j for j in ix if np.isfinite(x[-1,j]) and np.isfinite(x[-5:,j]).sum()>=4 and np.isfinite(x[:-5,j]).sum()>=24]
                if len(good)>=2:rise[k]=np.sort(np.nanmedian(x[-5:,good],axis=0)-np.nanmedian(x[:-5,good],axis=0))[-2]
        return level,flat,known,np.maximum(rise,0)/self.context_thermal


def fit_profile(frames,source_config,settings=None):
    capacities={e['equipment_id']:e['coil_capacity'] for e in source_config['equipment'] if e['code'].startswith('CV')}
    offsets={m:{s:[] for s in PAIRS} for m in CONTEXT_MODES}
    channels=[tuple(c) for c in settings['base']['channels']] if settings else []
    samples={m:{c:[] for c in channels} for m in CONTEXT_MODES}
    detector=OnlineDetector(settings) if settings else None
    history=deque(maxlen=37);previous_run=None;thermal=detector.thermal_limits.copy() if detector else None
    plateaus=[set() for _ in channels];longest=np.full(len(channels),3,int)
    for frame in frames:
        if frame['run_id']!=previous_run:history.clear();previous_run=frame['run_id']
        found=context(frame,capacities)
        if found is None:continue
        mode,_=found;modes=[mode];values={(m['equipment_id'],m['signal']):m for m in frame['measurements']}
        for c in channels:
            v=values[c]
            if v['quality']=='good' and type(v['value']) in (int,float) and math.isfinite(v['value']):
                for m in modes:samples[m][c].append(v['value'])
        if detector:
            raw=np.array([values[c]['value'] if values[c]['quality']=='good' else np.nan for c in channels]);history.append(raw)
            x=np.asarray(history)
            for width in (4,5,6,7,8,10,12,14,16):
                if len(x)>=width:
                    repeated=np.isfinite(x[-width:]).all(axis=0)&(np.ptp(x[-width:],axis=0)<=detector.tolerance);longest[repeated]=np.maximum(longest[repeated],width)
            if len(x)>=16:
                repeated=np.isfinite(x[-16:]).all(axis=0)&(np.ptp(x[-16:],axis=0)<=detector.tolerance)
                for j in np.flatnonzero(repeated):plateaus[j].add(float(raw[j]))
            if len(x)==37:
                z=(x-detector.center)/detector.scale
                for k,ix in enumerate(detector.temp_indexes):
                    if len(ix)>=2:
                        change=np.median(z[-5:,ix],axis=0)-np.median(z[:-5,ix],axis=0)
                        thermal[k]=max(thermal[k],1.5*float(np.sort(change)[-2]))
        for eq in {e for e,s in values}:
            for target,reference in PAIRS.items():
                a,b=values.get((eq,target)),values.get((eq,reference))
                if a and b and a['quality']==b['quality']=='good' and a['observed_at']==b['observed_at']==frame['simulated_at'] and all(type(v['value']) in (int,float) and math.isfinite(v['value']) for v in (a,b)):

                    for m in modes:offsets[m][target].append(a['value']-b['value'])
    if any(len(v)<64 for group in offsets.values() for v in group.values()):raise ValueError('normal context needs 64 reference samples per cell')
    result=dict(schema_version=1,source_config_id=source_config['config_id'],capacities=capacities,minimum_samples=64,
                offsets={m:{s:float(np.median(v)) for s,v in group.items()} for m,group in offsets.items()})
    if settings:
        original={(e,s):(center,scale) for e,s,center,scale in settings['base']['stats']};normal={}
        for mode,values in samples.items():
            rows=[]
            for j,c in enumerate(channels):
                x=np.asarray(values[c]);old_center,old_scale=original[c]
                if len(x)<64:rows.append([old_center,old_scale]);continue
                center=float(np.median(x));span=max(abs(x.min()-center),abs(x.max()-center))
                scale=max(old_scale,2.0*float(span)/settings['limits'][j])
                rows.append([center,scale])
            normal[mode]=rows
        result['normal_stats']=normal
        result['normal_scale_rule']='per-context normal training median and maximum deviation x2; original scale is floor; no fault/test fit'
        result['thermal_limits']=thermal.tolist()
        result['normal_plateaus']=[sorted(v) for v in plateaus]
        result['normal_plateau_bounds']=[]
        for j,c in enumerate(channels):
            values=[v for group in samples.values() for v in group[c]] if plateaus[j] else []
            result['normal_plateau_bounds'].append([float(min(values)),float(max(values))] if values else None)
        vibration_window=int(min(16,max([5]+[int(longest[j])+2 for j,c in enumerate(channels) if 'vib' in c[1]])))
        result['flat_windows']=[vibration_window if 'vib' in c[1] else 16 for c in channels]
        result['normal_flat_rule']='RMS sensors pool the longest normal plateau across equipment, plus two frames, bounded 5..16; other channels retain 16'
    return result
