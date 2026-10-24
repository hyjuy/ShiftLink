"""Optional citation-to-incident overlay; never participates in retrieval or answers."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3

from .incident_ontology import content_hash
from .publication import PUBLICATION_MODEL, validated_record


def problem(query_id, reason, card_id=None):
    return {'source_ref': {'kind':'query', 'id':query_id, 'path':'cited_cards', 'card_id':card_id},
            'reason':reason, 'binding_status':'unresolved'}


def add_links(base, links, query_id, issues):
    graph=deepcopy(base)
    ids=[]
    for node, edge in links:
        if len(graph['nodes']) >= 1000 or len(graph['edges']) >= 2000:
            graph['truncated']=True
            break
        graph['nodes'].append(node)
        graph['edges'].append(edge)
        ids.append(node['properties']['card_id'])
    graph['unresolved'].extend(issues)
    graph['nodes'].sort(key=lambda n:n['id'])
    for key in ('edges','unresolved'):
        graph[key].sort(key=lambda row:json.dumps(row,ensure_ascii=False,sort_keys=True))
    graph['publication_overlay']={'schema_version':'shiftlink-hpu-publication-v1',
                                  'query_id':query_id, 'card_ids':sorted(ids)}
    graph.pop('snapshot_hash',None)
    graph['snapshot_hash']=content_hash(graph)
    return graph


def _origin_matches(service, source, base, draft, equipment, asset):
    origin=draft['review_flags'].get('work_report',{})
    iid=base['scope']['incident_id']
    if origin.get('incident_id') != iid:
        return False
    roots=[n for n in base['nodes'] if n['type']=='Incident']
    assets={n['properties']['asset_id'] for n in base['nodes'] if n['type']=='Asset'}
    if len(roots)!=1 or asset not in assets:
        return False
    con=service.storage.connection
    row=con.execute('SELECT * FROM incidents WHERE incident_id=?',(iid,)).fetchone()
    names=[item[1] for item in con.execute('PRAGMA table_info(incidents)')]
    live=dict(zip(names,row)) if row else {}
    for key in ('assets','equipment_ids'):
        if key in live: live[key]=json.loads(live[key])
    if content_hash(live)!=roots[0]['provenance']['source_hash'] or live['assets'].get(equipment)!=asset:
        return False
    hid,index=origin.get('handover_id'),origin.get('record_index')
    sql=('SELECT h.payload FROM incident_records r JOIN handover_outbox h USING(handover_id) '
         'WHERE r.incident_id=? AND r.handover_id=? AND r.record_index=?')
    before=source.execute(sql,(iid,hid,index)).fetchone()
    current=con.execute(sql,(iid,hid,index)).fetchone()
    # The origin must also be present in the bounded, verified base projection.
    projected=any(n['provenance']['source_ref'].get('kind')=='report'
                  and n['provenance']['source_ref']['id']==hid for n in base['nodes'])
    return bool(projected and before and current and
                content_hash(json.loads(before[0]))==content_hash(json.loads(current[0])))


def connect(service, database, base, query_id):
    """Use saved citation witnesses; recheck publication tickets under the MES lock."""
    with service._lock:
        source=sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)
        try:
            source.execute('BEGIN')
            saved=source.execute('SELECT created_at,payload FROM query_log WHERE query_id=?',(query_id,)).fetchone()
            live=service.storage.get_query(query_id)
            if not saved or not live:
                return 404, {'error':'query not found in approved source'}
            query=json.loads(saved[1])
            if query!=live['payload'] or saved[0]!=live['created_at']:
                return 200, add_links(base,[],query_id,[problem(query_id,'query_source_mismatch')])
            links,ticket,issues,rows=[],[],[],[]
            context=query.get('query_context') or {}
            equipment,asset=context.get('equipment_id'),context.get('asset_id')
            cited=set(query.get('cited_card_ids') or [])
            snapshots=query.get('cited_cards') or []
            if query.get('no_knowledge') or query.get('review_queue'):
                snapshots=[]
            for card in snapshots[:30]:
                did=card.get('card_id')
                if did not in cited:
                    continue
                draft=service.storage.get_card_draft(did)
                artifact=draft['review_flags'].get('publication',{}) if draft else {}
                digest=content_hash(card)
                entry=(did,artifact.get('review_revision'),digest,equipment,asset)
                reason=None
                recorded=query.get('publication_ticket') or []
                if list(entry) not in recorded:
                    reason='citation_revision_unverified'
                if not service.publications.still_current([entry]):
                    reason='publication_not_current'
                else:
                    try:
                        row=service.storage.connection.execute('SELECT * FROM knowledge_publications WHERE draft_id=?',(did,)).fetchone()
                        if not row or tuple(row[:4])!=(did,entry[1],digest,PUBLICATION_MODEL):
                            raise ValueError('publication mismatch')
                        record,_=validated_record(draft,*row[1:])
                        if record['card']!=card or artifact['assets'].get(equipment)!=asset:
                            raise ValueError('citation mismatch')
                        if not reason and not _origin_matches(service,source,base,draft,equipment,asset):
                            reason='publication_origin_mismatch'
                    except (ValueError,KeyError,TypeError,IndexError):
                        reason='publication_integrity_mismatch'
                if reason:
                    issues.append(problem(query_id,reason,did));continue
                root=next(n for n in base['nodes'] if n['type']=='Incident')
                ident=json.dumps([base['scope']['source_namespace'],'CardVersion',did,card['version'],entry[1],digest],ensure_ascii=False,separators=(',',':'))
                provenance={'query_id':query_id,'source_hash':digest,'review_revision':entry[1],
                            'claim_kind':'reviewed_knowledge','binding_status':'verified'}
                node={'id':ident,'type':'CardVersion','properties':{'card_id':did,'version':card['version'],
                       'review_revision':entry[1],'content_hash':digest},'provenance':provenance}
                links.append((node,{'type':'DERIVED_FROM_INCIDENT','source':ident,'target':root['id'],
                                    'provenance':provenance}))
                ticket.append(entry);rows.append(tuple(row))
            missing=cited-{card.get('card_id') for card in snapshots}
            issues.extend(problem(query_id,'citation_snapshot_missing',did) for did in sorted(missing))
            result=add_links(base,links,query_id,issues)
            if ticket and (not service.publications.still_current(ticket) or any(
                    service.storage.connection.execute('SELECT * FROM knowledge_publications WHERE draft_id=?',(row[0],)).fetchone()!=row
                    for row in rows)):
                result=add_links(base,[],query_id,[*issues,problem(query_id,'publication_changed')])
            if len(snapshots)>30:
                result['truncated']=True
                result.pop('snapshot_hash');result['snapshot_hash']=content_hash(result)
            return 200,result
        finally:
            source.rollback();source.close()
