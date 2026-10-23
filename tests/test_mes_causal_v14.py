import unittest
from pathlib import Path
import numpy as np
from scripts import mes_causal_v14 as candidate
from tests.test_mes_causal_v13 import inputs,ticks

class RiseTests(unittest.TestCase):
    def args(self):
        a=inputs();a[0]['signed_z']=np.zeros((100,3));a[4]['level'][:]=0
        a[7]['thermal_rise_limits']=[.7]
        return a

    def test_weak_coherent_warming_is_detected_before_level_threshold(self):
        a=self.args();a[0]['signed_z'][60:,0]=1.;a[0]['signed_z'][60:,2]=1.
        self.assertEqual(ticks(candidate.previous.predict(*a)),[])
        self.assertTrue(any(60<=t<70 for t in ticks(candidate.predict(*a))))

    def test_single_sensor_spike_does_not_supply_coherence(self):
        a=self.args();a[0]['signed_z'][60:,0]=3.
        self.assertEqual(ticks(candidate.predict(*a)),[])

    def test_prefix_is_unchanged_by_future_values(self):
        a=self.args();before=candidate.thermal_rise(a)
        a[0]['signed_z'][70:]=100
        np.testing.assert_equal(before[:70],candidate.thermal_rise(a)[:70])

    def test_bad_and_hold_break_contiguous_history(self):
        a=self.args();a[0]['signed_z'][60:,0]=2.;a[0]['signed_z'][60:,2]=2.
        a[5][55]=True
        self.assertTrue(np.isnan(candidate.thermal_rise(a)[60,0]))
        a=self.args();a[0]['signed_z'][60,0]=np.nan
        self.assertTrue(np.isnan(candidate.thermal_rise(a)[60,0]))

class ExtendedRiseTests(RiseTests):
    def test_missing_current_is_unknown_but_one_old_bad_is_tolerated(self):
        a=self.args();a[0]['signed_z'][60:,0]=1.;a[0]['signed_z'][60:,2]=1.
        a[0]['signed_z'][64,0]=np.nan
        scores=candidate.thermal_rise(a)
        self.assertTrue(np.isnan(scores[64,0]));self.assertTrue(np.isfinite(scores[65,0]))

    def test_insufficient_recent_or_reference_support_is_unknown(self):
        a=self.args();a[0]['signed_z'][60:63,0]=np.nan
        self.assertTrue(np.isnan(candidate.thermal_rise(a)[64,0]))
        a=self.args();a[0]['signed_z'][30:45,0]=np.nan
        self.assertTrue(np.isnan(candidate.thermal_rise(a)[64,0]))

    def test_reset_requires_new_reference_and_ineligible_frames_are_quiet(self):
        a=self.args();a[0]['resets'][55]=True
        self.assertTrue(np.isnan(candidate.thermal_rise(a)[70,0]))
        a=self.args();a[0]['eligible_keys']=set()
        self.assertTrue(np.isnan(candidate.thermal_rise(a)).all())
        self.assertEqual(ticks(candidate.predict(*a)),[])

    def test_negative_shift_and_unrelated_temperature_are_not_coherent(self):
        a=self.args();a[0]['signed_z'][60:,0]=-2.;a[0]['signed_z'][60:,2]=-2.
        self.assertEqual(ticks(candidate.predict(*a)),[])
        a=self.args();a[1][2]=('OTHER','other_temp');a[0]['signed_z'][60:]=2.
        self.assertEqual(ticks(candidate.predict(*a)),[])

    def test_invalid_limits_fail_closed(self):
        for limits in ([],[0],[-1],[float('nan')],[float('inf')]):
            a=self.args();a[7]['thermal_rise_limits']=limits
            with self.assertRaises(ValueError):candidate.predict(*a)

    def test_augmentation_does_not_mutate_original_inputs(self):
        a=self.args();values=a[0]['values'].copy();levels=a[4]['level'].copy();channels=list(a[1])
        candidate.predict(*a)
        np.testing.assert_equal(values,a[0]['values']);np.testing.assert_equal(levels,a[4]['level']);self.assertEqual(channels,a[1])


from unittest.mock import patch
from tests import test_mes_causal_v13 as oldtests
from tests import test_mes_causal_v11 as recoverytests


