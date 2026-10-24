"""Incremental replay must not deserialize snapshots before the cursor."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import unittest
from unittest.mock import patch
from shiftlink.mes.contracts import Run,Snapshot,RuntimeEvent
from shiftlink.mes import storage
class IncrementalReplayTests(unittest.TestCase):
 def setUp(self):
  self.store=storage.MesStorage();self.addCleanup(self.store.close);self.at=datetime(2026,1,1,tzinfo=timezone.utc)
  self.store.create_run(Run('r',1,self.at));self.store.create_run(Run('other',2,self.at))
  for seq in range(1,1001):
   snap=Snapshot('r',seq,self.at+timedelta(seconds=seq),'L','running','normal')
   self.store.save_tick(snap,())
  self.store.save_tick(Snapshot('other',1001,self.at,'L','running','normal'),())
 def test_tail_decodes_only_requested_frames_and_does_not_change_history(self):
  before=self.store.connection.total_changes
  with patch.object(storage,'_snapshot',wraps=storage._snapshot) as decode:
   frames,events=self.store.replay('r',after_sequence=998)
  self.assertEqual([f.sequence for f in frames],[999,1000]);self.assertEqual(events,[])
  self.assertEqual(decode.call_count,2,'tail request decoded accumulated history')
  self.assertEqual(self.store.connection.total_changes,before)
 def test_empty_tail_decodes_no_history(self):
  with patch.object(storage,'_snapshot',wraps=storage._snapshot) as decode:
   self.assertEqual(self.store.replay('r',after_sequence=1000),([],[]))
  self.assertEqual(decode.call_count,0)
 def test_as_of_sequence_and_run_boundaries_are_preserved(self):
  frames,_=self.store.replay('r',after_sequence=8,as_of=self.at+timedelta(seconds=10))
  self.assertEqual([f.sequence for f in frames],[9,10])
  self.assertEqual(self.store.replay('missing'),([],[]))
  self.assertEqual(len(self.store.replay('r')[0]),1000)
if __name__=='__main__':unittest.main()

