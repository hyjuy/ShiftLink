"""Paired S30h trials against explicit citation/scope oracles, never a service hook."""
from copy import deepcopy
import json
import os
from pathlib import Path

import numpy as np
import pytest

from shiftlink.mes import hpu_retrieval_experiment as X
from shiftlink.mes.incident_ontology import content_hash, project_incident, read_incident_bundle
from test_s30h_publication_integrity import published_history
from test_s30h import pipe, E, G, chunk
from test_work_report_reuse_harness import service
from test_publication_worker import ACTOR

QUESTION='근무일지에서 필터 교체 후 137분 관찰 결과와 시각만 알려줘'


@pytest.fixture
def experiment(published_history, monkeypatch):
    svc,did=published_history
    witness=svc.query({'question':QUESTION,'equipment_id':'EQ-0001'})
    assert witness['cited_card_ids']==[did]
    asset=svc.active_config.equipment[0].asset_id
    with svc._lock:
        view,_=svc.publications.snapshot(svc.query_pipeline,'EQ-0001',asset,[])
    field=[r for r in view.rows if r['metadata']['source']==did]
    # Competing reviewed histories, not manuals: history-only retrieval now excludes manuals.
    template=next(c for c in view.cards if c['card_id']==did)
    distractors=[]
    for i in range(35):
        cid=f'K-fixture-{i}'
        view.cards.append({**deepcopy(template),'card_id':cid})
        distractors.append(chunk(f'field_{cid}_r2_0','card',cid,'HPU',page=1))
    view.rows=distractors+field
    view.vec=np.array([[3,0,0,0]]*35+[[.6,.8,0,0]]*len(field),dtype=np.float32)
    view.folders=np.array(['HPU']*len(view.rows))
    iid=svc.storage.get_card_draft(did)['review_flags']['work_report']['incident_id']
    db=svc.storage.connection.execute('PRAGMA database_list').fetchone()[2]
    graph=project_incident(read_incident_bundle(db,iid,source_namespace='experiment-fixture',catalog=svc.catalog.data,
        config_catalog_hashes={svc.active_config.config_id:content_hash(svc.catalog.data)}),equipment_type='HPU')
    return dict(service=svc,pipeline=view,database=db,graph=graph,witness_query_id=witness['query_id'],
        payload={'question':QUESTION,'eq_id':'EQ-0001','asset_id':asset,'incident_id':iid,'observations':[]}),did


def test_off_is_inert_and_does_not_change_normal_query(experiment, monkeypatch):
    args,did=experiment
    monkeypatch.delenv('SHIFTLINK_HPU_RETRIEVAL',raising=False)
    def forbidden(*a,**kw): raise AssertionError('disabled experiment accessed dependencies')
    monkeypatch.setattr(X,'connect',forbidden)
    monkeypatch.setattr(args['pipeline'],'run',forbidden)
    assert X.run_experiment(**args)=={'mode':'off','status':'disabled'}
    monkeypatch.setenv('SHIFTLINK_HPU_RETRIEVAL','experiment')
    assert X.run_experiment(**args,mode='off')['status']=='disabled'
    normal=args['service'].query({'question':QUESTION,'equipment_id':'EQ-0001'})
    assert normal['cited_card_ids']==[did], 'The experiment environment must not hook normal queries'


def test_relation_recovers_missed_history_without_mutation(experiment):
    args,did=experiment
    original=deepcopy(args['pipeline'].rows)
    vectors=args['pipeline'].vec.copy()
    before=list(args['service'].storage.connection.iterdump())
    result=X.run_experiment(**args,mode='experiment')
    assert result['status']=='completed'
    assert result['baseline']['abstained'] and result['baseline']['cited_card_ids']==[]
    assert result['trial']['cited_card_ids']==[did] and not result['trial']['abstained']
    assert result['added_card_ids']==[did]
    assert result['trial']['candidate_count']<=result['candidate_budget']
    assert result['timings_ms']['baseline']>=0 and result['timings_ms']['trial']>=0
    assert args['pipeline'].rows==original and np.array_equal(args['pipeline'].vec,vectors)
    assert list(args['service'].storage.connection.iterdump())==before


