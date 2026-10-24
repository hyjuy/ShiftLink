"""Separate fault-lifecycle candidate; frozen scores and previous episode code stay intact."""
import hashlib
from pathlib import Path
import numpy as np
from scripts.mes_causal_context import ContextDetector
from scripts.mes_causal_pda_service import BoundSource,digest

RECOVERY_FRAMES=32

class LifecycleDetector(ContextDetector):
    def _restart(self):
        super()._restart()
        k=len(self.equipment);n=len(self.channels)+k
        self.episode_on=np.zeros(k,bool);self.episode_quiet=np.zeros(k,int)
        self.episode_process=np.zeros((k,n),bool);self.episode_flat=self.episode_process.copy()
        self.episode_evidence=None

    def _scores(self,raw,reset,hold,ready):
        result=super()._scores(raw,reset,hold,ready)
        level,flat,flat_known,rise=result
        self.episode_evidence=(np.r_[level,rise],np.r_[flat,np.zeros(len(rise),bool)],
                               np.r_[flat_known,np.isfinite(rise)])
        return result

    def _merge(self,events,level,flat,flat_known):
        process=np.isfinite(level)&(level>self.aug_limits)
        healthy=np.isfinite(level)&(level<=self.aug_limits*(2/3))
        emitted=set()
        for k,(eq,ix) in enumerate(zip(self.equipment,self.aug_indexes)):
            if self.episode_on[k]:
                # A brief symptom-free interval is not evidence that the underlying fault was repaired.
                observed=(healthy[self.episode_process[k]].all() and flat_known[self.episode_flat[k]].all()
                          and not flat[self.episode_flat[k]].any())
                self.episode_quiet[k]=min(RECOVERY_FRAMES,self.episode_quiet[k]+1) if observed else 0
                novel=(process[ix]&~self.episode_process[k,ix]).any() or (flat[ix]&~self.episode_flat[k,ix]).any()
                distinct=eq in events and self.episode_quiet[k]>=5 and novel
                clear=self.episode_quiet[k]==RECOVERY_FRAMES and not process[ix].any() and not flat[ix].any()
                if distinct or clear:
                    self.episode_on[k]=False;self.episode_quiet[k]=0
                    self.episode_process[k]=self.episode_flat[k]=False
                elif self.episode_quiet[k]==0:
                    self.episode_process[k,ix]|=process[ix];self.episode_flat[k,ix]|=flat[ix]
            if eq in events and not self.episode_on[k]:
                emitted.add(eq);self.episode_on[k]=True
                self.episode_process[k,ix]|=process[ix];self.episode_flat[k,ix]|=flat[ix]
        return emitted

    def step(self,frame):
        events=super().step(frame)
        if not self.last_status['accepted']:return events
        if self.last_status['reset']:
            self.episode_on[:]=False;self.episode_quiet[:]=0
            self.episode_process[:]=self.episode_flat[:]=False
        if not self.last_status['ready']:return set()
        if self.last_status['hold']:
            self.episode_quiet[:]=0;return set()
        return self._merge(events,*self.episode_evidence)

    def context_state(self):
        return super().context_state()|dict(episode=dict(on=self.episode_on.tolist(),quiet=self.episode_quiet.tolist(),
            process=self.episode_process.tolist(),flat=self.episode_flat.tolist()))

    def load_context(self,state):
        if not isinstance(state,dict) or set(state)!={'ages','previous','episode'}:raise ValueError('episode context keys')
        episode=state['episode']
        if not isinstance(episode,dict) or set(episode)!={'on','quiet','process','flat'}:raise ValueError('episode state keys')
        shapes=dict(on=self.episode_on.shape,quiet=self.episode_quiet.shape,process=self.episode_process.shape,flat=self.episode_flat.shape)
        values={}
        for key,shape in shapes.items():
            value=np.asarray(episode[key],dtype=object)
            if value.shape!=shape:raise ValueError('episode state shape')
            kind=int if key=='quiet' else bool
            if any(type(x) is not kind for x in value.flat):raise ValueError('episode state type')
            if key=='quiet' and any(not 0<=x<RECOVERY_FRAMES for x in value.flat):raise ValueError('episode recovery count')
            values[key]=value.astype(kind)
        for k,ix in enumerate(self.aug_indexes):
            outside=np.ones(self.episode_process.shape[1],bool);outside[ix]=False
            if values['process'][k,outside].any() or values['flat'][k,outside].any():raise ValueError('episode source equipment')
            if not values['on'][k] and (values['quiet'][k] or values['process'][k].any() or values['flat'][k].any()):raise ValueError('inactive episode evidence')
        super().load_context(dict(ages=state['ages'],previous=state['previous']))
        self.episode_on=values['on'];self.episode_quiet=values['quiet']
        self.episode_process=values['process'];self.episode_flat=values['flat']

class LifecycleSource(BoundSource):
    def __init__(self,settings,source_config,normal_profile=None):
        if normal_profile is None:raise ValueError('episode candidate needs fixed normal profile')
        super().__init__(settings,source_config,normal_profile)
        self.fingerprint=digest(dict(base=self.fingerprint,lifecycle_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),recovery_frames=RECOVERY_FRAMES))

    def new_detector(self):
        detector=LifecycleDetector(self.settings,self.normal_profile);detector.config_id=self.config_id;return detector
