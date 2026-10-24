"""Default-off, paired offline S30h trials. Never imported by the serving query path."""
from copy import copy, deepcopy
import os
from statistics import mean
from time import perf_counter

from shiftlink.rag2.field_history import is_history_question
from shiftlink.rag2.s30h import S30hPipeline, CFG, G, GraphEvidence
from .publication import validated_record
from .publication_ontology import connect
from .incident_ontology import content_hash


def _view(pipeline):
    view=copy(pipeline)
    view.rows,view.cards=deepcopy(pipeline.rows),deepcopy(pipeline.cards)
    view.vec,view.folders=pipeline.vec.copy(),pipeline.folders.copy()
    return view


def _plan(service,pipeline,payload,database,graph,witness_query_id):
    from shiftlink.rag.retrieval import InMemoryToolProvider, _condition_status
    eq,asset=payload.get('eq_id'),payload.get('asset_id')
    if (not is_history_question(payload['question']) or pipeline.eq_type.get(eq)!='HPU'
            or graph.get('equipment_type')!='HPU' or payload.get('incident_id')!=graph['scope']['incident_id']
            or asset!=next((e.asset_id for e in service.active_config.equipment if e.equipment_id==eq),None)
            or not asset):
        return [],None,'outside_acceptance_scope'
    with service._lock:
        status,linked=connect(service,database,graph,witness_query_id)
        if status!=200:
            return [],None,'witness_unavailable'
        observer=InMemoryToolProvider(equipment_db=service.catalog.data['equipment'],
                                     equipment_types=service.catalog.data['equipment_types'])
        values={item['signal']:{'value':item['value'],'unit':item.get('unit')} for item in payload.get('observations',[])}
        values=observer._with_derived_states(observer._resolve_equipment([eq]),values)
        candidates=[]
        for node in linked['nodes']:
            if node['type']!='CardVersion':continue
            did=node['properties']['card_id']
            draft=service.storage.get_card_draft(did)
            artifact=draft['review_flags']['publication']
            row=service.storage.connection.execute('SELECT * FROM knowledge_publications WHERE draft_id=?',(did,)).fetchone()
            record,card=validated_record(draft,*row[1:],pipeline)
            if artifact['assets'].get(eq)!=asset or card.mes_equipment_id not in (None,eq) or _condition_status(card,values)!='verified':
                continue
            if sum(c.get('card_id')==did for c in pipeline.cards)!=1 or record['card'] not in pipeline.cards:
                continue
            for chunk,vector in zip(record['chunks'],record['vectors']):
                expected={**chunk,'metadata':{**chunk['metadata'],'version':card.version}}
                matches=[i for i,r in enumerate(pipeline.rows) if r['chunk_id']==chunk['chunk_id']]
                if len(matches)!=1:continue
                i=matches[0]
                import numpy as np
                if pipeline.rows[i]==expected and np.array_equal(pipeline.vec[i],np.asarray(vector,dtype=pipeline.vec.dtype)):
                    candidates.append(i);break
            if len(candidates)==2:break
        return candidates,linked['snapshot_hash'],'verified_relations' if candidates else 'no_eligible_relation'


def _outcome(result):
    output=result.output
    trace=result.tool_results
    return {'cited_card_ids':list(output.cited_card_ids),'abstained':bool(output.no_knowledge),
            'answer_hash':content_hash(output.answer),'route':trace.get('route'),
            'candidate_count':len(trace.get('candidates',[])), 'candidate_ids':trace.get('candidates',[]),
            'judge_count':len(trace.get('judge_p',[])), 'abstain_reason':trace.get('abstain_reason')}