@pytest.mark.parametrize('case', ['judge_reject','unrecorded_duration','current_action','other_asset','other_incident','other_equipment','named_other_unit','revoked','legacy','stale_chunk'])
def test_negative_boundaries(experiment,monkeypatch,case):
    args,did=experiment
    args={**args,'payload':deepcopy(args['payload'])}
    if case=='judge_reject': monkeypatch.setattr(E,'judge_dist',lambda *a,**kw:[1,0,0,0])
    if case=='unrecorded_duration': args['payload']['question']=QUESTION.replace('137','999')
    if case=='current_action': args['payload']['question']='과거 근무일지를 참고해서 지금 필터를 교체해도 되나요?'
    if case=='other_asset': args['payload']['asset_id']='replacement'
    if case=='other_incident': args['payload']['incident_id']='unrelated'
    if case=='other_equipment': args['payload'].update(eq_id='EQ-0004',asset_id='different')
    if case=='named_other_unit': args['payload']['question']='GR-01 근무일지의 필터 교체 순서와 결과는?'
    if case=='revoked': args['service'].review_card_draft(did,{'action':'reject','reason':'반례','expected_revision':2},ACTOR)
    if case=='legacy':
        con=args['service'].storage.connection
        with con: con.execute("UPDATE query_log SET payload=json_remove(payload,'$.publication_ticket') WHERE query_id=?",(args['witness_query_id'],))
    if case=='stale_chunk':
        args['pipeline'].rows=deepcopy(args['pipeline'].rows)
        for row in args['pipeline'].rows:
            if row['metadata']['source']==did: row['text']='changed'
    result=X.run_experiment(**args,mode='experiment')
    assert result['status']=='completed'
    assert result['trial']['cited_card_ids']==[] and result['trial']['abstained']
    if case not in {'judge_reject','unrecorded_duration'}: assert result['added_card_ids']==[]


def test_change_during_trial_invalidates_pair(experiment,monkeypatch):
    args,did=experiment
    original=E.judge_dist
    changed=[]
    def revoke(*a,**kw):
        if a[1]['chunk_id'].startswith('field_') and not changed:
            changed.append(True)
            args['service'].review_card_draft(did,{'action':'reject','reason':'실험 중 변경','expected_revision':2},ACTOR)
        return original(*a,**kw)
    monkeypatch.setattr(E,'judge_dist',revoke)
    result=X.run_experiment(**args,mode='experiment')
    assert result['status']=='invalidated' and result['reason']=='publication_changed'
    assert 'trial' not in result


def test_paired_report_against_fixed_oracles(experiment,monkeypatch):
    args,did=experiment
    cases=json.loads(Path('tests/fixtures/hpu_retrieval_cases.json').read_text(encoding='utf-8'))
    reports=[]
    for case in cases:
        payload={**args['payload'],'question':case['question']}
        if case.get('asset_mismatch'): payload['asset_id']='other'
        if case.get('incident_mismatch'): payload['incident_id']='other'
        if case.get('revoked'):
            args['service'].review_card_draft(did,{'action':'reject','reason':'고정 반례','expected_revision':2},ACTOR)
        with monkeypatch.context() as scoped:
            if case.get('judge_reject'): scoped.setattr(E,'judge_dist',lambda *a,**kw:[1,0,0,0])
            for repeat in range(5):
                result=X.run_experiment(**{**args,'payload':payload},mode='experiment',trial_first=bool(repeat%2))
                reports.append({**X.score_case(case,result,card_id=did),'repeat':repeat})
    report=X.summarize(reports)
    assert report['completed']==len(cases)*5 and report['trial']['wrong_citations']==0
    assert report['trial']['misconnections']==0
    assert report['trial']['expected_citation_hits']>report['baseline']['expected_citation_hits']
    assert report['trial']['abstentions']<report['baseline']['abstentions']
    assert report['decision']=='fixture_pass_only'
    path=os.environ.get('SHIFTLINK_HPU_EXPERIMENT_REPORT')
    if path:
        with Path(path).open('x',encoding='utf-8') as target:
            json.dump({'cases':reports,'summary':report},target,ensure_ascii=False,indent=2,allow_nan=False)


def test_missing_expected_citation_is_a_regression():
    output={'cited_card_ids':[],'abstained':True,'candidate_count':0,'judge_count':0}
    result={'status':'completed','baseline':output,'trial':output,'added_card_ids':[],
            'timings_ms':{'baseline':1,'trial_total':2},'order':['baseline','trial']}
    row=X.score_case({'id':'missed','expect_citation':True,'allow_relation':True},result,card_id='K-expected')
    assert X.summarize([row])['decision']=='fixture_regression_or_incomplete'


def test_errors_and_invalidated_pairs_are_not_successes(experiment):
    args,_=experiment
    assert X.run_experiment(**args,mode='invalid')['status']=='error'
    assert X.run_experiment(mode='experiment')['status']=='error'
    rows=[X.score_case({'id':'invalid'}, {'status':'invalidated'}, card_id='K-x')]
    assert X.summarize(rows)['excluded']==1
    assert X.summarize(rows)['decision']=='fixture_regression_or_incomplete'
