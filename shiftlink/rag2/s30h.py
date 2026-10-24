"""S30h answer mode for MES /api/query (team decision 10/16: demo = S30h).

Same run(payload) -> .output (AgentResponse) interface as agent.pipeline.FixedPipeline, so query_service and the PDA
stay as they are. The route is the evaluated one (jetson_bench.run on exp/source-rag-20261013): config C evidence,
v1 judge P(>=2) per chunk on a judge-only Ollama, drop < LO, forced answer when max >= HI, else the SFT model decides
and abstains when p_insuff >= T. Manual pages cited by the answer are listed at its end ("근거: ...") because the
response schema only carries card ids; safety notices are the equipment's KB safety cards (the PDA safety gate).
"""
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from shiftlink.agent.pipeline import JudgeUnavailableError
from shiftlink.agent.response import AgentResponse, SafetyNotice
from shiftlink.rag.knowledge_graph import expand_ranking

from shiftlink.agent.pi_analysis import prompt_block
from . import evidence_score as E
from . import generate as G
from . import mes_block as MB
from .embed import prefixes, slug
from .field_history import is_history_question, record_sources
from .retrieve import COMMON_FOLDERS, load
from .source_conditions import with_source_conditions

LO, HI, T = 0.3, 0.9, 0.35277185049977805   # preregistered 10/15; never round T
CFG = G.CONFIGS["C"]
ROOT = Path(__file__).resolve().parents[2]
UNIT_CODE = re.compile(r"\b(?:HPU|PDP|CAU|GR|RT|CV)-0\d\b")


def source_label(chunk: dict) -> str:
    m = chunk["metadata"]
    if m["kind"] == "card":
        return m["source"]
    if m["kind"] == "source":
        return f"{Path(m['source']).stem} p.{m['page']}"
    return "인계 기록"


def _num(x) -> str:
    return f"{x:g}" if isinstance(x, (int, float)) else str(x)


def state_lines(specs: dict, observations: list) -> list[str]:
    """M1 of the 10/20 MES-context run (exp/mes-context-20261020 mes_ctx.state_lines): one line per low/high MES state.
    specs: signal -> SignalSpec of the baseline configuration. Normal, missing and invalid signals add nothing, so with
    MES all normal the search text is the question alone."""
    values = {o["signal"]: o["value"] for o in observations}
    lines = []
    for o in observations:
        if not o["signal"].endswith("_state") or o["value"] not in ("low", "high"):
            continue
        sig = o["signal"][:-len("_state")]
        spec = specs.get(sig)
        if spec is None or sig not in values:
            continue
        v = values[sig]
        # stopped line: the MES marks 0 rpm/A/flow low, but it is not a fault (Jetson 10/20, line_mode stopped).
        # ponytail: also hides a real 0 on a running line; send line_mode in the request if that case matters.
        if spec.zero_when_stopped and v == 0:
            continue
        if spec.unit == "bool":
            lines.append(f"{spec.name.split(' (')[0]}: {_num(v)} (정상 {_num(spec.normal_max)})")
        else:
            rng = f"{_num(spec.normal_min)}–{_num(spec.normal_max)} {spec.unit}"
            lines.append(f"{spec.name} {_num(v)} {spec.unit} (정상 {rng} {'초과' if o['value'] == 'high' else '미만'})")
    return lines


class GraphEvidence(list):
    """Keep retrieval trace local to one call while preserving the public list interface."""
    def __init__(self, rows, trace):
        super().__init__(rows)
        self.graph_trace = trace


# field words for a signal whose MES name the question does not use (regex; 유압 not as in 유압유 / 유압 펌프 / 유압 유량)
ALIASES = {"air_pressure": r"공압", "hpu_pressure": r"유압(?!유|\s*(?:펌프|유량))"}
# a name word and what the field says for it: 베어링 열(이), not 열화 / 열교환
WORD_ALT = {"온도": r"온도|열(?:[이은을도만]|(?![가-힣]))"}
UNIT_WORDS = {"감속기", "롤러", "컨베이어", "배전반"}   # the selected unit already says which equipment
TAG = re.compile(r"(?<![A-Za-z])[A-Za-z]\d(?!\d)")   # a pole/phase tag like L1


