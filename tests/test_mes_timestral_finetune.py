import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch
from timestral import TimestralForecaster
from timestral.config import TimestralConfig
from timestral.model import TimestralModel

SPEC=importlib.util.spec_from_file_location('ft_tested',Path(__file__).resolve().parents[1]/'scripts/mes_timestral_finetune.py')
m=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
torch.set_num_threads(1)


def tiny():
    torch.manual_seed(9)
    config=TimestralConfig(patch_size=32,d_model=8,num_heads=2,mlp_hidden_dim=16,
        block_schedule=('time_variate',),quantile_knots=(.01,.5,.99),block_size=1,context_length=64)
    return TimestralForecaster(TimestralModel(config).eval())


def example():
    x=np.random.default_rng(17).normal(5,1,(2,64)).astype('float32')
    return x


class FinetuneTests(unittest.TestCase):
    def test_normal_roles_are_run_disjoint(self):
        splits={'train':{f't{i}':[({'sequence':1},{'faults':[]})] for i in range(6)},
                'validation':{f'c{i}':[({'sequence':1},{'faults':[]})] for i in range(6)}}
        roles=m.partition_normal(splits)
        self.assertEqual([len(roles[k]) for k in ('fit','selection','calibration')],[4,2,6])
        splits['train']['t0'][0][1]['faults']=[{'id':'bad'}]
        with self.assertRaises(ValueError):m.partition_normal(splits)

    def test_seed_or_run_reuse_rejected(self):
        a=[{'run_id':'a','seed':1}];b=[{'run_id':'b','seed':2}]
        m.require_disjoint(a,b)
        for bad in ([{'run_id':'x','seed':1}],[{'run_id':'a','seed':3}]):
            with self.assertRaises(ValueError):m.require_disjoint(a,bad)

    def test_target_transform_sign_and_missing(self):
        cache={'loc':np.array([[[10.],[-10.]]],dtype='float32'),
               'scale':np.full((1,2,1),2.,dtype='float32')}
        y=m.normalized_targets(np.array([[11.]],dtype='float32'),cache,True)
        np.testing.assert_allclose(y,np.arcsinh(np.array([[[.5],[-.5]]])),rtol=1e-6)
        missing=m.normalized_targets(np.array([[np.nan]]),cache,True)
        self.assertTrue(np.isnan(missing).all())

    def test_pinball_masks_missing_and_backpropagates(self):
        prediction=torch.zeros((2,3),requires_grad=True)
        target=torch.tensor([2.,float('nan')])
        loss=m.pinball(prediction,target,(.01,.5,.99))
        self.assertAlmostEqual(loss.item(),1.,places=6)
        loss.backward()
        self.assertTrue(torch.isfinite(prediction.grad).all())
        self.assertEqual(prediction.grad[1].abs().sum().item(),0)
        with self.assertRaises(ValueError):m.pinball(prediction,torch.full((2,),float('nan')),(.01,.5,.99))

    def test_cached_head_matches_official_symmetric_forecast(self):
        f=tiny();x=example();cache=m.capture_one(x,f)
        packed={k:v[None] for k,v in cache.items() if k not in ('reference',)}
        q=m.reconstruct(f.model.head,packed,f.config.use_asinh,f.quantile_real_cap_k)
        np.testing.assert_allclose(q.detach().numpy()[0],cache['reference'],rtol=1e-5,atol=1e-5)
        self.assertEqual(cache['hidden'].shape,(2,2,8))
        self.assertTrue(np.isfinite(q.detach().numpy()).all())

    def test_head_weights_change_but_backbone_is_frozen(self):
        f=tiny();cache=m.capture_one(example(),f)
        packed={k:np.stack([v,v]) for k,v in cache.items() if k!='reference'}
        packed['actual']=np.full((2,2),6.,dtype='float32')
        original={k:v.clone() for k,v in f.model.state_dict().items()}
        head,history=m.fit_head(f.model.head,packed,packed,epochs=2,batch=4)
        self.assertEqual(len(history['epochs']),2)
        self.assertTrue(any(not torch.equal(v,head.state_dict()[k]) for k,v in f.model.head.state_dict().items()))
        self.assertTrue(all(torch.equal(v,f.model.state_dict()[k]) for k,v in original.items()))
        self.assertIn(history['selected_epoch'],(1,2))

    def test_checkpoint_round_trip_and_no_overwrite(self):
        f=tiny()
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'checkpoint'
            m.save_checkpoint(f,target)
            restored=TimestralForecaster.from_pretrained(target)
            for k,v in f.model.state_dict().items():self.assertTrue(torch.equal(v,restored.model.state_dict()[k]))
            with self.assertRaises(FileExistsError):m.save_checkpoint(f,target)

    def test_success_requires_both_requested_metrics(self):
        before={'detected_events':35,'wrong_alert_equipment_seconds':21}
        self.assertFalse(m.requested_improvement(before,dict(before,detected_events=36)))
        self.assertFalse(m.requested_improvement(before,dict(before,wrong_alert_equipment_seconds=20)))
        self.assertTrue(m.requested_improvement(before,dict(detected_events=36,wrong_alert_equipment_seconds=20)))

    def test_parallel_capture_keeps_windows_and_passes_separate(self):
        f=tiny()
        frames=[({'run_id':'r','sequence':i+1,'simulated_at':f'2026-01-01T00:{i//60:02}:{i%60:02}+00:00',
                  'line_mode':'running','value':float(i+1)}, {'faults':[]}) for i in range(80)]
        channels=[('eq','a'),('eq','b')]
        with tempfile.TemporaryDirectory() as d:
            cache,keys,meta=m.collect({'r':frames},channels,
                lambda frame:{('eq','a'):frame['value'],('eq','b'):frame['value']+1},
                f,Path(d)/'parallel.npz',thin=2)
            self.assertEqual(keys,[('r',i) for i in range(65,81,2)])
            self.assertEqual(cache['hidden'].shape,(8,2,2,8))
            np.testing.assert_equal(cache['actual'][:,0],np.arange(65,81,2))
            self.assertLess(meta['max_official_reconstruction_error'],1e-4)


if __name__=='__main__':unittest.main()
