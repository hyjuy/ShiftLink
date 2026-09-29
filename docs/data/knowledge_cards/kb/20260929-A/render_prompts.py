"""Render prompts/<EQ>.md from prompt_template.md + plan.json and record sha256 in prompts/index.json."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent
REL = "docs/data/knowledge_cards/kb/20260929-A"
SOURCES = {
    "HPU": ["후보표: `docs/reports/source-card-review-20260925/HPU.md` (카드 후보 29건), `shared.md`",
            "원문: `docs/data/events/HPU/*.pdf`, `docs/manual/parker-hpu-*.pdf`, `docs/manual/bosch-*.pdf`(로컬 전용, 43쪽 미리보기본)"],
    "CV": ["후보표: `docs/reports/source-card-review-20260925/CV.md` (카드 후보 32건), `shared.md`",
           "원문: `docs/data/events/CV/*.pdf`",
           "T5 근거: `docs/sources/safety/M-101-2012 컨베이어의 안전에 관한 기술지침.pdf` (KOSHA). 기존 K-0301~K-0303과 겹치지 않는 조항을 쓴다"],
    "RT": ["후보표: `docs/reports/source-card-review-20260925/RT.md`, `shared.md`",
           "원문: `docs/data/events/RT/*.pdf`"],
    "GR": ["후보표: `docs/reports/source-card-review-20260925/GR.md` (후보 0건 — 원문에서 직접 찾는다), `shared.md`",
           "원문: `docs/data/events/GR/*.pdf`, `docs/manual/BR-*.pdf`(SKF 베어링 손상유형·재제조 가이드, 로컬 전용), `docs/data/events/shared/`의 NSK·SKF·Euro Bearing 자료"],
}

plan = json.loads((HERE / "plan.json").read_text(encoding="utf-8"))
tpl = (HERE / "prompt_template.md").read_text(encoding="utf-8")
index = {"batch_id": plan["batch_id"], "seed": plan["seed"],
         "template_sha256": hashlib.sha256(tpl.encode("utf-8")).hexdigest(), "prompts": {}}
for eq in SOURCES:
    slots = [s for s in plan["slots"] if s["equipment"] == eq]
    path = f"{REL}/prompts/{eq}.md"
    text = (tpl.replace("{PROMPT_ID}", f"{plan['batch_id']}/{eq}")
               .replace("{EQ}", eq)
               .replace("{PROMPT_PATH}", path)
               .replace("{SLOTS}", "\n".join(f"- {s['slot']} · {s['card_id']} · {s['tacit_type']}" for s in slots))
               .replace("{SOURCES}", "\n".join(f"- {x}" for x in SOURCES[eq])))
    (HERE / "prompts" / f"{eq}.md").write_text(text, encoding="utf-8", newline="\n")  # hash == file bytes
    index["prompts"][eq] = {"path": path, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                            "card_ids": [s["card_id"] for s in slots]}
(HERE / "prompts" / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v["sha256"][:12] for k, v in index["prompts"].items()}))
