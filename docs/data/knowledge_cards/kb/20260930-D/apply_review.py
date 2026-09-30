"""Apply review.md verdicts to out/*.json: accepted -> status=accepted, grade=L1. Other verdicts leave the card as is.

Edits only the status/grade text inside each card's own span, so hand-formatted out files keep their layout.
Run merge.py afterwards to rebuild cards.json / README.md / review.md, then ../build_kb.py.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
VERDICT = r"^## (K-\d{4}).*?^- \*\*판정\*\*: ?([^\n]*)$"
verdicts = dict(re.findall(VERDICT, (HERE / "review.md").read_text(encoding="utf-8"), re.M | re.S))
accepted = {cid for cid, v in verdicts.items() if v.strip().startswith("accepted")}

done = set()
dec = json.JSONDecoder()
for path in sorted((HERE / "out").glob("*.json")):
    raw = path.read_text(encoding="utf-8")
    out, i = [], raw.index("[") + 1
    out.append(raw[:i])
    while True:
        j = i + len(raw[i:]) - len(raw[i:].lstrip(" \t\r\n,"))
        if raw[j] == "]":
            out.append(raw[i:])
            break
        card, end = dec.raw_decode(raw, j)
        span = raw[j:end]
        if card["card_id"] in accepted:
            span = re.sub(r'("status":\s*)"draft"', r'\1"accepted"', span, count=1)
            span = re.sub(r'("grade":\s*)"L0"', r'\1"L1"', span, count=1)
            done.add(card["card_id"])
        out.append(raw[i:j] + span)
        i = end
    text = "".join(out)
    assert [c["card_id"] for c in json.loads(text)] == [c["card_id"] for c in json.loads(raw)]
    path.write_text(text, encoding="utf-8", newline="\n")

print(f"accepted verdicts: {len(accepted)} / promoted: {len(done)} / not found: {sorted(accepted - done)}")
