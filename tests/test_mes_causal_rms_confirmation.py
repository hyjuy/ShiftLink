"""Pi regressions for the separately versioned RMS confirmation profile."""
import copy,gzip,json,unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from scripts.mes_causal_active_advisory import ActiveAdvisorySource,ActiveAdvisorySession
ROOT=Path(__file__).resolve().parents[1]
OLD=Path('/home/pi/shiftlink/analytics/validation/mes-progressive-eval-20261024-v2')
if not OLD.is_dir():OLD=ROOT/'tests/fixtures/mes_causal_pi/rms_quantization'
def load(p):return json.loads(p.read_text())
class RmsConfirmationTests(unittest.TestCase):
 def setUp(self):
  self.settings=load(ROOT/'docs/research/evidence/mes-causal-v14c-20261023/settings.json');self.config=load(ROOT/'deploy/analytics/source-config.json')
  self.original=load(ROOT/'deploy/analytics/normal-profile.json');self.profile=load(ROOT/'deploy/analytics/normal-profile-rms16.json')
  self.binding=ActiveAdvisorySource(self.settings,self.config,self.profile)
 def frames(self,name):
  with gzip.open((OLD/'data' if (OLD/'data').is_dir() else OLD)/(name+'.json.gz'),'rt') as z:return json.load(z)
 def run_frames(self,frames,binding=None):
  with TemporaryDirectory() as temp:
   session=ActiveAdvisorySession(binding or self.binding,Path(temp)/'state.json');session.defer_flush=True;events=[]
   for f in frames:events.extend((f['sequence'],eq) for eq in session.feed(f,self.config['config_id']))
   return events
 def test_only_rms_window_changes_original_stays_eight(self):
  expected=copy.deepcopy(self.original)
  for j,c in enumerate(self.settings['base']['channels']):
   if 'vib_rms' in c[1]:
    self.assertEqual(self.original['flat_windows'][j],8);expected['flat_windows'][j]=16
  self.assertEqual(self.profile,expected)
 def test_two_consumed_false_notifications_are_removed(self):
  for name,eq,sequence in [('cooling_loss-03','EQ-0009',649),('normal-06','EQ-0008',515)]:
   with self.subTest(name=name):
    frames=[f for f in self.frames(name) if f['sequence']<=sequence]
    self.assertNotIn((sequence,eq),self.run_frames(frames))
    self.assertFalse(any(e==eq for _,e in self.run_frames(frames)))
 def test_in_range_persistent_real_freeze_still_detects_once(self):
  frames=self.frames('normal-06')[:260];eq='EQ-0008';signal='rt_vib_rms';begin=180
  value=next(m['value'] for m in frames[begin-1]['measurements'] if (m['equipment_id'],m['signal'])==(eq,signal))
  for f in frames[begin:]:
   next(m for m in f['measurements'] if (m['equipment_id'],m['signal'])==(eq,signal))['value']=value
  hits=[t for t,e in self.run_frames(frames) if e==eq]
  self.assertEqual(len(hits),1);self.assertLessEqual(hits[0]-frames[begin]['sequence'],15)
 def test_bad_and_stale_measurements_break_confirmation(self):
  for bad in ('quality','observed_at'):
   with self.subTest(bad=bad):
    frames=self.frames('normal-06')[:220];eq='EQ-0008'
    for i,f in enumerate(frames[180:200],180):
     m=next(m for m in f['measurements'] if m['equipment_id']==eq and m['signal']=='rt_vib_rms');m['value']=1.348
     if i%8==0:m[bad]='bad' if bad=='quality' else frames[i-1]['simulated_at']
    self.assertFalse(any(e==eq for _,e in self.run_frames(frames)))
 def test_checkpoint_rebuild_preserves_flat_confirmation(self):
  frames=self.frames('normal-06')[:220];eq='EQ-0008'
  for f in frames[180:]:next(m for m in f['measurements'] if m['equipment_id']==eq and m['signal']=='rt_vib_rms')['value']=1.348
  with TemporaryDirectory() as temp:
   path=Path(temp)/'state.json';session=ActiveAdvisorySession(self.binding,path)
   for f in frames[:190]:session.feed(f,self.config['config_id'])
   session.flush();other=ActiveAdvisorySession(self.binding,path)
   self.assertEqual([session.feed(f,self.config['config_id']) for f in frames[190:]],[other.feed(f,self.config['config_id']) for f in frames[190:]])
if __name__=='__main__':unittest.main()
