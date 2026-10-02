"""Connect a camera selection and observable MES readings to the fixed pipeline."""

import os
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

from shiftlink.agent.pipeline import FixedPipeline
from shiftlink.edge.ollama import DEFAULT_HOST, DEFAULT_TIMEOUT_S, OllamaModel
from shiftlink.rag.loader import load_card_provider
from shiftlink.rag.retrieval import InMemoryToolProvider

from .card_adapter import MesCardAdapter

ROOT = Path(__file__).resolve().parents[2]


def build_query_pipeline():
    return FixedPipeline(
        model=OllamaModel(model=os.environ.get('SHIFTLINK_QUERY_MODEL', 'exaone3.5:2.4b-instruct-q4_K_M'),
                          host=os.environ.get('OLLAMA_HOST', DEFAULT_HOST), timeout_s=DEFAULT_TIMEOUT_S),
        tools=load_card_provider(ROOT / 'docs/data/knowledge_cards/kb/kb_cards.json').provider,
    )


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
