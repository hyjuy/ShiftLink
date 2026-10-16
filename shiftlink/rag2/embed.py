"""RAG v2 stage 3a: embed chunks with an Ollama embedding model (resumable).

    python -m shiftlink.rag2.embed --dir <rag dir> --size 450 --model embeddinggemma:300m [--host http://127.0.0.1:11434]

Writes vectors_<size>__<model>.npy (L2-normalised, row i = chunk line i) and a manifest entry.
"""
import argparse
import json
import re
import time
import urllib.request
from pathlib import Path

import numpy as np

# Document/query prefixes each model expects (model cards). Same model for index and query (plan §5).
PREFIX = {
    "embeddinggemma": ("title: none | text: ", "task: search result | query: "),
    "qwen3-embedding": ("", "Instruct: Given a maintenance question, retrieve manual passages that answer it\nQuery: "),
}


def prefixes(model: str) -> tuple[str, str]:
    return next((v for k, v in PREFIX.items() if model.startswith(k)), ("", ""))


def slug(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]+", "_", model)


def embed(texts: list[str], model: str, host: str) -> np.ndarray:
    req = urllib.request.Request(f"{host}/api/embed", data=json.dumps({"model": model, "input": texts, "keep_alive": "10m"}).encode())
    vec = np.array(json.load(urllib.request.urlopen(req, timeout=600))["embeddings"], dtype=np.float32)
    return vec / np.linalg.norm(vec, axis=1, keepdims=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--size", type=int, default=450)
    ap.add_argument("--model", required=True)
    ap.add_argument("--host", default="http://127.0.0.1:11434")
    ap.add_argument("--batch", type=int, default=16)
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(a.dir / f"chunks_{a.size}.jsonl", encoding="utf-8")]
    out = a.dir / f"vectors_{a.size}__{slug(a.model)}.npy"
    part = out.with_suffix(".partial.npy")
    done = np.load(part) if part.exists() else np.zeros((0, 0), np.float32)
    doc_prefix, _ = prefixes(a.model)
    t0, vecs = time.time(), [done] if len(done) else []
    for i in range(len(done), len(rows), a.batch):
        vecs.append(embed([doc_prefix + r["embed_text"] for r in rows[i:i + a.batch]], a.model, a.host))
        if (i // a.batch) % 20 == 0:
            np.save(part, np.vstack(vecs))
            print(f"{i + a.batch}/{len(rows)} {time.time() - t0:.0f}s", flush=True)
    mat = np.vstack(vecs)
    assert len(mat) == len(rows)
    np.save(out, mat)
    part.unlink(missing_ok=True)
    man_path = a.dir / "manifest.json"
    man = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else {}
    man[out.name] = {"model": a.model, "chunks": f"chunks_{a.size}.jsonl", "rows": len(rows), "dim": int(mat.shape[1]),
                     "distance": "cosine (L2-normalised dot)", "doc_prefix": doc_prefix, "query_prefix": prefixes(a.model)[1],
                     "seconds": round(time.time() - t0), "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    man_path.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print("done", out.name, mat.shape)


if __name__ == "__main__":
    main()