def run_experiment(service=None,pipeline=None,payload=None,*,database=None,graph=None,witness_query_id=None,
                   mode=None,trial_first=False):
    """Compare independent pipeline views; no query save, index repair or answer promotion.

    Caller supplies an approved copy/base projection and an existing validated S30h
    view. Explicit enabling can invoke that view's configured models twice.
    """
    mode=os.environ.get('SHIFTLINK_HPU_RETRIEVAL','off') if mode is None else mode
    if mode=='off':return {'mode':'off','status':'disabled'}
    if mode!='experiment' or not isinstance(pipeline,S30hPipeline):
        return {'mode':mode,'status':'error','reason':'unsupported_experiment_configuration'}
    timings={}
    try:
        started=perf_counter()
        additions,digest,reason=_plan(service,pipeline,payload,database,graph,witness_query_id)
        timings['relation_prepare']=(perf_counter()-started)*1000
        admitted=[]
        def execute(name):
            started=perf_counter()
            view=_view(pipeline)
            timings[name+'_prepare']=(perf_counter()-started)*1000
            had_override='evidence' in view.__dict__
            prior=view.__dict__.get('evidence')
            original=view.evidence
            def evidence(question,eq_type,eq_id=None,units=None):
                ev=original(question,eq_type,eq_id,units)
                if eq_id!=payload['eq_id'] or eq_type!='HPU' or (units and view.eq_code[eq_id] not in units):
                    return ev
                by_id={r['chunk_id']:i for i,r in enumerate(view.rows)}
                selected={r['metadata']['source'] for r in ev if r['metadata']['kind']=='card'}
                extra=[i for i in additions if view.rows[i]['metadata']['source'] not in selected]
                if not extra:return ev
                # Keep one dense seed, then a bounded relation lane, within unchanged evidence budgets.
                dense=[by_id[r['chunk_id']] for r in ev]
                ranking=list(dict.fromkeys([*dense[:1],*extra,*dense[1:]]))
                chosen=G.evidence(view.rows,ranking,CFG)
                admitted.extend(view.rows[i]['metadata']['source'] for i in extra if view.rows[i] in chosen)
                if hasattr(ev,'graph_trace'):
                    return GraphEvidence(chosen,deepcopy(ev.graph_trace))
                return chosen
            try:
                if name=='trial':view.evidence=evidence
                started=perf_counter()
                result=view.run(deepcopy(payload))
                timings[name]=(perf_counter()-started)*1000
                return _outcome(result)
            finally:
                if name=='trial':
                    if had_override:view.evidence=prior
                    else:view.__dict__.pop('evidence',None)
        results={}
        order=('trial','baseline') if trial_first else ('baseline','trial')
        for name in order:
            started=perf_counter()
            results[name]=execute(name)
            timings[name+'_overhead']=max(0,(perf_counter()-started)*1000-timings[name+'_prepare']-timings[name])
        started=perf_counter()
        if admitted:
            status,current=connect(service,database,graph,witness_query_id)
            if status!=200 or current['snapshot_hash']!=digest:
                return {'mode':mode,'status':'invalidated','reason':'publication_changed','timings_ms':timings}
        timings['recheck']=(perf_counter()-started)*1000
        timings['baseline_total']=timings['baseline_prepare']+timings['baseline']+timings['baseline_overhead']
        timings['trial_total']=timings['relation_prepare']+timings['trial_prepare']+timings['trial']+timings['trial_overhead']+timings['recheck']
        return {'schema_version':'shiftlink-hpu-retrieval-trial-v1','mode':mode,'status':'completed',
                **results,'added_card_ids':sorted(set(admitted)),'scope_reason':reason,
                'candidate_budget':CFG.get('max_chunks',G.MAX_CHUNKS),'timings_ms':timings,'order':list(order)}
    except Exception as error:
        return {'mode':mode,'status':'error','reason':'experiment_failed','error_type':type(error).__name__}


def score_case(case,result,*,card_id):
    scored={'case_id':case['id'],'status':result['status']}
    if result['status']!='completed':return scored
    allowed={card_id} if case['expect_citation'] else set()
    relation_allowed={card_id} if case['allow_relation'] else set()
    for name in ('baseline','trial'):
        cites=set(result[name]['cited_card_ids'])
        scored[name]={**result[name], 'expected_citation_hits':len(cites & allowed),
                      'wrong_citations':len(cites-allowed),
                      'oracle_failures':int(cites!=allowed or result[name]['abstained']!=(not case['expect_citation'])),
                      'misconnections':len(set(result['added_card_ids'])-relation_allowed) if name=='trial' else 0}
    return {**scored,'timings_ms':result['timings_ms'],'order':result['order'],
            'added_card_ids':result['added_card_ids'],'expected_citations':len(allowed)}


def summarize(rows):
    valid=[r for r in rows if r['status']=='completed']
    out={'total':len(rows),'completed':len(valid),'excluded':len(rows)-len(valid)}
    for name in ('baseline','trial'):
        sums={k:sum(r[name][k] for r in valid) for k in ('expected_citation_hits','wrong_citations','misconnections','oracle_failures','candidate_count','judge_count')}
        sums['abstentions']=sum(r[name]['abstained'] for r in valid)
        expected=sum(r['expected_citations'] for r in valid)
        cited=sums['expected_citation_hits']+sums['wrong_citations']
        sums['citation_recall']=sums['expected_citation_hits']/expected if expected else None
        sums['citation_precision']=sums['expected_citation_hits']/cited if cited else None
        times=sorted(r['timings_ms']['trial_total'] if name=='trial' else
                     r['timings_ms'].get('baseline_total',r['timings_ms']['baseline']) for r in valid)
        sums['mean_ms']=mean(times) if times else None
        sums['p95_ms']=times[max(0,(95*len(times)+99)//100-1)] if times else None
        out[name]=sums
    out['mean_latency_delta_ms']=(out['trial']['mean_ms']-out['baseline']['mean_ms']) if valid else None
    out['decision']='fixture_pass_only' if (valid and out['excluded']==0 and out['trial']['wrong_citations']==0
        and out['trial']['misconnections']==0 and out['trial']['oracle_failures']==0) else 'fixture_regression_or_incomplete'
    return out
