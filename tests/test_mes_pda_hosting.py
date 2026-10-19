"""Jetson can disable PDA assets while retaining MES administration and APIs."""
from http.server import ThreadingHTTPServer
from threading import Thread
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from shiftlink.mes.server import _Handler


@pytest.mark.parametrize('enabled', [True, False])
def test_pda_hosting_does_not_disable_mes(tmp_path, monkeypatch, enabled):
    monkeypatch.setenv('SHIFTLINK_SERVE_PDA', '1' if enabled else '0')
    for name in ('index.html', 'pda.html', 'pda.js', 'knowledge-candidates.html', 'candidate-review.js'):
        (tmp_path/name).write_text('local test fixture', encoding='utf-8')
    handler=type('HostingHandler', (_Handler,), {'web_root':tmp_path,
        'service':SimpleNamespace(state=lambda:{'healthy':True})})
    server=ThreadingHTTPServer(('127.0.0.1',0),handler)
    worker=Thread(target=server.serve_forever);worker.start()
    def status(route):
        try:
            with urlopen(f'http://127.0.0.1:{server.server_port}'+route,timeout=5) as response:
                return response.status
        except HTTPError as error:
            return error.code
    try:
        for route in ('/', '/api/state', '/knowledge-candidates.html', '/static/candidate-review.js'):
            assert status(route)==200,route
        for route in ('/pda.html','/pda.html?version=1','/static/pda.js','/static/alias/pda.js'):
            assert status(route)==(200 if enabled else 404),route
    finally:
        server.shutdown();worker.join();server.server_close()
