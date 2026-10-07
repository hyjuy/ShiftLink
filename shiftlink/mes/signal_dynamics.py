"""Qualitative, uncalibrated normal dynamics for the local synthetic factory.

Latent load, ambient conditions, correlated channels and thermal inertia make
observations less trivial. No scenario, fault, alarm or label fields are read.
"""
import math
from dataclasses import replace
from datetime import timedelta
from random import Random


class SignalDynamics:
    def __init__(self, config, seed, run_nonce):
        self.config = config
        self.rng = Random(f'{seed}:{run_nonce}:normal-dynamics-v1')
        self.specs = {(e.equipment_id,s.signal):s for e in config.equipment for s in e.signals}
        self.eq_ids = [e.equipment_id for e in config.equipment if e.active]
        self.load = self.rng.uniform(.25,.75)
        self.target = self.rng.uniform(.15,.85)
        self.ambient = self.rng.uniform(.3,.7)
        self.next_target = 0
        self.local = {e:self.rng.uniform(.2,.8) for e in self.eq_ids}
        self.heat = {e:self.rng.uniform(.4,.6) for e in self.eq_ids}
        self.noise = {}
        self.samples = {}
        self.sequence = 0
        self.cached = None

    def _advance(self, sequence):
        for tick in range(self.sequence + 1,sequence + 1):
            if tick >= self.next_target:
                self.target = self.rng.uniform(.15,.85)
                self.next_target = tick + self.rng.randint(18,40)
            self.load += .12 * (self.target - self.load)
            self.ambient = min(.85,max(.15,self.ambient+self.rng.gauss(0,.001)))
            for eq in self.eq_ids:
                self.local[eq] = min(.9,max(.1,self.local[eq]+self.rng.gauss(0,.006)))
                load = .8*self.load+.2*self.local[eq]
                heat_target = .35+.3*load+.12*(self.ambient-.5)
                self.heat[eq] += .025*(heat_target-self.heat[eq])

    def values(self, sequence, at, measurements, equipment_states=None):
        """Return new Measurement instances; sequence uses one-second MES ticks.

        Re-reading the same sequence is idempotent. A new run needs a new object
        and unique run_nonce, including when the numeric seed stays unchanged.
        """
        if not isinstance(sequence,int) or isinstance(sequence,bool) or sequence < 1 or sequence < self.sequence:
            raise ValueError('sequence must be positive and monotonic')
        if at.tzinfo is None: raise ValueError('observation time must have timezone')
        if sequence == self.sequence and self.cached is not None: return list(self.cached)
        self._advance(sequence)
        loads = {eq:.8*self.load+.2*self.local[eq] for eq in self.eq_ids}
        states = {s.equipment_id:s.operating_state for s in (equipment_states or [])}
        values = {}
        for m in measurements:
            key=(m.equipment_id,m.signal); spec=self.specs[key]
            if m.quality != 'good' or spec.semantics.get('acquisition')=='event' or m.signal=='cv_queue_len':
                values[key]=m.value
                continue
            if spec.normal_min is None or spec.normal_max is None or not math.isfinite(spec.normal_min) or not math.isfinite(spec.normal_max):
                # Optional channels without a modeled range retain native values.
                values[key]=m.value
                continue
            if spec.zero_when_stopped and (m.value==0 or states.get(m.equipment_id) in ('stopped','waiting','fault')):
                values[key]=0.
                continue
            if spec.unit=='bool':
                values[key]=0.
                continue
            load=loads[m.equipment_id]
            noise=.8*self.noise.get(key,0)+self.rng.gauss(0,.002)
            self.noise[key]=noise
            fraction=.5+.55*(load-.5)+noise
            if 'temp' in m.signal:
                fraction=self.heat[m.equipment_id]+noise*.1
            elif m.signal in ('bus_voltage','hpu_pressure','hpu_pump_outlet_pressure','hpu_accumulator_gas_pressure','hpu_accumulator_fluid_pressure','air_pressure','air_nozzle_pressure'):
                fraction=.5-.25*(load-.5)+noise
            elif m.signal in ('gr_rpm','rt_speed','cv_speed'):
                fraction=.5+.4*(load-.5)+noise
            elif m.signal in ('fluid_viscosity','gr_oil_water_content','hpu_return_submergence','hpu_suction_head'):
                fraction=.5+.2*(self.local[m.equipment_id]-.5)+noise
            elif m.signal in ('gr_oil_level','hpu_oil_level'):
                fraction=.65+.08*(self.local[m.equipment_id]-.5)+noise
            low,high=spec.normal_min,spec.normal_max
            if low is None or high is None or not math.isfinite(m.value):
                raise ValueError(f'finite value and normal bounds required: {key}')
            value=low+(high-low)*fraction
            values[key]=min(high,max(low,value))
        # Preserve qualitative topology instead of assigning independent noise.
        for eq in self.eq_ids:
            def has(name): return (eq,name) in values
            def set_value(name,value):
                if not has(name): return
                spec=self.specs[(eq,name)]
                if spec.normal_min is None or spec.normal_max is None: return
                if spec.zero_when_stopped and values[(eq,name)]==0: return
                values[(eq,name)]=min(spec.normal_max,max(spec.normal_min,value))
            if has('hpu_oil_temp'):
                oil=values[(eq,'hpu_oil_temp')]
                set_value('hpu_cooler_oil_in_temp',oil)
                set_value('hpu_cooler_oil_out_temp',oil-5)
                if has('hpu_flow'):
                    set_value('hpu_cooler_oil_flow',values[(eq,'hpu_flow')])
                if has('hpu_cooler_water_in_temp'):
                    water=values[(eq,'hpu_cooler_water_in_temp')]
                    set_value('hpu_cooler_water_out_temp',water+5+2*loads[eq])
                if has('hpu_pressure'):
                    for name in ('hpu_pump_outlet_pressure','hpu_accumulator_gas_pressure','hpu_accumulator_fluid_pressure'):
                        set_value(name,values[(eq,'hpu_pressure')])
        output=[]
        for m in measurements:
            key=(m.equipment_id,m.signal); spec=self.specs[key]
            if m.quality!='good' or spec.semantics.get('acquisition')=='event':
                output.append(m)
                continue
            if spec.normal_min is None or spec.normal_max is None:
                output.append(m)
                continue
            value=round(values[key],3)
            if spec.unit=='pct': value=min(100.,max(0.,value))
            value=max(0.,value)
            observed_at=at
            if spec.semantics.get('acquisition')=='manual_sample':
                bucket=sequence//60
                cached=self.samples.get(key)
                if cached is None or cached[0]!=bucket:
                    self.samples[key]=(bucket,value,at-timedelta(seconds=sequence%60))
                _,value,observed_at=self.samples[key]
            output.append(replace(m,value=value,observed_at=observed_at))
        self.sequence=sequence
        self.cached=tuple(output)
        return output
