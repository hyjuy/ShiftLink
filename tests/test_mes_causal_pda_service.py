import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from scripts import mes_causal_pda_service as m
from scripts.mes_causal_schema import metadata
from tests.test_mes_causal_v14_stream import config, frames, channel_choices, modify
from shiftlink.pda.ai_insights import overlay_state


def source_config():
    c={'config_id':'placeholder','equipment':copy.deepcopy(metadata()['equipment'])}
    c['config_id']=m.config_digest(c)
    return c


def rows(count=240):
    c=source_config();out=frames(count)
    for f in out:
        f['config_id']=c['config_id']
        f['equipment']=[dict(equipment_id=e['equipment_id'],operating_state='running') for e in metadata()['equipment']]
    return out


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'state.json'

    def binding(self):return m.BoundSource(config(),source_config())

    def test_source_schema_and_hash_are_pinned(self):
        c=source_config();b=m.BoundSource(config(),c);b.validate_config(c)
        for field,value in [('unit','wrong'),('normal_max',99999)]:
            other=copy.deepcopy(c);other['equipment'][0]['signals'][0][field]=value
            with self.assertRaises(ValueError):b.validate_config(other)
            other['config_id']=m.config_digest(other)
            with self.assertRaises(ValueError):m.BoundSource(config(),other)

    def test_source_order_is_mapped_by_keys_without_forging_config(self):
        b=self.binding();f=rows(1)[0];original=copy.deepcopy(f);f['measurements'].reverse()
        adapted=b.adapt(f,b.config_id)
        self.assertEqual(adapted['config_id'],f['config_id'])
        self.assertEqual(adapted['measurements'],original['measurements'])
        with self.assertRaises(ValueError):b.adapt(f,'wrong')
        f['measurements'][0]=f['measurements'][1]
        with self.assertRaises(ValueError):b.adapt(f,b.config_id)

    def test_restart_replays_only_after_durable_cursor_with_same_notices(self):
        b=self.binding();data=rows();temp,current=channel_choices();modify(data,[current],100,210,6.)
        uninterrupted=m.AdvisorySession(b,Path(self.tmp.name)/'other.json');expected=[]
        for f in data:expected.append(uninterrupted.feed(f,b.config_id))
        a=m.AdvisorySession(b,self.path);actual=[]
        for f in data[:139]:actual.append(a.feed(f,b.config_id))
        a.flush();a=m.AdvisorySession(b,self.path)
        self.assertEqual(a.cursor,138)
        self.assertEqual(a.feed(data[138],b.config_id),set())
        for f in data[139:]:actual.append(a.feed(f,b.config_id))
        self.assertEqual(actual,expected)
        self.assertEqual({k:v for k,v in a.report(data[-1]).items() if k!='generated_at'}, {k:v for k,v in uninterrupted.report(data[-1]).items() if k!='generated_at'})

    def test_bad_measurement_restart_does_not_create_duplicate(self):
        b=self.binding();data=rows();temp,current=channel_choices();modify(data,[current],100,220,flat=True)
        for sample in data[125]['measurements']:
            if (sample['equipment_id'],sample['signal'])==current:sample['quality']='bad'
        a=m.AdvisorySession(b,self.path);seen=[]
        for f in data:
            seen.extend(a.feed(f,b.config_id))
            if f['sequence']==130:a.flush();a=m.AdvisorySession(b,self.path)
        self.assertEqual(seen.count(current[0]),1)

    def test_recent_notice_has_stable_id_and_no_haptics_contract(self):
        b=self.binding();data=rows();temp,current=channel_choices();modify(data,[current],100,130,6.)
        a=m.AdvisorySession(b,self.path)
        report=None
        for f in data[:120]:a.feed(f,b.config_id)
        report=a.report(data[119]);self.assertEqual(report['status'],'ready');self.assertFalse(report['operational_notifications'])
        self.assertEqual(len(report['items']),1);event=report['items'][0]['event_id']
        a.flush();a=m.AdvisorySession(b,self.path)
        self.assertEqual(a.report(data[119])['items'][0]['event_id'],event)
        for f in data[120:180]:a.feed(f,b.config_id)
        self.assertEqual(a.report(data[179])['items'],[])

    def test_run_change_pause_gap_and_lag_hide_advisories(self):
        b=self.binding();a=m.AdvisorySession(b,self.path);data=rows(140)
        for f in data:a.feed(f,b.config_id)
        for change,status in [({'sequence':150},'catching_up'),({'line_mode':'paused'},'inactive')]:
            self.assertEqual(a.report(data[-1]|change)['status'],status)
            self.assertEqual(a.report(data[-1]|change)['items'],[])
        next_frame=copy.deepcopy(data[-1]);next_frame['run_id']='new';next_frame['sequence']=0
        a.feed(next_frame,b.config_id);self.assertEqual(a.report(next_frame)['status'],'warming_up')

    def test_corrupt_or_different_model_journal_fails_closed(self):
        b=self.binding();self.path.write_text('{broken')
        with self.assertRaises(ValueError):m.AdvisorySession(b,self.path)
        self.path.unlink();a=m.AdvisorySession(b,self.path)
        for f in rows(80):a.feed(f,b.config_id)
        a.flush();value=json.loads(self.path.read_text());value['binding']='wrong';self.path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):m.AdvisorySession(b,self.path)

    def test_overlay_is_additive_and_stale_results_are_hidden(self):
        b=self.binding();data=rows(140);a=m.AdvisorySession(b,self.path)
        for f in data:a.feed(f,b.config_id)
        state=data[-1]|{'equipment':[{'equipment_id':e['equipment_id']} for e in metadata()['equipment']], 'active_alarms':[{'alarm_id':'old'}]}
        original=copy.deepcopy(state);result=a.report(state);result['generated_at']='2020-01-01T00:00:00+00:00';self.path.write_text(json.dumps(result))
        out=overlay_state(state,self.path)
        self.assertEqual(out['ai_insights']['status'],'stale');self.assertEqual(out['ai_insights']['items'],[])
        self.assertEqual({k:v for k,v in out.items() if k!='ai_insights'},original)
        self.assertEqual(state,original)
        self.assertEqual(overlay_state(state,None),state)




