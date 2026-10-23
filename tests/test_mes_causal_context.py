"""Development guards for the separate operation-context candidate."""
import copy,json,math
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase,main
from tests.test_mes_causal_pda_service import rows,source_config
from tests.test_mes_causal_v14_stream import config,modify,channel_choices
from scripts.mes_causal_v14_stream import OnlineDetector
from scripts.mes_causal_context import ContextDetector,fit_profile,MODES


def profile():
    config_id=source_config()['config_id']
    offsets={c:{'hpu_cooler_oil_out_temp':-5.,'hpu_cooler_water_out_temp':6.} for c in [a+':'+b for a in ('slow','nominal','fast') for b in ('empty','moving','queued')]}
    return dict(schema_version=1,source_config_id=config_id,offsets=offsets,capacities={'EQ-0009':3,'EQ-0010':3},minimum_samples=64)


def source_rows(n=200):
    data=rows(n)
    for f in data:
        f.update(coils=[],speed=1.)
        indexed={m['signal']:m for m in f['measurements'] if m['equipment_id']=='EQ-0001'}
        for target,ref,delta in [('hpu_cooler_oil_out_temp','hpu_cooler_oil_in_temp',-5),('hpu_cooler_water_out_temp','hpu_cooler_water_in_temp',6)]:indexed[target]['value']=indexed[ref]['value']+delta
        for m in f['measurements']:
            if m['signal']=='cv_queue_len':m['value']=0.
    return data


def detector():
    d=ContextDetector(config(),profile());d.config_id=profile()['source_config_id'];return d


class ContextTests(TestCase):
    def test_normal_outlet_relationship_and_empty_queue_do_not_notify(self):
        d=detector();self.assertFalse(any(d.step(f) for f in source_rows()))
    def test_missing_unknown_context_has_exact_original_behavior(self):
        for mode in ('missing','invalid'):
            a=detector();b=OnlineDetector(config());b.config_id=a.config_id
            data=rows(150);modify(data,[channel_choices()[1]],90,140,6.)
            if mode=='invalid':
                for f in data:f.update(coils=[],speed=True)
            self.assertEqual([a.step(f) for f in data],[b.step(f) for f in data])
    def test_outlet_bias_raw_stuck_and_coherent_rise_are_not_hidden(self):
        for kind in ('bias','stuck','rise','water_rise'):
            data=source_rows(200)
            if kind=='bias':modify(data,[('EQ-0001','hpu_cooler_oil_out_temp')],100,180,8.)
            if kind=='stuck':
                for f in data[100:180]:
                    next(m for m in f['measurements'] if m['signal']=='hpu_cooler_oil_out_temp')['value']=41.
            if kind in ('rise','water_rise'):
                for i,f in enumerate(data[100:180]):
                    for m in f['measurements']:
                        if m['equipment_id']=='EQ-0001' and ('temp' in m['signal']) and (kind=='rise' or 'water' in m['signal']):m['value']+=min(i*.2,6.)
            d=detector();notices=[(f['sequence'],d.step(f)) for f in data]
            self.assertTrue(any(100<=t<180 and 'EQ-0001' in e for t,e in notices),kind)
    def test_queue_measurement_mismatch_and_physical_stall_detect(self):
        for kind in ('mismatch','stall'):
            d=detector();data=source_rows()
            for t,f in enumerate(data[100:180],100):
                f['coils']=[dict(coil_id='fixed' if kind=='stall' else str(t),equipment_id='EQ-0009',position=1.)]
                next(m for m in f['measurements'] if m['equipment_id']=='EQ-0009' and m['signal']=='cv_queue_len')['value']=100/3 if kind=='stall' else 0.
            events=[(f['sequence'],d.step(f)) for f in data]
            self.assertTrue(any(100<=t<180 and 'EQ-0009' in e for t,e in events),kind)
    def test_busy_healthy_queue_and_mode_transitions_do_not_notify(self):
        d=detector();data=source_rows()
        for i,f in enumerate(data):
            f['speed']=(.5,1.,1.5)[(i//40)%3]
            if i%40>=20:
                f['coils']=[dict(coil_id=str(i//4),equipment_id='EQ-0009',position=1.)]
                next(m for m in f['measurements'] if m['equipment_id']=='EQ-0009' and m['signal']=='cv_queue_len')['value']=100/3
        self.assertFalse(any(d.step(f) for f in data))
    def test_context_state_restores_and_duplicate_frame_does_not_advance(self):
        d=detector();data=source_rows(100)
        for f in data:d.step(f)
        state=d.context_state();d.step(data[-1]);self.assertEqual(state,d.context_state())
        other=detector();other.load_context(state);self.assertEqual(other.context_state(),state)
        with self.assertRaises(ValueError):other.load_context({'ages':{'EQ-0009':True},'previous':{}})
    def test_bad_reference_or_out_of_range_value_is_not_normalized_away(self):
        d=detector();data=source_rows()
        for f in data[100:180]:
            for m in f['measurements']:
                if m['signal']=='hpu_cooler_oil_in_temp':m['quality']='bad'
                if m['signal']=='hpu_cooler_oil_out_temp':m['value']=90.
        self.assertTrue(any('EQ-0001' in d.step(f) for f in data))

    def test_full_capacity_queue_is_not_an_out_of_range_fault(self):
        p=profile();p['capacities']={'EQ-0009':1,'EQ-0010':1};d=ContextDetector(config(),p);d.config_id=p['source_config_id'];data=source_rows()
        for i,f in enumerate(data):
            f['coils']=[dict(coil_id=str(i//4),equipment_id='EQ-0009',position=1.)]
            next(m for m in f['measurements'] if m['equipment_id']=='EQ-0009' and m['signal']=='cv_queue_len')['value']=100.
        self.assertFalse(any(d.step(f) for f in data))

    def test_normal_statistics_fit_is_frozen_and_fault_does_not_change_it(self):
        source=source_config()
        for e in source['equipment']:
            e['code']='CV' if e['equipment_id'] in ('EQ-0009','EQ-0010') else 'other';e['coil_capacity']=3
        data=[]
        for mode in MODES:
            speed,load=mode.split(':');batch=source_rows(64)
            for i,f in enumerate(batch):
                f['run_id']=mode;f['speed']={'slow':.5,'nominal':1.,'fast':1.5}[speed]
                f['coils']=[] if load=='empty' else [dict(coil_id=str(i),equipment_id='EQ-0006' if load=='moving' else 'EQ-0009',position=.5 if load=='moving' else 1.)]
            data.extend(batch)
        fitted=fit_profile(iter(data),source,config());before=copy.deepcopy(fitted)
        d=ContextDetector(config(),fitted);d.config_id=fitted['source_config_id'];test=source_rows(150)
        modify(test,[('EQ-0006','rt_vib_rms')],100,140,8.)
        self.assertTrue(any('EQ-0006' in d.step(f) for f in test));self.assertEqual(fitted,before)
        bad=copy.deepcopy(fitted);bad['normal_stats']['nominal:empty'][0][1]=0
        with self.assertRaises(ValueError):ContextDetector(config(),bad)
if __name__=='__main__':main()
