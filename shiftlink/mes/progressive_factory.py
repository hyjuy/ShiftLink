"""Opt-in progressive synthetic episodes; never installs or enables a service."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from random import Random
from math import isfinite
from .random_factory import RandomFactoryEngine

# Generator mechanisms are explicit; do not import the detector's PATTERNS.
# These are qualitative demonstrations, not calibrated equipment physics.
MECHANISMS = {
    'hydraulic_leak': {'hpu_pressure': -1, 'hpu_flow': -1, 'hpu_oil_temp': 1},
    'cooling_loss': {'hpu_oil_temp': 1},
    'pneumatic_leak': {'air_pressure': -1},
    'drive_friction': {'gr_vib_rms': 1, 'gr_brg_temp': 1, 'gr_current': 1},
}

class ProgressiveFaultSchedule:
    def __init__(self, config, seed):
        self.rng=Random(f'progressive-v1:{seed}')
        self.specs={(eq.equipment_id,s.signal):s for eq in config.equipment for s in eq.signals}
        self.options=[(eq.equipment_id,kind) for eq in sorted(config.equipment,key=lambda x:x.equipment_id) if eq.active
                      for kind,signals in MECHANISMS.items() if all((eq.equipment_id,k) in self.specs
                      and self.specs[eq.equipment_id,k].normal_min is not None
                      and self.specs[eq.equipment_id,k].normal_max is not None
                      and self.specs[eq.equipment_id,k].normal_min < self.specs[eq.equipment_id,k].normal_max
                      and self.specs[eq.equipment_id,k].semantics.get('acquisition') not in ('event','manual_sample')
                      for k in signals)]
        self.clock=0;self.counter=0;self.active=None
        self.next_fault=self.rng.randint(180,420)
        self.last_sequence=None;self.last_output=None

    def make_fault(self, equipment_id, kind, sequence):
        targets={}
        for signal,direction in MECHANISMS[kind].items():
            spec=self.specs[equipment_id,signal];span=spec.normal_max-spec.normal_min
            target=spec.normal_max+span*.75 if direction>0 else max(0,spec.normal_min-span*.75)
            targets[signal]=min(100,target) if spec.unit=='pct' else target
        self.counter+=1
        return dict(id=f'progressive-{self.counter:06d}',equipment_id=equipment_id,kind=kind,
                    start=sequence,end=None,age=0,intensity=0.,signal_targets=targets)

    def step(self, sequence, equipment):
        if type(sequence) is not int or sequence<0:raise ValueError('sequence must be a nonnegative integer')
        if self.last_sequence==sequence:return deepcopy(self.last_output)
        if self.last_sequence is not None and sequence!=self.last_sequence+1:
            raise ValueError('sequence must advance by one')
        self.last_sequence=sequence
        running={e.equipment_id for e in equipment if e.operating_state=='running'}
        if running:self.clock+=1
        if self.active is None and self.clock>=self.next_fault:
            available=[(eq,kind) for eq,kind in self.options if eq in running]
            if available:
                eq,kind=self.rng.choice(available);self.active=self.make_fault(eq,kind,sequence)
        if self.active is not None and self.active['equipment_id'] in running:
            self.active['age']+=1
            self.active['intensity']=min(1.,self.active['age']/120)
        self.last_output=deepcopy(self.active)
        return deepcopy(self.active)

    def repair(self, equipment_id):
        if self.active is None or self.active['equipment_id']!=equipment_id:
            raise ValueError('해당 설비에 진행 중인 모의 고장이 없습니다.')
        self.active=None;self.last_output=None
        self.next_fault=self.clock+self.rng.randint(180,420)

class ProgressiveFactoryEngine(RandomFactoryEngine):
    def __init__(self, run, config, run_nonce='demo', *, enabled=True):
        # Keep the original random factory and its expiry/alarms untouched.
        super().__init__(run,config,run_nonce=run_nonce,faults_enabled=False,hazard=0)
        self.progressive_enabled = enabled
        self._manual_mode = not enabled

    def _initialize_dynamics(self):
        super()._initialize_dynamics()
        self._progressive_recovery = None
        self._recovery_signals = set()
        self._normal_scheduler=self.scheduler
        self.scheduler=ProgressiveFaultSchedule(self.config,sha256(f'{self.run.seed}:{self.run_nonce}:{self.config.config_id}:{self.reset_index}'.encode()).hexdigest())

    @property
    def snapshot(self):
        snapshot = super().snapshot
        return replace(snapshot, recovery=self._progressive_recovery or snapshot.recovery,
                       simulation_mode='progressive' if getattr(self, 'progressive_enabled', False) else 'standard')

    def set_progressive(self, enabled):
        if type(enabled) is not bool:
            raise ValueError('enabled must be a boolean')
        if enabled == self.progressive_enabled:
            return self.snapshot
        if self.scheduler.active is not None or (self._progressive_recovery and self._progressive_recovery['stage'] != 'completed'):
            raise ValueError('진행 중인 모의 고장의 수리·정상 회복 확인을 먼저 완료하세요.')
        if self._scenario != 'normal' or self._recovery_ticks:
            raise ValueError('현재 시나리오의 복구를 완료한 뒤 랜덤 모드를 켜세요.')
        self._initialize_dynamics()
        self.progressive_enabled = enabled
        self._manual_mode = not enabled
        self._queue_event('simulation_mode_changed', None, 'progressive' if enabled else 'standard')
        if enabled:
            self.start()
        return self.snapshot

    def _observed_signals(self, snapshot, equipment_id=None):
        specs = self.dynamics.specs
        running = {e.equipment_id for e in snapshot.equipment if e.operating_state == 'running'}
        for m in snapshot.measurements:
            spec = specs.get((m.equipment_id, m.signal))
            if (spec is None or m.equipment_id not in running or (equipment_id and m.equipment_id != equipment_id)
                    or spec.semantics.get('acquisition') in ('event', 'manual_sample')
                    or spec.normal_min is None or spec.normal_max is None):
                continue
            valid = m.quality == 'good' and m.unit == spec.unit and isfinite(m.value) and m.observed_at == snapshot.simulated_at
            yield m, valid, valid and spec.normal_min <= m.value <= spec.normal_max

    def _observe_recovery(self, snapshot):
        plan = self._progressive_recovery
        if plan and plan['stage'] != 'completed':
            if plan['stage'] == 'stabilizing':
                readings = list(self._observed_signals(snapshot, plan['equipment_id']))
                normal = {m.signal for m, valid, ok in readings if ok}
                healthy = self._recovery_signals <= normal and all(valid and ok for m, valid, ok in readings)
                plan['remaining_ticks'] = max(0, plan['remaining_ticks'] - 1) if healthy else 3
                if plan['remaining_ticks'] == 0:
                    plan['stage'] = 'completed'
                    self._event('recovered', plan['equipment_id'], '모의 수리 후 유효 센서의 정상 회복을 3회 연속 확인')
            return
        abnormal = [(m.equipment_id, m.signal) for m, valid, ok in self._observed_signals(snapshot) if valid and not ok]
        if not abnormal:
            return
        equipment_id = abnormal[0][0]
        self._recovery_signals = {signal for eq, signal in abnormal if eq == equipment_id}
        self._progressive_recovery = self.recovery_plan(equipment_id)

    def recovery_plan(self, equipment_id):
        # A user-selected repair procedure is available before a range crossing;
        # it contains no scheduler target, mechanism or fault timing.
        plan = self._progressive_recovery
        if plan and plan['equipment_id'] == equipment_id and plan['stage'] != 'completed':
            return deepcopy(plan)
        return dict(title='관측 이상 · 모의 수리 및 회복 확인', equipment_id=equipment_id,
            stage='actions', remaining_ticks=0, product_hold=False, required=True,
            actions=[dict(action_id='verify', title='모의 수리 완료 기록',
                detail='주입된 모의 고장을 수리 처리합니다. 정상 회복은 재가동 후 센서로 별도 확인합니다.', completed=False)])

    def prepare_recovery(self, equipment_id):
        fault = self.scheduler.active
        if fault is None or fault['equipment_id'] != equipment_id:
            raise ValueError('선택한 설비에 수리 처리할 모의 고장이 없습니다. 다른 설비의 고장은 해제하지 않습니다.')
        plan = self._progressive_recovery
        if plan and plan['stage'] in ('ready', 'stabilizing'):
            raise ValueError('진행 중인 정상 회복 확인을 먼저 완료하세요.')
        self._progressive_recovery = self.recovery_plan(equipment_id)
        self._recovery_signals = {m.signal for m, valid, ok in self._observed_signals(self.snapshot, equipment_id)}

    def perform_action(self, action_id):
        plan = self._progressive_recovery
        if not self._manual_mode and plan:
            if action_id != 'verify' or plan['stage'] not in ('actions', 'ready'):
                raise ValueError('화면에 표시된 모의 수리 단계부터 완료하세요.')
            if plan['stage'] == 'ready':
                return self.snapshot
            fault = self.scheduler.active
            if fault and fault['equipment_id'] != plan['equipment_id']:
                raise ValueError('다른 설비의 고장은 이 조치로 해제할 수 없습니다.')
            self.pause()
            if fault:
                self.repair_fault(plan['equipment_id'])
            plan['actions'][0]['completed'] = True
            plan['stage'] = 'ready'
            self._queue_event('recovery_action_completed', plan['equipment_id'], '모의 수리 완료 기록')
            return self.snapshot
        return super().perform_action(action_id)

    def recover(self):
        plan = self._progressive_recovery
        if not self._manual_mode and plan:
            if plan['stage'] == 'actions':
                raise ValueError('모의 수리 완료를 먼저 기록하세요.')
            if plan['stage'] == 'ready':
                plan.update(stage='stabilizing', remaining_ticks=3)
                self._queue_event('recovery_started', plan['equipment_id'], '모의 수리 후 정상 회복 관찰 시작')
                self.start()
            return self.snapshot
        return super().recover()

    def reset(self):
        run = super().reset()
        self.progressive_enabled = False
        self._manual_mode = True
        return run

    def _overlay(self, measurements, fault, equipment):
        if fault is None:return tuple(measurements)
        eq=fault['equipment_id']
        if not any(e.equipment_id==eq and e.operating_state=='running' for e in equipment):return tuple(measurements)
        values={}
        for m in measurements:
            if m.equipment_id==eq and m.signal in fault['signal_targets'] and m.quality=='good':
                value=m.value+fault['intensity']*(fault['signal_targets'][m.signal]-m.value)
                values[m.signal]=round(value,6)
        # Preserve the existing HPU oil circuit's measured relationships.
        rows={m.signal:m for m in measurements if m.equipment_id==eq}
        for source,dest in [('hpu_flow','hpu_cooler_oil_flow'),('hpu_oil_temp','hpu_cooler_oil_in_temp')]:
            if source in values and dest in rows and rows[dest].quality=='good':values[dest]=values[source]
        if 'hpu_oil_temp' in values and 'hpu_cooler_oil_out_temp' in rows and rows['hpu_cooler_oil_out_temp'].quality=='good':
            drop=5-4*fault['intensity'] if fault['kind']=='cooling_loss' else 5
            values['hpu_cooler_oil_out_temp']=round(values['hpu_oil_temp']-drop,6)
        return tuple(replace(m,value=values[m.signal]) if m.equipment_id==eq and m.signal in values else m for m in measurements)

    def tick(self, count=1):
        if type(count) is not int or count<0:raise ValueError('count must be a nonnegative integer')
        for _ in range(count):
            before=self.snapshot.sequence;scheduler=self.scheduler;self.scheduler=self._normal_scheduler
            try:snapshot=super().tick()
            finally:self.scheduler=scheduler
            if snapshot.sequence==before:break
            if self._manual_mode:continue
            fault=self.scheduler.step(snapshot.sequence,snapshot.equipment)
            self._snapshot=replace(snapshot,measurements=self._overlay(snapshot.measurements,fault,snapshot.equipment))
            self._observe_recovery(self._snapshot)
            self._symptom_frames[-1]=self._snapshot
            self.truth[-1]['faults']=[] if fault is None else [deepcopy(fault)]
            self.truth[-1]['profile'].update(version='progressive-factory-v1',mode='progressive',faults_enabled=True,interval_ticks=[180,420],attack_ticks=120,max_active=1)
        return self.snapshot

    def repair_fault(self, equipment_id):
        if self.snapshot.line_mode not in ('paused','stopped'):
            raise ValueError('모의 운전을 일시정지한 뒤 수리 완료를 기록하세요.')
        self.scheduler.repair(equipment_id)
        self._queue_event('synthetic_repair_recorded',equipment_id,'모의 수리 완료; 재가동 후 센서 회복 확인 필요')
        return self.snapshot

    def set_scenario(self, *args, **kwargs):
        if self.scheduler.active is not None:raise ValueError('모의 고장 수리 후 전환하거나 새 실행을 시작하세요.')
        if self._progressive_recovery and self._progressive_recovery['stage'] != 'completed':
            raise ValueError('모의 수리 후 정상 회복 확인을 먼저 완료하세요.')
        scheduler=self.scheduler;self.scheduler=self._normal_scheduler
        try:
            snapshot = super().set_scenario(*args,**kwargs)
            self.progressive_enabled = False
            self._progressive_recovery = None
            return self.snapshot
        finally:self.scheduler=scheduler