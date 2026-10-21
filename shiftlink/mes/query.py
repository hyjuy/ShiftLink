"""Connect a camera selection and observable MES readings to the fixed pipeline."""

import json
import os
import time
import urllib.request
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

from shiftlink.agent.pipeline import FixedPipeline
from shiftlink.agent.response import AgentResponse
from shiftlink.edge.ollama import DEFAULT_HOST, DEFAULT_TIMEOUT_S, KEEP_ALIVE, OllamaModel
from shiftlink.rag.loader import load_card_provider
from shiftlink.rag.retrieval import InMemoryToolProvider

from .card_adapter import MesCardAdapter
from .smalltalk import LEAD, REPLY, classify

ROOT = Path(__file__).resolve().parents[2]
# Demo server defaults (hybrid confirmed 10/7): SFT answer model + guard v2 (E1 on a guard hit) and the SFT judge.
ANSWER_MODE = 'hybrid'
ANSWER_MODEL = 'exaone-sft-answer'
JUDGE_MODEL = 'exaone-sft-judge'


def build_query_pipeline():
    if os.environ.get('SHIFTLINK_ANSWER_MODE', ANSWER_MODE) == 's30h':   # team decision 10/16 (demo = S30h)
        from shiftlink.rag2.s30h import S30hPipeline
        host = os.environ.get('OLLAMA_HOST', DEFAULT_HOST)
        return S30hPipeline(
            index_dir=os.environ.get('SHIFTLINK_S30H_INDEX', str(ROOT / 'data/rag2')), host=host,
            judge_host=os.environ.get('SHIFTLINK_S30H_JUDGE_HOST', host),
            answer_model=os.environ.get('SHIFTLINK_S30H_ANSWER_MODEL', 'exaone-rag-aug-ck106'),
            judge_model=os.environ.get('SHIFTLINK_JUDGE_MODEL', JUDGE_MODEL),
            judge_ctx=int(os.environ.get('SHIFTLINK_S30H_JUDGE_CTX', '2048')),
            source_conditions=os.environ.get('SHIFTLINK_S30H_SOURCE_CONDITIONS') == '1',
            cards=load_card_provider(ROOT / 'docs/data/knowledge_cards/kb/kb_cards.json').provider.cards)
    return FixedPipeline(
        model=OllamaModel(model=os.environ.get('SHIFTLINK_QUERY_MODEL', ANSWER_MODEL),
                          judge_model=os.environ.get('SHIFTLINK_JUDGE_MODEL', JUDGE_MODEL),
                          host=os.environ.get('OLLAMA_HOST', DEFAULT_HOST), timeout_s=DEFAULT_TIMEOUT_S),
        tools=load_card_provider(ROOT / 'docs/data/knowledge_cards/kb/kb_cards.json').provider,
        answer_mode=os.environ.get('SHIFTLINK_ANSWER_MODE', ANSWER_MODE),  # 'extract' = E1 only (no answer model)
        judge_strict=True,  # no judge, no answer: the server replies 503 "try again" instead of showing a card unjudged
    )


def warm_models(pipeline, *, attempts=30, wait_s=10.0, sleep=time.sleep):
    """Load the judge (and, unless extract, the answer model) into Ollama so the first PDA query does not wait ~50 s.

    Same num_ctx as the real calls, or Ollama reloads on the first query. Retries while Ollama is still starting after boot.
    Returns the names that loaded.
    """
    if pipeline.answer_mode == 's30h':
        return pipeline.warm(attempts=attempts, wait_s=wait_s, sleep=sleep)
    model = pipeline.model
    targets = [(model.judge_model, model.judge_num_ctx)]
    if pipeline.answer_mode != 'extract' and model.model != model.judge_model:
        targets.append((model.model, model.num_ctx))
    loaded = []
    for name, num_ctx in targets:
        for _ in range(attempts):
            try:
                model._post('/api/generate', {'model': name, 'keep_alive': KEEP_ALIVE, 'options': {'num_ctx': num_ctx}})
            except Exception:  # noqa: BLE001 - Ollama not up yet or model missing: try again later
                sleep(wait_s)
                continue
            loaded.append(name)
            break
    return loaded


def judge_model_status(host=None, name=None, timeout=3.0):
    """'ok' | 'missing' | 'unreachable': is the judge model registered in Ollama? Used for a startup warning."""
    host = (host or os.environ.get('OLLAMA_HOST', DEFAULT_HOST)).rstrip('/')
    name = name or os.environ.get('SHIFTLINK_JUDGE_MODEL', JUDGE_MODEL)
    try:
        with urllib.request.urlopen(f'{host}/api/tags', timeout=timeout) as response:
            names = {m.get('name', '') for m in json.load(response).get('models', [])}
    except Exception:  # noqa: BLE001 - any failure means we cannot confirm the model
        return 'unreachable'
    return 'ok' if name in names or f'{name}:latest' in names else 'missing'


