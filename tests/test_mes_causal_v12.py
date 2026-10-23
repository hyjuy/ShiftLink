import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
from scripts import mes_causal_v12 as candidate
from scripts import mes_causal_v11 as baseline
from tests.test_mes_causal_v11 import normal


class CalibrationTests(unittest.TestCase):
    def test_normal_envelope_covers_repeated_small_excursions(self):
        # v11 false starts came from 1.5 < normal thermal scores < 1.61.
        scores=np.array([[1.55,.2],[1.61,.4],[1.55,.2],[1.55,.2],[100.,100.]])
        limits=candidate.calibrate(scores,[('normal',i) for i in range(4)]+[('fault',0)],{'normal'},[1.5,1.5])
        np.testing.assert_allclose(limits,[1.771,1.5])

    def test_normal_peak_that_cannot_trigger_notice_does_not_reduce_sensitivity(self):
        limits=candidate.calibrate(np.array([[1.7],[.2],[.3],[.2]]),[('normal',i) for i in range(4)],{'normal'},[1.5])
        np.testing.assert_array_equal(limits,[1.5])

    def test_short_excursions_from_different_runs_do_not_join(self):
        limits=candidate.calibrate(np.ones((6,1))*1.6,[('a',i) for i in range(3)]+[('b',i) for i in range(3)],{'a','b'},[1.5])
        np.testing.assert_array_equal(limits,[1.5])

    def test_missing_normal_channel_rejected(self):
        with self.assertRaises(ValueError):
            candidate.calibrate(np.array([[np.nan]]),[('normal',0)],{'normal'},[1.5])

    def test_empty_normal_selection_rejected(self):
        with self.assertRaises(ValueError):
            candidate.calibrate(np.array([[2.]]),[('fault',0)],{'normal'},[1.5])

    def test_original_limits_never_lowered_and_input_not_mutated(self):
        original=np.array([2.,1.5]);level=np.array([[1.,1.]])
        actual=candidate.calibrate(level,[('normal',0)],{'normal'},original)
        np.testing.assert_array_equal(actual,original)
        np.testing.assert_array_equal(level,[[1.,1.]])

    def test_recalibration_removes_normal_excursion_keeps_strong_fault_and_flat(self):
        values=normal(120);values[70:,1]=values[69,1]
        keys=[('r',i) for i in range(120)]
        resets=np.zeros(120,bool);resets[0]=True
        data=dict(values=values,keys=keys,equipment=['E'],eligible_keys=set(keys),resets=resets)
        level=np.zeros_like(values);level[20:30,0]=1.6;level[45:55,0]=4
        args=(data,[('E',str(j)) for j in range(8)],np.ones(8)*1e-8,np.ones(8,bool),
              {'level':level},np.zeros(120,bool),{'level':np.ones(8)*1.5},{'patience':4})
        before=baseline.predict(*args)
        adjusted=list(args);adjusted[6]={'level':np.array([1.8]+[1.5]*7)}
        after=candidate.predict(*adjusted)
        self.assertEqual([t for (r,t),eqs in before.items() if eqs],[23,48,84])
        self.assertEqual([t for (r,t),eqs in after.items() if eqs],[48,84])

    def test_new_test_role_requires_lock_and_seeds_are_separate(self):
        from scripts import mes_causal_v12_data as data
        from scripts import mes_causal_v11_data as previous
        with self.assertRaises(ValueError):data.generate('unused','test')
        for role in ('development','test'):
            for family in ('A','B'):
                for index in range(7):
                    self.assertNotEqual(data.identity(role,family,index),previous.identity(role,family,index))
        self.assertNotEqual(data.identity('development','A',0),data.identity('test','A',0))

    def test_reference_selection_uses_controls_and_unpaired_normal_groups(self):
        from scripts import mes_causal_v12_run as runner
        manifest={'runs':[dict(run_id='normal',group_id='g0',control=False),
            dict(run_id='fault',group_id='g1',control=False),dict(run_id='control',group_id='g1',control=True)]}
        self.assertEqual(runner.normal_runs(manifest),{'normal','control'})

    def test_freeze_blocks_failed_development_and_remaining_known_false_starts(self):
        from scripts import mes_causal_v12_run as runner
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'result.json').write_text(json.dumps({'checks':{'recall':False}}))
            with self.assertRaisesRegex(AssertionError,'development failed'):runner.freeze(root)
            (root/'result.json').write_text(json.dumps({'checks':{'recall':True}}))
            (root/'diagnostic-v11-replay.json').write_text(json.dumps({'case':{'v11':[668,718],'v12':[668,718]}}))
            with self.assertRaisesRegex(AssertionError,'known normal regressions remain'):runner.freeze(root)

    def test_new_http_dataset_keeps_quality_stress_and_exclusive_outputs(self):
        from scripts import mes_causal_v12_data as data
        from scripts import mes_causal_data as source
        with tempfile.TemporaryDirectory() as folder,patch.dict(data.ROLES,{'development':(2,450)}):
            root=Path(folder)/'development';data.generate(root,'development')
            runs,manifest=source.read_role(root);self.assertEqual(len(runs),6)
            for entry in manifest['runs']:
                for q in entry['quality_stress']:
                    frame=runs[entry['run_id']][q['tick']]
                    self.assertEqual(len(frame['measurements']),69)
                    m=next(m for m in frame['measurements'] if (m['equipment_id'],m['signal'])==(q['equipment'],q['signal']))
                    self.assertEqual(m['quality'],'bad')
            with self.assertRaises(FileExistsError):data.generate(root,'development')


if __name__=='__main__':unittest.main()
