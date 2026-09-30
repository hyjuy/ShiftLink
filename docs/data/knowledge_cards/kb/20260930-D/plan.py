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

# Round 2 (2026-09-30): sources added (Kaishan manual, USBR FIST 3-16, KOSHA E-40·E-57·B-E-13) -> +5 per equipment.
# Round-1 slots above stay byte-identical so their dispatched prompt hashes still match.
TABLE_R2 = {
    "CAU": [("T1", "압축기 과부하 트립·고온 정지"), ("T1", "압축기 이상음·진동"), ("T3", "부하 운전 불가·공급량 부족 확인 순서"),
            ("T3", "정기 정비 순서(필터·분리기·오일)"), ("T5", "정비 전 압력 해제·재기동 방지")],
    "PDP": [("T1", "열화상·접속부 과열"), ("T1", "차단기 조작 불량·동작 지연"), ("T3", "배선차단기 트립 후 점검 순서"),
            ("T3", "차단기 시험 순서"), ("T5", "수변전설비 점검·조작 안전")],
}
for eq, rows in TABLE_R2.items():
    for t, hint in rows:
        slots.append({"slot": f"S{len(slots) + 1:02d}", "card_id": f"K-{next_id}", "equipment": eq,
                      "tacit_type": t, "hint": hint, "round": 2})
        next_id += 1

# Round 3 (2026-09-30): KOSHA M-103-2017 공기압 시스템, G-17-2017 압축공기 안전한 사용 added after round 2 was dispatched.
TABLE_R3 = {"CAU": [("T5", "공압 계통 잔압·축적 에너지"), ("T5", "압축공기 사용 금지 행위")]}
for eq, rows in TABLE_R3.items():
    for t, hint in rows:
        slots.append({"slot": f"S{len(slots) + 1:02d}", "card_id": f"K-{next_id}", "equipment": eq,
                      "tacit_type": t, "hint": hint, "round": 3})
        next_id += 1

# 2026-09-30 renumbering (user request): the skipped K-1312 slot (CAU T1 이상음·진동 — no source basis) is dropped
# and later cards move up one number. Prompts were dispatched with the old IDs, so each slot keeps "generated_as"
# and render_prompts.py renders the old IDs to reproduce the dispatched prompt bytes (sha256 in prompts/index.json).
DROPPED = {"K-1312"}
next_id = FIRST_ID
for s in slots:
    if s["card_id"] in DROPPED:
        s["generated_as"], s["card_id"], s["dropped"] = s["card_id"], None, True
        continue
    if s["card_id"] != f"K-{next_id}":
        s["generated_as"], s["card_id"] = s["card_id"], f"K-{next_id}"
    next_id += 1

out = {"batch_id": BATCH, "seed": SEED, "generator": "plan.py", "slots": slots}
Path(__file__).with_name("plan.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({eq: [s["tacit_type"] for s in slots if s["equipment"] == eq] for eq in TABLE}, ensure_ascii=False))
