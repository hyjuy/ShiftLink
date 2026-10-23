import unittest
from datetime import datetime,timedelta,timezone
import numpy as np
from scripts import mes_timestral_close as m

def fixture(z,ratio=None):
    keys=[('r',i) for i in range(len(z))]
    start=datetime(2026,1,1,tzinfo=timezone.utc)
    obs=[dict(run=r,sequence=i,at=(start+timedelta(seconds=i)).isoformat(),inactive=False) for r,i in keys]
    return dict(keys=keys,raw_z=np.array(z,float).reshape(-1,1),ratio=np.array(ratio or [1]*len(z),float).reshape(-1,1),equipment=['e'],resets=[False]*len(z),observations=obs)

class CloseTests(unittest.TestCase):
    params=dict(z=2.5,ratio=.1,count=3)
    def test_persistent_entry_and_original_display_preserved(self):
        d=fixture([3,3,3,0]);old={k:({'other'} if k[1]==3 else set()) for k in d['keys']}
        self.assertEqual(list(m.augment(d,old,self.params).values()),[set(),set(),{'e'},{'other'}])
        self.assertEqual(old[('r',2)],set())
    def test_nan_and_resets_clear_count(self):
        for value in ('nan','reset','run','gap'):
            d=fixture([3]*6)
            if value=='nan':d['ratio'][2,0]=np.nan
            if value=='reset':d['resets'][2]=True
            if value=='run':d['keys'][2:]=[('s',i) for i in range(2,6)]
            if value=='gap':d['keys'][2:]=[('r',i) for i in range(4,8)]
            old={k:set() for k in d['keys']};out=m.augment(d,old,self.params)
            self.assertFalse(out[d['keys'][2]],value)
            self.assertEqual(out[d['keys'][-1]],{'e'},value)
    def test_thresholds_and_prefix_causality(self):
        d=fixture([3,3,3,3],[.1,.2,.2,.2]);old={k:set() for k in d['keys']}
        full=m.augment(d,old,self.params);self.assertFalse(full[('r',2)]);self.assertEqual(full[('r',3)],{'e'})
        for k in ('keys','raw_z','ratio','resets'):d[k]=d[k][:3]
        self.assertEqual(m.augment(d,{k:v for k,v in old.items() if k[1]<3},self.params),{k:v for k,v in full.items() if k[1]<3})
    def test_close_new_fault_first_notice(self):
        d=fixture([3]*11);a={k:({'e'} if k[1] in (0,10) else set()) for k in d['keys']}
        out=m.pulses(d,a,dict(cooldown=120,quiet=3))
        self.assertEqual([k[1] for k,v in out.items() if v],[0,10])
    def test_quiet_boundary_and_chatter(self):
        d=fixture([3]*8);a={k:({'e'} if k[1] in (0,2,6) else set()) for k in d['keys']}
        out=m.pulses(d,a,dict(cooldown=120,quiet=3))
        self.assertEqual([k[1] for k,v in out.items() if v],[0,6])
    def test_contract(self):
        d=fixture([3]);a={('r',0):set()}
        for params in (dict(z=-1,ratio=.1,count=1),dict(z=2,ratio=.1,count=0),dict(z=2,ratio=float('nan'),count=1)):
            with self.assertRaises(ValueError):m.augment(d,a,params)
        d['keys']*=2
        with self.assertRaises(ValueError):m.augment(d,a,self.params)
    def test_onset_only_does_not_hold_new_signal(self):
        d=fixture([3,3,3,3,0,3,3,3]);old={k:set() for k in d['keys']}
        out=m.augment(d,old,dict(self.params,onset_only=True))
        self.assertEqual([k[1] for k,v in out.items() if v],[2,7])
    def test_selected_quiet_five_boundary_and_close_ten_seconds(self):
        for restart,expected in ((5,[0]),(6,[0,6]),(10,[0,10])):
            d=fixture([3]*(restart+1));old={k:({'e'} if k[1] in (0,restart) else set()) for k in d['keys']}
            out=m.pulses(d,old,dict(cooldown=45,quiet=5))
            self.assertEqual([k[1] for k,v in out.items() if v],expected)

if __name__=='__main__':unittest.main()