def _asks(question: str, name: str) -> bool:
    words = [w for w in name.split() if re.search("[가-힣]", w) and w not in UNIT_WORDS][-2:]   # 감속기 진동 RMS -> 진동
    if not words or not all(re.search(WORD_ALT.get(w, re.escape(w)), question) for w in words):
        return False
    tag = TAG.search(name)   # "L1 표면 온도" is not about the L2 pole; "차단기 표면 온도" (no tag) is about every pole
    return not (tag and TAG.search(question) and tag.group() not in TAG.findall(question))


ASKED_UNIT = re.compile(r"(?<![A-Za-z])(HPU|PDP|CAU|GR|RT|CV)\s*-?\s*0?(\d)(?!\d)", re.I)   # GR-02, gr02, GR 2


SENTENCE = re.compile(r".+?(?:[.!?](?=\s|$)|\n|$)\s*", re.S)   # a "." inside 12.5 does not end a sentence


TYPE_NOUN = {"GR": "감속기", "RT": "롤러", "CV": "컨베이어"}   # types with several units; the catalog has no Korean names
RELATIVE = {"좌측", "우측"}   # 조작반 좌측 5 m: a direction from the panel, not what the field calls the unit


def asked_units(question: str) -> list[str]:
    """Unit codes written in the question, normalised to the catalog form (GR-02)."""
    return [f"{t.upper()}-0{n}" for t, n in ASKED_UNIT.findall(question)]


RANGE_Q = re.compile(r"정상\s*범위|정상\s*값|기준\s*(?:값|치|범위)|몇\s*(?:부터|까지)|얼마\s*(?:부터|까지)|상한|하한")


def unobserved(question: str, specs: dict, observations: list) -> list[str]:
    """Names of the unit's signals the question asks about that have no valid MES observation (10/21 MX-C27/C28: the
    model filled a dropped bearing temperature / air pressure with another signal and called it normal). A signal is
    asked about when the last two Korean words of its name (e.g. 베어링, 온도) or its ALIASES are in the question.
    No observations at all = no MES snapshot: nothing is flagged, the [MES] block already says 유효 관측 없음."""
    if not observations:
        return []
    seen = {o["signal"] for o in observations}
    names = []
    for sig, spec in specs.items():
        name = spec.name.split(" (")[0]
        if sig not in seen and (_asks(question, name) or (sig in ALIASES and re.search(ALIASES[sig], question))):
            names.append(name)
    return names


