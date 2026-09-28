"""Read-only static checks, not role execution, independent review or freezing."""
import hashlib
import json
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parent

def read(name):
    return json.loads((root / name).read_text(encoding="utf-8-sig"))

selection = read("card-selection.json")
source = root.parent.parent / "20260926-t4-equipment" / "cards.json"
cards = {c["card_id"]: c for c in json.loads(source.read_text(encoding="utf-8-sig"))}
assert hashlib.sha256(source.read_bytes()).hexdigest() == selection["source_cards_sha256"]
projection = json.loads((root.parent / "catalog-projection.json").read_text(encoding="utf-8-sig"))
catalog_codes = {e["code"] for e in projection["equipment"]}
coverage = read("coverage-and-lineage.json")["scenarios"]
ledger = read("evaluation-only/fact-ledger.json")["cases"]
assert len(coverage) == len(ledger) == 6
assert {c["family"] for c in coverage} == {"HPU", "GR", "RT", "CV", "PDP", "CAU"}
assert all(set(c["equipment_codes"]) <= catalog_codes for c in coverage)
lengths = {(r["scenario_id"], r["condition"]): r for r in read("input-lengths.json")}
selected = {s["scenario_id"]: s for s in selection["selections"]}
assert len(selected) == 6
for case in ledger:
    sid = case["scenario_id"]
    selected_card = selected[sid]
    card = cards[selected_card["card_id"]]
    assert selected_card["exposed_fields"] == ["know_how"]
    assert selected_card["exposed_text"] == card["know_how"]
    assert selected_card["version"] == card["version"]
    assert (selected_card["split"], selected_card["status"], selected_card["grade"]) == ("dev", "draft", "L0")
    assert selected_card["exposed_text_sha256"] == hashlib.sha256(card["know_how"].encode("utf-8")).hexdigest()
    packets = [read(f"sender-packets/{sid}-{condition}.json") for condition in ("none", "checklist", "t4")]
    for key in ("task", "access_rule", "notes"):
        assert packets[0][key] == packets[1][key] == packets[2][key]
    assert packets[0]["support"] == ""
    assert len(packets[1]["support"].splitlines()) == 5
    assert packets[2]["support"] == card["know_how"]
    assert packets[0]["notes"] == case["memo_fragments"]
    assert (root / f"source-memos/{sid}.txt").read_text(encoding="utf-8") == "\n\n".join(case["memo_fragments"]) + "\n"
    assert case["facts_count"] == sum(a["kind"] == "fact" for a in case["atoms"])
    assert case["unknown_count"] == sum(a["kind"] == "unknown" for a in case["atoms"])
    assert len({a["atom_id"] for a in case["atoms"]}) == len(case["atoms"])
    assert all(0 <= a["evidence_memo_index"] < len(case["memo_fragments"]) for a in case["atoms"])
    receiver = read(f"receiver-templates/{sid}.json")
    assert set(receiver) == {"task", "access_rule", "initial", "handoff"}
    assert receiver["handoff"] is None
    assert receiver["initial"] == case["initial"]
    for condition, packet in zip(("none", "checklist", "t4"), packets):
        assert set(packet) == {"task", "access_rule", "notes", "support"}
        length = lengths[(sid, condition)]
        assert length["support_unicode_characters"] == len(packet["support"])
        assert length["support_utf8_bytes"] == len(packet["support"].encode("utf-8"))
        assert length["token_count"] == "unavailable"
        # Narrow mechanical screen only; semantic leakage still needs the independent reviewer.
        serialized = json.dumps(packet, ensure_ascii=False)
        assert all(term not in serialized for term in ("F8", "정답", "평가 예시", "숨김표식", "atom_id", "expected", "K-00"))
        assert all(term not in json.dumps(receiver, ensure_ascii=False) for term in ("F8", "정답", "평가 예시", "숨김표식", "atom_id", "expected"))

plan = read("run-plan.json")
schedule = plan["schedule"]
assert plan["planned_pairs"] == len(schedule) == 54
assert plan["planned_role_calls"] == len(schedule) * 2 == 108
assert plan["maximum_role_attempts_including_one_infrastructure_retry_each"] == 216
assert plan["baseline_requested_output_character_total_max"] == 108 * 1800 == 194400
assert all(plan[key] == "unavailable" for key in ("total_tokens_budget", "total_cost_budget", "enforced_total_wall_clock_limit"))
assert len({r["run_id"] for r in schedule}) == 54
assert [r["order"] for r in schedule] == list(range(1, 55))
assert set(Counter((r["scenario_id"], r["condition"]) for r in schedule).values()) == {3}
assert all(r["fork_turns_for_each_role"] == "none" and r["status"] == "not_run" for r in schedule)
assert all((root / r["sender_packet"]).is_file() and (root / r["receiver_template"]).is_file() for r in schedule)
assert len(list((root / "sender-packets").glob("*.json"))) == 18
assert len(list((root / "receiver-templates").glob("*.json"))) == 6
assert read("execution-log-template.json")["records"] == []
assert read("evaluation-only/judgment-template.json")["records"] == []
print(json.dumps({"static_validation": "pass", "author_check_only": True, "scenario_count": 6,
    "sender_packets": 18, "receiver_templates": 6, "planned_pairs": 54, "planned_role_calls": 108,
    "executed_role_calls": 0, "fact_atoms": sum(c["facts_count"] for c in ledger),
    "unknown_atoms": sum(c["unknown_count"] for c in ledger),
    "support_characters": [{"scenario": s["scenario_id"], "none": 0,
        "checklist": lengths[(s["scenario_id"], "checklist")]["support_unicode_characters"],
        "t4": lengths[(s["scenario_id"], "t4")]["support_unicode_characters"]} for s in selection["selections"]],
    "independent_design_review": "pending", "freeze": "pending", "semantic_leakage_review": "pending"}, ensure_ascii=False, indent=2))
