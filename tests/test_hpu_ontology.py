"""Offline incident projection contracts; no models or production database."""
from copy import deepcopy
import json
import sqlite3

import pytest

from shiftlink.mes.incident_ontology import content_hash, project_incident, read_incident_bundle
from shiftlink.mes.hpu_ontology import project_hpu
from test_work_report_reuse_harness import service, ask
from test_work_report_capture import captured


@pytest.fixture
def bundle(service):
    query = ask(service)
    saved = service.record_work_report(captured(service, query_id=query['query_id']))
    incident_id = saved['incidents'][0]['incident_id']
    return read_incident_bundle(
        service.storage.connection.execute('PRAGMA database_list').fetchone()[2], incident_id,
        source_namespace='synthetic-test', catalog=service.catalog.data,
        config_catalog_hashes={service.active_config.config_id: content_hash(service.catalog.data)})


def nodes(graph, kind):
    return [n for n in graph['nodes'] if n['type'] == kind]


def relations(graph, kind):
    return [e for e in graph['edges'] if e['type'] == kind]


def test_service_to_readonly_bundle_to_graph_preserves_originals(service, bundle):
    before = list(service.storage.connection.iterdump())
    original = deepcopy(bundle)
    graph = project_hpu(bundle)
    assert len(nodes(graph, 'Asset')) == len(nodes(graph, 'Incident')) == 1
    assert len(nodes(graph, 'Action')) == 2
    assert len(relations(graph, 'HAS_ACTION')) == 2
    assert len(relations(graph, 'NEXT_RECORDED_STEP')) == 1
    assert nodes(graph, 'Observation')
    normal = [n for n in nodes(graph, 'Outcome') if n['properties']['outcome_kind'] == 'normal_operation']
    assert normal[0]['properties']['minutes'] == 120
    assert normal[0]['provenance']['claim_kind'] == 'worker_report'
    assert all(n['properties']['scope'] in {'query_snapshot', 'save_snapshot'} for n in nodes(graph, 'Observation'))
    assert not relations(graph, 'SUPPORTED_BY'), 'Save-time sensors do not prove 120-minute normal operation'
    assert bundle == original
    assert list(service.storage.connection.iterdump()) == before
    assert not nodes(graph, 'CardVersion'), 'Stages 1-2 must not publish or expose draft cards'


def test_projection_is_deterministic_independent_and_versioned(bundle):
    first = project_hpu(bundle)
    assert first == project_hpu(json.loads(json.dumps(bundle)))
    reordered = deepcopy(bundle)
    reordered['queries'].reverse()
    assert project_hpu(reordered) == first
    first['nodes'].clear()
    assert project_hpu(bundle)['nodes']
    changed = deepcopy(bundle)
    changed['reports'][0]['record']['action_steps'][0]['observed_result'] = '원문 변경'
    assert project_hpu(changed)['snapshot_hash'] != project_hpu(bundle)['snapshot_hash']
    assert project_hpu({**bundle, 'source_namespace': 'other'})['snapshot_hash'] != project_hpu(bundle)['snapshot_hash']


@pytest.mark.parametrize('damage', ['asset', 'config', 'run', 'incident'])
def test_wrong_query_context_never_attaches_observations(bundle, damage):
    damaged = deepcopy(bundle)
    context = damaged['queries'][0]['payload']['query_context']
    if damage == 'run':
        damaged['queries'][0]['payload']['evidence']['run_id'] = 'another-run'
    else:
        context[{'asset': 'asset_id', 'config': 'config_id', 'incident': 'incident_id'}[damage]] = 'other'
    graph = project_hpu(damaged)
    assert not [n for n in nodes(graph, 'Observation') if n['properties']['scope'] == 'query_snapshot']
    assert graph['unresolved']


@pytest.mark.parametrize('damage', ['catalog_hash', 'missing_config', 'asset', 'type'])
def test_unknown_or_conflicting_historical_binding_is_not_inferred(bundle, damage):
    b = deepcopy(bundle)
    cfg = b['incident']['config_id']
    if damage == 'catalog_hash': b['config_catalog_hashes'][cfg] = 'wrong'
    if damage == 'missing_config': b['configurations'].clear()
    if damage == 'asset': b['incident']['assets']['EQ-0001'] = 'replacement'
    if damage == 'type': b['catalog']['equipment'][0]['equipment_type_id'] = 'missing'
    graph = project_hpu(b)
    assert not nodes(graph, 'Asset')
    assert graph['unresolved']


