import unittest
import numpy as np
from pathlib import Path
import tempfile
from unittest.mock import patch

from scripts import mes_causal_v10 as v


class V10Tests(unittest.TestCase):
    def test_global_repeat_is_quality_issue_not_single_sensor_plateau(self):
        x=np.column_stack([np.arange(30.)+j for j in range(8)])
        x[8:21]=x[7]
        resets=np.zeros(30,bool);resets[0]=True
        flags=v.acquisition_repeats(x,np.ones(8,bool),resets)
        self.assertEqual(np.flatnonzero(flags).tolist(),list(range(8,21)))
        x=np.column_stack([np.arange(30.)+j for j in range(8)])
        x[8:21,0]=x[7,0]
        self.assertFalse(v.acquisition_repeats(x,np.ones(8,bool),resets).any())

    def test_spike_then_global_hold_cannot_be_process_alarm(self):
        x=np.zeros((60,8));x+=np.sin(np.arange(60.))[:,None]*.05
        x[15,0]=30;x[16:29]=x[15]
        reset=np.zeros(60,bool);reset[0]=True
        hold=v.acquisition_repeats(x,np.ones(8,bool),reset)
        filtered=v.robust_levels(x,5,reset,hold)
        self.assertLess(np.nanmax(np.abs(filtered)),.1)
        self.assertTrue(np.isnan(filtered[16:29]).all())

    def test_sustained_negative_shift_is_detectable_after_single_impulse(self):
        x=np.zeros((70,2));x[10,1]=100;x[30:,0]=-3
        reset=np.zeros(70,bool);reset[0]=True
        y=v.robust_levels(x,5,reset,np.zeros(70,bool))
        self.assertLess(np.nanmax(np.abs(y[:30])),.01)
        self.assertEqual(y[34,0],-3)

    def test_bad_values_and_reset_break_history(self):
        x=np.ones((20,2))*3;x[7,0]=np.nan
        reset=np.zeros(20,bool);reset[0]=True;reset[12]=True
        y=v.robust_levels(x,5,reset,np.zeros(20,bool))
        self.assertTrue(np.isnan(y[7:12,0]).all())
        self.assertTrue(np.isnan(y[12:16]).all())
        self.assertTrue(np.isfinite(y[16:]).all())

    def test_channel_calibration_does_not_spread_outlier(self):
        a=np.ones((100,3));b=a.copy();b[:,2]=100
        np.testing.assert_equal(v.channel_limits(a,.995)[:2],v.channel_limits(b,.995)[:2])
        with self.assertRaises(ValueError):v.channel_limits(np.full((10,1),np.nan),.995)

    def test_new_test_requires_frozen_candidate(self):
        with self.assertRaises(ValueError):v.generate('unused','test',None)
        self.assertNotEqual(v.identity('development','A',1)[1],v.identity('test','A',1)[1])

    def test_hold_does_not_rearm_active_alarm_but_real_recovery_does(self):
        evidence=np.ones((65,1),bool);holds=np.zeros(65,bool)
        holds[15:30]=True;evidence[15:30]=False;evidence[40:50]=False
        notices=v.notifications(evidence,4,np.zeros(65,bool),holds,np.zeros_like(evidence))
        self.assertEqual(np.flatnonzero(notices[:,0]).tolist(),[3,53])

    def test_signed_ewma_resets_invalid_channels(self):
        x=np.ones((12,2));x[4,0]=np.nan
        y=v.smooth_signed(x,np.zeros(12,bool),np.zeros(12,bool))
        self.assertTrue(np.isnan(y[4,0]));self.assertEqual(y[5,0],1)

    def test_local_http_generation_is_exclusive_and_has_69_channels(self):
        from scripts import mes_causal_data as d
        with tempfile.TemporaryDirectory() as folder,patch.dict(v.ROLES,{'fit':(1,200)}):
            root=Path(folder)/'fit';v.generate(root,'fit');runs,manifest=d.read_role(root)
            self.assertEqual(len(runs),2)
            self.assertTrue(all(len(f['measurements'])==69 for frames in runs.values() for f in frames))
            self.assertTrue(all(r['hold'][1]<=14 for r in manifest['runs']))
            with self.assertRaises(FileExistsError):v.generate(root,'fit')

    def test_sustained_shift_and_single_flat_emit_with_quality_gate(self):
        n=100;values=np.column_stack([np.sin(np.arange(n)+j)*.05 for j in range(8)])
        values[30:60,0]-=4;values[65:,1]=values[64,1]
        keys=[('r',i) for i in range(n)];reset=np.zeros(n,bool);reset[0]=True
        channels=[('E',str(j)) for j in range(8)]
        data=dict(values=values,keys=keys,equipment=['E'],eligible_keys=set(keys),resets=reset)
        stats={c:(0,1) for c in channels};variable=np.ones(8,bool)
        computed,holds=v.process_scores(data,stats,channels,variable,5)
        rows=v.predict(data,channels,np.ones(8)*1e-8,variable,computed,holds,
                       {'level':np.ones(8)},dict(patience=4),'no_timestral')
        emitted=[t for (r,t),eq in rows.items() if eq]
        self.assertEqual(len(emitted),2)
        self.assertTrue(30<=emitted[0]<60);self.assertEqual(emitted[1],79)

    def test_integrated_hold_rebuild_cannot_duplicate_process_or_flat(self):
        n=100;channels=[('E',str(j)) for j in range(8)]
        for kind in ('process','flat'):
            values=np.column_stack([np.sin(np.arange(n)+j)*.05 for j in range(8)])
            if kind=='process':values[:,0]+=3
            else:values[5:,0]=values[4,0]
            values[35:45]=values[34]
            keys=[('r',i) for i in range(n)];reset=np.zeros(n,bool);reset[0]=True
            data=dict(values=values,keys=keys,equipment=['E'],eligible_keys=set(keys),resets=reset)
            variable=np.ones(8,bool);stats={c:(0,1) for c in channels}
            computed,holds=v.process_scores(data,stats,channels,variable,9)
            rows=v.predict(data,channels,np.ones(8)*1e-8,variable,computed,holds,
                           {'level':np.ones(8)},dict(patience=4),'no_timestral')
            self.assertEqual(sum(bool(eqs) for eqs in rows.values()),1,kind)


if __name__=='__main__':unittest.main()
