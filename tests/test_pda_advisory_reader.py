"""Direct trust-boundary checks for the Pi-owned advisory overlay."""
import copy,json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase,main
from shiftlink.pda.ai_insights import read_insights,overlay_state,overlay_response

class ReaderTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'result.json'
        self.now=datetime(2026,1,1,tzinfo=timezone.utc)
        self.state=dict(run_id='r',config_id='c',sequence=10,simulated_at=self.now.isoformat(),line_mode='running',equipment=[dict(equipment_id='E')],active_alarms=[dict(id='old')])
        item=dict(equipment_id='E',event_id='r:9:E',sequence=9,observed_at=self.now.isoformat(),state='recent',signals=[dict(signal='x',direction='high'),dict(signal='bad',direction='unknown')])
        self.value=dict(schema_version=1,status='ready',operational_notifications=False,run_id='r',config_id='c',sequence=10,input_at=self.now.isoformat(),generated_at=self.now.isoformat(),items=[item,copy.deepcopy(item),dict(item,equipment_id='unknown')])
    def read(self,**change):
        self.path.write_text(json.dumps(self.value|change));return read_insights(self.path,self.state,'c',now=self.now)
    def test_ready_filters_duplicates_and_keeps_only_safe_signals(self):
        result=self.read();self.assertEqual(result['status'],'ready');self.assertEqual(len(result['items']),1)
        self.assertEqual(result['items'][0]['signals'],[dict(signal='x',direction='high')]);self.assertFalse(result['operational_notifications'])
        for change in (dict(sequence=True),dict(sequence=11),dict(event_id=None),dict(observed_at=None),dict(state='unknown')):
            self.assertEqual(self.read(items=[self.value['items'][0]|change])['items'],[])
    def test_age_identity_lag_and_format_boundaries_hide_results(self):
        for change,status in [(dict(generated_at=(self.now+timedelta(seconds=6)).isoformat()),'unavailable'),(dict(generated_at=(self.now-timedelta(seconds=11)).isoformat()),'stale'),(dict(config_id='other'),'unavailable'),(dict(run_id='other'),'warming_up'),(dict(sequence=True),'unavailable'),(dict(sequence=11),'unavailable'),(dict(sequence=6,input_at=(self.now-timedelta(seconds=4)).isoformat()),'catching_up'),(dict(input_at=(self.now-timedelta(seconds=1)).isoformat()),'unavailable'),(dict(operational_notifications=True),'unavailable'),(dict(status='bad'),'unavailable'),(dict(status='warming_up'),'warming_up')]:
            with self.subTest(change=change):
                value=self.read(**change);self.assertEqual(value['status'],status);self.assertEqual(value['items'],[])
    def test_inactive_missing_oversized_and_malformed_files_fail_closed(self):
        for mode in ('paused','stopped','recovering','quality_hold'):
            self.state['line_mode']=mode;self.assertEqual(self.read()['status'],'inactive')
        self.assertEqual(read_insights(None,self.state,'c')['status'],'disabled')
        for raw in ('{broken','[]','x'*262145):
            self.path.write_text(raw);self.assertEqual(read_insights(self.path,self.state,'c',now=self.now)['status'],'unavailable')
        self.path.unlink();self.assertEqual(overlay_state(self.state,self.path),self.state)
        self.assertEqual(overlay_response(b'{broken',self.path),b'{broken')
        self.path.write_text('{}');before=copy.deepcopy(self.state);out=overlay_state(self.state,self.path)
        self.assertEqual(self.state,before);self.assertEqual({k:v for k,v in out.items() if k!='ai_insights'},before)

if __name__=='__main__':main()
