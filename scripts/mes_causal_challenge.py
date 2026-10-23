"""Generator B: second-order demand and nonlinear reservoir/motor balances.

Independent implementation of qualitative assumptions, not field validation.
"""
import math
from random import Random

from scripts.mes_causal_schema import signals, units, MANUAL


class ChallengeDynamics:
    def __init__(self, seed):
        self.random = Random(seed)
        self.specifications = signals()
        self.ids = sorted({key[0] for key in self.specifications})
        self.phase = self.random.uniform(0, 6)
        self.demand, self.velocity = 0., 0.
        self.shift = {e: self.random.uniform(-.22, .22) for e in self.ids}
        self.nodes = {e: [0.] * 6 for e in self.ids}
        self.delayed = [0.] * 8
        self.freeze = {}

    def process_state(self):
        return {e: list(v) for e, v in self.nodes.items()}

    def step(self, t, events):
        command = .7 * math.sin(t / 29 + self.phase) + (.45 if t % 103 > 60 else -.35)
        self.velocity = .72 * self.velocity + .06 * (command - self.demand)
        self.demand += self.velocity
        interventions = [e for e in events if e['start'] <= t < e['end']]
        for eq in self.ids:
            drag = loss = cooling = resistance = 0.
            for event in interventions:
                if event['equipment'] != eq:
                    continue
                amount = event['amplitude'] * (1 - math.exp(-(t - event['start'] + 1) / 5))
                if event['kind'] == 'friction': drag += amount
                if event['kind'] == 'leak': loss += amount
                if event['kind'] == 'cooling_loss': cooling += amount
                if event['kind'] == 'blockage': resistance += amount
            p, q, torque, heat, motion, shake = self.nodes[eq]
            demand = self.demand + self.shift[eq]
            parent = self.delayed[0] if eq in ('EQ-0006', 'EQ-0007', 'EQ-0008') else 0
            p += .24 * (.28 * demand - p - loss * (1 + .15 * abs(p)) + .8 * resistance + .55 * parent)
            q += .18 * (.4 * demand - q - .9 * loss - 1.3 * resistance * (1 + .1 * abs(q)))
            torque += .3 * (.7 * demand + drag * (1 + .2 * abs(motion)) - torque)
            heat += .018 * (.35 * torque + 2.6 * cooling - heat)
            motion += .27 * (.65 * demand - motion - .95 * drag + .3 * parent)
            shake += .35 * (.1 * demand + 1.7 * drag - shake)
            self.nodes[eq] = [p, q, torque, heat, motion, shake]
        self.delayed = self.delayed[1:] + [self.nodes['EQ-0001'][0]]
        readings = {}
        for key, definition in self.specifications.items():
            eq, name = key
            p, q, torque, heat, motion, shake = self.nodes[eq]
            terms = (0. if name in MANUAL else heat if 'temp' in name else torque if 'current' in name
                     else shake if 'vib' in name else q if 'flow' in name
                     else p if any(word in name for word in ('pressure', 'press', '_dp'))
                     else -motion if 'queue' in name else motion if ('speed' in name or 'rpm' in name)
                     else -.25 * (self.demand + self.shift[eq]) if name == 'bus_voltage'
                     else .25 * torque if name == 'cv_belt_tension' else 0.)
            # Heavy-tailed independent measurement noise, separate from process states.
            noise = self.random.gauss(0, 1) / math.sqrt(max(.2, self.random.gammavariate(3., 1.) / 3))
            middle, width = units(definition)
            reading = middle + width * (.13 * terms + .021 * noise)
            if self.random.random() < .0015:
                reading += width * self.random.gauss(0, .9)
            if definition['unit'] == 'bool':
                reading = float(terms > 1.8)
            for intervention in interventions:
                if (intervention['equipment'], intervention.get('signal')) != key:
                    continue
                if intervention['kind'] == 'sensor_bias':
                    reading += width * intervention['amplitude'] * .15
                elif intervention['kind'] == 'sensor_stuck':
                    reading = self.freeze.setdefault((key, intervention['start']), reading)
            readings[key] = max(0., reading) if definition['normal_min'] is not None and definition['normal_min'] >= 0 else reading
        return readings
