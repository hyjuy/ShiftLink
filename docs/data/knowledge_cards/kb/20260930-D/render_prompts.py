"""Render prompts/<EQ>.md from prompt_template.md + plan.json and record sha256 in prompts/index.json."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent
REL = "docs/data/knowledge_cards/kb/20260930-D"
MES_ID = {"CAU": "EQ-0003", "PDP": "EQ-0002"}
SAFETY = "docs/sources/safety"
SOURCES = {
    "CAU": ["원문: `docs/data/sources/CAU/compressed-air-ref-eng.pdf` — CEATI *Compressed Air Energy Efficiency Reference Guide* (118쪽)",
            "원문: `docs/data/sources/CAU/Manual-on-Energy-Efficiency.pdf` — UNEP/TERI *Energy Efficient Technologies and Best Practices in Steel Rolling Industries* (116쪽, 압축공기 절)",
            "한계: 두 자료 모두 에너지 효율 중심이다. 고장 진단·안전 근거가 부족한 슬롯은 skip한다",
            f"T5 보조: `{SAFETY}/산업안전보건기준에 관한 규칙(고용노동부령)(제00450호)(20260302).pdf` 중 압축공기·공기압축기 관련 조항이 있으면 쓴다"],
    "PDP": ["원문: `docs/data/sources/PDP/15001-20000_16339.pdf` — UNIDO 1987 *Electrical and Mechanical Maintenance in Rolling Mills* (스캔 OCR, 품질 낮음 — 쪽마다 직접 대조)",
            "원문: `docs/data/sources/PDP/d2e0a4ea3d7e62b24193679803b73e6.pdf` — ABB *Electrical System Service* 소개 (8쪽, 브로슈어라 절차 근거로 약함)",
            f"안전(KOSHA): `{SAFETY}/E-7-2012 전기작업에 관한 기술지침.pdf`, `{SAFETY}/E-105-2011 전기작업안전에 관한 기술지침.pdf`, "
            f"`{SAFETY}/E-154-2016 전기작업계획서의 작성에 관한 기술지침.pdf`, `{SAFETY}/E-14-2012 감전시 응급조치에 관한 기술지침.pdf`, "
            f"`{SAFETY}/E-92-2017+접지설비+계획+및+유지관리에+관한+기술지침.pdf`",
            f"법령: `{SAFETY}/산업안전보건기준에 관한 규칙(고용노동부령)(제00450호)(20260302).pdf`의 전기 관련 조항(정전 작업·충전부 방호 등)",
            f"`{SAFETY}/KOSHA_Guide(기술지침)_길라잡이.pdf`·지침 목록 PDF는 참고용이며 카드 근거로 쓰지 않는다"],
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
               .replace("{MES_ID}", MES_ID[eq])
               .replace("{PROMPT_PATH}", path)
               .replace("{SLOTS}", "\n".join(f"- {s['slot']} · {s['card_id']} · {s['tacit_type']} · {s['hint']}" for s in slots))
               .replace("{SOURCES}", "\n".join(f"- {x}" for x in SOURCES[eq])))
    (HERE / "prompts" / f"{eq}.md").write_text(text, encoding="utf-8", newline="\n")  # hash == file bytes
    index["prompts"][eq] = {"path": path, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                            "card_ids": [s["card_id"] for s in slots]}
(HERE / "prompts" / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v["sha256"][:12] for k, v in index["prompts"].items()}))
