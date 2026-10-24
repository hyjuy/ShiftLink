"""Offline, read-only incident projections shared by equipment types. No service hooks."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import sqlite3


SCHEMA_VERSION = 'shiftlink-incident-ontology-v1'
RELATIONS = {
    'INSTANCE_OF': ('Asset', 'EquipmentType'),
    'INVOLVES_ASSET': ('Incident', 'Asset'),
    'OBSERVED_ON': ('Observation', 'Asset'),
    'HAS_OBSERVATION': ('Incident', 'Observation'),
    'HAS_ACTION': ('Incident', 'Action'),
    'PERFORMED_ON': ('Action', 'Asset'),
    'NEXT_RECORDED_STEP': ('Action', 'Action'),
    'HAS_RECORDED_RESULT': ('Action', 'Outcome'),
    'HAS_OUTCOME': ('Incident', 'Outcome'),
    'SUPPORTED_BY': ('Outcome', 'Observation'),
}


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def content_hash(value):
    return sha256(_json(value).encode('utf-8')).hexdigest()


def _take(value, keys):
    return {k: deepcopy(value[k]) for k in keys if k in value}


def _time_basis(value):
    try:
        parsed = datetime.fromisoformat(value)
        return 'offset_datetime' if parsed.utcoffset() is not None else 'unknown'
    except (ValueError, TypeError):
        return 'unknown'


def _measurements(evidence):
    return [_take(row, ('equipment_id', 'asset_id', 'signal', 'value', 'unit', 'quality',
                        'observed_at', 'normal_min', 'normal_max'))
            for row in evidence.get('measurements', [])]


def _evidence(evidence):
    result = _take(evidence, ('run_id', 'config_id', 'equipment_id', 'asset_id', 'simulated_at', 'scope'))
    result['measurements'] = _measurements(evidence)
    return result


def _record(record):
    result = _take(record, ('equipment', 'story', 'symptom', 'occurred_at', 'outcome', 'result',
                           'normal_run_status', 'normal_run_minutes', 'normal_run_evidence',
                           'source_session_id', 'query_id', 'incident_id', 'capture_version', 'solution'))
    result['action_steps'] = [_take(step, ('action', 'observed_result', 'failed', 'worker', 'performed_at'))
                              for step in record.get('action_steps', [])]
    return result


def _session(session):
    data = session['data']
    clean = _take(data, ('run_id',))
    for key in ('before', 'after'):
        if isinstance(data.get(key), dict):
            clean[key] = _evidence(data[key])
    clean['steps'] = [{**_take(step, ('action', 'result_text', 'simulated_at', 'order')),
                       'measurements': _measurements(step)} for step in data.get('steps', [])]
    if isinstance(data.get('verdict'), dict):
        verdict = data['verdict']
        clean['verdict'] = _take(verdict, ('verdict', 'text', 'suggested_result'))
        clean['verdict']['check'] = _take(verdict.get('check', {}), ('recovered',))
    return {**_take(session, ('session_id', 'equipment_id', 'status')), 'data': clean}


def read_incident_bundle(database, incident_id, *, source_namespace, catalog=None,
                         config_catalog_hashes=None, max_records=30):
    """Read a bounded, consistent copy. Caller attests config -> source catalog hashes.

    Use an approved offline SQLite copy; unlike MesStorage this performs no DDL/PRAGMA writes.
    """
    if not isinstance(source_namespace, str) or not source_namespace.strip():
        raise ValueError('source_namespace is required')
    if type(max_records) is not int or not 1 <= max_records <= 100:
        raise ValueError('max_records must be 1..100')
    uri = Path(database).resolve().as_uri() + '?mode=ro'
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    try:
        con.execute('BEGIN')
        row = con.execute('SELECT * FROM incidents WHERE incident_id=?', (incident_id,)).fetchone()
        if row is None:
            raise KeyError('incident not found')
        incident = dict(row)
        for key in ('assets', 'equipment_ids'):
            incident[key] = json.loads(incident[key])
        reports = con.execute(
            'SELECT r.handover_id,r.record_index,h.created_at,h.payload,s.evidence '
            'FROM incident_records r JOIN handover_outbox h USING(handover_id) '
            'LEFT JOIN work_report_sensor_evidence s USING(handover_id) '
            'WHERE r.incident_id=? ORDER BY r.handover_id,r.record_index LIMIT ?',
            (incident_id, max_records + 1)).fetchall()
        truncated = len(reports) > max_records
        records, session_ids, query_ids = [], set(), set()
        for report in reports[:max_records]:
            record = _record(json.loads(report['payload'])['work_report']['records'][report['record_index']])
            item = {**_take(dict(report), ('handover_id', 'record_index', 'created_at')), 'record': record,
                    'sensor_evidence': _evidence(json.loads(report['evidence'])) if report['evidence'] else None}
            records.append(item)
            if record.get('source_session_id'): session_ids.add(record['source_session_id'])
            if record.get('query_id'): query_ids.add(record['query_id'])
        linked = con.execute('SELECT query_id FROM incident_queries WHERE incident_id=? ORDER BY query_id LIMIT ?',
                             (incident_id, max_records + 1)).fetchall()
        truncated |= len(linked) > max_records
        query_ids.update(row['query_id'] for row in linked[:max_records])
        truncated |= len(query_ids) > max_records
        queries = []
        for query_id in sorted(query_ids)[:max_records]:
            query = con.execute('SELECT payload FROM query_log WHERE query_id=?', (query_id,)).fetchone()
            if query:
                payload = json.loads(query['payload'])
                queries.append({'query_id': query_id, 'payload': {
                    'query_context': _take(payload.get('query_context') or {},
                                           ('config_id', 'equipment_id', 'asset_id', 'incident_id')),
                    'evidence': _evidence(payload.get('evidence') or {})}})
        sessions = []
        for session_id in sorted(session_ids):
            row = con.execute('SELECT * FROM resolution_sessions WHERE session_id=?', (session_id,)).fetchone()
            if row:
                sessions.append(_session({**dict(row), 'data': json.loads(row['data'])}))
        run_ids = {q['payload']['evidence'].get('run_id') for q in queries}
        run_ids.update(r['sensor_evidence'].get('run_id') for r in records if r['sensor_evidence'])
        run_ids.update(s['data'].get('run_id') for s in sessions)
        runs = {}
        for run_id in sorted(run_ids - {None}):
            row = con.execute('SELECT payload FROM runs WHERE run_id=?', (run_id,)).fetchone()
            if row: runs[run_id] = json.loads(row['payload']).get('config_id')
        config_ids = {incident['config_id'], *runs.values()}
        config_ids.update(q['payload']['query_context'].get('config_id') for q in queries)
        configurations = {}
        for config_id in sorted(config_ids - {None}):
            row = con.execute('SELECT payload FROM configurations WHERE config_id=?', (config_id,)).fetchone()
            if row:
                payload = json.loads(row['payload'])
                configurations[config_id] = {'equipment': [
                    _take(eq, ('equipment_id', 'asset_id', 'signals')) for eq in payload.get('equipment', [])]}
        return {'source_namespace': source_namespace, 'catalog': deepcopy(catalog or {}),
                'config_catalog_hashes': deepcopy(config_catalog_hashes or {}), 'incident': incident,
                'configurations': configurations, 'runs': runs, 'reports': records, 'queries': queries,
                'sessions': sessions, 'truncated': truncated}
    finally:
        con.rollback()
        con.close()


class _Graph:
    def __init__(self, namespace):
        self.namespace, self.nodes, self.edges, self.unresolved = namespace, {}, {}, []
        self.truncated = False

    def problem(self, ref, reason, status='unresolved'):
        self.unresolved.append({'source_ref': ref, 'reason': reason, 'binding_status': status})

    def provenance(self, ref, original, claim_kind):
        return {'source_ref': ref, 'source_hash': content_hash(original),
                'schema_version': SCHEMA_VERSION, 'source_namespace': self.namespace,
                'claim_kind': claim_kind, 'review_state': 'not_assessed', 'binding_status': 'verified'}

    def node(self, kind, key, props, provenance):
        ident = _json([self.namespace, SCHEMA_VERSION, kind, *key])
        if ident not in self.nodes and len(self.nodes) >= 1000:
            self.truncated = True
            return None
        self.nodes[ident] = {'id': ident, 'type': kind, 'properties': deepcopy(props), 'provenance': provenance}
        return ident

    def edge(self, kind, start, end, provenance):
        if start is None or end is None:
            return
        if (self.nodes[start]['type'], self.nodes[end]['type']) != RELATIONS[kind]:
            raise ValueError('ontology domain/range mismatch')
        edge = {'type': kind, 'source': start, 'target': end, 'provenance': provenance}
        if len(self.edges) >= 2000:
            self.truncated = True
            return
        self.edges[_json(edge)] = edge


def project_incident(bundle, *, equipment_type):
    """Pure projection of one explicit incident; selection is a catalog FK, not a code prefix."""
    namespace = bundle.get('source_namespace')
    if not isinstance(namespace, str) or not namespace.strip() or not isinstance(equipment_type, str) or not equipment_type.strip():
        raise ValueError('source_namespace and equipment_type are required')
    graph = _Graph(namespace)
    incident = bundle['incident']
    iid, config_id = incident['incident_id'], incident['config_id']
    configs, runs = bundle.get('configurations', {}), bundle.get('runs', {})
    catalog = bundle.get('catalog', {})
    catalog_hash = content_hash(catalog)
    attestations = bundle.get('config_catalog_hashes', {})
    root_ref = {'kind': 'incident', 'id': iid, 'path': 'assets'}
    root_prov = graph.provenance(root_ref, incident, 'worker_report')

    def binding(eq, asset, cfg):
        if cfg not in configs:
            return 'missing_historical_configuration'
        entries = [e for e in configs[cfg].get('equipment', []) if e['equipment_id'] == eq]
        if len(entries) != 1 or entries[0]['asset_id'] != asset:
            return 'asset_configuration_conflict'
        if attestations.get(cfg) != catalog_hash:
            return 'unverified_catalog_binding'
        masters = [e for e in catalog.get('equipment', []) if e['equipment_id'] == eq]
        types = [t for t in catalog.get('equipment_types', [])
                 if masters and t['equipment_type_id'] == masters[0]['equipment_type_id']]
        if len(masters) != 1 or len(types) != 1:
            return 'unknown_equipment_type'
        if types[0]['type_code'] != equipment_type:
            return 'outside_equipment_scope'
        return None

    selected = {}
    incident_node = None
    for eq, asset in sorted(incident['assets'].items()):
        reason = binding(eq, asset, config_id)
        if reason:
            if reason != 'outside_equipment_scope': graph.problem(root_ref, reason)
            continue
        if incident_node is None:
            incident_node = graph.node('Incident', [iid], _take(incident, ('incident_id', 'created_at', 'config_id')), root_prov)
        an = graph.node('Asset', [asset], {'asset_id': asset, 'is_synthetic': catalog.get('_meta', {}).get('is_synthetic')}, root_prov)
        tn = graph.node('EquipmentType', [equipment_type], {'type_code': equipment_type}, root_prov)
        prov = {**root_prov, 'equipment_id': eq, 'config_id': config_id}
        graph.edge('INVOLVES_ASSET', incident_node, an, prov)
        graph.edge('INSTANCE_OF', an, tn, prov)
        selected[eq] = (asset, an)

    def context_valid(eq, cfg, run=None, asset=None):
        if eq not in selected or (run is not None and runs.get(run) != cfg):
            return False
        return asset in (None, selected[eq][0]) and binding(eq, selected[eq][0], cfg) is None

    def observations(evidence, eq, ref, scope, prov):
        output = []
        cfg = evidence.get('config_id', config_id)
        specs = {s['signal']: s for e in configs[cfg]['equipment'] if e['equipment_id'] == eq
                 for s in e.get('signals', [])}
        for index, row in enumerate(evidence.get('measurements', [])):
            if row.get('equipment_id', eq) != eq: continue
            signal = row.get('signal')
            if row.get('asset_id', selected[eq][0]) != selected[eq][0]:
                graph.problem(ref, 'measurement_asset_conflict', 'conflict'); continue
            if signal not in specs or row.get('unit') != specs[signal]['unit']:
                graph.problem(ref, 'measurement_unit_conflict', 'conflict'); continue
            props = {**_take(row, ('signal', 'value', 'unit', 'quality', 'normal_min', 'normal_max')),
                     'observed_at_raw': row.get('observed_at'), 'time_basis': _time_basis(row.get('observed_at')),
                     'scope': scope, 'run_id': evidence.get('run_id'), 'config_id': cfg,
                     'snapshot_at_raw': evidence.get('simulated_at')}
            rp = graph.provenance({**ref, 'path': ref['path'] + f'.measurements[{index}]'}, row, 'sensor_observation')
            on = graph.node('Observation', [ref['kind'], ref['id'], ref['path'], index, content_hash(row)], props, rp)
            graph.edge('OBSERVED_ON', on, selected[eq][1], rp)
            graph.edge('HAS_OBSERVATION', incident_node, on, rp)
            output.append(on)
        return output

    def actions(steps, eq, ref, revision, claim='worker_report', session_context=None):
        previous = None
        for index, step in enumerate(steps):
            text = step.get('action', '')
            result = step.get('observed_result', step.get('result_text', ''))
            if not text.strip() and not result.strip(): continue
            field = 'action_steps' if ref['kind'] == 'report' else 'steps'
            sr = {**ref, 'path': ref['path'] + f'.{field}[{index}]'}
            prov = graph.provenance(sr, step, claim)
            props = {'action': text, 'ordinal': index, 'failed_raw': step.get('failed'),
                     'performed_at_raw': step.get('performed_at', step.get('simulated_at')),
                     'time_basis': _time_basis(step.get('performed_at', step.get('simulated_at')))}
            if step.get('worker'):
                props['worker_ref'] = {**sr, 'path': sr['path'] + '.worker'}
            action = graph.node('Action', [ref['kind'], ref['id'], ref['path'], revision, index], props, prov)
            graph.edge('HAS_ACTION', incident_node, action, prov)
            graph.edge('PERFORMED_ON', action, selected[eq][1], prov)
            graph.edge('NEXT_RECORDED_STEP', previous, action, prov)
            if result:
                outcome = graph.node('Outcome', [action, 'step_result'], {'outcome_kind': 'step_result', 'text': result}, prov)
                graph.edge('HAS_RECORDED_RESULT', action, outcome, prov)
                if session_context:
                    evidence = {**step, **session_context}
                    for obs in observations(evidence, eq, sr, 'session_step', prov):
                        graph.edge('SUPPORTED_BY', outcome, obs, prov)
            previous = action

    reports = bundle.get('reports', [])
    valid_reports = []
    for report in reports:
        record = _record(report['record'])
        ref = {'kind': 'report', 'id': report['handover_id'], 'path': f"work_report.records[{report['record_index']}]"}
        if record.get('incident_id') not in (None, iid):
            graph.problem(ref, 'report_incident_conflict', 'conflict'); continue
        equipment = record.get('equipment', [])
        if len(equipment) != 1:
            graph.problem(ref, 'ambiguous_action_equipment'); continue
        eq = equipment[0]
        if eq not in selected: continue
        valid_reports.append(report)
        evidence = report.get('sensor_evidence')
        if evidence:
            if evidence.get('run_id') and context_valid(eq, evidence.get('config_id'), evidence['run_id']):
                observations(_evidence(evidence), eq,
                             {'kind': 'report_sensor', 'id': report['handover_id'], 'path': 'server_sensor_evidence'},
                             'save_snapshot', root_prov)
            else:
                graph.problem(ref, 'report_evidence_context_conflict', 'conflict')
        prov = graph.provenance(ref, record, 'worker_report')
        if record.get('story') or record.get('symptom'):
            obs = graph.node('Observation', ['report', report['handover_id'], report['record_index'], 'worker'], {
                'text': record.get('story') or record['symptom'], 'scope': 'worker_report',
                'occurred_at_raw': record.get('occurred_at'), 'time_basis': _time_basis(record.get('occurred_at'))}, prov)
            graph.edge('OBSERVED_ON', obs, selected[eq][1], prov)
            graph.edge('HAS_OBSERVATION', incident_node, obs, prov)
        actions(record.get('action_steps', []), eq, ref, 'immutable')
        for kind, keys in [('reported_outcome', ('outcome', 'result')),
                           ('normal_operation', ('normal_run_status', 'normal_run_minutes', 'normal_run_evidence'))]:
            props = _take(record, keys)
            if not props: continue
            if kind == 'normal_operation':
                props = {'status': props.get('normal_run_status'), 'minutes': props.get('normal_run_minutes'),
                         'text': props.get('normal_run_evidence')}
            outcome = graph.node('Outcome', ['report', report['handover_id'], report['record_index'], kind],
                                 {'outcome_kind': kind, **props}, prov)
            graph.edge('HAS_OUTCOME', incident_node, outcome, prov)

    for query in bundle.get('queries', []):
        payload = query['payload']
        ctx, evidence = payload.get('query_context') or {}, payload.get('evidence') or {}
        ref = {'kind': 'query', 'id': query['query_id'], 'path': 'evidence'}
        eq = ctx.get('equipment_id')
        explicit = any(r['record'].get('query_id') == query['query_id'] for r in valid_reports)
        if (ctx.get('incident_id') not in (None, iid) or not (ctx.get('incident_id') == iid or explicit)
                or not ctx.get('asset_id') or not evidence.get('run_id')
                or evidence.get('config_id') not in (None, ctx.get('config_id'))
                or not context_valid(eq, ctx.get('config_id'), evidence['run_id'], ctx['asset_id'])
                or evidence.get('equipment_id') != eq):
            graph.problem(ref, 'query_context_conflict', 'conflict'); continue
        observations({**_evidence(evidence), 'config_id': ctx['config_id']}, eq, ref, 'query_snapshot', root_prov)

    for session in bundle.get('sessions', []):
        clean = _session(session)
        data, eq = clean['data'], clean.get('equipment_id')
        sid = clean['session_id']
        ref = {'kind': 'session', 'id': sid, 'path': 'data'}
        linked = [r for r in valid_reports if r['record'].get('source_session_id') == sid
                  and r['record'].get('equipment') == [eq]]
        run = data.get('run_id')
        evidence = [data[k] for k in ('before', 'after') if k in data]
        if (not linked or not run or not context_valid(eq, runs.get(run), run)
                or not evidence or any(e.get('run_id') != run or e.get('equipment_id') != eq
                                      or e.get('asset_id', selected.get(eq, (None,))[0]) != selected.get(eq, (None,))[0]
                                      for e in evidence)):
            graph.problem(ref, 'session_binding_unresolved'); continue
        revision = content_hash(data)
        actions(data.get('steps', []), eq, ref, revision,
                session_context={'run_id': run, 'config_id': runs[run]})
        supports = []
        for key in ('before', 'after'):
            if key in data:
                supports.extend(observations({**data[key], 'config_id': runs[run]}, eq, {**ref, 'path': f'data.{key}'},
                                             f'session_{key}', root_prov))
        verdict = data.get('verdict')
        if verdict:
            prov = graph.provenance(ref, verdict, 'mes_assessment')
            outcome = graph.node('Outcome', ['session', sid, revision, 'verdict'], {
                'outcome_kind': 'mes_assessment', **_take(verdict, ('verdict', 'text', 'suggested_result')),
                'recovered': verdict.get('check', {}).get('recovered')}, prov)
            graph.edge('HAS_OUTCOME', incident_node, outcome, prov)
            for obs in supports: graph.edge('SUPPORTED_BY', outcome, obs, prov)

    result = {'schema_version': SCHEMA_VERSION, 'equipment_type': equipment_type,
              'scope': {'source_namespace': namespace, 'incident_id': iid},
              'nodes': sorted(graph.nodes.values(), key=lambda n:n['id']),
              'edges': sorted(graph.edges.values(), key=_json),
              'unresolved': sorted(graph.unresolved, key=_json),
              'truncated': bool(bundle.get('truncated') or graph.truncated)}
    result['snapshot_hash'] = content_hash(result)
    return result