class PollBoundaryTests(unittest.TestCase):
    setUp=ProductionTests.setUp
    binding=ProductionTests.binding
    def test_replay_is_complete_and_pinned_before_publication(self):
        from unittest.mock import patch
        b=self.binding();a=m.AdvisorySession(b,self.path);data=rows(80)
        batch=dict(config_id=b.config_id,config_preserved=True,is_synthetic=True,snapshots=data)
        state=data[-1]|dict(is_synthetic=True)
        with patch.object(m,'replay_stream',side_effect=lambda *_: iter([('frame',f) for f in batch['snapshots']]+[('meta',(k,v)) for k,v in batch.items() if k!='snapshots'])):self.assertEqual(m.poll(a,'http://source',state)['status'],'ready')
        a.flush();self.assertEqual(m.AdvisorySession(b,self.path).cursor,79)
        bad=copy.deepcopy(batch);bad['snapshots']=data[1:]
        with patch.object(m,'replay_stream',side_effect=lambda *_: iter([('frame',f) for f in bad['snapshots']]+[('meta',(k,v)) for k,v in bad.items() if k!='snapshots'])):
            with self.assertRaises(ValueError):m.poll(m.AdvisorySession(b,Path(self.tmp.name)/'fresh.json'),'http://source',state)
        for change in ({'config_id':'wrong'},{'config_preserved':False},{'is_synthetic':False}):
            with patch.object(m,'replay_stream',side_effect=lambda *_: iter([('frame',f) for f in batch['snapshots']]+[('meta',(k,v)) for k,v in (batch|change).items() if k!='snapshots'])):
                with self.assertRaises(ValueError):m.poll(m.AdvisorySession(b,Path(self.tmp.name)/'fresh.json'),'http://source',state)
        with self.assertRaises(ValueError):m.poll(a,'http://source',state|{'is_synthetic':False})

    def test_actual_proxy_preserves_all_upstream_fields(self):
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        from threading import Thread
        from urllib.request import urlopen
        from shiftlink.pda.__main__ import make_handler
        b=self.binding();data=rows(80);a=m.AdvisorySession(b,self.path)
        for f in data:a.feed(f,b.config_id)
        state=data[-1]|dict(equipment=[{'equipment_id':e['equipment_id']} for e in metadata()['equipment']],active_alarms=[{'id':'existing'}])
        self.path.write_text(json.dumps(a.report(state)))
        class Source(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(inner):
                body=json.dumps(state).encode();inner.send_response(200);inner.end_headers();inner.wfile.write(body)
        upstream=ThreadingHTTPServer(('127.0.0.1',0),Source);Thread(target=upstream.serve_forever,daemon=True).start()
        proxy=ThreadingHTTPServer(('127.0.0.1',0),make_handler('http://127.0.0.1:'+str(upstream.server_port),ai_insights_path=self.path))
        Thread(target=proxy.serve_forever,daemon=True).start()
        try:
            with urlopen('http://127.0.0.1:'+str(proxy.server_port)+'/api/state') as r:actual=json.load(r)
            self.assertEqual(actual['ai_insights']['status'],'ready')
            self.assertEqual({k:v for k,v in actual.items() if k!='ai_insights'},state)
        finally:proxy.shutdown();proxy.server_close();upstream.shutdown();upstream.server_close()

    def test_nonrunning_equipment_values_cannot_start_advisory(self):
        b=self.binding();data=rows(140);temp,current=channel_choices();modify(data,[current],75,130,6.)
        for f in data:
            for eq in f['equipment']:
                if eq['equipment_id']==current[0]:eq['operating_state']='waiting'
        a=m.AdvisorySession(b,self.path)
        self.assertFalse(any(a.feed(f,b.config_id) for f in data))
        for f in data[:2]:
            adapted=b.adapt(f,b.config_id)
            self.assertTrue(all(v['quality']!='good' for v in adapted['measurements'] if v['equipment_id']==current[0]))
            self.assertTrue(all(v['quality']=='good' for v in f['measurements']))

    def test_streamed_large_replay_and_truncated_tail(self):
        from io import BytesIO
        payload=dict(snapshots=[rows(1)[0] for _ in range(80)],events=[],config_id=source_config()['config_id'],config_preserved=True,is_synthetic=True)
        raw=json.dumps(payload,ensure_ascii=False).encode()
        values=list(m.iter_replay(BytesIO(raw)))
        self.assertEqual(sum(k=='frame' for k,v in values),80)
        self.assertEqual(dict(v for k,v in values if k=='meta')['config_id'],payload['config_id'])
        with self.assertRaises(ValueError):list(m.iter_replay(BytesIO(raw[:-2])))

    def test_malformed_upstream_response_is_preserved(self):
        from shiftlink.pda.ai_insights import overlay_response
        self.assertEqual(overlay_response(b'not JSON',self.path),b'not JSON')
        self.assertEqual(overlay_response(b'[]',self.path),b'[]')

    def test_stream_chunks_include_utf8_and_reject_extra_document(self):
        from io import BytesIO
        class Chunks(BytesIO):
            def read(self,size=-1):return super().read(min(size,7))
        payload=dict(snapshots=rows(2),events=[{'note':'온도'}],config_id=source_config()['config_id'],config_preserved=True,is_synthetic=True)
        raw=json.dumps(payload,ensure_ascii=False).encode()
        self.assertEqual(len([v for k,v in m.iter_replay(Chunks(raw)) if k=='frame']),2)
        with self.assertRaises(ValueError):list(m.iter_replay(Chunks(raw+b' {}')))

    def test_service_cli_once_stop_and_error_publish_safe_status(self):
        from unittest.mock import patch
        import sys,signal,hashlib
        directory=Path(self.tmp.name);settings=directory/'settings.json';source=directory/'source.json';output=directory/'runtime.json'
        settings.write_text(json.dumps(config()));c=source_config();source.write_text(json.dumps(c));data=rows(80);state=data[-1]|dict(is_synthetic=True)
        batch=[('frame',f) for f in data]+[('meta',v) for v in dict(config_id=c['config_id'],config_preserved=True,is_synthetic=True).items()]
        argv=['service','--mes-url','http://source','--settings',str(settings),'--source-config',str(source),'--state-dir',str(directory/'journal'),'--output',str(output),'--once']
        old={s:signal.getsignal(s) for s in (signal.SIGTERM,signal.SIGINT)}
        try:
            with patch.object(sys,'argv',argv),patch.object(m,'SETTINGS_SHA256',hashlib.sha256(settings.read_bytes()).hexdigest()),patch.object(m,'get_json',side_effect=[state,dict(config=c,is_synthetic=True)]),patch.object(m,'replay_stream',return_value=iter(batch)):
                m.main()
            self.assertEqual(json.loads(output.read_text())['status'],'ready')
            (directory/'journal/STOP').touch()
            with patch.object(sys,'argv',argv),patch.object(m,'SETTINGS_SHA256',hashlib.sha256(settings.read_bytes()).hexdigest()),patch.object(m,'get_json',return_value=state):m.main()
            self.assertEqual(json.loads(output.read_text())['status'],'disabled')
            (directory/'journal/STOP').unlink()
            with patch.object(sys,'argv',argv),patch.object(m,'SETTINGS_SHA256',hashlib.sha256(settings.read_bytes()).hexdigest()),patch.object(m,'get_json',side_effect=[state|{'config_id':'bad'},dict(config=c,is_synthetic=True)]):
                with self.assertRaises(ValueError):m.main()
            result=json.loads(output.read_text());self.assertEqual(result['status'],'model_error');self.assertEqual(result['items'],[])
        finally:
            for s,h in old.items():signal.signal(s,h)

    def test_real_mes_starts_at_one_and_fault_mode_is_nonoperating(self):
        from unittest.mock import patch
        b=self.binding();a=m.AdvisorySession(b,self.path);data=rows(100)[1:]
        for f in data[:10]:f['line_mode']='fault'
        batch=[('frame',f) for f in data]+[('meta',v) for v in dict(config_id=b.config_id,config_preserved=True,is_synthetic=True).items()]
        with patch.object(m,'replay_stream',return_value=iter(batch)):
            self.assertEqual(m.poll(a,'http://source',data[-1]|{'is_synthetic':True})['status'],'ready')
        self.assertEqual(a.cursor,99)
        unknown=copy.deepcopy(data[-1]);unknown['sequence']=100;unknown['line_mode']='unknown_mode'
        with self.assertRaises(ValueError):a.feed(unknown,b.config_id)

    def test_pause_without_new_sensor_sequence_clears_model_warmth(self):
        b=self.binding();a=m.AdvisorySession(b,self.path);data=rows(80)
        for f in data:a.feed(f,b.config_id)
        m.poll(a,'http://unused',data[-1]|{'is_synthetic':True,'line_mode':'paused'})
        self.assertFalse(a.detector.was_ready);self.assertEqual(a.detector.warm,0)
        a.flush();self.assertFalse(m.AdvisorySession(b,self.path).detector.was_ready)

    def test_all_bad_measurements_and_common_hold_are_not_healthy(self):
        b=self.binding();a=m.AdvisorySession(b,self.path);data=rows(100)
        for f in data[:80]:a.feed(f,b.config_id)
        f=copy.deepcopy(data[80])
        for sample in f['measurements']:sample['quality']='bad'
        a.feed(f,b.config_id);self.assertEqual(a.report(f)['status'],'unavailable')

if __name__=='__main__':unittest.main()
