"""KB-20260929-A slot plan. Same SEED -> same plan.json (card IDs, equipment, tacit type per slot).

The seed fixes only this plan. LLM card text is not byte-reproducible; each card's exact
prompt is kept under prompts/ and referenced by provenance.prompt_version (path@sha256).
"""
import json
import random
from pathlib import Path

SEED = 20260929
BATCH = "KB-20260929-A"
FIRST_ID = 1001
# equipment -> (slot count, minimum T5 safety cards)
QUOTA = {"HPU": (8, 2), "CV": (8, 2), "RT": (7, 2), "GR": (7, 1)}
FILL = ["T1", "T1", "T2", "T3"]  # draw pool for non-safety slots

rng = random.Random(SEED)
slots, next_id = [], FIRST_ID
for eq, (n, n_t5) in QUOTA.items():
    types = ["T5"] * n_t5 + [rng.choice(FILL) for _ in range(n - n_t5)]
    rng.shuffle(types)
    for t in types:
        slots.append({"slot": f"S{len(slots) + 1:02d}", "card_id": f"K-{next_id}", "equipment": eq, "tacit_type": t})
        next_id += 1

out = {"batch_id": BATCH, "seed": SEED, "generator": "plan.py", "slots": slots}
Path(__file__).with_name("plan.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({eq: [s["tacit_type"] for s in slots if s["equipment"] == eq] for eq in QUOTA}, ensure_ascii=False))
