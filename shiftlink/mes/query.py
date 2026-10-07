"""Connect a camera selection and observable MES readings to the fixed pipeline."""

import json
import os
import time
import urllib.request
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

from shiftlink.agent.pipeline import FixedPipeline
from shiftlink.edge.ollama import DEFAULT_HOST, DEFAULT_TIMEOUT_S, KEEP_ALIVE, OllamaModel
from shiftlink.rag.loader import load_card_provider
from shiftlink.rag.retrieval import InMemoryToolProvider

from .card_adapter import MesCardAdapter

ROOT = Path(__file__).resolve().parents[2]
# Demo server defaults (hybrid confirmed 10/7): SFT answer model + guard v2 (E1 on a guard hit) and the SFT judge.
ANSWER_MODE = 'hybrid'
ANSWER_MODEL = 'exaone-sft-answer'
JUDGE_MODEL = 'exaone-sft-judge'


def build_query_pipeline():
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
    if not isinstance(body, dict) or set(body) - {'question', 'equipment_id', 'scan_id', 'k'}:
        raise ValueError('query body must contain question and optional equipment_id, scan_id, k')
    question = body.get('question')
    if not isinstance(question, str) or not question.strip() or len(question) > 4000:
        raise ValueError('question must be a nonblank string of at most 4000 characters')
    if 'equipment_id' in body and 'scan_id' in body:
        raise ValueError('select equipment_id or scan_id, not both')
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
        # Only these fields reach MesCardAdapter. Scenario labels and ground truth are excluded.
        snap = asdict(service.engine.snapshot)
        visible = {key: snap[key] for key in ('run_id', 'line_id', 'simulated_at', 'measurements', 'active_alarms')}
        observed = {'config_id': config.config_id, 'snapshot': visible}
        observer = SimpleNamespace(observations=lambda *args, **kwargs: observed)
        empty = InMemoryToolProvider(cards=[], equipment_db=service.catalog.data['equipment'],
                                     equipment_types=service.catalog.data['equipment_types'])
        prepared = MesCardAdapter(observer, config, empty).search(
            visible['run_id'], equipment_id, question, k=body.get('k', 5))
        if pipeline is None:
            if service.query_pipeline is None:
                service.query_pipeline = build_query_pipeline()
            pipeline = service.query_pipeline
    # A model request can take a minute; never hold the simulator lock during it.
    result = pipeline.run(prepared['request'].model_dump(mode='json'))
    return {**result.output.model_dump(mode='json'), 'scan': scan,
            'evidence': prepared['evidence'], 'is_synthetic': True}
