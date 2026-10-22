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

from . import evidence_score as E
from . import generate as G
from . import mes_block as MB
from .embed import prefixes, slug
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


ALIASES = {"air_pressure": ("공압",)}   # field words for a signal whose MES name the question does not use


def unobserved(question: str, specs: dict, observations: list) -> list[str]:
    """Names of the unit's signals the question asks about that have no valid MES observation (10/21 MX-C27/C28: the
    model filled a dropped bearing temperature / air pressure with another signal and called it normal). A signal is
    asked about when every word of its name's last two words (e.g. 베어링, 온도) or one of its ALIASES is in the question.
    No observations at all = no MES snapshot: nothing is flagged, the [MES] block already says 유효 관측 없음."""
    if not observations:
        return []
    seen = {o["signal"] for o in observations}
    names = []
    for sig, spec in specs.items():
        name = spec.name.split(" (")[0]
        if sig not in seen and (all(w in question for w in name.split()[-2:]) or any(a in question for a in ALIASES.get(sig, ()))):
            names.append(name)
    return names


class S30hPipeline:
    answer_mode = "s30h"

    def __init__(self, index_dir, host, judge_host, answer_model="exaone-rag-aug-ck106", judge_model="exaone-sft-judge",
                 judge_ctx=2048, judge_workers=2, cards=(), catalog=None, source_conditions=False, mes_block=False,
                 event_label=False, mes_only=False, mes_prefix=False, p_fix=False, unobserved_guard=False):
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
        # experimental (default off): the unit's MES snapshot as an [MES] block in the answer prompt, for an answer model
        # trained on it (MES SFT 10/21); ck106 never saw the block
        self.mes_block = mes_block
        self.event_label = event_label   # with the block only: event chunks shown as 인계 기록 (separate switch for ablation)
        # with the block only: drop_all still asks the model with the [MES] block and no evidence, same threshold T
        # (option A of 10/21; the MES SFT data has 338 such rows, ck106 has none)
        self.mes_only = mes_only
        self.mes_prefix = mes_prefix   # independent of the block: works with ck106 too
        self.unobserved_guard = unobserved_guard   # code answers a question about a signal the MES has no valid value for
        cat = catalog or json.loads((ROOT / "docs/data/reference/00_plant_and_relations.json").read_text(encoding="utf-8"))
        types = {t["equipment_type_id"]: t["type_code"] for t in cat["equipment_types"]}
        self.eq_type, self.eq_code = {}, {}
        for e in cat["equipment"]:
            self.eq_type[e["equipment_id"]] = self.eq_type[e["code"]] = types[e["equipment_type_id"]]
            self.eq_code[e["equipment_id"]] = e["code"]
        from shiftlink.mes.configuration import from_catalog   # names/ranges as the MES shows them (catalog points have no names)
        self.specs = {e.equipment_id: {s.signal: s for s in e.signals} for e in from_catalog(cat).equipment}
        from shiftlink.mes.engine import MesEngine
        self.alarm_labels = MesEngine.ALARM_LABELS

    def _post(self, host, path, body, timeout=300):
        req = urllib.request.Request(f"{host}{path}", data=json.dumps(body).encode())
        return json.load(urllib.request.urlopen(req, timeout=timeout))

    def _embed(self, question: str) -> np.ndarray:
        # CPU (num_gpu 0): a third GPU model on the Jetson makes Ollama evict the others (10/15 NvMap error 12)
        d = self._post(self.host, "/api/embed", {"model": CFG["model"], "input": [prefixes(CFG["model"])[1] + question],
                                                  "keep_alive": -1, "options": {"num_gpu": 0}}, timeout=120)
        v = np.array(d["embeddings"][0], dtype=np.float32)
        return v / np.linalg.norm(v)

    def evidence(self, question: str, eq_type: str | None, eq_id: str | None = None) -> list[dict]:
        idx = np.where(np.isin(self.folders, list(COMMON_FOLDERS | {eq_type})))[0] if eq_type else np.arange(len(self.rows))
        ranking = idx[np.argsort(-(self.vec[idx] @ self._embed(question)))][:CFG["top"]].tolist()
        ev = G.evidence(self.rows, ranking, CFG)
        # another unit's handover event is not this unit's history: drop it without moving the next chunk up
        # (F′ of the 10/20 event-filter run, ShiftLink-records/experiments/evfilter_20261020; backfilling cost 충분 answers)
        code = self.eq_code.get(eq_id)
        return [r for r in ev if not code or r["metadata"]["kind"] != "event" or code in self.event_units[r["chunk_id"]]]

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
        eq_type = self.eq_type.get(eq_id)
        t0 = time.time()
        # MES low/high states go into the embedding search only; the judge and answer prompts keep the question
        # (adopted 10/20 by user decision although prereg gate Q1 missed by one: docs/experiments/mes-context-result-20261020.md)
        mes = state_lines(self.specs.get(eq_id, {}), payload.get("observations") or [])
        missing = unobserved(question, self.specs.get(eq_id, {}), payload.get("observations") or []) if self.unobserved_guard else []
        if missing:
            # ponytail: also replaces a knowledge question that names the dropped signal (e.g. its limit) while the sensor
            # is bad; narrow the match to state questions if that costs answers
            answer = (f"{self.eq_code[eq_id]} {', '.join(missing)}: 지금 MES에 유효한 측정값이 없습니다. "
                      "다른 신호나 과거 기록으로 대신 판단하지 말고 현장 계기로 직접 확인하세요.")
            output = AgentResponse(mode="query", answer=answer, no_knowledge=True, cited_card_ids=[],
                                   safety_notices=self.safety(eq_id, eq_type))
            return SimpleNamespace(mode="query", output=output, tool_results={
                "answer_mode": "s30h", "mes_lines": mes, "route": "unobserved", "candidates": [], "judge_p": [], "kept": [],
                "p_insuff": None, "abstain_reason": "unobserved", "unobserved": missing, "seconds": round(time.time() - t0, 2)})
        ev = self.evidence("\n".join([question, *mes]), eq_type, eq_id)
        with ThreadPoolExecutor(self.judge_workers) as ex:
            dists = list(ex.map(lambda r: E.judge_dist(question, r, self.judge_host, model=self.judge_model, ctx=self.judge_ctx), ev))
        if any(p is None for p in dists):   # strict like hybrid: never answer from evidence the judge did not score
            raise JudgeUnavailableError("judge returned no score distribution")
        scores = [p[2] + p[3] for p in dists]
        kept = [(r, s) for r, s in zip(ev, scores) if s >= LO]
        ev2 = [r for r, _ in kept]
        route = "drop_all" if not ev2 else "confident" if max(s for _, s in kept) >= HI else "model"
        block = None
        if self.mes_block and eq_id in self.specs:
            block = MB.render(self.eq_code[eq_id], self.specs[eq_id], payload.get("observations") or [],
                              payload.get("snapshot_at"), payload.get("active_alarms") or [], self.alarm_labels)
        if route == "drop_all" and block and self.mes_only:
            route = "mes_only"   # no evidence survived, but the unit's MES can still answer a state question ([M] only)
        p, extra = (MB.prompt(question, block, ev2, self.event_label), {"system": MB.SYSTEM}) if block else (G.prompt(question, ev2), {})
        if route == "drop_all":
            out = {"raw": json.dumps({"insufficient_evidence": True, "answer": "", "citations": []}), "prompt_tokens": 0}
        elif route == "confident":
            out = G.ask_raw(p, self.host, G.FORCE_PREFIX, **extra)
        else:
            out = G.ask(p, self.host, logprobs=True, **extra)
        res = G.check(out, ev2, question, block)
        abstain = res["abstain"] or (route in ("model", "mes_only") and out.get("p_insuff") is not None and out["p_insuff"] >= T)
        cited = [] if abstain else [ev2[int(c[1:]) - 1] for c in res["valid_cites"] if c != "M"]
        answer = ""
        condition_cards = []
        if not abstain:
            labels = list(dict.fromkeys(source_label(r) for r in cited)) + (["MES 현재값"] if "M" in res["valid_cites"] else [])
            answer = res["answer"]
            if self.source_conditions:
                answer, condition_cards = with_source_conditions(answer, res["valid_cites"], ev2, self.cards)
            answer = re.sub(r"\s*\[(?:S\d+|M)\]", "", answer).strip() + ("\n근거: " + " · ".join(labels) if labels else "")
        if self.mes_prefix and eq_id in self.specs:
            # (가) 10/21: code states the unit's MES; an abstention becomes that state + "no action found" (still no_knowledge)
            head = MB.summary(self.eq_code[eq_id], self.specs[eq_id], payload.get("observations") or [],
                              payload.get("active_alarms") or [], self.alarm_labels)
            answer = f"{head}\n{answer}" if answer else f"{head} {MB.NO_ACTION}"
        output = AgentResponse(mode="query", answer=answer, no_knowledge=abstain,
                               cited_card_ids=list(dict.fromkeys(r["metadata"]["source"] for r in cited if r["metadata"]["kind"] == "card")),
                               safety_notices=self.safety(eq_id, eq_type))
        # why it answered or abstained (MES query log): candidates with their judge P(>=2), what survived LO, the route,
        # the model's decision probability and the abstain reason (drop_all / insufficient / no_cite / broken_json / threshold)
        reason = ("drop_all" if route == "drop_all" else "threshold" if abstain and not res["abstain"] else res["reason"]) if abstain else ""
        tool_results = {"answer_mode": "s30h", "mes_lines": mes, "route": route, "candidates": [r["chunk_id"] for r in ev],
                        "judge_p": [round(s, 4) for s in scores], "kept": [r["chunk_id"] for r in ev2],
                        "p_insuff": out.get("p_insuff"), "abstain_reason": reason, "seconds": round(time.time() - t0, 2)}
        if self.source_conditions:
            tool_results["source_condition_cards"] = condition_cards
        return SimpleNamespace(mode="query", output=output, tool_results=tool_results)

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
