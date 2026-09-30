"""KB-20260930-D slot plan (CAU·PDP). Slots are a fixed table from the batch C/D guide §5, not drawn.

SEED is kept only for the provenance format (seed_ids) shared with batch A. LLM card text is not
byte-reproducible; each card's exact prompt is kept under prompts/ (path@sha256).
"""
import json
from pathlib import Path

SEED = 20260930
BATCH = "KB-20260930-D"
FIRST_ID = 1301
# equipment -> [(tacit type, topic hint from guide §5)]
TABLE = {
    "CAU": [("T1", "압력 저하"), ("T1", "이상음"), ("T3", "압력 저하 확인 순서"),
            ("T5", "압축공기 안전"), ("T2", "air_pressure + compressor_current")],
    "PDP": [("T1", "차단기 동작"), ("T1", "전압 변동"), ("T3", "차단기 트립 후 확인 순서"),
            ("T5", "충전부 작업 금기"), ("T2", "bus_voltage + breaker_trip")],
}

slots, next_id = [], FIRST_ID
for eq, rows in TABLE.items():
    for t, hint in rows:
        slots.append({"slot": f"S{len(slots) + 1:02d}", "card_id": f"K-{next_id}", "equipment": eq,
                      "tacit_type": t, "hint": hint})
        next_id += 1

out = {"batch_id": BATCH, "seed": SEED, "generator": "plan.py", "slots": slots}
Path(__file__).with_name("plan.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({eq: [s["tacit_type"] for s in slots if s["equipment"] == eq] for eq in TABLE}, ensure_ascii=False))