def query_service(service, body, *, pipeline=None):
    if not isinstance(body, dict) or set(body) - {'question', 'equipment_id', 'scan_id', 'k', 'incident_id'}:
        raise ValueError('query body must contain question and optional equipment_id, scan_id, k, incident_id')
    question = body.get('question')
    if not isinstance(question, str) or not question.strip() or len(question) > 4000:
        raise ValueError('question must be a nonblank string of at most 4000 characters')
    if 'equipment_id' in body and 'scan_id' in body:
        raise ValueError('select equipment_id or scan_id, not both')
    # greeting/thanks/bye alone -> a fixed reply, no model; a leading greeting -> only the rest goes to the pipeline
    smalltalk, rest = classify(question)
    with service._lock:
        scan = service._scans[-1].copy() if service._scans else None
        if 'equipment_id' in body:
            equipment_id = body['equipment_id']
            if not isinstance(equipment_id, str) or not equipment_id:
                raise ValueError('equipment_id must be a nonblank string')
            scan = None
        else:
            if not scan:
                raise ValueError('no recent equipment scan; select equipment_id explicitly')
            if 'scan_id' in body and body['scan_id'] != scan['scan_id']:
                raise ValueError('equipment scan changed; scan again before asking')
            equipment_id = scan['equipment_id']
        config = service.active_config
        equipment = next((eq for eq in config.equipment if eq.equipment_id == equipment_id and eq.active), None)
        if equipment is None:
            raise ValueError('equipment_id must name active equipment')
        incident_id = body.get('incident_id')
        if 'incident_id' in body:
            if not isinstance(incident_id, str) or not incident_id.strip() or len(incident_id) > 64:
                raise ValueError('incident_id must be a nonblank string of at most 64 characters')
            incident = service.storage.get_incident(incident_id)
            if incident is None or incident['assets'].get(equipment_id) != equipment.asset_id:
                raise ValueError('incident does not match the selected equipment/asset')
        context = {'config_id': config.config_id, 'equipment_id': equipment_id, 'asset_id': equipment.asset_id,
                   'incident_id': incident_id}
        # Only these fields reach MesCardAdapter. Scenario labels and ground truth are excluded.
        snap = asdict(service.engine.snapshot)
        visible = {key: snap[key] for key in ('run_id', 'line_id', 'simulated_at', 'measurements', 'active_alarms')}
        observed = {'config_id': config.config_id, 'snapshot': visible}
        observer = SimpleNamespace(observations=lambda *args, **kwargs: observed)
        empty = InMemoryToolProvider(cards=[], equipment_db=service.catalog.data['equipment'],
                                     equipment_types=service.catalog.data['equipment_types'])
        prepared = MesCardAdapter(observer, config, empty).search(
            visible['run_id'], equipment_id, rest or question, k=body.get('k', 5))
        if rest is None:
            return {**AgentResponse(mode='query', answer=REPLY[smalltalk]).model_dump(mode='json'), 'scan': scan,
                    'query_context': context, 'knowledge_status': 'smalltalk', 'evidence': prepared['evidence'],
                    'is_synthetic': True, 'smalltalk': smalltalk}
        if pipeline is None:
            if service.query_pipeline is None:
                service.query_pipeline = build_query_pipeline()
            pipeline = service.query_pipeline
        pipeline, publication_ticket = service.publications.snapshot(
            pipeline,equipment_id,equipment.asset_id,prepared['request'].model_dump(mode='json')['observations'])
    # A model request can take a minute; never hold the simulator lock during it.
    result = pipeline.run(prepared['request'].model_dump(mode='json'))
    output = result.output.model_dump(mode='json')
    if smalltalk in LEAD and output.get('answer') and not output.get('no_knowledge') and not output.get('review_queue'):
        output['answer'] = LEAD[smalltalk] + output['answer']
    if output.get('review_queue') or output.get('validation_errors'):
        knowledge_status = 'answer_withheld'
    elif output.get('no_knowledge') and output.get('unverified_card_ids'):
        knowledge_status = 'conditions_unverified'
    elif output.get('no_knowledge'):
        knowledge_status = 'no_applicable_card'
    elif output.get('cited_card_ids'):
        knowledge_status = 'answered'
    else:
        knowledge_status = 'unknown'
    return {**output, 'scan': scan, 'query_context': context, 'knowledge_status': knowledge_status,
            'evidence': prepared['evidence'], 'is_synthetic': True,
            **({'_publication_ticket':publication_ticket} if publication_ticket else {}),
            **({'s30h_trace': result.tool_results} if getattr(pipeline, 'answer_mode', None) == 's30h' else {})}
