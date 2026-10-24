"""Explicit real-model benchmark. No model mocking, rank manipulation, or operational writes.

Run only with SHIFTLINK_HPU_LIVE_INDEX, MAIN_HOST, JUDGE_HOST and OUTPUT set.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request

import numpy as np
import pytest

from shiftlink.mes.hpu_retrieval_experiment import run_experiment
from shiftlink.mes.incident_ontology import content_hash, project_incident, read_incident_bundle
from shiftlink.rag.loader import load_card_provider
from shiftlink.rag2.s30h import S30hPipeline
from test_work_report_reuse_harness import service
from test_work_report_capture import captured


class RecordingPipeline(S30hPipeline):
    def run(self,payload):
        result=super().run(payload)
        self.captures.append({'output':result.output.model_dump(mode='json'),
                              'trace':deepcopy(result.tool_results)})
        return result


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_real_model_hpu_pairs(service,tmp_path,monkeypatch):
    names=['INDEX','MAIN_HOST','JUDGE_HOST','OUTPUT']
    settings={name:os.environ.get('SHIFTLINK_HPU_LIVE_'+name) for name in names}
    assert all(settings.values()), 'Explicit real-model endpoints, index and new output directory are required'
    out=Path(settings['OUTPUT']);out.mkdir(parents=True,exist_ok=False)
    main,judge=settings['MAIN_HOST'],settings['JUDGE_HOST']
    monkeypatch.setenv('OLLAMA_HOST',main)
    index=Path(settings['INDEX'])
    index_hashes={p.name:file_hash(p) for p in index.glob('*700*')}
    model_info={}
    for role,host in [('main',main),('judge',judge)]:
        model_info[role]=json.load(urllib.request.urlopen(host+'/api/tags',timeout=15))
    kb=Path('docs/data/knowledge_cards/kb/kb_cards.json')
    provider=load_card_provider(kb).provider
    pipe=RecordingPipeline(index,main,judge,answer_model='exaone-rag-mes-ck176',
        judge_model='exaone-sft-judge',judge_ctx=2048,cards=[c.model_dump(mode='json') for c in provider.cards],
        catalog=service.catalog.data,mes_block=True,event_label=True,mes_only=False,mes_prefix=True,p_fix=True,
        unobserved_guard=True,unit_guard=True,source_conditions=True,knowledge_graph=True)
    pipe.captures=[]
    service.query_pipeline=pipe
    note=captured(service,normal_run_minutes=137,normal_run_evidence='137분 연속 운전, 정지·재발 없음')
    note['work_report']['records'][0]['action_steps'][0].update(worker='검증자',performed_at='2026-10-22T09:10')
    note['work_report']['records'][0]['action_steps'][1].update(worker='검증자',performed_at='2026-10-22T09:20')
    saved=service.record_work_report(note)
    did=saved['candidates'][0]['draft_id']
    actor={'id':'isolated-live-benchmark','name':'격리 합성 기록 검증'}
    for revision,action in enumerate(('approve','quality_pass')):
        service.review_card_draft(did,{'action':action,'reason':'격리 합성 fixture 원문 확인','expected_revision':revision},actor)
    assert service.publications.process_one(), 'Real embedding publication did not run'
    artifact=service.storage.get_card_draft(did)['review_flags']['publication']
    assert artifact['state']=='published',artifact.get('error')
    iid=saved['incidents'][0]['incident_id']
    witness_attempts=[];witness=None
    for question in ['근무일지에서 필터 교체 후 137분 관찰 결과와 시각만 알려줘',
                     '근무일지의 필터 교체 순서와 결과는?',
                     '근무일지에서 필터 오염 확인과 필터 교체, 2026-10-22T09:10 조치 기록을 원문 그대로 읽어줘']:
        result=service.query({'question':question,'equipment_id':'EQ-0001','incident_id':iid})
        witness_attempts.append({'question':question,'result':result})
        if did in result.get('cited_card_ids',[]):witness=result;break
    metadata={'models_mocked':False,'index_rank_modified':False,'data_kind':'synthetic_reviewed_work_report',
        'models':model_info,'index_hashes_before':index_hashes,'kb_hash_before':file_hash(kb),
        'card_id':did,'incident_id':iid,'witness_attempts':witness_attempts,
        'adoption_gates':{'new_misconnections':0,'new_wrong_field_citations':0,'source_mutations':0,
                         'required_recovered_cases':1,'provisional_mean_added_ms':1000,'provisional_p95_ratio':1.1},
        'temperature':0,'answer_model':'exaone-rag-mes-ck176','judge_model':'exaone-sft-judge'}
    (out/'setup.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    assert witness is not None, 'No real judged citation witness; see setup.json. Do not fabricate a ticket.'
    db=service.storage.connection.execute('PRAGMA database_list').fetchone()[2]
    base=project_incident(read_incident_bundle(db,iid,source_namespace='isolated-real-hpu-20261025',
        catalog=service.catalog.data,config_catalog_hashes={service.active_config.config_id:content_hash(service.catalog.data)}),equipment_type='HPU')
    cases=json.loads(Path('tests/fixtures/hpu_retrieval_live_cases.json').read_text(encoding='utf-8'))
    original_config=service.active_config
    records=[]
    for index_case,case in enumerate(cases):
        if case.get('revoked'):
            service.review_card_draft(did,{'action':'reject','reason':'격리 반려 대조군','expected_revision':2},actor)
        if case.get('replacement'):
            eq=original_config.equipment[0]
            service.active_config=replace(original_config,equipment=(replace(eq,asset_id='AS-LIVE-REPLACEMENT'),*original_config.equipment[1:]))
        equipment=case.get('equipment_id','EQ-0001')
        eq=next(e for e in service.active_config.equipment if e.equipment_id==equipment)
        observations=deepcopy(witness['evidence'].get('measurements',[])) if equipment=='EQ-0001' else []
        # Use the unchanged MES request observations, which carry signal/value/unit/quality.
        observations=[{**r,'signal':r.get('signal')} for r in observations if r.get('equipment_id',equipment)==equipment]
        with service._lock:
            view,_=service.publications.snapshot(pipe,equipment,eq.asset_id,observations)
        payload={'question':case['question'],'eq_id':equipment,'asset_id':eq.asset_id,'incident_id':iid,
                 'observations':observations,'active_alarms':[]}
        before=list(service.storage.connection.iterdump())
        for repeat in range(2):
            pipe.captures.clear()
            started=time.time()
            comparison=run_experiment(service,view,payload,database=db,graph=base,
                witness_query_id=witness['query_id'],mode='experiment',trial_first=bool((index_case+repeat)%2))
            raw=dict(zip(comparison.get('order',[]),deepcopy(pipe.captures)))
            item={'case':case,'repeat':repeat,'comparison':comparison,'raw':raw,'wall_seconds':time.time()-started}
            records.append(item)
            with (out/'pairs.jsonl').open('a',encoding='utf-8') as target:
                target.write(json.dumps(item,ensure_ascii=False,allow_nan=False)+'\n')
            print(json.dumps({'case_id':case['id'],'repeat':repeat,'status':comparison['status'],
                'baseline':comparison.get('baseline'),'trial':comparison.get('trial'),
                'added':comparison.get('added_card_ids'),'seconds':item['wall_seconds']},ensure_ascii=False),flush=True)
        assert list(service.storage.connection.iterdump())==before, 'Paired run wrote business records'
        service.active_config=original_config
    final={'pairs':len(records),'completed':sum(r['comparison']['status']=='completed' for r in records),
        'index_unchanged':index_hashes=={p.name:file_hash(p) for p in Path(settings['INDEX']).glob('*700*')},
        'kb_unchanged':metadata['kb_hash_before']==file_hash(kb),'ordinary_query_hook_added':False}
    (out/'final.json').write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding='utf-8')
    assert final['index_unchanged'] and final['kb_unchanged']