def test_same_position_replacement_cannot_move_old_incident(bundle):
    b = deepcopy(bundle)
    current = deepcopy(b['configurations'][b['incident']['config_id']])
    current['equipment'][0]['asset_id'] = 'AS-REPLACEMENT'
    b['configurations']['current-only'] = current
    graph = project_hpu(b)
    assert {n['properties']['asset_id'] for n in nodes(graph, 'Asset')} == set(b['incident']['assets'].values())


def test_equipment_selection_uses_fk_and_common_projector(bundle):
    b = deepcopy(bundle)
    for row in b['catalog']['equipment_types']:
        if row['type_code'] == 'HPU': row['type_code'] = 'PDP'
    b['config_catalog_hashes'][b['incident']['config_id']] = content_hash(b['catalog'])
    assert not project_hpu(b)['nodes']
    other = project_incident(b, equipment_type='PDP')
    assert len(nodes(other, 'Asset')) == 1
    assert len(nodes(other, 'Action')) == 2
    assert other['equipment_type'] == 'PDP'


def test_multi_equipment_actions_are_not_assigned_to_one_hpu(bundle):
    b = deepcopy(bundle)
    b['reports'][0]['record']['equipment'].append('EQ-0002')
    graph = project_hpu(b)
    assert not nodes(graph, 'Action')
    assert any(x['reason'] == 'ambiguous_action_equipment' for x in graph['unresolved'])


def test_raw_steps_missing_time_and_sensor_quality_are_not_upgraded(bundle):
    b = deepcopy(bundle)
    steps = b['reports'][0]['record']['action_steps']
    steps.insert(0, {'action': '', 'observed_result': '', 'failed': False})
    steps[1].update(worker='작업자 원문', performed_at='2026-10-16T09:20', failed=False)
    sensor = b['reports'][0]['sensor_evidence']['measurements'][0]
    sensor.update(value=None, quality='bad', observed_at=None)
    graph = project_hpu(b)
    action = sorted(nodes(graph, 'Action'), key=lambda n:n['properties']['ordinal'])[0]
    assert action['properties']['ordinal'] == 1
    assert action['properties']['time_basis'] == 'unknown'
    assert action['properties']['failed_raw'] is False
    assert 'success' not in action['properties']
    assert '작업자 원문' not in json.dumps(graph, ensure_ascii=False), 'Names stay in source records'
    bad = [n for n in nodes(graph, 'Observation') if n['properties'].get('quality') == 'bad']
    assert bad and bad[0]['properties']['value'] is None
    assert bad[0]['properties']['time_basis'] == 'unknown'


def add_session(bundle):
    b = deepcopy(bundle)
    run = b['reports'][0]['sensor_evidence']['run_id']
    b['reports'][0]['record']['source_session_id'] = 'RS-test'
    b['sessions'] = [{'session_id':'RS-test', 'equipment_id':'EQ-0001', 'status':'open', 'data':{
        'run_id':run, 'before':{'run_id':run, 'equipment_id':'EQ-0001', 'simulated_at':'2026-10-16T01:00:00+00:00',
                               'measurements':[], 'alarms':[]},
        'steps':[{'action':'점검', 'simulated_at':'2026-10-16T01:01:00+00:00','measurements':[], 'result_text':'변화 미확인'}],
        'after':{'run_id':run, 'equipment_id':'EQ-0001','simulated_at':'2026-10-16T01:02:00+00:00','measurements':[]},
        'verdict':{'verdict':'unresolved','text':'MES 복구 미확인','check':{'recovered':False}}}}]
    return b


