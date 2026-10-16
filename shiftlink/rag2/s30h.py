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
from .embed import prefixes, slug
from .retrieve import COMMON_FOLDERS, load

LO, HI, T = 0.3, 0.9, 0.35277185049977805   # preregistered 10/15; never round T
CFG = G.CONFIGS["C"]
ROOT = Path(__file__).resolve().parents[2]


def source_label(chunk: dict) -> str:
    m = chunk["metadata"]
    if m["kind"] == "card":
        return m["source"]
    if m["kind"] == "source":
        return f"{Path(m['source']).stem} p.{m['page']}"
    return "인계 기록"


class S30hPipeline:
    answer_mode = "s30h"

    def __init__(self, index_dir, host, judge_host, answer_model="exaone-rag-aug-ck106", judge_model="exaone-sft-judge",
                 judge_ctx=2048, judge_workers=2, cards=(), catalog=None):
        index_dir = Path(index_dir)
        self.rows = load(index_dir, CFG["size"])
        self.vec = np.load(index_dir / f"vectors_{CFG['size']}__{slug(CFG['model'])}.npy")
        if len(self.vec) != len(self.rows):
            raise ValueError(f"index mismatch: {len(self.rows)} chunks, {len(self.vec)} vectors")
        self.folders = np.array([r["metadata"]["folder"] for r in self.rows])
        self.host, self.judge_host = host.rstrip("/"), judge_host.rstrip("/")
        self.judge_model, self.judge_ctx, self.judge_workers = judge_model, judge_ctx, judge_workers
        self.model = SimpleNamespace(model=answer_model)   # the server logs pipeline.model.model
        # ponytail: module globals of the evaluated code; one pipeline per process. Pass them as arguments if that changes.
        G.GEN_MODEL, G.KEEP_ALIVE, E.KEEP_ALIVE = answer_model, -1, -1
        # the MES passes loader KnowledgeCard models; tests pass plain dicts
        self.cards = [c if isinstance(c, dict) else c.model_dump(mode="json") for c in cards]
        cat = catalog or json.loads((ROOT / "docs/data/reference/00_plant_and_relations.json").read_text(encoding="utf-8"))
        types = {t["equipment_type_id"]: t["type_code"] for t in cat["equipment_types"]}
        self.eq_type = {}
        for e in cat["equipment"]:
            self.eq_type[e["equipment_id"]] = self.eq_type[e["code"]] = types[e["equipment_type_id"]]

    def _post(self, host, path, body, timeout=300):
        req = urllib.request.Request(f"{host}{path}", data=json.dumps(body).encode())
        return json.load(urllib.request.urlopen(req, timeout=timeout))

    def _embed(self, question: str) -> np.ndarray:
        # CPU (num_gpu 0): a third GPU model on the Jetson makes Ollama evict the others (10/15 NvMap error 12)
        d = self._post(self.host, "/api/embed", {"model": CFG["model"], "input": [prefixes(CFG["model"])[1] + question],
                                                  "keep_alive": -1, "options": {"num_gpu": 0}}, timeout=120)
        v = np.array(d["embeddings"][0], dtype=np.float32)
        return v / np.linalg.norm(v)

    def evidence(self, question: str, eq_type: str | None) -> list[dict]:
        idx = np.where(np.isin(self.folders, list(COMMON_FOLDERS | {eq_type})))[0] if eq_type else np.arange(len(self.rows))
        ranking = idx[np.argsort(-(self.vec[idx] @ self._embed(question)))][:CFG["top"]].tolist()
        return G.evidence(self.rows, ranking, CFG)

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
        ev = self.evidence(question, eq_type)
        with ThreadPoolExecutor(self.judge_workers) as ex:
            dists = list(ex.map(lambda r: E.judge_dist(question, r, self.judge_host, model=self.judge_model, ctx=self.judge_ctx), ev))
        if any(p is None for p in dists):   # strict like hybrid: never answer from evidence the judge did not score
            raise JudgeUnavailableError("judge returned no score distribution")
        scores = [p[2] + p[3] for p in dists]
        kept = [(r, s) for r, s in zip(ev, scores) if s >= LO]
        ev2 = [r for r, _ in kept]
        route = "drop_all" if not ev2 else "confident" if max(s for _, s in kept) >= HI else "model"
        if route == "drop_all":
            out = {"raw": json.dumps({"insufficient_evidence": True, "answer": "", "citations": []}), "prompt_tokens": 0}
        elif route == "confident":
            out = G.ask_raw(G.prompt(question, ev2), self.host, G.FORCE_PREFIX)
        else:
            out = G.ask(G.prompt(question, ev2), self.host, logprobs=True)
        res = G.check(out, ev2, question)
        abstain = res["abstain"] or (route == "model" and out.get("p_insuff") is not None and out["p_insuff"] >= T)
        cited = [] if abstain else [ev2[int(c[1:]) - 1] for c in res["valid_cites"]]
        answer = ""
        if not abstain:
            labels = list(dict.fromkeys(source_label(r) for r in cited))
            answer = re.sub(r"\s*\[S\d+\]", "", res["answer"]).strip() + ("\n근거: " + " · ".join(labels) if labels else "")
        output = AgentResponse(mode="query", answer=answer, no_knowledge=abstain,
                               cited_card_ids=list(dict.fromkeys(r["metadata"]["source"] for r in cited if r["metadata"]["kind"] == "card")),
                               safety_notices=self.safety(eq_id, eq_type))
        # why it answered or abstained (MES query log): candidates with their judge P(>=2), what survived LO, the route,
        # the model's decision probability and the abstain reason (drop_all / insufficient / no_cite / broken_json / threshold)
        reason = ("drop_all" if route == "drop_all" else "threshold" if abstain and not res["abstain"] else res["reason"]) if abstain else ""
        tool_results = {"answer_mode": "s30h", "route": route, "candidates": [r["chunk_id"] for r in ev],
                        "judge_p": [round(s, 4) for s in scores], "kept": [r["chunk_id"] for r in ev2],
                        "p_insuff": out.get("p_insuff"), "abstain_reason": reason, "seconds": round(time.time() - t0, 2)}
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
