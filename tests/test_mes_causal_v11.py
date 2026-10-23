import unittest
import numpy as np
import tempfile
from pathlib import Path
from unittest.mock import patch
from scripts import mes_causal_v10 as baseline
from scripts import mes_causal_v11 as candidate


def run(values,width=5,resets=None):
    n,c=values.shape;channels=[('E',str(j)) for j in range(c)]
    keys=[('r',i) for i in range(n)]
    if resets is None:resets=np.zeros(n,bool);resets[0]=True
    data=dict(values=values,keys=keys,equipment=['E'],eligible_keys=set(keys),resets=resets)
    variable=np.ones(c,bool);stats={key:(0.,1.) for key in channels}
    computed,holds=baseline.process_scores(data,stats,channels,variable,width)
    rows=candidate.predict(data,channels,np.ones(c)*1e-8,variable,computed,holds,
                           {'level':np.ones(c)*1.5},dict(width=width,patience=4))
    return [t for (r,t),eqs in rows.items() if eqs]


def normal(n=120):return np.column_stack([np.sin(np.arange(n)+j)*.05 for j in range(8)])


class RecoveryTests(unittest.TestCase):
    def test_bad_sample_during_same_flat_does_not_renotify(self):
        values=normal();values[5:,0]=values[4,0];values[40,0]=np.nan
        self.assertEqual(run(values),[19])

    def test_repeated_bad_and_long_missing_do_not_prove_recovery(self):
        values=normal(180);values[5:,0]=values[4,0]
        values[40:60,0]=np.nan;values[85,0]=np.nan;values[110:115,0]=np.nan
        self.assertEqual(run(values),[19])

    def test_real_recovery_allows_a_new_flat_event(self):
        values=normal();values[5:65,0]=values[4,0];values[40,0]=np.nan
        values[70:,0]=values[69,0]
        self.assertEqual(run(values),[19,84])

    def test_five_real_moving_samples_after_bad_allow_close_new_flat(self):
        values=normal();values[5:41,0]=values[4,0];values[40,0]=np.nan
        values[46:,0]=values[45,0]
        self.assertEqual(run(values),[19,60])

    def test_bad_sample_during_sustained_process_change_does_not_renotify(self):
        values=normal();values[:,0]+=4;values[40,0]=np.nan
        self.assertEqual(len(run(values,width=9)),1)

    def test_unrelated_missing_channel_does_not_block_recovery(self):
        values=normal(130);values[15:45,0]+=4;values[80:110,0]+=4
        values[35:120,1]=np.nan
        ticks=run(values)
        self.assertEqual(len(ticks),2)
        self.assertTrue(15<=ticks[0]<45 and 80<=ticks[1]<110)

    def test_global_repeat_rebuild_preserves_active_process_and_flat(self):
        for kind in ('process','flat'):
            values=normal()
            if kind=='process':values[:,0]+=4
            else:values[5:,0]=values[4,0]
            values[35:50]=values[34]
            self.assertEqual(len(run(values,width=9)),1,kind)

    def test_reset_starts_a_new_episode(self):
        values=normal();values[5:,0]=values[4,0]
        resets=np.zeros(120,bool);resets[0]=True;resets[60]=True
        self.assertEqual(run(values,resets=resets),[19,75])

    def test_normal_and_single_impulse_stay_quiet(self):
        values=normal();values[20,0]=100
        self.assertEqual(run(values),[])


class DataContractTests(unittest.TestCase):
    def test_test_requires_lock_and_new_role_identity_is_disjoint(self):
        from scripts import mes_causal_v11_data as d
        with self.assertRaises(ValueError):d.generate('unused','test')
        self.assertNotEqual(d.identity('development','A',0),d.identity('test','A',0))

    def test_http_quality_stress_is_shared_with_control_and_files_exclusive(self):
        from scripts import mes_causal_data as source
        from scripts import mes_causal_v11_data as d
        from scripts import mes_causal_v9 as check
        with tempfile.TemporaryDirectory() as folder,patch.dict(d.ROLES,{'development':(2,450)}):
            root=Path(folder)/'development';d.generate(root,'development')
            runs,manifest=source.read_role(root);check.check_disjoint([manifest])
            self.assertEqual(len(runs),6)
            for entry in manifest['runs']:
                for stress in entry['quality_stress']:
                    frame=runs[entry['run_id']][stress['tick']]
                    measurement=next(m for m in frame['measurements'] if
                        (m['equipment_id'],m['signal'])==(stress['equipment'],stress['signal']))
                    self.assertEqual(measurement['quality'],'bad')
            for group in {e['group_id'] for e in manifest['runs']}:
                entries=[e for e in manifest['runs'] if e['group_id']==group]
                if len(entries)==2:self.assertEqual(entries[0]['quality_stress'],entries[1]['quality_stress'])
            with self.assertRaises(FileExistsError):d.generate(root,'development')


if __name__=='__main__':unittest.main()
