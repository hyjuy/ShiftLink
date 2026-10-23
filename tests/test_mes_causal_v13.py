import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
from scripts import mes_causal_v13 as candidate
from scripts import mes_causal_v11 as previous
from tests import test_mes_causal_v11 as original_tests


def inputs():
    n=100;keys=[('r',i) for i in range(n)]
    values=np.column_stack([np.sin(np.arange(n)+j)*.05 for j in range(3)])
    resets=np.zeros(n,bool);resets[0]=True
    data=dict(values=values,keys=keys,equipment=['E'],eligible_keys=set(keys),resets=resets)
    level=np.zeros_like(values);level[10:30,0]=4;level[30:50,0]=1.2;level[50:65,0]=1.6
    return [data,[('E','bearing_temp'),('E','motor_current'),('E','other_temp')],np.ones(3)*1e-8,
            np.ones(3,bool),{'level':level},np.zeros(n,bool),{'level':np.ones(3)*1.5},{'patience':4}]


def ticks(rows):return [t for (run,t),eqs in rows.items() if eqs]


class ThermalRecoveryTests(unittest.TestCase):
    def test_residual_heat_not_a_new_episode(self):
        args=inputs()
        self.assertEqual(ticks(previous.predict(*args)),[13,53])
        self.assertEqual(ticks(candidate.predict(*args)),[13])

    def test_hold_is_unknown_and_reset_starts_a_new_episode(self):
        args=inputs();args[5][30:45]=True;args[4]['level'][30:45,0]=np.nan
        self.assertEqual(ticks(candidate.predict(*args)),[13])
        args[0]['resets'][45]=True
        self.assertEqual(ticks(candidate.predict(*args)),[13,53])

    def test_temperature_flat_bad_does_not_renotify(self):
        args=inputs();args[4]['level'][:]=.5
        args[0]['values'][5:,0]=args[0]['values'][4,0]
        args[0]['values'][40,0]=np.nan;args[4]['level'][40,0]=np.nan
        self.assertEqual(ticks(candidate.predict(*args)),[19])


class V11CompatibilityTests(original_tests.RecoveryTests):
    def setUp(self):
        replacement=patch.object(original_tests,'candidate',candidate)
        replacement.start();self.addCleanup(replacement.stop)


class NotificationAndDataTests(unittest.TestCase):
    def test_supply_context_does_not_hide_independent_local_evidence(self):
        args=inputs();args[1]=[('P','hpu_pressure'),('C','rt_clamp_press'),('C','motor_current')]
        args[0]['equipment']=['C','P'];args[4]['level'][:]=3
        args[0]['signed_z']=-np.ones((100,3))
        rows={key:set() for key in args[0]['keys']};rows['r',10]={'P'};rows['r',20]={'C'}
        self.assertEqual(candidate.associations(args,rows,[]),[])
        notes=candidate.associations(args,rows,[{'from':'P','to':'C','relation':'hydraulic_supply'}])
        self.assertEqual(len(notes),1);self.assertTrue(notes[0]['local_evidence_present'])
        self.assertFalse(notes[0]['causal_claim']);self.assertTrue(notes[0]['notification_preserved'])
        self.assertEqual(rows['r',20],{'C'})

    def test_context_requires_observed_parent_and_correct_direction(self):
        args=inputs();args[1]=[('P','hpu_pressure'),('C','rt_clamp_press'),('C','motor_current')]
        args[0]['equipment']=['C','P'];args[4]['level'][:]=3;args[0]['signed_z']=np.ones((100,3))
        rows={key:set() for key in args[0]['keys']};rows['r',20]={'C'}
        links=[{'from':'P','to':'C','relation':'hydraulic_supply'}]
        self.assertEqual(candidate.associations(args,rows,links),[])
        args[0]['signed_z'][:]=-1
        self.assertEqual(candidate.associations(args,rows,links),[])
        rows['r',10]={'P'};self.assertEqual(len(candidate.associations(args,rows,links)),1)
        args[0]['resets'][15]=True;self.assertEqual(candidate.associations(args,rows,links),[])

    def test_isolated_http_contract_quality_and_exclusive_files(self):
        from scripts import mes_causal_v13_data as data
        from scripts import mes_causal_data as source
        with self.assertRaises(ValueError):data.generate('unused','test')
        with tempfile.TemporaryDirectory() as folder,patch.dict(data.ROLES,{'development':(2,450)}):
            root=Path(folder)/'development';data.generate(root,'development');runs,manifest=source.read_role(root)
            self.assertEqual(len(runs),6)
            for entry in manifest['runs']:
                first=runs[entry['run_id']][0]
                expected=source.Session(entry['family'],entry['seed'],entry['run_id'],[]).advance()
                self.assertEqual(first,expected)
                for q in entry['quality_stress']:
                    m=next(m for m in runs[entry['run_id']][q['tick']]['measurements'] if
                           (m['equipment_id'],m['signal'])==(q['equipment'],q['signal']))
                    self.assertEqual(m['quality'],'bad')
            with self.assertRaises(FileExistsError):data.generate(root,'development')

    def test_five_normal_samples_allow_a_close_new_thermal_episode(self):
        args=inputs();args[4]['level'][30:35,0]=.8;args[4]['level'][35:50,0]=2
        self.assertEqual(ticks(candidate.predict(*args)),[13,38])

    def test_independent_current_during_warm_tail_is_preserved(self):
        args=inputs();args[4]['level'][50:65,0]=1.2;args[4]['level'][50:65,1]=4
        self.assertEqual(ticks(candidate.predict(*args)),[13,53])

    def test_new_flat_sensor_during_warm_tail_is_preserved(self):
        args=inputs();args[4]['level'][50:65,0]=1.2
        args[0]['values'][46:,2]=args[0]['values'][45,2]
        self.assertEqual(ticks(candidate.predict(*args)),[13,60])

    def test_missing_samples_do_not_establish_thermal_recovery(self):
        args=inputs();args[4]['level'][30:50,0]=np.nan
        self.assertEqual(ticks(candidate.predict(*args)),[13])


if __name__=='__main__':unittest.main()
