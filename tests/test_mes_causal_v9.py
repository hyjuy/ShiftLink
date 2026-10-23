import unittest
import numpy as np
from pathlib import Path
import tempfile
from unittest.mock import patch

from scripts import mes_causal_v9 as v9


class V9Tests(unittest.TestCase):
    def test_chunk_cache_reuses_exact_input_and_rejects_changes(self):
        from scripts import mes_causal_v9_cache as cache
        calls=[]
        def predict(x):calls.append(len(x));return x+1,x+2,dict(seconds=.1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'parts';x=np.arange(12).reshape(6,2)
            a,b,_=cache.run_chunks(x,predict,root,'model',chunk=2)
            np.testing.assert_array_equal(a,x+1);np.testing.assert_array_equal(b,x+2)
            cache.run_chunks(x,predict,root,'model',chunk=2)
            self.assertEqual(calls,[2,2,2])
            with self.assertRaises(ValueError):cache.run_chunks(x+1,predict,root,'model',chunk=2)
            with self.assertRaises(ValueError):cache.run_chunks(x,predict,root,'changed-model',chunk=2)

    def test_archive_is_exclusive_and_roundtrips(self):
        from scripts import mes_causal_v9_cache as cache
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'a.npz';cache.archive(p,a=np.arange(5))
            with np.load(p) as f:np.testing.assert_array_equal(f['a'],np.arange(5))
            with self.assertRaises(FileExistsError):cache.archive(p,a=np.arange(2))

    def test_http_roles_preserve_contract_and_benign_hold(self):
        from scripts import mes_causal_data as d
        with tempfile.TemporaryDirectory() as folder,patch.dict(v9.ROLES,{'fit':(1,170)}):
            path=Path(folder)/'fit';v9.generate(path,'fit')
            runs,manifest=d.read_role(path)
            self.assertEqual(len(runs),2)
            v9.check_disjoint([manifest])
            for frames in runs.values():
                a=next(m for m in frames[140]['measurements'] if m['signal']=='hpu_pressure')
                b=next(m for m in frames[151]['measurements'] if m['signal']=='hpu_pressure')
                self.assertEqual(a['value'],b['value'])
                self.assertNotEqual(a['observed_at'],b['observed_at'])
            with self.assertRaises(FileExistsError):v9.generate(path,'fit')

    def test_selection_prioritizes_normal_budget(self):
        from scripts.mes_causal_v9_run import choose
        a=dict(params=dict(q=.95,patience=4,flat=16),metrics=dict(pristine_normal_false_starts_per_line_hour=0,
               attributable_events=2,duplicate_notifications=0,attributable_within_10s=1))
        b=dict(params=a['params'],metrics=dict(a['metrics'],pristine_normal_false_starts_per_line_hour=20,attributable_events=10))
        self.assertIs(choose([a,b]),a)

    def test_paired_control_excludes_chance_matches(self):
        from scripts.mes_causal_v9_run import evaluate
        runs={r:[dict(sequence=t,line_mode='running') for t in range(20)] for r in ('f','c')}
        ledger=dict(f=[dict(event_id='e',kind='sensor_stuck',equipment='E',start=5,end=15)],c=[])
        rows={(r,t):({'E'} if t==6 else set()) for r in runs for t in range(20)}
        manifest=dict(runs=[dict(run_id='f',group_id='g',control=False),dict(run_id='c',group_id='g',control=True)])
        m=evaluate(runs,ledger,rows,manifest,set(rows))
        self.assertEqual(m['detected_events'],1);self.assertEqual(m['attributable_events'],0)

    def test_impulse_does_not_notify_but_sustained_change_does(self):
        evidence=np.zeros((50,1),bool); evidence[5]=True; evidence[20:40]=True
        notices=v9.transitions(evidence,patience=4,recovery=5)
        self.assertEqual(np.flatnonzero(notices[:,0]).tolist(),[23])

    def test_flatline_requires_variable_channel_and_current_observations(self):
        values=np.r_[np.sin(np.arange(50)),np.ones(24)][:,None]
        flags=v9.flatlines(values,np.array([.001]),np.array([True]),16)
        self.assertTrue(flags[-1,0]);self.assertFalse(flags[55,0])
        self.assertFalse(v9.flatlines(np.zeros((80,1)),np.array([.001]),np.array([False]),16).any())
        values[60]=np.nan
        self.assertFalse(v9.flatlines(values,np.array([.001]),np.array([True]),16)[-1,0])

    def test_reset_prevents_old_evidence_and_missing_cannot_be_flat(self):
        evidence=np.ones((12,1),bool); reset=np.zeros(12,bool);reset[6]=True
        notices=v9.transitions(evidence,patience=4,recovery=5,resets=reset)
        self.assertEqual(np.flatnonzero(notices[:,0]).tolist(),[3,9])
        self.assertFalse(v9.flatlines(np.full((30,1),np.nan),np.array([1.]),np.array([True]),16).any())

    def test_new_identifiers_and_test_lock(self):
        self.assertNotEqual(v9.identity('fit','A',0)[0],v9.identity('test','A',0)[0])
        self.assertGreater(v9.identity('test','B',1)[1],800000)
        with self.assertRaises(ValueError):v9.require_lock(None)

    def test_invalid_current_equipment_cannot_emit_from_held_ewma(self):
        keys=[('r',i) for i in range(20)]
        data=dict(keys=keys,equipment=['E'],raw_z=np.full((20,1),np.nan),ewma=np.full((20,1),100.),
                  eligible_keys=set(keys),resets=np.zeros(20,bool))
        notices=v9.predict(data,[('E','x')],np.array([.01]),np.array([True]),
                           dict(ewma=np.ones(1)),dict(patience=4,flat=16),'ewma')
        self.assertFalse(any(notices.values()))


if __name__=='__main__': unittest.main()
