"""Opt-in real Ollama embedding -> durable publication -> S30h dense retrieval smoke.

SHIFTLINK_LIVE_EMBED_HOST must be provided. This does not evaluate answer/judge quality.
Run explicitly: python -m pytest tests/publication_live.py -q -s
"""
import os
import json

import numpy as np
import pytest

from test_work_report_reuse_harness import service, ask
from test_work_report_capture import captured
from test_publication_worker import quality_pass
from shiftlink.rag.embedding import PUBLICATION_MODEL, ollama_embed, normalise, prefixes
from shiftlink.rag2.embed import slug
from shiftlink.rag2.s30h import S30hPipeline, CFG


def test_real_embedding_to_s30h_search_pool(service,tmp_path,monkeypatch):
    host=os.environ.get('SHIFTLINK_LIVE_EMBED_HOST')
    if not host:pytest.fail('Set SHIFTLINK_LIVE_EMBED_HOST to the running Ollama host; no model is downloaded by this test')
    assert CFG['model']==PUBLICATION_MODEL
    monkeypatch.setenv('OLLAMA_HOST',host)
    initial=normalise(ollama_embed([prefixes(PUBLICATION_MODEL)[0]+'필터 점검과 교체'],PUBLICATION_MODEL,host),1)
    dimension=len(initial[0])
    index=tmp_path/'isolated-index';index.mkdir()
    (index/f"chunks_{CFG['size']}.jsonl").write_text('',encoding='utf-8')
    np.save(index/f"vectors_{CFG['size']}__{slug(PUBLICATION_MODEL)}.npy",np.empty((0,dimension),dtype=np.float32))
    query=ask(service)
    assert query['knowledge_status']=='no_applicable_card'
    note=captured(service);note['work_report']['records'][0]['query_id']=query['query_id']
    draft_id=quality_pass(service,note)
    pipe=S30hPipeline(index,host,host)
    service.query_pipeline=pipe
    service.publications.process_one()
    artifact=service.storage.get_card_draft(draft_id)['review_flags']['publication']
    assert artifact['state']=='published',artifact.get('error')
    eq=service.active_config.equipment[0]
    with service._lock:
        view,ticket=service.publications.snapshot(pipe,eq.equipment_id,eq.asset_id,[])
    evidence=view.evidence('필터가 오염됐을 때 점검과 교체 결과는?',eq.code.split('-')[0],eq.equipment_id)
    assert ticket and any(row['metadata']['source']==draft_id for row in evidence)
    print(json.dumps({'real_embedding_model':PUBLICATION_MODEL,'dimension':dimension,'published_card':draft_id,
                      'retrieved':True,'judge_and_answer_evaluated':False},ensure_ascii=False))