def test_worker_outcome_and_mes_verdict_are_separate_and_session_revision_changes_id(bundle):
    b = add_session(bundle)
    graph = project_hpu(b)
    assert {n['provenance']['claim_kind'] for n in nodes(graph, 'Outcome')} == {'worker_report','mes_assessment'}
    mes = [n for n in nodes(graph,'Outcome') if n['properties']['outcome_kind']=='mes_assessment']
    assert mes[0]['properties']['recovered'] is False
    ids = {n['id'] for n in nodes(graph,'Action') if n['provenance']['source_ref']['kind']=='session'}
    b['sessions'][0]['data']['steps'].insert(0, {'action':'추가 단계','measurements':[]})
    new_ids = {n['id'] for n in nodes(project_hpu(b),'Action') if n['provenance']['source_ref']['kind']=='session'}
    assert ids.isdisjoint(new_ids)


@pytest.mark.parametrize('damage',['unlinked','run','asset'])
def test_legacy_or_unlinked_sessions_are_quarantined(bundle, damage):
    b=add_session(bundle)
    if damage=='unlinked': b['reports'][0]['record'].pop('source_session_id')
    if damage=='run': b['sessions'][0]['data']['run_id']='other'
    if damage=='asset': b['sessions'][0]['data']['before']['asset_id']='other'
    graph=project_hpu(b)
    assert not [n for n in nodes(graph,'Action') if n['provenance']['source_ref']['kind']=='session']
    assert graph['unresolved']


def test_private_labels_and_advisory_do_not_enter_projection(bundle):
    b=deepcopy(bundle)
    b['ground_truth']={'secret_cause':'PRIVATE-LABEL'}
    b['reports'][0]['record'].update(scenario_id='PRIVATE-LABEL', pi_analysis={'cause':'PRIVATE-LABEL'})
    b['queries'][0]['payload']['evidence']['ground_truth']='PRIVATE-LABEL'
    graph=project_hpu(b)
    assert 'PRIVATE-LABEL' not in json.dumps(graph)
    assert not {'CAUSES','CURES','SAFE_TO_RUN'} & {e['type'] for e in graph['edges']}


def test_adapter_is_readonly_does_not_create_missing_files_and_reports_limits(service, bundle, tmp_path):
    db=service.storage.connection.execute('PRAGMA database_list').fetchone()[2]
    before=list(service.storage.connection.iterdump())
    args=dict(source_namespace='synthetic-test',catalog=service.catalog.data,
              config_catalog_hashes=bundle['config_catalog_hashes'])
    original=read_incident_bundle(db,bundle['incident']['incident_id'],**args)
    assert original==bundle
    assert list(service.storage.connection.iterdump())==before
    missing=tmp_path/'absent.sqlite3'
    with pytest.raises(sqlite3.OperationalError):read_incident_bundle(missing,'missing',**args)
    assert not missing.exists()
    with pytest.raises(KeyError):read_incident_bundle(db,'missing',**args)
    with pytest.raises(ValueError):read_incident_bundle(db,bundle['incident']['incident_id'],max_records=True,**args)
    with pytest.raises(ValueError):read_incident_bundle(db,bundle['incident']['incident_id'],source_namespace='',catalog={})


def test_adapter_truncation_is_explicit(service,bundle):
    db=service.storage.connection.execute('PRAGMA database_list').fetchone()[2]
    q=deepcopy(bundle['queries'][0]['payload'])
    q['query_context']['incident_id']=bundle['incident']['incident_id']
    service.storage.save_query(q)
    limited=read_incident_bundle(db,bundle['incident']['incident_id'],source_namespace='test',
                               catalog=service.catalog.data,config_catalog_hashes=bundle['config_catalog_hashes'],max_records=1)
    assert limited['truncated']
    assert len(limited['queries'])==1
    assert project_hpu(limited)['truncated']


def test_limits_schema_and_malformed_values_are_explicit(bundle):
    with pytest.raises(ValueError):project_incident(bundle,equipment_type='')
    with pytest.raises(ValueError):project_hpu({**bundle,'source_namespace':''})
    with pytest.raises(ValueError):content_hash({'value':float('nan')})
    b=deepcopy(bundle)
    b['reports'][0]['sensor_evidence']['measurements'][0]['unit']='incorrect'
    graph=project_hpu(b)
    assert any(x['reason']=='measurement_unit_conflict' for x in graph['unresolved'])

