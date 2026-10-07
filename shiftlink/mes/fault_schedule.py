"""Replayable synthetic running-equipment anomalies; no hardware control."""
from copy import deepcopy
from math import isfinite
from random import Random
from shiftlink.mes.symptoms import PATTERNS


class FaultSchedule:
    def __init__(self,config,seed,enabled=True,hazard=.015,max_active=3):
        if isinstance(hazard, bool) or not isinstance(hazard, (int, float)) or not isfinite(hazard) or not 0 <= hazard <= 1:
            raise ValueError('hazard must be finite and within 0..1')
        if not isinstance(max_active,int) or isinstance(max_active,bool) or not 1 <= max_active <= 3:
            raise ValueError('max_active must be an integer within 1..3')
        self.rng=Random(f'fault-schedule:{seed}')
        self.enabled=enabled; self.hazard=hazard; self.max_active=max_active
        self.options={}; self.active=[]; self.cooldown={}; self.last_sequence=None; self.last_output=[]; self.counter=0
        for eq in sorted(config.equipment,key=lambda item:item.equipment_id):
            if not eq.active or not eq.capabilities: continue
            specs={s.signal:s for s in eq.signals}
            eligible=[]
            for pattern in PATTERNS:
                if pattern.pattern_id in {'pdp_trip','rt_lift'}: continue
                if eq.code.split('-')[0]!=pattern.family or not pattern.states.keys()<=specs.keys(): continue
                if any(specs[k].normal_min is None or specs[k].normal_max is None or specs[k].semantics.get('acquisition') in ('event', 'manual_sample') for k in pattern.states): continue
                if any(state=='low' and specs[k].normal_min<=0 or state=='high' and specs[k].unit=='pct' and specs[k].normal_max>=100 for k,state in pattern.states.items()): continue
                eligible.append((pattern,specs))
            if eligible: self.options[eq.equipment_id]=eligible

    def _new(self,equipment_id,sequence):
        pattern,specs=self.rng.choice(self.options[equipment_id])
        severity=self.rng.uniform(.35,1)
        targets={}; units={}; states={}
        for signal,state in pattern.states.items():
            spec=specs[signal]; units[signal]=spec.unit; states[signal]=state
            if state=='normal': targets[signal]=None; continue
            span=max(spec.normal_max-spec.normal_min,abs(spec.normal_max)*.1,.001)
            if spec.unit=='bool': target=1 if state=='high' else 0
            elif state=='zero': target=0
            elif state=='low': target=max(0,spec.normal_min-span*severity*self.rng.uniform(.3,.9))
            else: target=spec.normal_max+span*severity*self.rng.uniform(.3,.9)
            if spec.unit=='pct': target=max(0,min(100,target))
            if not isfinite(target): raise ValueError('nonfinite configured target')
            targets[signal]=target
        self.counter+=1
        return dict(id=f'fault-{self.counter:06d}',equipment_id=equipment_id,pattern_id=pattern.pattern_id,kind='equipment',start=sequence,end=sequence+self.rng.randint(10,30),mode=self.rng.choice(('abrupt','ramp','intermittent')),severity=severity,signal_targets=targets,signal_units=units,signal_states=states,pulse_period=self.rng.randint(3,7),pulse_duty=self.rng.uniform(.4,.8))

    def step(self,sequence):
        if not isinstance(sequence,int) or isinstance(sequence,bool) or sequence<0:
            raise ValueError('sequence must be a nonnegative integer')
        if self.last_sequence==sequence: return deepcopy(self.last_output)
        if self.last_sequence is not None and sequence!=self.last_sequence+1:
            raise ValueError('sequence must advance by one; skipped/backward ticks are not allowed')
        self.last_sequence=sequence
        for fault in self.active:
            if sequence>=fault['end']: self.cooldown[fault['equipment_id']]=sequence+self.rng.randint(8,25)
        self.active=[f for f in self.active if sequence<f['end']]
        if self.enabled:
            occupied={f['equipment_id'] for f in self.active}
            eligible=[eq for eq in self.options if eq not in occupied and sequence>=self.cooldown.get(eq,0)]
            self.rng.shuffle(eligible)
            for eq in eligible:
                if len(self.active)>=self.max_active: break
                if self.rng.random()<self.hazard: self.active.append(self._new(eq,sequence))
        output=[]
        for fault in self.active:
            age=sequence-fault['start']; duration=fault['end']-fault['start']
            attack=min(1,(age+1)/max(3,duration//3)) if fault['mode']=='ramp' else 1
            release=min(1,(fault['end']-sequence)/4)
            pulse=1 if fault['mode']!='intermittent' or age%fault['pulse_period']<fault['pulse_period']*fault['pulse_duty'] else 0
            output.append(dict(fault,intensity=round(attack*release*pulse,6)))
        self.last_output=deepcopy(output)
        return output
