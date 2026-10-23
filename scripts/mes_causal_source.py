"""Generator A: first-order load/pressure/flow/thermal state equations.

Qualitative assumptions, not a calibrated physical plant.
"""
from collections import deque
import math
import random

from scripts.mes_causal_schema import signals, units, MANUAL


class SourceDynamics:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.specs = signals()
        self.equipment = sorted({e for e, _ in self.specs})
        self.load, self.target = 0., 0.
        self.gain = self.rng.uniform(.7, 1.3)
        self.offset = {e: self.rng.uniform(-.15, .15) for e in self.equipment}
        self.state = {e: dict(pressure=0., flow=0., torque=0., heat=0., speed=0., vibration=0.) for e in self.equipment}
        self.supply = deque([0.] * 5, maxlen=5)
        self.stuck = {}

    def process_state(self):
        return {e: dict(v) for e, v in self.state.items()}

    def step(self, t, events):
        if t % 37 == 0:
            self.target = self.rng.uniform(-1, 1)
        self.load += .09 * (self.target - self.load)
        active = [v for v in events if v['start'] <= t < v['end']]
        for eq in self.equipment:
            causes = {kind: sum(v['amplitude'] for v in active if v['equipment'] == eq and v['kind'] == kind)
                      for kind in ('friction', 'leak', 'cooling_loss', 'blockage')}
            friction, leak, cool, block = (causes[k] for k in ('friction', 'leak', 'cooling_loss', 'blockage'))
            load = self.gain * self.load + self.offset[eq]
            upstream = self.supply[0] if eq in ('EQ-0006', 'EQ-0007', 'EQ-0008') else 0.
            targets = dict(pressure=.35 * load - 1.5 * leak + block + .45 * upstream,
                           flow=.5 * load - 1.3 * leak - 1.6 * block,
                           torque=.6 * load + 1.3 * friction + .25 * block,
                           heat=.4 * load + 1.1 * friction + 2.2 * cool,
                           speed=.5 * load - 1.1 * friction + .25 * upstream,
                           vibration=.2 * load + 1.5 * friction)
            for key, target in targets.items():
                rate = .025 if key == 'heat' else .22 if key == 'flow' else .4
                self.state[eq][key] += rate * (target - self.state[eq][key])
        self.supply.append(self.state['EQ-0001']['pressure'])
        output = {}
        for channel, spec in self.specs.items():
            eq, name = channel
            s = self.state[eq]
            if name in MANUAL:
                component = 0.
            elif 'temp' in name:
                component = s['heat']
            elif 'current' in name:
                component = s['torque']
            elif 'vib' in name:
                component = s['vibration']
            elif 'flow' in name:
                component = s['flow']
            elif 'pressure' in name or 'press' in name or name.endswith('_dp'):
                component = s['pressure']
            elif 'speed' in name or 'rpm' in name or 'queue' in name:
                component = -s['speed'] if 'queue' in name else s['speed']
            elif name == 'bus_voltage':
                component = -.2 * (self.gain * self.load + self.offset[eq])
            elif name == 'cv_belt_tension':
                component = .2 * s['torque']
            else:
                component = 0.  # No assumed process coupling for unmodeled measurements.
            center, band = units(spec)
            value = center + band * (.12 * component + self.rng.gauss(0, .018))
            if self.rng.random() < .002:
                value += band * self.rng.gauss(0, .8)
            if spec['unit'] == 'bool':
                value = float(component > 1.5)
            for event in active:
                if (event['equipment'], event.get('signal')) == channel:
                    if event['kind'] == 'sensor_bias':
                        value += event['amplitude'] * band * .17
                    elif event['kind'] == 'sensor_stuck':
                        value = self.stuck.setdefault((channel, event['start']), value)
            output[channel] = max(0., value) if spec['normal_min'] is not None and spec['normal_min'] >= 0 else value
        return output
