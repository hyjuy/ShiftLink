"""Opt-in display candidate; original detector, worker and previous evidence stay frozen.

Run with python -m scripts.mes_causal_active_advisory and the original worker CLI.
Use separate state/output paths. This module does not install or start a service.
"""
import hashlib
from pathlib import Path
from scripts import mes_causal_pda_service as worker
from scripts.mes_causal_lifecycle import LifecycleSource,LifecycleDetector
from shiftlink.pda.ai_insights import stopped_equipment_for_retention

class ActiveAdvisoryDetector(LifecycleDetector):
    def _restart(self):
        # Warm-up/reset may discard numeric history, never count as recovery.
        episode={k:getattr(self,'episode_'+k).copy() for k in ('on','process','flat')} if hasattr(self,'episode_on') else None
        super()._restart()
        if episode:
            for k,value in episode.items():setattr(self,'episode_'+k,value)

    def step(self,frame):
        prior={k:getattr(self,'episode_'+k).copy() for k in ('on','process','flat')}
        events=super().step(frame)
        if self.last_status['accepted'] and self.last_status['reset'] and not self.last_status['discontinuity']:
            for k,value in prior.items():setattr(self,'episode_'+k,value)
            self.episode_quiet[:]=0
            events-=set(eq for eq,on in zip(self.equipment,prior['on']) if on)
        return events

class ActiveAdvisorySource(LifecycleSource):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fingerprint=worker.digest(dict(base=self.fingerprint,display_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))

    def new_detector(self):
        detector=ActiveAdvisoryDetector(self.settings,self.normal_profile);detector.config_id=self.config_id;return detector

class ActiveAdvisorySession(worker.AdvisorySession):
    def sync_stop(self,state):
        super().sync_stop(state)
        if state['run_id']!=self.run or state['sequence'] not in (self.cursor,self.cursor+1):return
        for eq,row in self.notices.items():
            if eq in stopped_equipment_for_retention(state) and eq not in self.stopped_notices and row.get('state')=='active':
                held=dict(row,state='before_stop',stop_sequence=state['sequence'],stopped_at=state['simulated_at'])
                if worker.valid_stop_notice(held,state['sequence']):
                    self.stopped_notices[eq]=held;self.stop_dirty=True

    def feed(self,frame,config_id):
        stopped=dict(self.stopped_notices)
        deferred=self.defer_flush;self.defer_flush=True
        try:events=super().feed(frame,config_id)
        finally:self.defer_flush=deferred
        if not self.detector.last_status['accepted']:return events
        removed=False
        if frame['line_mode']=='running':
            running={e['equipment_id'] for e in frame['equipment'] if e.get('operating_state')=='running'}
            if not self.detector.last_status['discontinuity']:
                for eq,row in stopped.items():
                    if eq in running and self.detector.episode_on[self.detector.equipment.index(eq)]:
                        self.notices[eq]={k:v for k,v in row.items() if k not in ('stop_sequence','stopped_at')}
                        self.notices[eq]['state']='active'
            for eq in list(self.notices):
                if eq not in running:continue
                k=self.detector.equipment.index(eq)
                if not self.detector.episode_on[k]:
                    del self.notices[eq];removed=True
                elif self.detector.was_ready and not self.detector.last_status.get('hold'):
                    self.notices[eq].update(state='active',confirmed_sequence=self.cursor,confirmed_at=frame['simulated_at'])
        if not deferred and (events or removed or self.stop_dirty or self.since_save>=30):self.flush()
        return events

    def report(self,state,*,stalled=False):
        result=super().report(state,stalled=stalled)
        if result['status']!='ready':return result
        running={e['equipment_id'] for e in state['equipment'] if e.get('operating_state')=='running'}
        held=[row for row in result['items'] if row['state']=='before_stop']
        active=[dict(row) for eq,row in self.notices.items() if eq in running and row.get('state')=='active'
                and self.detector.episode_on[self.detector.equipment.index(eq)]]
        return result|dict(items=held+active)

def main():
    # Process-local selection also makes worker.poll's rollback use this session.
    worker.BoundSource=ActiveAdvisorySource;worker.AdvisorySession=ActiveAdvisorySession
    worker.main()

if __name__=='__main__':main()
