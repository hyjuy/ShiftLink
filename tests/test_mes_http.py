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
        self.service = MesService(Path('docs/00_plant_and_relations.json'))
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

    def test_file_database_survives_service_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'mes.sqlite3'
            first = MesService(Path('docs/00_plant_and_relations.json'), MesStorage(database))
            first.control({'command': 'start'})
            first.tick()
            run_id = first.engine.run.run_id
            expected = first.replay(run_id, -1)
            first.storage.close()
            second = MesService(Path('docs/00_plant_and_relations.json'), MesStorage(database))
            try:
                self.assertEqual(second.replay(run_id, -1), expected)
            finally:
                second.storage.close()
