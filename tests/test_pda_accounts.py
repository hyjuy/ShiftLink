import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from shiftlink.mes.accounts import Accounts
from shiftlink.mes.server import _Handler


class AccountTests(unittest.TestCase):
    def test_registration_login_failure_and_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory) / 'accounts.json'
            handler = type('AccountHandler', (_Handler,), {'accounts': Accounts(store)})
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f'http://127.0.0.1:{server.server_port}'

            def request(path, data=None, origin=None, token=None):
                headers = {'Content-Type': 'application/json'}
                if origin:
                    headers['Origin'] = origin
                if token:
                    headers['Authorization'] = 'Bearer ' + token
                req = urllib.request.Request(base + path,
                    data=json.dumps(data).encode() if data is not None else None, headers=headers)
                try:
                    res = urllib.request.urlopen(req)
                except urllib.error.HTTPError as error:
                    res = error
                with res:
                    return res.status, json.load(res)

            try:
                self.assertEqual(request('/api/admin/accounts')[0], 401)
                account = {'id': 'TEST-01', 'name': '테스트', 'password': 'test-only-password'}
                self.assertEqual(request('/api/account/setup', account)[0], 404)
                self.assertEqual(request('/api/admin/accounts', account)[0], 401)
                self.assertEqual(request('/api/admin/login', {'id':'admin','password':'admin'}, 'http://other.invalid')[0], 403)
                status, login = request('/api/admin/login', {'id':'admin','password':'admin'})
                self.assertEqual(status, 200)
                token = login['token']
                self.assertEqual(request('/api/admin/accounts', account, token=token)[0], 201)
                self.assertNotIn(account['password'], store.read_text())
                self.assertEqual(store.stat().st_mode & 0o777, 0o600)
                self.assertEqual(request('/api/admin/accounts', account, token=token)[0], 409)
                status, listing = request('/api/admin/accounts', token=token)
                self.assertEqual(status, 200)
                self.assertEqual(len(listing['accounts']), 2)
                self.assertNotIn('hash', json.dumps(listing))
                self.assertEqual(request('/api/account/login', {**account, 'password':'wrong'})[0], 401)
                self.assertEqual(request('/api/account/login', account), (200, {'operator':{'id':'TEST-01','name':'테스트'}}))
                self.assertEqual(request('/api/account/login', {'id':'admin','password':'admin'})[0], 401)
                self.assertEqual(request('/api/admin/logout', {}, token=token)[0], 200)
                self.assertEqual(request('/api/admin/accounts', account, token=token)[0], 401)
                # Isolate throttle checks from earlier rejected credentials.
                handler.accounts.failures.clear()
                for _ in range(5):
                    self.assertEqual(request('/api/account/login', {**account,'password':'wrong'})[0], 401)
                self.assertEqual(request('/api/account/login', account)[0], 429)
            finally:
                server.shutdown()
                server.server_close()
