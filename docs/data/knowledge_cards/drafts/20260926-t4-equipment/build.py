"""Assemble reviewed synthetic specifications; leave production registries untouched."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))
from shiftlink.agent.schemas import KnowledgeCard, SCHEMA_VERSION


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    spec_paths = [HERE / name for name in ("specs-hpu-gr.json", "specs-rt-cv.json")]
    batches = [read(p) for p in spec_paths]
    specs = sorted([s for b in batches for s in b["specs"]], key=lambda s: s["method_key"])
    assert specs and len({s["method_key"] for s in specs}) == len(specs)
    catalog_path = ROOT / "docs/data/reference/00_plant_and_relations.json"
    catalog = read(catalog_path)
    equipment = {e["equipment_id"]: e for e in catalog["equipment"]}
    # Inventory card artifacts only. Never open evaluation sealed/holdout data.
    inventory = sorted(p for p in (ROOT / "docs/data/knowledge_cards").rglob("*.json")
                       if HERE not in p.parents and (p.name == "cards.json" or p.name == "01_kb_cards_shared.json"))
    used = set()
    for path in inventory:
        used.update(re.findall(r"K-\d{4}", path.read_text(encoding="utf-8-sig")))
    policy = {
        "policy_version": "equipment-t4-synthetic-v1",
        "quantity_rule": "No quota or maximum. Retain distinct applicable handover mechanisms; log exclusions and coverage gaps.",
        "confidence_definition": "Local development convention inherited from prior synthetic T4: directly supported original method fields / 5. All five fields here are synthetic, so 0; not efficacy or production requester confidence.",
        "safety_boundary": "합성 개발용 인계 방법이며 현장 표준이 아니다. 수신 확인, 정보 해결, 작업·운전·재가동 승인은 별개다. 기록에 없는 원인·수치·차단점·승인권을 생성하지 않는다.",
        "instance_mapping": "equipment is schema family; equipment-map.json declares design scope, not an enforced production routing rule. PDP/CAU use COMMON per catalog.",
        "id_inventory_scope": [p.relative_to(ROOT).as_posix() for p in inventory],
        "global_id_certification": False,
    }
    content = json.dumps({"specs": specs, "policy": policy}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    version = "synthetic-" + hashlib.sha256(content.encode()).hexdigest()[:12]
    # Preserve allocation and timestamp on regeneration; review hashes must then be refreshed after rereview.
    old_map = read(HERE / "equipment-map.json")["cards"] if (HERE / "equipment-map.json").exists() else []
    old_ids = {m["method_key"]: m["card_id"] for m in old_map}
    available = iter(f"K-{i:04}" for i in range(1, 10000) if f"K-{i:04}" not in used | set(old_ids.values()))
    now = read(HERE / "manifest.json")["generated_at"] if (HERE / "manifest.json").exists() else datetime.now(timezone.utc).isoformat()
    cards, mappings, sources = [], [], []
    for s in specs:
        card_id = old_ids[s["method_key"]] if s["method_key"] in old_ids else next(available)
        source_id = "SYN-T4-EQ-" + s["method_key"]
        source = {"source_id": source_id, "method_key": s["method_key"], "is_synthetic": True,
                  "direct_original_support_fields": [], "catalog_role": "Synthetic equipment identity/configuration only; not evidence of handover effectiveness.", "design": s}
        payload = {
            "card_id": card_id, "version": version, "grade": "L0", "status": "draft", "split": "dev",
            "tacit_type": "T4", "equipment": s["equipment"], "component": s["component"], "scenario": "S1",
            "title": "[합성·개발용] " + s["title"],
            "know_how": "[합성 인계 방법] " + " ".join(s["procedure"]) + " 미완료 처리: " + s["unresolved_handling"] + " " + policy["safety_boundary"],
            "rationale": "[합성 설계 이유] " + s["rationale"],
            "safety_flag": True, "safety_basis": "[합성 설계 경계] " + policy["safety_boundary"],
            "confidence": 0, "type_payload": {"handover_method": s["handover_method"]},
            "generalization_evidence": {"generalization_scope": "합성 장비 인계 개발용. 적용 범위는 equipment-map.json 참조. 실제 현장 검증 없음.", "confidence_basis": policy["confidence_definition"]},
            "safety_review": {"status": "pending_review"},
            "provenance": {"seed_ids": [source_id], "persona_id": s["persona_id"], "event_ids": [],
                           "generator": "Codex delegated synthetic design + " + Path(__file__).relative_to(ROOT).as_posix(),
                           "generated_at": now, "extraction_method": "explicit_synthetic_equipment_handover_design",
                           "prompt_version": policy["policy_version"], "schema_version": SCHEMA_VERSION,
                           "sources": [{"source_id": source_id, "locator": "synthetic-sources.json#" + s["method_key"], "document_version": version}]},
        }
        cards.append(KnowledgeCard.model_validate(payload).model_dump(mode="json", exclude_none=True))
        sources.append(source)
        mappings.append({"card_id": card_id, "method_key": s["method_key"], "equipment_family": s["equipment_family"],
                         "schema_equipment": s["equipment"], "applicable_equipment_ids": s["applicable_equipment_ids"],
                         "applicable_codes": [equipment[x]["code"] for x in s["applicable_equipment_ids"]],
                         "related_equipment_ids": s.get("related_equipment_ids", []),
                         "related_codes": [equipment[x]["code"] for x in s.get("related_equipment_ids", [])],
                         "catalog_refs": s["catalog_refs"], "trigger": s["trigger"], "scope_enforced_in_production": False})
    save("cards.json", cards)
    save("synthetic-sources.json", sources)
    save("equipment-map.json", {"is_synthetic": True, "routing_note": policy["instance_mapping"], "cards": mappings})
    save("batch-policy.json", policy)
    save("excluded-candidates.json", [s for b in batches for s in b["excluded_candidates"]])
    input_paths = spec_paths + inventory + [catalog_path, ROOT / "seeds/personas_v0.1.yaml", ROOT / "shiftlink/agent/schemas.py"]
    save("manifest.json", {"generated_at": now, "content_version": version, "card_ids": [c["card_id"] for c in cards],
                           "prior_card_ids": sorted(used), "cards_sha256": digest(HERE / "cards.json"),
                           "input_hashes": {p.relative_to(ROOT).as_posix(): digest(p) for p in input_paths},
                           "production_generation_run": False, "operational_registry_modified": False,
                           "human_approval": False, "adopted": False})
    lines = ["# 장비별 합성 T4 지식카드", "", f"신규 {len(cards)}건. 모두 draft / L0 / dev. 장비 구성과 방법 모두 합성 개발 범위다.", "",
             "| 카드 | 유형 | 적용 장비 | 인계 방법 |", "|---|---|---|---|"]
    for c, s, m in zip(cards, specs, mappings):
        lines.append(f"| {c['card_id']} ({s['method_key']}) | {s['equipment_family']} | {', '.join(m['applicable_codes'])} | {s['title']} |")
    for c, s, m in zip(cards, specs, mappings):
        lines += ["", f"## {c['card_id']} · {s['title']}", "", "**적용 장비:** " + ", ".join(m["applicable_codes"]),
                  "", "**적용 상황:** " + s["trigger"], "", "**방법:** " + " ".join(s["procedure"]), "",
                  "| T4 필드 | 합성 제안 |", "|---|---|"]
        for field, value in s["handover_method"].items():
            lines.append(f"| {field} | {' / '.join(value) if isinstance(value, list) else value} |")
        lines += ["", "**미해결·미회신 처리:** " + s["unresolved_handling"], "", "**차별성:** " + s["distinguishing_feature"],
                  "", "**합성 예시:** " + s["synthetic_narrative"]]
    (HERE / "cards.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"new_cards": len(cards), "version": version}, ensure_ascii=False))


if __name__ == "__main__":
    main()
