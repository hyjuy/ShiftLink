"""Exercise real HTTP requests against the same handler used by the UI."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from shiftlink.mes.server import MesService, _Handler
from shiftlink.mes.storage import MesStorage


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.service = MesService(Path('docs/data/00_plant_and_relations.json'))
        handler = type('TestHandler', (_Handler,), {
            'service': self.service, 'web_root': Path('shiftlink/mes/web')})
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.worker = threading.Thread(target=self.server.serve_forever)
        self.worker.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.worker.join()
        self.server.server_close()
        self.service.storage.close()

    def get(self, path):
        with urlopen(self.base + path, timeout=5) as response:
            return response.read()

    def post(self, payload):
        request = Request(self.base + '/api/control', json.dumps(payload).encode(),
                          {'Content-Type': 'application/json'})
        with urlopen(request, timeout=5) as response:
            return json.load(response)

    def test_live_history_export_and_reset(self):
        self.assertIn(b'line-map', self.get('/'))
        self.assertIn(b'function', self.get('/static/app.js'))
        self.assertTrue(json.loads(self.get('/api/catalog'))['is_synthetic'])
        self.post({'command': 'start'})
        self.service.tick()
        run_id = json.loads(self.get('/api/state'))['run_id']
        self.post({'command': 'scenario', 'scenario_id': 'hydraulic_fault'})
        self.service.tick()
        events = json.loads(self.get('/api/events?after_sequence=1'))
        self.assertEqual(events['run_id'], run_id)
        self.assertIn('alarm_raised', [event['event_type'] for event in events['events']])
        replay = json.loads(self.get(f'/api/runs/{run_id}/replay'))
        self.assertEqual(replay['snapshots'][-1]['line_mode'], 'fault')
        self.assertIn(b'snapshot', self.get('/api/export?format=jsonl'))
        self.assertTrue(self.get('/api/export?format=csv').startswith(b'kind,run_id'))
        reset = self.post({'command': 'reset'})
        self.assertNotEqual(reset['run_id'], run_id)
        self.assertEqual(len(json.loads(self.get('/api/runs'))['runs']), 2)
        self.assertEqual(json.loads(self.get(f'/api/runs/{run_id}/replay')), replay)

    def test_invalid_requests_return_json_errors(self):
        for payload in ([], {'command': 'unknown'}, {'command': 'speed', 'speed': None}):
            with self.assertRaises(HTTPError) as caught:
                self.post(payload)
            self.assertEqual(caught.exception.code, 400)
            self.assertIn('error', json.load(caught.exception))
        with self.assertRaises(HTTPError) as caught:
            self.get('/api/runs/missing/replay')
        self.assertEqual(caught.exception.code, 404)

    def test_recovery_actions_through_http_and_saved_replay(self):
        self.post({'command': 'start'})
        state = self.post({'command': 'scenario', 'scenario_id': 'gearbox_leak'})
        self.service.tick()
        self.assertEqual(state['recovery']['stage'], 'actions')
        with self.assertRaises(HTTPError) as caught:
            self.post({'command': 'recover'})
        self.assertEqual(caught.exception.code, 400)
        for action in state['recovery']['actions']:
            state = self.post({'command': 'recovery_action', 'action_id': action['action_id']})
            self.service.tick()
        self.assertEqual(state['recovery']['stage'], 'ready')
        state = self.post({'command': 'recover'})
        self.assertEqual(state['recovery']['stage'], 'stabilizing')
        self.service.tick(); self.service.tick()
        replay = json.loads(self.get(f"/api/runs/{state['run_id']}/replay"))
        self.assertEqual(replay['snapshots'][-1]['recovery']['stage'], 'completed')
        self.assertTrue(replay['snapshots'][-1]['components'])

    def post_json(self, path, payload):
        request = Request(self.base + path, json.dumps(payload).encode(),
                          {'Content-Type': 'application/json'})
        with urlopen(request, timeout=5) as response:
            return json.load(response)

    def test_config_endpoints_validate_apply_and_replay_linkage(self):
        config = json.loads(self.get('/api/config'))['config']
        self.assertTrue(config['route'])
        self.assertTrue(config['layout'])
        state = json.loads(self.get('/api/state'))
        self.assertEqual(state['config_id'], config['config_id'])

        # stored config is retrievable for replay rendering
        stored = json.loads(self.get(f"/api/configs/{config['config_id']}"))['config']
        self.assertEqual(stored['config_id'], config['config_id'])

        # validate: broken draft reports concrete errors, nothing changes
        broken = json.loads(json.dumps(config)); broken['route'] = ['EQ-MISSING']
        verdict = self.post_json('/api/config/validate', {'draft': broken})
        self.assertFalse(verdict['valid']); self.assertTrue(verdict['errors'])

        # apply while running -> 409, engine keeps its run
        self.post({'command': 'start'}); self.service.tick()
        run_before = json.loads(self.get('/api/state'))['run_id']
        with self.assertRaises(HTTPError) as caught:
            self.post_json('/api/config/apply', {'base_config_id': config['config_id'], 'draft': config})
        self.assertEqual(caught.exception.code, 409)

        # paused apply with an HPU asset swap -> new run, old replay intact
        self.post({'command': 'pause'})
        swapped = json.loads(json.dumps(config))
        for item in swapped['equipment']:
            if item['code'].startswith('HPU'):
                item['asset_id'] = 'AS-EQ-0001-002'; item['name'] += ' 교체'
        swapped['version_label'] = 'B-hpu-swap'
        result = self.post_json('/api/config/apply', {
            'base_config_id': config['config_id'], 'draft': swapped,
            'reason': 'HPU 교체', 'actor': '테스트(자기기입)'})
        self.assertNotEqual(result['run_id'], run_before)
        replay = json.loads(self.get(f'/api/runs/{run_before}/replay'))
        self.assertEqual(replay['config_id'], config['config_id'])
        self.assertTrue(replay['config_preserved'])

        # stale base now conflicts
        with self.assertRaises(HTTPError) as caught:
            self.post_json('/api/config/apply', {'base_config_id': config['config_id'], 'draft': config})
        self.assertEqual(caught.exception.code, 409)

    def test_file_database_survives_service_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'mes.sqlite3'
            first = MesService(Path('docs/data/00_plant_and_relations.json'), MesStorage(database))
            first.control({'command': 'start'})
            first.tick()
            run_id = first.engine.run.run_id
            expected = first.replay(run_id, -1)
            first.storage.close()
            second = MesService(Path('docs/data/00_plant_and_relations.json'), MesStorage(database))
            try:
                self.assertEqual(second.replay(run_id, -1), expected)
            finally:
                second.storage.close()
