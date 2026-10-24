"""Shadow diagnostics are opt-in and never enter the answer or business storage."""
from copy import deepcopy
import json
import subprocess
import sys

import pytest

from shiftlink.mes import ontology_shadow as shadow
from shiftlink.mes.hpu_ontology import main
from test_hpu_ontology import bundle, service


@pytest.fixture(autouse=True)
def default_off(monkeypatch):
    monkeypatch.delenv('SHIFTLINK_HPU_ONTOLOGY', raising=False)


@pytest.fixture
def arguments(service, bundle):
    return dict(database=service.storage.connection.execute('PRAGMA database_list').fetchone()[2],
                incident_id=bundle['incident']['incident_id'], source_namespace=bundle['source_namespace'],
                catalog=service.catalog.data, config_catalog_hashes=bundle['config_catalog_hashes'])


def test_default_and_explicit_off_do_no_io(arguments, monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError('Disabled shadow must not read or project')
    monkeypatch.setattr(shadow, 'read_incident_bundle', forbidden)
    monkeypatch.setattr(shadow, 'project_incident', forbidden)
    output = tmp_path / 'disabled.json'
    for mode in (None, 'off'):
        result = shadow.run_shadow(**arguments, mode=mode, output=output)
        assert result == {'mode': 'off', 'status': 'disabled'}
    assert not output.exists()


def test_shadow_records_connections_reasons_and_stable_graph(arguments, tmp_path):
    output = tmp_path / 'diagnostics.json'
    result = shadow.run_shadow(**arguments, mode='shadow', output=output)
    assert result['status'] == 'completed' and result['mode'] == 'shadow'
    assert result['summary']['node_counts']['Action'] == 2
    assert result['summary']['edge_counts']['HAS_ACTION'] == 2
    assert result['summary']['unresolved_count'] == 0
    assert result['summary']['projection_state'] == 'connected'
    assert result['timings_ms']['read'] >= 0 and result['timings_ms']['project'] >= 0
    assert json.loads(output.read_text(encoding='utf-8')) == result
    repeated = shadow.run_shadow(**arguments, mode='shadow')
    assert repeated['graph'] == result['graph']
    assert 'query_response' not in result


def test_no_attestation_is_visible_as_unresolved_not_a_successful_connection(arguments):
    result = shadow.run_shadow(**{**arguments, 'config_catalog_hashes': {}}, mode='shadow')
    assert result['status'] == 'completed'
    assert result['summary']['projection_state'] == 'unresolved'
    assert result['summary']['unresolved_by_reason']['unverified_catalog_binding'] >= 1
    assert result['graph']['unresolved']
    assert not result['graph']['nodes']


def test_truncated_and_outside_scope_are_distinguishable(arguments, monkeypatch):
    original = shadow.project_incident
    def truncated(*args, **kwargs):
        graph = original(*args, **kwargs)
        graph['truncated'] = True
        return graph
    monkeypatch.setattr(shadow, 'project_incident', truncated)
    assert shadow.run_shadow(**arguments, mode='shadow')['summary']['projection_state'] == 'truncated'
    monkeypatch.setattr(shadow, 'project_incident', original)
    other = shadow.run_shadow(**arguments, mode='shadow', equipment_type='PDP')
    assert other['summary']['projection_state'] == 'empty'
    assert other['summary']['node_counts'] == {}


def test_environment_can_only_enable_separate_shadow_runner(arguments, monkeypatch):
    monkeypatch.setenv('SHIFTLINK_HPU_ONTOLOGY', 'shadow')
    assert shadow.run_shadow(**arguments)['status'] == 'completed'
    assert shadow.run_shadow(**arguments, mode='off')['status'] == 'disabled'
    monkeypatch.setenv('SHIFTLINK_HPU_ONTOLOGY', 'explain')
    result = shadow.run_shadow(**arguments)
    assert result['status'] == 'error' and result['error']['stage'] == 'configuration'


@pytest.mark.parametrize('stage', ['read', 'project'])
def test_diagnostic_failures_are_safe_and_do_not_modify_business_data(arguments, service, monkeypatch, stage):
    before = list(service.storage.connection.iterdump())
    def broken(*args, **kwargs):
        raise RuntimeError('PASSWORD-DO-NOT-PRINT connection details')
    target = 'read_incident_bundle' if stage == 'read' else 'project_incident'
    monkeypatch.setattr(shadow, target, broken)
    result = shadow.run_shadow(**arguments, mode='shadow')
    assert result['status'] == 'error'
    assert result['error'] == {'stage': stage, 'type': 'RuntimeError'}
    assert 'PASSWORD-DO-NOT-PRINT' not in json.dumps(result)
    assert 'graph' not in result
    assert list(service.storage.connection.iterdump()) == before


def test_output_never_overwrites_existing_files_including_source_database(arguments, tmp_path):
    path = tmp_path / 'existing.json'
    path.write_text('keep', encoding='utf-8')
    for output in (path, arguments['database']):
        result = shadow.run_shadow(**arguments, mode='shadow', output=output)
        assert result['status'] == 'error' and result['error']['stage'] == 'write'
        assert result['error']['type'] == 'FileExistsError'
    assert path.read_text(encoding='utf-8') == 'keep'


def test_shadow_does_not_change_query_payload_results_calls_or_database(arguments, service, monkeypatch):
    calls = []
    original = service.query_pipeline.run
    def capture(payload):
        calls.append(deepcopy(payload))
        return original(payload)
    monkeypatch.setattr(service.query_pipeline, 'run', capture)
    question = {'question':'압력이 낮고 경보가 발생했습니다', 'equipment_id':'EQ-0001'}
    first = service.query(question)
    stored = list(service.storage.connection.iterdump())
    for mode in ('off', 'shadow'):
        assert shadow.run_shadow(**arguments, mode=mode)['status'] in {'disabled', 'completed'}
        assert len(calls) == 1
        assert list(service.storage.connection.iterdump()) == stored
    second = service.query(question)
    assert calls[0] == calls[1]
    assert {k:v for k,v in first.items() if k!='query_id'} == {k:v for k,v in second.items() if k!='query_id'}
    assert 'ontology' not in calls[0] and 'shadow' not in second


def test_off_cli_ignores_unreadable_input_and_creates_nothing(tmp_path, capsys):
    output = tmp_path / 'off.json'
    assert main(['--mode','off','--db',str(tmp_path/'missing'),'--output',str(output)]) == 0
    assert json.loads(capsys.readouterr().out) == {'mode':'off','status':'disabled'}
    assert not output.exists()


def test_real_cli_writes_full_artifact_but_prints_only_summary(arguments, tmp_path):
    catalog = tmp_path/'catalog.json'
    catalog.write_text(json.dumps(arguments['catalog']), encoding='utf-8')
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps({k:arguments[k] for k in ('source_namespace','config_catalog_hashes')}), encoding='utf-8')
    output = tmp_path/'shadow.json'
    command = [sys.executable,'-m','shiftlink.mes.hpu_ontology','--mode','shadow',
               '--db',arguments['database'],'--incident-id',arguments['incident_id'],
               '--catalog',str(catalog),'--manifest',str(manifest),'--output',str(output)]
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=60)
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert 'graph' not in summary
    artifact = json.loads(output.read_text(encoding='utf-8'))
    assert artifact['graph']['nodes'] and summary['summary'] == artifact['summary']
    assert '필터' not in result.stdout


def test_cli_missing_or_bad_inputs_return_nonzero(tmp_path, capsys):
    with pytest.raises(SystemExit) as error:
        main(['--mode','shadow'])
    assert error.value.code == 2
    capsys.readouterr()
    path = tmp_path/'bad.json'
    path.write_text('{bad', encoding='utf-8')
    assert main(['--mode','shadow','--db','missing','--incident-id','INC-x',
                 '--catalog',str(path),'--manifest',str(path)]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'error' and result['error']['stage'] == 'input'
