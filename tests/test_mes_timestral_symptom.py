import unittest
import numpy as np
from tests.test_mes_timestral_close import fixture
from scripts import mes_timestral_symptom as m

def symptom(z):
    d=fixture(np.max(np.abs(z),axis=1).tolist());d['channels']=[('e','a'),('e','b')];d['signed_z']=np.array(z,float)
    return d

class SymptomTests(unittest.TestCase):
    p=dict(cooldown=120,normal_count=8,z=2.5,stable=1)
    def test_distinct_symptom_preserves_close_first_notice(self):
        d=symptom([[3,0],[3,0],[0,-4]]);a={k:({'e'} if k[1]!=1 else set()) for k in d['keys']}
        out=m.notifications(d,a,self.p);self.assertEqual([k[1] for k,v in out.items() if v],[0,2])
    def test_same_symptom_chatter_is_suppressed(self):
        d=symptom([[3,0]]*5);a={k:({'e'} if k[1]%2==0 else set()) for k in d['keys']}
        self.assertEqual([k[1] for k,v in m.notifications(d,a,self.p).items() if v],[0])
    def test_low_first_score_learns_emerging_symptom(self):
        d=symptom([[1,0],[3,0],[3,0]]);a={k:({'e'} if k[1]!=1 else set()) for k in d['keys']}
        self.assertEqual([k[1] for k,v in m.notifications(d,a,self.p).items() if v],[0])
    def test_sign_reversal_and_normal_reset(self):
        d=symptom([[3,0],[3,0],[-3,0]]);a={k:({'e'} if k[1]!=1 else set()) for k in d['keys']}
        self.assertEqual(sum(map(len,m.notifications(d,a,self.p).values())),2)
        d=symptom([[3,0],[0,0],[0,0],[3,0]]);a={k:({'e'} if k[1] in (0,3) else set()) for k in d['keys']}
        self.assertEqual(sum(map(len,m.notifications(d,a,dict(self.p,normal_count=2)).values())),2)
    def test_stability_and_missing(self):
        d=symptom([[3,0],[0,4],[3,0]]);a={k:{'e'} for k in d['keys']}
        self.assertEqual(sum(map(len,m.notifications(d,a,dict(self.p,stable=2)).values())),1)
        d['signed_z'][1]=np.nan
        self.assertEqual(sum(map(len,m.notifications(d,a,self.p).values())),1)
    def test_boundaries_and_prefix(self):
        for kind in ('reset','clock','inactive'):
            d=symptom([[3,0],[3,0],[3,0]]);a={k:{'e'} for k in d['keys']}
            if kind=='reset':d['resets'][2]=True
            if kind=='clock':d['observations'][2]['at']='2026-01-01T00:00:10+00:00'
            if kind=='inactive':d['observations'][1]['inactive']=True
            self.assertEqual(sum(map(len,m.notifications(d,a,self.p).values())),2)
        d=symptom([[3,0],[0,-4],[3,0]]);a={k:{'e'} for k in d['keys']};out=m.notifications(d,a,self.p)
        for k in ('keys','raw_z','ratio','resets','observations','signed_z'):d[k]=d[k][:2]
        self.assertEqual(m.notifications(d,{k:v for k,v in a.items() if k[1]<2},self.p),{k:v for k,v in out.items() if k[1]<2})
    def test_contract(self):
        d=symptom([[3,0]]);a={('r',0):{'e'}}
        with self.assertRaises(ValueError):m.notifications(d,a,dict(self.p,stable=0))
        d['signed_z']=np.zeros((1,1))
        with self.assertRaises(ValueError):m.notifications(d,a,self.p)
    def test_channel_fluctuation_inside_same_on_is_not_new_warning(self):
        d=symptom([[3,0],[0,4],[3,0]]);a={k:{'e'} for k in d['keys']}
        self.assertEqual([k[1] for k,v in m.notifications(d,a,self.p).items() if v],[0])

if __name__=='__main__':unittest.main()
