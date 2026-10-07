"""Local sensor/warning overlay; synthetic, not a calibrated physical model."""
from dataclasses import replace
from hashlib import sha256
from datetime import timedelta
from shiftlink.mes.engine import MesEngine
from shiftlink.mes.contracts import Alarm
from .signal_dynamics import SignalDynamics
from .fault_schedule import FaultSchedule


class RandomFactoryEngine(MesEngine):
    def __init__(self, run, config, run_nonce='demo', faults_enabled=True, hazard=.015):
        super().__init__(run, config)
        self.run_nonce = run_nonce
        self.faults_enabled = faults_enabled
        self.hazard = hazard
        self.reset_index = 0
        self._initialize_dynamics()

    def _initialize_dynamics(self):
        nonce = f'{self.run_nonce}:config:{self.config.config_id}:reset:{self.reset_index}'
        self.dynamics = SignalDynamics(self.config, self.run.seed, nonce)
        seed = sha256(f'{self.run.seed}:{nonce}:faults'.encode()).hexdigest()
        self.scheduler = FaultSchedule(self.config, seed, self.faults_enabled, self.hazard)
        self.truth = []
        self._previous_faults = {}
        self._manual_mode = False

    def tick(self, count=1):
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError('count must be a nonnegative integer')
        for _ in range(count):
            before = self.snapshot.sequence
            snapshot = super().tick()
            if snapshot.sequence == before:
                break
            if self._manual_mode:
                self._record_truth(snapshot.sequence, [], 'manual_scenario')
                continue
            measurements = self.dynamics.values(snapshot.sequence, snapshot.simulated_at, snapshot.measurements, snapshot.equipment)
            faults = self.scheduler.step(snapshot.sequence)
            targets = {(f['equipment_id'], signal): (target, f['intensity'])
                       for f in faults for signal, target in f['signal_targets'].items() if target is not None}
            result = []
            for m in measurements:
                target = targets.get((m.equipment_id, m.signal))
                if target is not None and m.quality == 'good':
                    value = m.value + target[1] * (target[0] - m.value)
                    if m.unit == 'bool': value = float(value >= .5)
                    if m.unit == 'pct': value = max(0, min(100, value))
                    m = replace(m, value=round(value, 6))
                result.append(m)
            indexed = {(m.equipment_id, m.signal): m for m in result}
            coupled = {}
            for (eq, signal), target in targets.items():
                if signal == 'hpu_flow':
                    coupled[(eq, 'hpu_cooler_oil_flow')] = indexed[(eq, signal)].value
                elif signal == 'hpu_oil_temp':
                    coupled[(eq, 'hpu_cooler_oil_in_temp')] = indexed[(eq, signal)].value
            result = [replace(m, value=coupled[(m.equipment_id, m.signal)]) if (m.equipment_id, m.signal) in coupled else m for m in result]
            active = {f['id']: f for f in faults}
            for ident, fault in active.items():
                if ident not in self._previous_faults:
                    self._event('performance_warning', fault['equipment_id'], 'synthetic equipment performance changed')
            for ident, fault in self._previous_faults.items():
                if ident not in active:
                    self._event('performance_restored', fault['equipment_id'], 'synthetic equipment performance restored')
            self._previous_faults = active
            affected = {f['equipment_id'] for f in faults if f['intensity'] > 0}
            alarms = tuple(Alarm(f['id'], 'AL-RANDOM-PERFORMANCE', f['equipment_id'], 'warning',
                                 self.run.started_at + timedelta(seconds=f['start'] * self.run.tick_seconds),
                                 label='Synthetic performance warning') for f in faults if f['intensity'] > 0)
            self._snapshot = replace(snapshot, measurements=tuple(result), active_alarms=alarms,
                equipment=tuple(replace(e, fault_level='warning') if e.equipment_id in affected else e for e in snapshot.equipment))
            self._symptom_frames[-1] = self._snapshot
            self._record_truth(snapshot.sequence, faults, 'random_factory')
        return self.snapshot

    def _record_truth(self, sequence, faults, mode):
        self.truth.append({'run_id': self.run.run_id, 'sequence': sequence, 'faults': faults,
            'profile': {'version': 'random-factory-v1', 'seed': self.run.seed,
                        'run_nonce': self.run_nonce, 'reset_index': self.reset_index,
                        'config_id': self.config.config_id, 'hazard': self.hazard,
                        'faults_enabled': self.faults_enabled, 'mode': mode}})

    def reset(self):
        run = super().reset()
        self.reset_index += 1
        self._initialize_dynamics()
        return run

    def set_scenario(self, *args, **kwargs):
        # Explicit legacy scenarios use the existing engine until the next reset.
        snapshot = super().set_scenario(*args, **kwargs)
        self._manual_mode = True
        self.scheduler.active.clear()
        self._previous_faults.clear()
        return snapshot