class S30hPipeline:
    answer_mode = "s30h"

    def __init__(self, index_dir, host, judge_host, answer_model="exaone-rag-aug-ck106", judge_model="exaone-sft-judge",
                 judge_ctx=2048, judge_workers=2, cards=(), catalog=None, source_conditions=False, mes_block=False,
                 event_label=False, mes_only=False, mes_prefix=False, p_fix=False, unobserved_guard=False, unit_guard=False,
                 unit_header=False, range_answer=False, knowledge_graph=True):
        index_dir = Path(index_dir)
        self.rows = load(index_dir, CFG["size"])
        self.vec = np.load(index_dir / f"vectors_{CFG['size']}__{slug(CFG['model'])}.npy")
        if len(self.vec) != len(self.rows):
            raise ValueError(f"index mismatch: {len(self.rows)} chunks, {len(self.vec)} vectors")
        self.folders = np.array([r["metadata"]["folder"] for r in self.rows])
        # event chunks are all folder COMMON; tag each with the unit codes in its text, else those of its whole event
        by_event = {}
        for r in self.rows:
            if r["metadata"]["kind"] == "event":
                by_event.setdefault(r["metadata"]["source"], set()).update(UNIT_CODE.findall(r["text"]))
        self.event_units = {r["chunk_id"]: set(UNIT_CODE.findall(r["text"])) or by_event[r["metadata"]["source"]]
                            for r in self.rows if r["metadata"]["kind"] == "event"}
        self.host, self.judge_host = host.rstrip("/"), judge_host.rstrip("/")
        self.judge_model, self.judge_ctx, self.judge_workers = judge_model, judge_ctx, judge_workers
        self.model = SimpleNamespace(model=answer_model)   # the server logs pipeline.model.model
        # ponytail: module globals of the evaluated code; one pipeline per process. Pass them as arguments if that changes.
        G.GEN_MODEL, G.KEEP_ALIVE, E.KEEP_ALIVE = answer_model, -1, -1
        G.P_FIX = p_fix   # p_insuff spellings summed (generate.P_FIX); off = the values T was calibrated on
        # the MES passes loader KnowledgeCard models; tests pass plain dicts
        self.cards = [c if isinstance(c, dict) else c.model_dump(mode="json") for c in cards]
        self.source_conditions = source_conditions
        self.knowledge_graph = knowledge_graph
        # experimental (default off): the unit's MES snapshot as an [MES] block in the answer prompt, for an answer model
        # trained on it (MES SFT 10/21); ck106 never saw the block
        self.mes_block = mes_block
        self.event_label = event_label   # with the block only: event chunks shown as 인계 기록 (separate switch for ablation)
        # with the block only: drop_all still asks the model with the [MES] block and no evidence, same threshold T
        # (option A of 10/21; the MES SFT data has 338 such rows, ck106 has none)
        self.mes_only = mes_only
        self.mes_prefix = mes_prefix   # independent of the block: works with ck106 too
        self.unobserved_guard = unobserved_guard   # code answers a question about a signal the MES has no valid value for
        self.unit_guard = unit_guard   # the question's unit codes decide which unit the answer is about (run())
        self.unit_header = unit_header   # answers start with [GR-01 기준]
        # drop_all + a question for a signal's normal range: code answers from the MES range (10/22 NQ-D08: the range
        # is only in the MES; with MES_ONLY off nothing answered it). Not for 정격 (a manufacturer rating, NQ-M08).
        self.range_answer = range_answer
        cat = catalog or json.loads((ROOT / "docs/data/reference/00_plant_and_relations.json").read_text(encoding="utf-8"))
        types = {t["equipment_type_id"]: t["type_code"] for t in cat["equipment_types"]}
        self.eq_type, self.eq_code = {}, {}
        for e in cat["equipment"]:
            self.eq_type[e["equipment_id"]] = self.eq_type[e["code"]] = types[e["equipment_type_id"]]
            self.eq_code[e["equipment_id"]] = e["code"]
        self.eq_id = {c: i for i, c in self.eq_code.items()}
        # field names of a type with several units, from the catalog location (입측 조작반 좌측 5 m -> 입측 감속기 = GR-01):
        # every Korean word of the location that no other unit of the type has, followed by the type's noun
        by_type = {}
        for e in cat["equipment"]:
            if types[e["equipment_type_id"]] in TYPE_NOUN:
                words = {w for w in re.findall(r"[가-힣]{2,}", e.get("location_text") or "") if w != TYPE_NOUN[types[e["equipment_type_id"]]] and w not in RELATIVE}
                by_type.setdefault(types[e["equipment_type_id"]], []).append((e["code"], words))
        self.place_names = []
        for t, units in by_type.items():
            for c, words in units:
                for w in sorted(words - set().union(*(o for oc, o in units if oc != c))):
                    self.place_names.append((re.compile(rf"{w}\s*{TYPE_NOUN[t]}"), c))
        from shiftlink.mes.configuration import from_catalog   # names/ranges as the MES shows them (catalog points have no names)
        self.specs = {e.equipment_id: {s.signal: s for s in e.signals} for e in from_catalog(cat).equipment}
        from shiftlink.mes.engine import MesEngine
        self.alarm_labels = MesEngine.ALARM_LABELS

    def units_in(self, text: str) -> list[str]:
        """Catalog unit codes a text names: written codes (GR-02) and place names (출측 감속기)."""
        named = asked_units(text) + [c for rx, c in self.place_names if rx.search(text)]
        return [c for c in dict.fromkeys(named) if c in self.eq_id]

    def _post(self, host, path, body, timeout=300):
        req = urllib.request.Request(f"{host}{path}", data=json.dumps(body).encode())
        return json.load(urllib.request.urlopen(req, timeout=timeout))

    def _embed(self, question: str) -> np.ndarray:
        # CPU (num_gpu 0): a third GPU model on the Jetson makes Ollama evict the others (10/15 NvMap error 12)
        d = self._post(self.host, "/api/embed", {"model": CFG["model"], "input": [prefixes(CFG["model"])[1] + question],
                                                  "keep_alive": -1, "options": {"num_gpu": 0}}, timeout=120)
        v = np.array(d["embeddings"][0], dtype=np.float32)
        return v / np.linalg.norm(v)

    def evidence(self, question: str, eq_type: str | None, eq_id: str | None = None, units: set | None = None) -> list[dict]:
        """units: unit codes whose handover records stay (the unit guard's asked units); default the eq_id's unit."""
        idx = np.where(np.isin(self.folders, list(COMMON_FOLDERS | {eq_type})))[0] if eq_type else np.arange(len(self.rows))
        history = is_history_question(question)
        if history:
            eligible = {r['metadata']['source'] for r in record_sources(question, self.rows, self.cards, eq_id)}
            idx = np.array([i for i in idx if self.rows[i]['chunk_id'].startswith('field_')
                            and self.rows[i]['metadata']['source'] in eligible], dtype=int)
            if not len(idx):
                return []
        ranking = idx[np.argsort(-(self.vec[idx] @ self._embed(question)))].tolist()
        trace = None
        if self.knowledge_graph:
            ranking, trace = expand_ranking(self.rows, ranking, self.cards, eq_type, eq_id, top=CFG["top"])
        else:
            ranking = ranking[:CFG["top"]]
        if history:
            allowed = set(idx)
            ranking = [i for i in ranking if i in allowed]
        ev = G.evidence(self.rows, ranking, CFG)
        # another unit's handover event is not this unit's history: drop it without moving the next chunk up
        # (F′ of the 10/20 event-filter run, ShiftLink-records/experiments/evfilter_20261020; backfilling cost 충분 answers)
        units = units or ({self.eq_code[eq_id]} if eq_id in self.eq_code else None)
        ev = [r for r in ev if not units or r["metadata"]["kind"] != "event" or units & self.event_units[r["chunk_id"]]]
        if trace is not None:
            selected = {r["chunk_id"] for r in ev}
            trace["paths"] = [path for path in trace["paths"] if path["chunk_id"] in selected]
            return GraphEvidence(ev, trace)
        return ev

    def safety(self, eq_id: str, eq_type: str | None) -> list[SafetyNotice]:
        out = []
        for c in self.cards:
            if not c.get("safety_flag") or c.get("equipment") not in (eq_type, "COMMON"):
                continue
            if c.get("mes_equipment_id") and c["mes_equipment_id"] != eq_id:
                continue
            steps = (c.get("type_payload") or {}).get("steps") or []
            stops = list(dict.fromkeys(s for st in steps for s in st.get("stop_conditions", [])))
            out.append(SafetyNotice(card_id=c["card_id"], safety_basis=c.get("safety_basis", ""), stop_conditions=stops))
        return out

    def run(self, payload) -> SimpleNamespace:
        question, eq_id = payload["question"], payload["eq_id"]
        history = is_history_question(question)
        eq_type = self.eq_type.get(eq_id)
        t0 = time.time()
        # MES low/high states go into the embedding search only; the judge and answer prompts keep the question
        # (adopted 10/20 by user decision although prereg gate Q1 missed by one: docs/experiments/mes-context-result-20261020.md)
        code = self.eq_code.get(eq_id)
        # unit guard (10/22): the MES request holds the selected unit only (MesCardAdapter filters by equipment_id). A
        # question naming other units (GR-02 while GR-01 is selected) is about them: no selected-unit MES, their type's
        # folders and handover records, their safety cards; and the answer names no unit outside them.
        asked = self.units_in(question) if self.unit_guard else []
        away = bool(asked) and code not in asked
        if away:
            types = {self.eq_type[c] for c in asked}
            eq_type = types.pop() if len(types) == 1 else None
            if len(asked) == 1:
                eq_id = self.eq_id[asked[0]]
        observations = [] if away else payload.get("observations") or []
        alarms = [] if away else payload.get("active_alarms") or []
        mes = [] if history else state_lines(self.specs.get(eq_id, {}), observations)
        missing = unobserved(question, self.specs.get(eq_id, {}), observations) if self.unobserved_guard and not history else []
        if missing:
            # ponytail: also replaces a knowledge question that names the dropped signal (e.g. its limit) while the sensor
            # is bad; narrow the match to state questions if that costs answers
            answer = (f"{code} {', '.join(missing)}: 지금 MES에 유효한 측정값이 없습니다. "
                      "다른 신호나 과거 기록으로 대신 판단하지 말고 현장 계기로 직접 확인하세요.")
            output = AgentResponse(mode="query", answer=answer, no_knowledge=True, cited_card_ids=[],
                                   safety_notices=self.safety(eq_id, eq_type))
            return SimpleNamespace(mode="query", output=output, tool_results={
                "answer_mode": "s30h", "mes_lines": mes, "route": "unobserved", "candidates": [], "judge_p": [], "kept": [],
                "p_insuff": None, "abstain_reason": "unobserved", "unobserved": missing, "seconds": round(time.time() - t0, 2)})
        # An impossible record scope cannot gain a valid source through embedding retrieval.
        eligible = {r['metadata']['source'] for r in record_sources(question, self.rows, self.cards, eq_id)} if history else None
        ev = [] if history and not eligible else self.evidence("\n".join([question, *mes]), eq_type, eq_id, units=set(asked) or None)
        if history:
            # Reject inapplicable records before network judging; keep original chunks for the judge.
            selected = [r for r in ev if r['chunk_id'].startswith('field_') and r['metadata']['source'] in eligible]
            if getattr(ev, 'graph_trace', None) is not None:
                trace = {**ev.graph_trace, 'paths': [p for p in ev.graph_trace['paths']
                         if p['chunk_id'] in {r['chunk_id'] for r in selected}]}
                ev = GraphEvidence(selected, trace)
            else:
                ev = selected
        with ThreadPoolExecutor(self.judge_workers) as ex:
            dists = list(ex.map(lambda r: E.judge_dist(question, r, self.judge_host, model=self.judge_model, ctx=self.judge_ctx), ev))
        if any(p is None for p in dists):   # strict like hybrid: never answer from evidence the judge did not score
            raise JudgeUnavailableError("judge returned no score distribution")
        scores = [p[2] + p[3] for p in dists]
        kept = [(r, s) for r, s in zip(ev, scores) if s >= LO]
        ev2 = [r for r, _ in kept]
        route = "drop_all" if not ev2 else "confident" if max(s for _, s in kept) >= HI else "model"
        if history:
            ev2 = record_sources(question, ev2, self.cards, eq_id)
            route = "record_history" if ev2 else "drop_all"
        block = None
        if self.mes_block and eq_id in self.specs and not away and not history:
            block = MB.render(self.eq_code[eq_id], self.specs[eq_id], observations,
                              payload.get("snapshot_at"), alarms, self.alarm_labels)
        if route == "drop_all" and block and self.mes_only:
            route = "mes_only"   # no evidence survived, but the unit's MES can still answer a state question ([M] only)
        p, extra = (MB.prompt(question, block, ev2, self.event_label), {"system": MB.SYSTEM}) if block else (G.prompt(question, ev2), {})
        if not history and not away and payload.get('analysis_context'):
            p += "\n\n" + prompt_block(payload['analysis_context'])
        if route == "drop_all":
            out = {"raw": json.dumps({"insufficient_evidence": True, "answer": "", "citations": []}), "prompt_tokens": 0}
        elif route == "record_history":
            # Render only approved historical facts, retaining every recorded step, worker and time.
            text = "근무일지에 기록된 과거 조치·관찰입니다. 현재 상태·작업 승인을 뜻하지 않습니다.\n"
            text += "\n\n".join(f"{row['text']} [S{i}]" for i, row in enumerate(ev2, 1))
            out = {"raw": json.dumps({"insufficient_evidence": False, "answer": text,
                                      "citations": [f'S{i}' for i in range(1, len(ev2)+1)]}), "prompt_tokens": 0}
        elif route == "confident":
            out = G.ask_raw(p, self.host, G.FORCE_PREFIX, **extra)
        else:
            out = G.ask(p, self.host, logprobs=True, **extra)
        res = G.check(out, ev2, question, block)
        abstain = res["abstain"] or (route in ("model", "mes_only") and out.get("p_insuff") is not None and out["p_insuff"] >= T)
        ranged = []
        if self.range_answer and not history and route == "drop_all" and eq_id in self.specs and RANGE_Q.search(question) and "정격" not in question:
            ranged = [sp for sp in self.specs[eq_id].values() if sp.unit != "bool" and sp.normal_min is not None
                      and sp.normal_max is not None and _asks(question, sp.name.split(" (")[0])]
        dropped = []
        if self.unit_guard and not abstain and code:
            # a sentence naming a unit the question is not about (another unit's handover record, the selected unit's MES)
            # is cut; nothing left = abstain
            allowed = set(asked) or {code}
            parts = SENTENCE.findall(res["answer"])
            dropped = [s.strip() for s in parts if set(self.units_in(s)) - allowed]
            res["answer"] = "".join(s for s in parts if not set(self.units_in(s)) - allowed).strip()
            if not res["answer"]:
                abstain, res["abstain"], res["reason"] = True, True, "other_unit"
        cited = [] if abstain else [ev2[int(c[1:]) - 1] for c in res["valid_cites"] if c != "M"]
        answer = ""
        condition_cards = []
        if not abstain:
            labels = list(dict.fromkeys(source_label(r) for r in cited)) + (["MES 현재값"] if "M" in res["valid_cites"] else [])
            answer = res["answer"]
            if self.source_conditions:
                answer, condition_cards = with_source_conditions(answer, res["valid_cites"], ev2, self.cards)
            answer = re.sub(r"\s*\[(?:S\d+|M)\]", "", answer).strip() + ("\n근거: " + " · ".join(labels) if labels else "")
        if ranged:
            abstain = False
            answer = " ".join(f"{self.eq_code[eq_id]} {sp.name.split(' (')[0]} 정상 범위는 {_num(sp.normal_min)}–{_num(sp.normal_max)} {sp.unit}입니다."
                               for sp in ranged) + " MES 판정 기준값이며 제조사 정격이나 고장 한계가 아닙니다.\n근거: MES 기준값"
        if self.unit_header and answer and code and not away:
            # 10/22 trial: say which unit the answer is about, so a worker sees a unit the rules did not catch
            answer = f"[{', '.join(asked) or code} 기준] {answer}"
        if away:
            head = f"선택된 설비({code})와 질문의 설비({', '.join(asked)})가 달라 {code}의 MES 현재값은 쓰지 않았습니다."
            answer = f"{head}\n{answer}" if answer else f"{head} {MB.NO_ACTION}"
        elif self.mes_prefix and eq_id in self.specs and not history:
            # (가) 10/21: code states the unit's MES; an abstention becomes that state + "no action found" (still no_knowledge)
            head = MB.summary(self.eq_code[eq_id], self.specs[eq_id], payload.get("observations") or [],
                              payload.get("active_alarms") or [], self.alarm_labels)
            answer = f"{head}\n{answer}" if answer else f"{head} {MB.NO_ACTION}"
        output = AgentResponse(mode="query", answer=answer, no_knowledge=abstain,
                               review_queue=res["reason"] == "unsupported_number",
                               cited_card_ids=list(dict.fromkeys(r["metadata"]["source"] for r in cited if r["metadata"]["kind"] == "card")),
                               safety_notices=self.safety(eq_id, eq_type))
        # why it answered or abstained (MES query log): candidates with their judge P(>=2), what survived LO, the route,
        # the model's decision probability and the abstain reason (drop_all / insufficient / no_cite / broken_json / threshold)
        reason = ("drop_all" if route == "drop_all" else "threshold" if abstain and not res["abstain"] else res["reason"]) if abstain else ""
        tool_results = {"answer_mode": "s30h", "mes_lines": mes, "route": route, "candidates": [r["chunk_id"] for r in ev],
                        "judge_p": [round(s, 4) for s in scores], "kept": [r["chunk_id"] for r in ev2],
                        "p_insuff": out.get("p_insuff"), "abstain_reason": reason,
                        "number_violations": res['number_violations'], "seconds": round(time.time() - t0, 2)}
        if getattr(ev, "graph_trace", None) is not None:
            tool_results["knowledge_graph"] = ev.graph_trace
        if self.source_conditions:
            tool_results["source_condition_cards"] = condition_cards
        if self.unit_guard:
            tool_results.update(asked_units=asked, other_unit=away, unit_dropped=dropped)
        return SimpleNamespace(mode="query", output=output, tool_results=tool_results, cited_chunks=cited)

    def warm(self, attempts=30, wait_s=10.0, sleep=time.sleep) -> list[str]:
        """Load the judge (judge server, its own ctx), then ck106 (ctx 4096), then the CPU embedding, before the first query.
        Judge first, as in the measured layout: on 10/16 the judge loaded after ck106 hit NvMap error 12 once (Ollama retried)."""
        targets = [(self.judge_host, "/api/generate", {"model": self.judge_model, "keep_alive": -1, "options": {"num_ctx": self.judge_ctx}}),
                   (self.host, "/api/generate", {"model": self.model.model, "keep_alive": -1, "options": {"num_ctx": 4096}}),
                   (self.host, "/api/embed", {"model": CFG["model"], "input": ["x"], "keep_alive": -1, "options": {"num_gpu": 0}})]
        loaded = []
        for host, path, body in targets:
            for _ in range(attempts):
                try:
                    self._post(host, path, body)
                except Exception:  # noqa: BLE001 - Ollama not up yet: try again later
                    sleep(wait_s)
                    continue
                loaded.append(body["model"])
                break
        return loaded
