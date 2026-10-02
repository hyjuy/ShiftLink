"""G3: a PDA POST is durable across actual HTTP server replacement."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from shiftlink.mes.server import MesService, _Handler
from shiftlink.mes.storage import MesStorage


class HandoverHttpTests(unittest.TestCase):
    def start_server(self, database):
        self.service = MesService(Path('docs/data/reference/00_plant_and_relations.json'), MesStorage(database))
        handler = type('HandoverHandler', (_Handler,), {'service': self.service})
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.worker = threading.Thread(target=self.server.serve_forever)
        self.worker.start()

    def stop_server(self):
        self.server.shutdown()
        self.worker.join()
        self.server.server_close()
        self.service.storage.close()

    def post(self, payload):
        request = Request(f'http://127.0.0.1:{self.server.server_port}/api/handover',
                          json.dumps(payload).encode(), {'Content-Type': 'application/json'})
        with urlopen(request, timeout=5) as response:
            return json.load(response)

    def test_restart_retry_and_conflict(self):
        payload = {'handover_id': 'HO-HTTP-1', 'memo_text': 'Check GR-01 before startup'}
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'mes.sqlite3'
            self.start_server(database)
            try:
                first = self.post(payload)
                self.assertFalse(first['duplicate'])
            finally:
                self.stop_server()
            self.start_server(database)
            try:
                retry = self.post(payload)
                self.assertTrue(retry['duplicate'])
                self.assertEqual(retry['created_at'], first['created_at'])
                self.assertEqual(self.service.storage.get_handover(payload['handover_id'])['payload'], payload)
                self.assertEqual(self.service.storage.connection.execute('SELECT COUNT(*) FROM handover_outbox').fetchone()[0], 1)
                with self.assertRaises(HTTPError) as caught:
                    self.post({**payload, 'memo_text': 'Changed note'})
                self.assertEqual(caught.exception.code, 409)
                caught.exception.close()
                with self.assertRaises(HTTPError) as caught:
                    self.post({'handover_id': 'HO-invalid', 'memo_text': ''})
                self.assertEqual(caught.exception.code, 400)
                caught.exception.close()
                long_note = {'handover_id': 'HO-long', 'memo_text': '점검' * 2000}
                self.assertFalse(self.post(long_note)['duplicate'])
            finally:
                self.stop_server()
