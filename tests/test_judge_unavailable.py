"""No judge, no answer: a judge that cannot run must not let a card through unjudged (demo server answers 503 "try again")."""
import io
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from shiftlink.agent.pipeline import FixedPipeline, JudgeUnavailableError
from shiftlink.mes import query as query_module
from shiftlink.mes.server import MesService, _Handler
from test_router_pipeline import RecordingTools

CARD = {"card_id": "K-0001", "title": "펌프 소음", "tacit_type": "T1", "condition_status": "verified",
        "know_how": "흡입관 이음부부터 본다.", "safety_flag": False}
QUERY = {"question": "펌프 소음이 커요", "line_id": "L1", "eq_id": "HPU-01"}


class Tools(RecordingTools):
    def search_cards(self, **_):
        return [dict(CARD)]


class Model:
    calls = 0

    def __call__(self, **_):
        Model.calls += 1
        return {"answer": "모델이 쓴 문장입니다.", "cited_card_ids": ["K-0001"]}


def broken_judge(question, card):
    raise ConnectionError("HTTP 404 model 'exaone-sft-judge' not found")


def test_strict_pipeline_raises_instead_of_answering_unjudged():
    pipe = FixedPipeline(model=Model(), tools=Tools(), judge=broken_judge, answer_mode="extract", judge_strict=True)
    with pytest.raises(JudgeUnavailableError, match="ConnectionError"):
        pipe.run(QUERY)


def test_default_pipeline_keeps_the_old_fall_through_for_evaluation_scripts():
    Model.calls = 0
    result = FixedPipeline(model=Model(), tools=Tools(), judge=broken_judge).run(QUERY)
    assert Model.calls == 1 and not result.output.no_knowledge  # unjudged, as before


def test_demo_pipeline_is_strict():
    assert query_module.build_query_pipeline().judge_strict is True


@pytest.mark.parametrize("payload, expected", [
    ({"models": [{"name": "exaone-sft-judge:latest"}]}, "ok"),
    ({"models": [{"name": "other:latest"}]}, "missing"),
])
def test_judge_model_status_reads_the_ollama_model_list(monkeypatch, payload, expected):
    class Response(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *exc): return False
    monkeypatch.setattr(query_module.urllib.request, "urlopen", lambda *a, **k: Response(json.dumps(payload).encode()))
    assert query_module.judge_model_status("http://x", "exaone-sft-judge") == expected


def test_judge_model_status_is_unreachable_when_ollama_is_down(monkeypatch):
    def down(*a, **k):
        raise OSError("connection refused")
    monkeypatch.setattr(query_module.urllib.request, "urlopen", down)
    assert query_module.judge_model_status("http://x", "m") == "unreachable"


def test_query_endpoint_answers_503_with_a_wait_message():
    service = MesService(Path("docs/data/reference/00_plant_and_relations.json"))

    class Pipeline:
        def run(self, payload):
            raise JudgeUnavailableError("ConnectionError: refused")

    service.query_pipeline = Pipeline()
    handler = type("H", (_Handler,), {"service": service, "web_root": Path("shiftlink/mes/web"), "api_only": False})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    try:
        req = Request(f"http://127.0.0.1:{server.server_port}/api/query",
                      json.dumps({"question": "q", "equipment_id": "EQ-0004"}).encode(), {"Content-Type": "application/json"})
        with pytest.raises(HTTPError) as caught:
            urlopen(req, timeout=5)
        body = json.load(caught.value)
        assert caught.value.code == 503 and body["retry"] is True
        assert body["error"] == "판정 모델을 쓸 수 없습니다. 잠시 후 다시 시도해 주세요."
        assert service.storage.pending_queries() == []  # nothing is logged or uploaded for a failed query
    finally:
        server.shutdown()
        worker.join()
        server.server_close()
        service.storage.close()
