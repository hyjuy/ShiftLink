"""Admin-only explanations from an explicitly configured, approved SQLite copy."""
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, unquote

from .ontology_shadow import run_shadow


def explain(accounts, token, incident_id, query):
    # Gate before authentication or source access; shadow never enables an HTTP read.
    if os.environ.get('SHIFTLINK_HPU_ONTOLOGY', 'off') != 'explain':
        return 404, {'error': 'not found'}
    if not accounts.administrator(token):
        return 401, {'error': 'MES 관리자 로그인이 필요합니다.'}
    try:
        params = parse_qs(query, keep_blank_values=True)
        if set(params) - {'limit', 'offset', 'snapshot_hash', 'asset_id'} or any(len(v) != 1 for v in params.values()):
            raise ValueError()
        limit = int(params.get('limit', ['100'])[0])
        offset = int(params.get('offset', ['0'])[0])
        digest = params.get('snapshot_hash', [''])[0]
        iid = unquote(incident_id)
        if not iid or len(iid) > 256 or '/' in iid or not 1 <= limit <= 100 or not 0 <= offset <= 2000:
            raise ValueError()
        if offset and not digest:
            raise ValueError()
    except ValueError:
        return 400, {'error': 'invalid ontology parameters'}
    try:
        catalog = json.loads(Path(os.environ['SHIFTLINK_HPU_ONTOLOGY_CATALOG']).read_text(encoding='utf-8'))
        manifest = json.loads(Path(os.environ['SHIFTLINK_HPU_ONTOLOGY_MANIFEST']).read_text(encoding='utf-8'))
        if not isinstance(catalog, dict) or not isinstance(manifest, dict):
            raise ValueError()
        namespace = manifest['source_namespace']
        bindings = manifest.get('config_catalog_hashes', {})
        if not isinstance(namespace, str) or not namespace.strip() or not isinstance(bindings, dict):
            raise ValueError()
        result = run_shadow(os.environ['SHIFTLINK_HPU_ONTOLOGY_DB'], iid,
            source_namespace=namespace, catalog=catalog, config_catalog_hashes=bindings,
            mode='shadow', max_records=30)
    except Exception:
        return 503, {'error': 'ontology source unavailable'}
    if result['status'] != 'completed':
        if result['error'] == {'stage': 'read', 'type': 'KeyError'}:
            return 404, {'error': 'not found'}
        return 503, {'error': 'ontology source unavailable'}
    graph = result['graph']
    asset = params.get('asset_id', [None])[0]
    if asset is not None and asset not in {n['properties']['asset_id'] for n in graph['nodes'] if n['type'] == 'Asset'}:
        return 404, {'error': 'not found'}
    if digest and digest != graph['snapshot_hash']:
        return 409, {'error': 'ontology snapshot changed; restart pagination'}
    # Each collection uses the same offset/limit. Edges may refer to nodes on another page.
    totals = {key: len(graph[key]) for key in ('nodes', 'edges', 'unresolved')}
    end = offset + limit
    return 200, {**graph, **{key: graph[key][offset:end] for key in totals},
        'summary': result['summary'],
        'page': {'offset': offset, 'limit': limit, 'totals': totals,
                 'next_offset': end if end < max(totals.values()) else None}}
