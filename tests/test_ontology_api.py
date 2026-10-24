"""Authenticated, opt-in ontology reads must not enter the query pipeline."""
import json
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

import pytest

from shiftlink.mes import ontology_api
from shiftlink.mes.accounts import Accounts
from shiftlink.mes.server import _Handler
from test_ontology_shadow import arguments, service, bundle, default_off


@pytest.fixture
def api(arguments, service, tmp_path, monkeypatch):
    for name, value in [('DB', arguments['database']), ('CATALOG', arguments['catalog']),
                        ('MANIFEST', {k: arguments[k] for k in ('source_namespace', 'config_catalog_hashes')})]:
        if name != 'DB':
            path = tmp_path / (name + '.json')
            path.write_text(json.dumps(value), encoding='utf-8')
            value = str(path)
        monkeypatch.setenv('SHIFTLINK_HPU_ONTOLOGY_' + name, value)
    accounts = Accounts(tmp_path / 'accounts.json')
    _, login = accounts.request('POST', '/api/admin/login', {'id':'admin', 'password':'admin'})
    accounts.request('POST', '/api/admin/accounts', {'id':'TEST-01','name':'test','password':'test-password'}, token=login['token'])
    _, operator = accounts.request('POST', '/api/account/login', {'id':'TEST-01','password':'test-password'})
    handler = type('OntologyHandler', (_Handler,), {'service':service, 'accounts':accounts})
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    route = '/api/incidents/' + arguments['incident_id'] + '/ontology'
    def request(suffix='', token=login['token'], path=None):
        req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}' + (path or route) + suffix,
                                     headers={'Authorization':'Bearer ' + token})
        try:
            response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)
    yield request, operator['token']
    server.shutdown()
    server.server_close()
    thread.join()


def test_off_and_shadow_do_not_read(api, monkeypatch):
    def forbidden(*a, **kw): raise AssertionError('must not read')
    monkeypatch.setattr(ontology_api, 'run_shadow', forbidden)
    for mode in ('off','shadow'):
        monkeypatch.setenv('SHIFTLINK_HPU_ONTOLOGY', mode)
        assert api[0]()[0] == 404


def test_authentication_before_data_access(api, monkeypatch):
    monkeypatch.setenv('SHIFTLINK_HPU_ONTOLOGY','explain')
    def forbidden(*a, **kw): raise AssertionError('must not read')
    monkeypatch.setattr(ontology_api, 'run_shadow', forbidden)
    for token in ('', 'bad-token', api[1]):
        assert api[0](token=token)[0] == 401


def test_graph_scope_reasons_and_readonly(api, arguments, service, monkeypatch):
    monkeypatch.setenv('SHIFTLINK_HPU_ONTOLOGY','explain')
    before = list(service.storage.connection.iterdump())
    status, graph = api[0]()
    assert status == 200
    assert graph['scope'] == {'source_namespace':arguments['source_namespace'], 'incident_id':arguments['incident_id']}
    assert graph['nodes'] and graph['edges'] and graph['snapshot_hash']
    assert graph['unresolved'] == []
    assert list(service.storage.connection.iterdump()) == before
    assert api[0](path='/api/incidents/INC-not-present/ontology')[0] == 404
    assert api[0]('?asset_id=OTHER')[0] == 404
    manifest = {'source_namespace':arguments['source_namespace'], 'config_catalog_hashes':{}}
    from pathlib import Path
    import os
    Path(os.environ['SHIFTLINK_HPU_ONTOLOGY_MANIFEST']).write_text(json.dumps(manifest), encoding='utf-8')
    status, graph = api[0]()
    assert status == 200 and not graph['nodes']
    assert any(r['reason']=='unverified_catalog_binding' for r in graph['unresolved'])


def test_paging_requires_same_snapshot(api, monkeypatch):
    monkeypatch.setenv('SHIFTLINK_HPU_ONTOLOGY','explain')
    status, first = api[0]('?limit=1')
    assert status == 200 and first['page']['next_offset'] == 1
    assert len(first['nodes']) == 1
    assert api[0]('?limit=1&offset=1')[0] == 400
    assert api[0]('?limit=1&offset=1&snapshot_hash=old')[0] == 409
    status, second = api[0]('?limit=1&offset=1&snapshot_hash=' + first['snapshot_hash'])
    assert status == 200 and second['snapshot_hash'] == first['snapshot_hash']
    assert second['nodes'][0]['id'] != first['nodes'][0]['id']


@pytest.mark.parametrize('query', ['?limit=0','?limit=101','?offset=-1','?limit=x','?db=secret', '?limit=1&limit=2'])
def test_bad_parameters(api, monkeypatch, query):
    monkeypatch.setenv('SHIFTLINK_HPU_ONTOLOGY','explain')
    assert api[0](query)[0] == 400


def test_safe_unavailable_and_query_unchanged(api, service, monkeypatch):
    from copy import deepcopy
    monkeypatch.setenv('SHIFTLINK_HPU_ONTOLOGY','explain')
    calls=[]
    original=service.query_pipeline.run
    def capture(payload):
        calls.append(deepcopy(payload))
        return original(payload)
    monkeypatch.setattr(service.query_pipeline, 'run', capture)
    body={'question':'압력이 낮고 경보가 발생했습니다','equipment_id':'EQ-0001'}
    first=service.query(body)
    assert api[0]()[0] == 200
    monkeypatch.setenv('SHIFTLINK_HPU_ONTOLOGY_CATALOG','SECRET-missing-file')
    status, error=api[0]()
    assert status == 503 and 'SECRET' not in json.dumps(error)
    second=service.query(body)
    assert calls[0] == calls[1] and len(calls)==2
    assert {k:v for k,v in first.items() if k!='query_id'} == {k:v for k,v in second.items() if k!='query_id'}
