"""Apply the 2026-09-30 human review: staged card edits -> out/<EQ>.json, verdicts -> status/grade.

accepted  -> status=accepted, grade=L1
수정       -> staged fix applied, stays draft/L0, verdict line becomes a re-review request
Run merge.py afterwards to rebuild cards.json / README.md / review.md.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
REVIEWED = HERE / "review_20260930_reviewed.md"
STAGED = HERE / "out" / "review-20260930"

VERDICT = r"^## (K-\d{4}).*?^- \*\*판정\*\*: ?([^\n]*)$"
verdicts = dict(re.findall(VERDICT, REVIEWED.read_text(encoding="utf-8"), re.M | re.S))
# Re-review (second pass) verdicts live in review.md; an "accepted" there is final.
second = dict(re.findall(VERDICT, (HERE / "review.md").read_text(encoding="utf-8"), re.M | re.S))
final = {cid: (second[cid] if second.get(cid, "").startswith("accepted") else v) for cid, v in verdicts.items()}
staged = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in STAGED.glob("K-*.json")}

counts = {"accepted": 0, "fixed": 0, "staged_replaced": 0}
for eq_file in sorted((HERE / "out").glob("*.json")):
    cards = json.loads(eq_file.read_text(encoding="utf-8"))
    for i, card in enumerate(cards):
        cid = card["card_id"]
        if cid in staged:
            cards[i] = card = staged[cid]
            counts["staged_replaced"] += 1
        verdict = final.get(cid, "").strip()
        if verdict.startswith("accepted"):
            card["status"], card["grade"] = "accepted", "L1"
            counts["accepted"] += 1
        elif verdict.startswith("수정"):
            card["status"], card["grade"] = "draft", "L0"
            counts["fixed"] += cid in staged
    eq_file.write_text(json.dumps(cards, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")

# Re-review request for fixed cards; merge.py keeps whatever the verdict line says.
review = HERE / "review.md"
text = review.read_text(encoding="utf-8")
for cid, verdict in verdicts.items():
    if verdict.startswith("수정") and cid in staged and not final[cid].startswith("accepted"):
        text = re.sub(rf"(^## {cid}\b.*?^- \*\*판정\*\*: )[^\n]*",
                      lambda m: m.group(1) + f"재검수 요청 (수정 반영 2026-09-30, 이전 판정: {verdict})",
                      text, count=1, flags=re.M | re.S)
review.write_text(text, encoding="utf-8", newline="\n")
print(counts, "| missing staged fixes:",
      [c for c, v in verdicts.items() if v.startswith("수정") and c not in staged])
