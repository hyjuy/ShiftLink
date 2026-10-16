"""S30h answer mode (rag2/s30h.py): routes, threshold, citations, safety notices and the MES hookup, Ollama mocked."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from shiftlink.agent.pipeline import JudgeUnavailableError
from shiftlink.mes import query as Q
from shiftlink.rag2 import evidence_score as E
from shiftlink.rag2 import generate as G
from shiftlink.rag2 import s30h as S

CATALOG = {"equipment_types": [{"equipment_type_id": "ET-1", "type_code": "HPU"}, {"equipment_type_id": "ET-2", "type_code": "GR"}],
           "equipment": [{"equipment_id": "EQ-0001", "code": "HPU-01", "equipment_type_id": "ET-1"},
                         {"equipment_id": "EQ-0004", "code": "GR-01", "equipment_type_id": "ET-2"}]}
CARDS = [{"card_id": "K-S1", "equipment": "HPU", "safety_flag": True, "safety_basis": "감압 후 정비",
          "type_payload": {"steps": [{"stop_conditions": ["압력이 남아 있으면 멈춘다"]}]}},
         {"card_id": "K-S2", "equipment": "GR", "safety_flag": True, "safety_basis": "다른 설비"},
         {"card_id": "K-S3", "equipment": "HPU", "safety_flag": True, "safety_basis": "다른 설치", "mes_equipment_id": "EQ-9999"},
         {"card_id": "K-A1", "equipment": "HPU", "safety_flag": False, "safety_basis": ""}]


def chunk(cid, kind, source, folder, page=None, text="펌프 압력 152 bar 확인"):
    return {"chunk_id": cid, "text": text, "tokens": 50,
            "metadata": {"kind": kind, "source": source, "page": page, "folder": folder, "section": None}}


ROWS = [chunk("c1", "source", "hpu_manual.pdf", "HPU", page=12), chunk("c2", "card", "K-1003", "HPU"),
        chunk("c3", "source", "gr_manual.pdf", "GR", page=3), chunk("c4", "source", "safety.pdf", "safety", page=1)]


@pytest.fixture
def pipe(tmp_path, monkeypatch):
    (tmp_path / "chunks_700.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in ROWS), encoding="utf-8")
    np.save(tmp_path / "vectors_700__embeddinggemma_300m.npy", np.eye(4, dtype=np.float32))
    p = S.S30hPipeline(tmp_path, "http://main:11434", "http://judge:11436", cards=CARDS, catalog=CATALOG)
    monkeypatch.setattr(p, "_embed", lambda q: np.array([1, 1, 1, 1], dtype=np.float32) / 2)
    return p


def judged(monkeypatch, p2: dict, seen=None):
    """p2: chunk_id -> P(>=2); None = the judge gave no distribution."""
    def fake(question, r, host, model, ctx):
        if seen is not None:
            seen.append((r["chunk_id"], host, model, ctx))
        p = p2[r["chunk_id"]]
        return None if p is None else [1 - p, 0.0, p, 0.0]
    monkeypatch.setattr(E, "judge_dist", fake)


def answer(text, cites, p_insuff=None):
    return {"raw": json.dumps({"insufficient_evidence": False, "answer": text, "citations": cites}, ensure_ascii=False),
            "prompt_tokens": 10, "seconds": 1.0, "p_insuff": p_insuff}


def test_folder_filter_keeps_equipment_and_common_folders(pipe):
    assert [r["chunk_id"] for r in pipe.evidence("q", "HPU")] == ["c1", "c2", "c4"]
    assert len(pipe.evidence("q", None)) == 4


def test_confident_route_forces_an_answer_and_lists_sources(pipe, monkeypatch):
    seen = []
    judged(monkeypatch, {"c1": 0.95, "c2": 0.5, "c4": 0.1}, seen)
    calls = []
    monkeypatch.setattr(G, "ask_raw", lambda p, host, prefix: calls.append((host, prefix)) or
                        {"raw": prefix + '압력 152 bar를 확인합니다 [S1][S2]", "citations": ["S1", "S2"]}', "prompt_tokens": 9})
    r = pipe.run({"question": "압력이 낮아요", "eq_id": "EQ-0001"})
    assert r.tool_results["route"] == "confident" and r.tool_results["kept"] == ["c1", "c2"]   # c4 < 0.3 dropped
    assert calls == [("http://main:11434", G.FORCE_PREFIX)]
    assert {(h, m, c) for _, h, m, c in seen} == {("http://judge:11436", "exaone-sft-judge", 2048)}
    out = r.output
    assert not out.no_knowledge and "[S" not in out.answer
    assert out.answer.endswith("근거: hpu_manual p.12 · K-1003")
    assert out.cited_card_ids == ["K-1003"]
    assert [n.card_id for n in out.safety_notices] == ["K-S1"]   # same type, no other installation, safety only
    assert out.safety_notices[0].stop_conditions == ["압력이 남아 있으면 멈춘다"]


def test_model_route_abstains_at_threshold(pipe, monkeypatch):
    judged(monkeypatch, {"c1": 0.6, "c2": 0.4, "c4": 0.0})
    monkeypatch.setattr(G, "ask", lambda p, host, logprobs: answer("152 bar 확인 [S1]", ["S1"], p_insuff=S.T))
    r = pipe.run({"question": "q", "eq_id": "EQ-0001"})
    out = r.output
    assert out.no_knowledge and out.answer == "" and out.cited_card_ids == [] and r.tool_results["abstain_reason"] == "threshold"
    assert [n.card_id for n in out.safety_notices] == ["K-S1"]   # the safety gate stays even without an answer


def test_model_route_answers_below_threshold(pipe, monkeypatch):
    judged(monkeypatch, {"c1": 0.6, "c2": 0.4, "c4": 0.0})
    monkeypatch.setattr(G, "ask", lambda p, host, logprobs: answer("152 bar 확인 [S1]", ["S1"], p_insuff=S.T - 1e-9))
    r = pipe.run({"question": "q", "eq_id": "EQ-0001"})
    assert r.tool_results["route"] == "model" and not r.output.no_knowledge
    assert r.output.answer == "152 bar 확인\n근거: hpu_manual p.12"


def test_nothing_kept_abstains_without_a_model_call(pipe, monkeypatch):
    judged(monkeypatch, {"c1": 0.29, "c2": 0.0, "c4": 0.1})
    monkeypatch.setattr(G, "ask", lambda *a, **k: pytest.fail("no model call when every chunk is dropped"))
    r = pipe.run({"question": "q", "eq_id": "EQ-0001"})
    assert r.tool_results["route"] == "drop_all" and r.output.no_knowledge and r.tool_results["abstain_reason"] == "drop_all"
    assert r.tool_results["kept"] == [] and r.tool_results["judge_p"] == [0.29, 0.0, 0.1]


def test_judge_failure_is_unavailable_not_unfiltered(pipe, monkeypatch):
    judged(monkeypatch, {"c1": 0.9, "c2": None, "c4": 0.1})
    with pytest.raises(JudgeUnavailableError):
        pipe.run({"question": "q", "eq_id": "EQ-0001"})


def test_mes_builds_s30h_and_warms_its_three_models(pipe, tmp_path, monkeypatch):
    monkeypatch.setenv("SHIFTLINK_ANSWER_MODE", "s30h")
    monkeypatch.setenv("SHIFTLINK_S30H_INDEX", str(tmp_path))
    monkeypatch.setenv("SHIFTLINK_S30H_JUDGE_HOST", "http://judge:11436")
    built = Q.build_query_pipeline()
    assert built.answer_mode == "s30h" and built.judge_host == "http://judge:11436" and built.model.model == "exaone-rag-aug-ck106"
    assert G.KEEP_ALIVE == -1 and E.KEEP_ALIVE == -1
    notices = built.safety("EQ-0001", "HPU")   # real KB cards (loader models), not dicts
    assert notices and all(n.card_id.startswith("K-") and n.safety_basis for n in notices)
    posts = []
    monkeypatch.setattr(built, "_post", lambda host, path, body, timeout=300: posts.append((host, path, body["model"], body["options"])))
    assert Q.warm_models(built) == ["exaone-sft-judge", "exaone-rag-aug-ck106", "embeddinggemma:300m"]   # judge first
    assert posts[0][0] == "http://judge:11436" and posts[0][3] == {"num_ctx": 2048} and posts[2][3] == {"num_gpu": 0}


def test_query_service_returns_the_pda_shape(pipe, monkeypatch):
    from pathlib import Path
    from shiftlink.mes.server import MesService
    service = MesService(Path("docs/data/reference/00_plant_and_relations.json"))
    try:
        judged(monkeypatch, {"c1": 0.95, "c2": 0.1, "c4": 0.1})
        monkeypatch.setattr(G, "ask_raw", lambda p, host, prefix: {"raw": prefix + '152 bar [S1]", "citations": ["S1"]}'})
        service.query_pipeline = pipe
        result = service.query({"question": "압력", "equipment_id": "EQ-0001"})
        assert result["answer"].startswith("152 bar") and result["no_knowledge"] is False
        assert {"cited_card_ids", "safety_notices", "evidence", "scan", "review_queue"} <= set(result)
        logged = json.loads(service.storage.pending_queries()[-1][2])["s30h_trace"]   # why it answered, kept in the MES log
        assert logged["route"] == "confident" and logged["candidates"] == ["c1", "c2", "c4"] and logged["judge_p"] == [0.95, 0.1, 0.1]
        assert logged["kept"] == ["c1"] and logged["abstain_reason"] == ""
    finally:
        service.storage.close()
