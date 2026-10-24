"""Opt-in diagnostics on approved SQLite copies; never called by the query pipeline."""
from collections import Counter
import json
import os
from pathlib import Path
from time import perf_counter

from .incident_ontology import project_incident, read_incident_bundle


def failure(stage, error):
    # Database/IO exception messages can contain paths or credentials.
    return {'mode': 'shadow', 'status': 'error', 'error': {'stage': stage, 'type': type(error).__name__}}


def _summary(graph):
    nodes = Counter(n['type'] for n in graph['nodes'])
    edges = Counter(e['type'] for e in graph['edges'])
    reasons = Counter(item['reason'] for item in graph['unresolved'])
    if graph['truncated']:
        state = 'truncated'
    elif reasons:
        state = 'partial' if nodes else 'unresolved'
    else:
        state = 'connected' if nodes else 'empty'
    return {'projection_state': state, 'snapshot_hash': graph['snapshot_hash'],
            'node_counts': dict(sorted(nodes.items())), 'edge_counts': dict(sorted(edges.items())),
            'unresolved_count': len(graph['unresolved']), 'unresolved_by_reason': dict(sorted(reasons.items())),
            'truncated': graph['truncated']}


def run_shadow(database=None, incident_id=None, *, source_namespace=None, catalog=None,
               config_catalog_hashes=None, mode=None, output=None, max_records=30, equipment_type='HPU'):
    """Return a diagnostic envelope; off does no reads, projections or writes.

    Errors belong to this diagnostic run, never to a query response. The optional
    artifact contains source text; stdout consumers should use the summary only.
    """
    mode = os.environ.get('SHIFTLINK_HPU_ONTOLOGY', 'off') if mode is None else mode
    if mode == 'off':
        return {'mode': 'off', 'status': 'disabled'}
    if mode != 'shadow':
        return failure('configuration', ValueError())
    stage = 'read'
    try:
        started = perf_counter()
        bundle = read_incident_bundle(database, incident_id, source_namespace=source_namespace,
            catalog=catalog, config_catalog_hashes=config_catalog_hashes, max_records=max_records)
        read_ms = (perf_counter() - started) * 1000
        stage = 'project'
        started = perf_counter()
        graph = project_incident(bundle, equipment_type=equipment_type)
        project_ms = (perf_counter() - started) * 1000
        result = {'schema_version': 'shiftlink-ontology-shadow-v1', 'mode': 'shadow', 'status': 'completed',
                  'summary': _summary(graph), 'timings_ms': {'read': read_ms, 'project': project_ms}, 'graph': graph}
        if output is not None:
            stage = 'write'
            text = json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + '\n'
            # Exclusive creation also protects source DB/catalog/manifest aliases and symlinks.
            with Path(output).open('x', encoding='utf-8') as target:
                target.write(text)
        return result
    except Exception as error:
        return failure(stage, error)
