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


def test_other_units_events_are_dropped_without_backfill(tmp_path, monkeypatch):
    rows = [chunk("e1", "event", "K-1101", "COMMON", text="14:18 HPU-01 압력 저하 알람"),
            chunk("e2", "event", "K-1110", "COMMON", text="GR-01 베어링 85℃, 주 모터 정지"),
            chunk("e3", "event", "K-1110", "COMMON", text="운전 복귀는 아직 안 된다"),   # no code: inherits GR-01
            chunk("c1", "card", "K-1003", "HPU"), chunk("c2", "source", "hpu_manual.pdf", "HPU", page=5)]
    (tmp_path / "chunks_700.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    np.save(tmp_path / "vectors_700__embeddinggemma_300m.npy", np.eye(5, dtype=np.float32))
    p = S.S30hPipeline(tmp_path, "http://main:11434", "http://judge:11436", catalog=CATALOG)
    monkeypatch.setattr(p, "_embed", lambda q: np.array([4, 5, 3, 2, 1], dtype=np.float32) / 7.4)
    assert [r["chunk_id"] for r in p.evidence("q", "HPU")] == ["e2", "c1", "c2"]   # event_cap 1: the top event only
    assert [r["chunk_id"] for r in p.evidence("q", "HPU", "EQ-0001")] == ["c1", "c2"]   # GR-01 event out, e1 not moved up
    assert [r["chunk_id"] for r in p.evidence("q", "GR", "EQ-0004")] == ["e2"]   # GR-01 keeps it
    monkeypatch.setattr(p, "_embed", lambda q: np.array([1, 2, 5, 0, 0], dtype=np.float32) / 5.5)
    assert "e3" in [r["chunk_id"] for r in p.evidence("q", "HPU")]
    assert "e3" not in [r["chunk_id"] for r in p.evidence("q", "HPU", "EQ-0001")]   # codeless chunk inherits GR-01


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


@pytest.mark.parametrize("probability", [None, S.T - 1e-9, S.T])
def test_source_conditions_are_opt_in_and_do_not_change_route_or_abstention(pipe, monkeypatch, probability):
    from shiftlink.rag2.source_conditions import NOTICE
    cards = json.loads(S.ROOT.joinpath("docs/data/knowledge_cards/kb/kb_cards.json").read_text(encoding="utf-8"))["cards"]
    card = next(c for c in cards if c["card_id"] == "K-1027")
    ev = [chunk("card_K-1027", "card", "K-1027", "GR", text=card["know_how"])]
    pipe.cards = [card]
    def fixed_evidence(question, eq_type, equipment_id, units=None):
        assert eq_type == "GR" and equipment_id == "EQ-0004"
        return ev
    monkeypatch.setattr(pipe, "evidence", fixed_evidence)
    judged(monkeypatch, {"card_K-1027": 0.95 if probability is None else 0.6})
    calls = []
    def fake(*args, **kwargs):
        calls.append((args, kwargs))
        return answer("누유를 확인합니다 [S1]", ["S1"], probability)
    monkeypatch.setattr(G, "ask_raw", fake)
    monkeypatch.setattr(G, "ask", fake)
    payload = {"question": "누유", "eq_id": "EQ-0004"}
    baseline = pipe.run(payload)
    assert "수행 조건" not in baseline.output.answer
    pipe.source_conditions = True
    candidate = pipe.run(payload)
    assert len(calls) == 2 and calls[0] == calls[1]
    assert candidate.tool_results["route"] == baseline.tool_results["route"]
    assert candidate.tool_results["p_insuff"] == baseline.tool_results["p_insuff"]
    assert candidate.output.no_knowledge == baseline.output.no_knowledge
    assert candidate.output.cited_card_ids == baseline.output.cited_card_ids
    assert candidate.output.safety_notices == baseline.output.safety_notices
    if probability == S.T:
        assert candidate.output.answer == "" and candidate.tool_results["source_condition_cards"] == []
    else:
        assert NOTICE in candidate.output.answer and "[S" not in candidate.output.answer
        assert "재기동을 막은 뒤" in candidate.output.answer
        assert candidate.output.answer.endswith("누유를 확인합니다\n근거: K-1027")
        assert candidate.tool_results["source_condition_cards"] == ["K-1027"]


def test_nothing_kept_abstains_without_a_model_call(pipe, monkeypatch):
    judged(monkeypatch, {"c1": 0.29, "c2": 0.0, "c4": 0.1})
    monkeypatch.setattr(G, "ask", lambda *a, **k: pytest.fail("no model call when every chunk is dropped"))
    r = pipe.run({"question": "q", "eq_id": "EQ-0001"})
    assert r.tool_results["route"] == "drop_all" and r.output.no_knowledge and r.tool_results["abstain_reason"] == "drop_all"
    assert r.tool_results["kept"] == [] and r.tool_results["judge_p"] == [0.29, 0.0, 0.1]


def test_mes_low_high_states_reach_the_search_only(pipe, monkeypatch):
    searched, judged_q, prompts = [], [], []
    monkeypatch.setattr(pipe, "_embed", lambda q: searched.append(q) or np.ones(4, dtype=np.float32) / 2)
    monkeypatch.setattr(E, "judge_dist", lambda q, r, host, model, ctx: judged_q.append(q) or [0.0, 0.0, 1.0, 0.0])
    monkeypatch.setattr(G, "ask_raw", lambda p, host, prefix: prompts.append(p) or {"raw": prefix + '확인 [S1]", "citations": ["S1"]}'})
    obs = [{"signal": "hpu_oil_level", "value": 60}, {"signal": "hpu_oil_level_state", "value": "low"},
           {"signal": "hpu_pressure", "value": 150}, {"signal": "hpu_pressure_state", "value": "normal"}]
    r = pipe.run({"question": "필터 차압 경보", "eq_id": "EQ-0001", "observations": obs})
    assert searched == ["필터 차압 경보\n유압유 탱크 유면 60 pct (정상 70–100 pct 미만)"]
    assert r.tool_results["mes_lines"] == ["유압유 탱크 유면 60 pct (정상 70–100 pct 미만)"]
    assert set(judged_q) == {"필터 차압 경보"} and "정상 70–100" not in prompts[0]   # judge and answer keep the question
    searched.clear()
    pipe.run({"question": "필터 차압 경보", "eq_id": "EQ-0001", "observations": obs[2:]})
    assert searched == ["필터 차압 경보"]   # MES all normal: same search as before
    searched.clear()
    stopped = [{"signal": "hpu_pump_current", "value": 0}, {"signal": "hpu_pump_current_state", "value": "low"}]
    pipe.run({"question": "필터 차압 경보", "eq_id": "EQ-0001", "observations": stopped})
    assert searched == ["필터 차압 경보"]   # line stopped: 0 A is not an abnormal state


def test_mes_block_is_opt_in_and_reaches_the_answer_prompt(pipe, monkeypatch):
    judged(monkeypatch, {"c1": 0.95, "c2": 0.1, "c4": 0.1})
    calls = []
    monkeypatch.setattr(G, "ask_raw", lambda p, host, prefix, **kw: calls.append((p, kw)) or
                        {"raw": prefix + '유면이 60 pct로 낮습니다 [M]. 압력 152 bar를 확인합니다 [S1]", "citations": ["M", "S1"]}'})
    obs = [{"signal": "hpu_oil_level", "value": 60}, {"signal": "hpu_oil_level_state", "value": "low"}]
    payload = {"question": "유압 경보", "eq_id": "EQ-0001", "observations": obs, "snapshot_at": "2026-10-21T00:00:00+00:00",
               "active_alarms": []}
    off = pipe.run(payload)
    assert "[MES]" not in calls[0][0] and calls[0][1] == {}
    assert off.output.answer == "유면이 60 pct로 낮습니다. 압력 152 bar를 확인합니다\n근거: hpu_manual p.12"   # [M] not a source when off
    pipe.mes_block = True
    on = pipe.run(payload)
    p, kw = calls[1]
    assert p.index("[질문]") < p.index("[MES]") < p.index("[근거]") and kw["system"].count("[M]") == 1
    assert '<mes id="M" eq="HPU-01" snapshot_at="2026-10-21T00:00:00+00:00">\n활성 경보: 없음\n유압유 탱크 유면 60 pct · 낮음 (기준 70–100)' in p
    assert on.output.answer == "유면이 60 pct로 낮습니다. 압력 152 bar를 확인합니다\n근거: hpu_manual p.12 · MES 현재값"
    assert on.output.cited_card_ids == [] and on.tool_results["route"] == "confident"


def test_mes_only_route_asks_the_model_when_nothing_is_kept(pipe, monkeypatch):
    judged(monkeypatch, {"c1": 0.1, "c2": 0.0, "c4": 0.1})
    asked = []
    monkeypatch.setattr(G, "ask", lambda p, host, logprobs, **kw: asked.append(p) or
                        answer("MES 기준 HPU-01 유면은 60 pct로 낮습니다 [M].", ["M"], p_insuff=S.T - 1e-9))
    obs = [{"signal": "hpu_oil_level", "value": 60}, {"signal": "hpu_oil_level_state", "value": "low"}]
    payload = {"question": "유면 괜찮죠?", "eq_id": "EQ-0001", "observations": obs, "snapshot_at": "t", "active_alarms": []}
    pipe.mes_block = True
    assert pipe.run(payload).tool_results["route"] == "drop_all" and asked == []   # mes_only off: as before
    pipe.mes_only = True
    r = pipe.run(payload)
    assert r.tool_results["route"] == "mes_only" and asked[0].endswith("[근거]\n") and "[MES]" in asked[0]
    assert r.output.answer == "MES 기준 HPU-01 유면은 60 pct로 낮습니다.\n근거: MES 현재값" and not r.output.no_knowledge
    monkeypatch.setattr(G, "ask", lambda p, host, logprobs, **kw: answer("낮습니다 [M].", ["M"], p_insuff=S.T))
    assert pipe.run(payload).output.no_knowledge   # same threshold T as the model route
    pipe.mes_block = False
    assert pipe.run(payload).tool_results["route"] == "drop_all"   # needs the block


def test_mes_prefix_states_the_unit_in_code_and_fills_abstentions(pipe, monkeypatch):
    obs = [{"signal": "hpu_oil_level", "value": 60}, {"signal": "hpu_oil_level_state", "value": "low"}]
    payload = {"question": "q", "eq_id": "EQ-0001", "observations": obs, "active_alarms": ["AL-HYD-LOW"]}
    judged(monkeypatch, {"c1": 0.95, "c2": 0.1, "c4": 0.1})
    monkeypatch.setattr(G, "ask_raw", lambda p, host, prefix: {"raw": prefix + '152 bar [S1]", "citations": ["S1"]}'})
    assert pipe.run(payload).output.answer == "152 bar\n근거: hpu_manual p.12"   # off: unchanged
    pipe.mes_prefix = True
    head = "현재 MES(HPU-01): 유압유 탱크 유면 60 pct 낮음(기준 70–100), 활성 경보 유압 공급 저하(AL-HYD-LOW)."
    assert pipe.run(payload).output.answer == f"{head}\n152 bar\n근거: hpu_manual p.12"
    judged(monkeypatch, {"c1": 0.1, "c2": 0.0, "c4": 0.1})
    out = pipe.run(payload).output
    assert out.no_knowledge and out.answer == f"{head} 근거 자료에서 이 상황의 조치를 찾지 못했습니다. 조치는 정비 담당 확인이 필요합니다."


def test_unobserved_guard_answers_a_dropped_signal_in_code(pipe, monkeypatch):
    # MX-C27/C28 (10/21): bearing temperature dropped for bad quality; the model called it normal from the surface temperature
    obs = [{"signal": "gr_surface_temp", "value": 30}, {"signal": "gr_surface_temp_state", "value": "normal"}]
    judged(monkeypatch, {"c3": 0.95, "c4": 0.1})
    monkeypatch.setattr(G, "ask_raw", lambda p, host, prefix: {"raw": prefix + '베어링 온도 30도로 정상 [S1]", "citations": ["S1"]}'})
    payload = {"question": "입측 감속기 베어링 쪽 온도 MES로 보면 어때요?", "eq_id": "EQ-0004", "observations": obs}
    assert pipe.run(payload).tool_results["route"] == "confident"   # off: as before
    pipe.unobserved_guard = True
    pipe.specs["EQ-0004"]["gr_brg_temp"] = SimpleNamespace(name="감속기 베어링 온도")   # the test catalog has no GR points
    monkeypatch.setattr(E, "judge_dist", lambda *a, **k: pytest.fail("no search or judge for an unobserved signal"))
    r = pipe.run(payload)
    assert r.tool_results["route"] == "unobserved" and r.tool_results["unobserved"] == ["감속기 베어링 온도"]
    assert r.output.no_knowledge and r.output.answer.startswith("GR-01 감속기 베어링 온도: 지금 MES에 유효한 측정값이 없습니다.")
    assert [n.card_id for n in r.output.safety_notices] == ["K-S2"]
    assert S.unobserved("CAU 공압 지금 몇 kPa예요?", {"air_pressure": SimpleNamespace(name="압축공기 압력")}, obs) == ["압축공기 압력"]
    assert S.unobserved("표면 온도 괜찮아요?", pipe.specs["EQ-0004"], obs) == []   # observed signal
    assert S.unobserved("베어링 온도 괜찮아요?", pipe.specs["EQ-0004"], []) == []   # no MES snapshot at all
    # field words: 유압 (not 유압유 / 유압 펌프), 열 (not 열화), 진동 without RMS, a pole tag picks its pole
    hpu = {"hpu_pressure": SimpleNamespace(name="유압 공급 압력"), "hpu_oil_temp": SimpleNamespace(name="유압유 온도"),
           "hpu_pump_current": SimpleNamespace(name="유압 펌프 전류")}
    assert S.unobserved("유압 떨어졌어요?", hpu, obs) == ["유압 공급 압력"]
    assert S.unobserved("유압유 온도 괜찮아요?", hpu, obs) == ["유압유 온도"]
    assert S.unobserved("유압 펌프 전류 봐줘", hpu, obs) == ["유압 펌프 전류"]
    gr = {"gr_brg_temp": SimpleNamespace(name="감속기 베어링 온도"), "gr_vib_rms": SimpleNamespace(name="감속기 진동 RMS")}
    assert S.unobserved("베어링 열이 나요", gr, obs) == ["감속기 베어링 온도"]
    assert S.unobserved("베어링 열화 원인이 뭐예요?", gr, obs) == []
    assert S.unobserved("GR 진동 괜찮아요?", gr, obs) == ["감속기 진동 RMS"]
    poles = {f"p{n}": SimpleNamespace(name=f"차단기 L{n}극 표면 온도") for n in (1, 2)}
    assert S.unobserved("L1 표면 온도 높아요?", poles, obs) == ["차단기 L1극 표면 온도"]
    assert len(S.unobserved("차단기 표면 온도 어때요?", poles, obs)) == 2


def test_unit_guard_keeps_the_answer_on_the_units_the_question_names(pipe, monkeypatch):
    # 10/22: with GR-01 selected, "GR-02 ..." got GR-01's MES ("MES 기준 GR-01 ...") in 17/288 C4 answers
    pipe.eq_code["EQ-0005"], pipe.eq_id["GR-02"], pipe.eq_type["EQ-0005"] = "GR-02", "EQ-0005", "GR"
    pipe.eq_type["GR-02"] = "GR"
    judged(monkeypatch, {"c3": 0.95, "c4": 0.1})
    prompts = []
    monkeypatch.setattr(G, "ask_raw", lambda p, host, prefix, **kw: prompts.append(p) or {"raw": prefix +
                        'GR-01 베어링은 46.4도로 정상입니다 [S1]. 오일 레벨 12.5 pct를 확인합니다 [S1].", "citations": ["S1"]}'})
    obs = [{"signal": "gr_surface_temp", "value": 30}, {"signal": "gr_surface_temp_state", "value": "normal"}]
    payload = {"question": "GR-02 베어링 어때요?", "eq_id": "EQ-0004", "observations": obs, "snapshot_at": "t", "active_alarms": []}
    pipe.mes_block = True
    off = pipe.run(payload)
    assert "[MES]" in prompts[0] and off.output.answer.startswith("GR-01 베어링은")   # off: as before
    pipe.unit_guard = True
    r = pipe.run(payload)
    assert "[MES]" not in prompts[1]   # GR-01's values never reach a GR-02 question
    assert r.output.answer == ("선택된 설비(GR-01)와 질문의 설비(GR-02)가 달라 GR-01의 MES 값은 쓰지 않았습니다.\n"
                               "오일 레벨 12.5 pct를 확인합니다.\n근거: gr_manual p.3")
    assert r.tool_results["other_unit"] and r.tool_results["unit_dropped"] == ["GR-01 베어링은 46.4도로 정상입니다 [S1]."]
    mine = pipe.run({**payload, "question": "베어링 어때요?"})   # no code in the question: the selected unit
    assert "[MES]" in prompts[2] and not mine.tool_results["other_unit"] and mine.output.answer.startswith("GR-01 베어링은")
    monkeypatch.setattr(G, "ask_raw", lambda p, host, prefix, **kw: {"raw": prefix + 'HPU-01 압력을 봅니다 [S1].", "citations": ["S1"]}'})
    out = pipe.run({**payload, "question": "베어링 어때요?"})
    assert out.output.no_knowledge and out.tool_results["abstain_reason"] == "other_unit"   # only another unit's sentence
    assert S.asked_units("gr02랑 GR 1, RT-03베어링, HPU-012") == ["GR-02", "GR-01", "RT-03"]
    pipe.unit_header = True
    monkeypatch.setattr(G, "ask_raw", lambda p, host, prefix, **kw: {"raw": prefix + '오일을 봅니다 [S1].", "citations": ["S1"]}'})
    judged(monkeypatch, {"c3": 0.95, "c4": 0.1})
    assert pipe.run({**payload, "question": "베어링 어때요?"}).output.answer.startswith("[GR-01 기준] 오일을 봅니다.")


def test_place_names_come_from_the_catalog_location(pipe, tmp_path):
    cat = {"equipment_types": CATALOG["equipment_types"],
           "equipment": [{"equipment_id": "EQ-0001", "code": "HPU-01", "equipment_type_id": "ET-1", "location_text": "유틸리티실 A동 1층"},
                         {"equipment_id": "EQ-0004", "code": "GR-01", "equipment_type_id": "ET-2", "location_text": "입측 조작반 좌측 5 m"},
                         {"equipment_id": "EQ-0005", "code": "GR-02", "equipment_type_id": "ET-2", "location_text": "출측 조작반 우측 4 m"}]}
    p = S.S30hPipeline(tmp_path, "http://main:11434", "http://judge:11436", catalog=cat)   # the pipe fixture wrote the index
    assert p.units_in("출측 감속기 누유요") == ["GR-02"] and p.units_in("입측감속기 온도") == ["GR-01"]
    assert p.units_in("조작반 감속기") == [] and p.units_in("좌측 감속기") == []   # shared word / panel direction
    assert p.units_in("GR-01이랑 출측 감속기") == ["GR-01", "GR-02"]


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


@pytest.mark.parametrize("flag,enabled", [(None, False), ("0", False), ("1", True)])
def test_mes_source_condition_flag(pipe, tmp_path, monkeypatch, flag, enabled):
    monkeypatch.setenv("SHIFTLINK_ANSWER_MODE", "s30h")
    monkeypatch.setenv("SHIFTLINK_S30H_INDEX", str(tmp_path))
    monkeypatch.delenv("SHIFTLINK_S30H_SOURCE_CONDITIONS", raising=False)
    if flag is not None:
        monkeypatch.setenv("SHIFTLINK_S30H_SOURCE_CONDITIONS", flag)
    assert Q.build_query_pipeline().source_conditions is enabled
    monkeypatch.delenv("SHIFTLINK_S30H_MES_BLOCK", raising=False)
    if flag is not None:
        monkeypatch.setenv("SHIFTLINK_S30H_MES_BLOCK", flag)
    assert Q.build_query_pipeline().mes_block is enabled
    monkeypatch.delenv("SHIFTLINK_S30H_EVENT_LABEL", raising=False)
    if flag is not None:
        monkeypatch.setenv("SHIFTLINK_S30H_EVENT_LABEL", flag)
    assert Q.build_query_pipeline().event_label is enabled
    monkeypatch.delenv("SHIFTLINK_S30H_MES_ONLY", raising=False)
    if flag is not None:
        monkeypatch.setenv("SHIFTLINK_S30H_MES_ONLY", flag)
    assert Q.build_query_pipeline().mes_only is enabled
    monkeypatch.delenv("SHIFTLINK_S30H_MES_PREFIX", raising=False)
    if flag is not None:
        monkeypatch.setenv("SHIFTLINK_S30H_MES_PREFIX", flag)
    assert Q.build_query_pipeline().mes_prefix is enabled
    monkeypatch.delenv("SHIFTLINK_S30H_UNOBSERVED", raising=False)
    if flag is not None:
        monkeypatch.setenv("SHIFTLINK_S30H_UNOBSERVED", flag)
    assert Q.build_query_pipeline().unobserved_guard is enabled
    monkeypatch.delenv("SHIFTLINK_S30H_UNIT_GUARD", raising=False)
    if flag is not None:
        monkeypatch.setenv("SHIFTLINK_S30H_UNIT_GUARD", flag)
    assert Q.build_query_pipeline().unit_guard is enabled
    monkeypatch.delenv("SHIFTLINK_S30H_UNIT_HEADER", raising=False)
    if flag is not None:
        monkeypatch.setenv("SHIFTLINK_S30H_UNIT_HEADER", flag)
    assert Q.build_query_pipeline().unit_header is enabled
    monkeypatch.delenv("SHIFTLINK_S30H_P_FIX", raising=False)
    if flag is not None:
        monkeypatch.setenv("SHIFTLINK_S30H_P_FIX", flag)
    Q.build_query_pipeline()
    assert G.P_FIX is enabled
    monkeypatch.setattr(G, "P_FIX", False)   # module global: back to the default for later tests


def test_p_fix_sums_token_spellings(monkeypatch):
    # B3 MX-C02a 10/21: ' false' -0.0, ' true' -6.67, then 'false' -10.66 overwrote ' false' (recorded 0.982)
    lp = [{"token": t, "top_logprobs": []} for t in ('{"', "ins", "ufficient", "_", "evidence", '":')]
    lp.append({"token": " false", "top_logprobs": [{"token": " false", "logprob": -0.0}, {"token": " true", "logprob": -6.67},
                                                   {"token": "false", "logprob": -10.66}]})
    monkeypatch.setattr(G, "P_FIX", False)
    assert round(G.p_insufficient(lp)[0], 3) == 0.982
    monkeypatch.setattr(G, "P_FIX", True)
    p, missing = G.p_insufficient(lp)
    assert p < 0.002 and not missing


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
