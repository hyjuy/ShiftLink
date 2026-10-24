"""Pi-only lifecycle regressions; all original sources and consumed results stay intact."""
import copy,gzip,json,unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import numpy as np
from scripts.mes_causal_pda_service import AdvisorySession
from scripts.mes_causal_lifecycle import LifecycleSource as Source
ROOT=Path(__file__).resolve().parents[1]
PREVIOUS=Path('/home/pi/shiftlink/analytics/validation/episode-notices-20261024')
class LifecycleRegressions(unittest.TestCase):
    def setUp(self):
        self.settings=json.loads((ROOT/'docs/research/evidence/mes-causal-v14c-20261023/settings.json').read_text())
        self.config=json.loads((ROOT/'deploy/analytics/source-config.json').read_text())
        self.profile=json.loads((ROOT/'deploy/analytics/normal-profile.json').read_text())
        self.binding=Source(self.settings,self.config,self.profile);self.d=self.binding.new_detector()
        self.k=3;self.eq=self.d.equipment[self.k];self.j=int(self.d.indexes[self.k][0]);self.n=len(self.d.aug_limits)
    def evidence(self,high=False):
        level=np.zeros(self.n);level[self.j]=self.d.aug_limits[self.j]*2 if high else 0
        return level,np.zeros(self.n,bool),np.ones(self.n,bool)
    def test_twelve_normal_frames_inside_same_fault_do_not_rearm(self):
        self.d._merge({self.eq},*self.evidence(True))
        for _ in range(12):self.d._merge(set(),*self.evidence())
        self.assertEqual(self.d._merge({self.eq},*self.evidence(True)),set(),'brief quiet interval reissued same fault')
    def test_checkpoint_keeps_short_quiet_interval(self):
        self.d._merge({self.eq},*self.evidence(True))
        for _ in range(12):self.d._merge(set(),*self.evidence())
        state=self.d.context_state();other=self.binding.new_detector();other.load_context(state)
        self.assertEqual(other._merge({self.eq},*self.evidence(True)),set(),'restart forgot active episode')
    def test_different_equipment_first_notice_is_independent(self):
        self.d._merge({self.eq},*self.evidence(True));x=self.evidence()
        eq=self.d.equipment[4];x[0][int(self.d.indexes[4][0])]=2*self.d.aug_limits[int(self.d.indexes[4][0])]
        self.assertEqual(self.d._merge({eq},*x),{eq})
    def test_stable_recovery_allows_new_same_sensor_fault(self):
        self.d._merge({self.eq},*self.evidence(True))
        for _ in range(32):self.d._merge(set(),*self.evidence())
        self.assertEqual(self.d._merge({self.eq},*self.evidence(True)),{self.eq})
    def test_new_distinct_sensor_after_old_evidence_recovers_is_not_hidden(self):
        self.d._merge({self.eq},*self.evidence(True))
        for _ in range(6):self.d._merge(set(),*self.evidence())
        x=self.evidence();j=int(self.d.indexes[self.k][-1]);x[0][j]=2*self.d.aug_limits[j]
        self.assertEqual(self.d._merge({self.eq},*x),{self.eq})
    def test_bad_evidence_never_counts_as_recovery(self):
        self.d._merge({self.eq},*self.evidence(True));x=self.evidence();x[0][self.j]=np.nan
        for _ in range(40):self.d._merge(set(),*x)
        self.assertTrue(self.d.episode_on[self.k]);self.assertEqual(self.d.episode_quiet[self.k],0)
    def test_pending_distinct_source_at_recovery_boundary_can_restore(self):
        self.d._merge({self.eq},*self.evidence(True))
        for _ in range(31):self.d._merge(set(),*self.evidence())
        x=self.evidence();j=int(self.d.indexes[self.k][-1]);x[0][j]=2*self.d.aug_limits[j]
        self.d._merge(set(),*x);state=self.d.context_state();other=self.binding.new_detector();other.load_context(state)
        self.assertEqual(other.context_state(),state)
    def test_consumed_variance_fault_remains_one_notice(self):
        with gzip.open(PREVIOUS/'test/cases/variance-01.json.gz','rt') as f:frames=json.load(f)
        with TemporaryDirectory() as tmp:
            session=AdvisorySession(self.binding,Path(tmp)/'state.json');session.defer_flush=True;notices=[]
            for frame in frames:
                if 'EQ-0009' in session.feed(frame,self.binding.config_id):notices.append(frame['sequence'])
        self.assertEqual(notices,[153],'same held-out variance fault generated another notice')
if __name__=='__main__':unittest.main()