def compatible(*args):
    a=list(args);a[0]=dict(a[0]);a[0].setdefault('signed_z',a[0]['values'])
    a[7]=dict(a[7],thermal_rise_limits=[1e6]*len(a[0]['equipment']))
    return candidate.predict(*a)


class ThermalCompatibilityTests(oldtests.ThermalRecoveryTests):
    def setUp(self):
        proxy=type('Proxy',(),{'predict':staticmethod(compatible)})
        replacement=patch.object(oldtests,'candidate',proxy);replacement.start();self.addCleanup(replacement.stop)


class RecoveryCompatibilityTests(recoverytests.RecoveryTests):
    def setUp(self):
        proxy=type('Proxy',(),{'predict':staticmethod(compatible)})
        replacement=patch.object(recoverytests,'candidate',proxy);replacement.start();self.addCleanup(replacement.stop)


class DataTests(unittest.TestCase):
    def test_unused_roles_require_freeze_and_identities_are_disjoint(self):
        from scripts import mes_causal_v14_data as data
        from scripts import mes_causal_v13_data as previous
        with self.assertRaises(ValueError):data.generate('unused','test')
        identities=[data.identity(r,f,i) for r in data.ROLES for f in ('A','B') for i in range(7)]
        self.assertEqual(len(identities),len(set(identities)))
        self.assertNotEqual(data.identity('test','A',0),previous.identity('test','A',0))


class PipelineTests(unittest.TestCase):
    def test_predictions_are_persisted_before_private_truth_is_opened(self):
        import tempfile,pickle,json
        from scripts import mes_causal_v14_run as runner
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);cache=root/'cache';cache.mkdir();target=root/'result';target.mkdir()
            a=inputs();a[0]['signed_z']=np.zeros((100,3));a[7]['thermal_rise_limits']=[.7]
            with (cache/'r.pkl').open('wb') as stream:pickle.dump(a,stream)
            b=inputs();b[4]['level'][:]=0;b[0]['values']+=np.sin(np.arange(100))[:,None]*.01
            b[0]['keys']=[('c',i) for i in range(100)];b[0]['eligible_keys']=set(b[0]['keys'])
            b[0]['signed_z']=np.zeros((100,3));b[7]['thermal_rise_limits']=[.7]
            with (cache/'c.pkl').open('wb') as stream:pickle.dump(b,stream)
            ledger={'r':[dict(event_id='0',equipment='E',kind='cooling_loss',start=10,end=30)],'c':[]}
            runner.d.write_new(root/'events.private.json',ledger)
            runner.d.write_new(root/'manifest.json',dict(ledger_sha256=runner.d.sha(root/'events.private.json'),runs=[
                dict(run_id='r',control=False,group_id='g'),dict(run_id='c',control=True,group_id='g')]))
            real=runner.load
            def guarded(path):
                if Path(path).name=='events.private.json':self.assertTrue((target/'predictions.json').is_file())
                return real(path)
            with patch.object(runner,'load',side_effect=guarded):
                result=runner.assess(root,target,{'thermal_rise_limits':[.7]},cache)
            self.assertTrue(all(result['checks'].values()));self.assertEqual(result['methods']['v14']['detected_events'],1)

    def test_new_generator_http_contract_and_exclusive_output(self):
        import tempfile
        from scripts import mes_causal_v14_data as data
        from scripts import mes_causal_data as source
        with tempfile.TemporaryDirectory() as folder,patch.dict(data.ROLES,{'development':(2,420)}):
            root=Path(folder)/'development';data.generate(root,'development');runs,manifest=source.read_role(root)
            self.assertEqual(len(runs),6)
            for entry in manifest['runs']:
                expected=source.Session(entry['family'],entry['seed'],entry['run_id'],[]).advance()
                self.assertEqual(runs[entry['run_id']][0],expected)
                for q in entry['quality_stress']:
                    m=next(m for m in runs[entry['run_id']][q['tick']]['measurements'] if (m['equipment_id'],m['signal'])==(q['equipment'],q['signal']))
                    self.assertEqual(m['quality'],'bad')
            with self.assertRaises(FileExistsError):data.generate(root,'development')


if __name__=='__main__':unittest.main()
