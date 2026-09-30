"""Batch C contract checks. Run from repository root with PYTHONPATH=.test-deps."""
import hashlib
import json
import argparse
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from shiftlink.agent.schemas import Artifact, Event, KnowledgeCard
from policy_gate import adoption_issues


def read(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def main(require_kb_ready=False):
    cards_raw = read("cards.json")
    cards = [KnowledgeCard.model_validate(c) for c in cards_raw]
    manifest = read("policy_manifest.json")
    manifest_hash = hashlib.sha256((HERE / "policy_manifest.json").read_bytes()).hexdigest()
    registry = json.loads((ROOT / "seeds/source_registry.json").read_text(encoding="utf-8"))
    registered_sources = {s["source_id"]: s for s in registry["sources"]}
    events = [Event.model_validate(e) for e in read("events.json")]
    artifacts = [Artifact.model_validate(a) for a in read("artifacts.json")]
    slots = {s["card_id"]: s for s in read("plan.json")["slots"]}
    assert Counter(c.tacit_type for c in cards) == {"T2": 10, "T6": 9}, "T2/T6 count"
    assert len({c.card_id for c in cards}) == len(cards) == 19, "duplicate/count"
    assert {c.card_id for c in cards} == set(slots), "slot coverage"
    assert Counter(e.split for e in events) == {"kb": 15, "dev": 5}, "event splits"
    ev = {e.event_id: e for e in events}
    ar = {a.artifact_id: a for a in artifacts}
    assert len(ev) == 20 and len(ar) == len(artifacts) == 40, "event/artifact IDs"
    kb_projection = read("records/kb_events.json")
    event_fields = {"event_id", "scenario", "equipment", "timeline", "measurements", "restart_attempts", "split"}
    expected_projection = [{k: v for k, v in e.model_dump().items() if k in event_fields}
                           for e in events if e.split == "kb"]
    assert kb_projection == expected_projection, "KB event observation projection differs from ledger"
    assert {e["event_id"] for e in kb_projection} == {e.event_id for e in events if e.split == "kb"}
    assert all(not {"true_cause", "true_actions", "cards_expected"} & set(e) for e in kb_projection), "ground truth in extraction input"
    kb_artifacts = read("records/kb_artifacts.json")
    assert kb_artifacts == [a.model_dump() for a in artifacts if a.split == "kb"], "KB artifact projection differs from ledger"
    assert {a["artifact_id"] for a in kb_artifacts} == {a.artifact_id for a in artifacts if a.split == "kb"}
    assert read("records/dev_events.json") == [] and read("records/dev_artifacts.json") == [], "quarantined evaluation inputs became active"
    assert manifest["independent_dev_event_ids"] == [], "contaminated dev events cannot be independent evaluation"
    quarantined = read("records/quarantined_dev_events.json")
    assert {e["event_id"] for e in quarantined} == set(manifest["quarantined_dev_event_ids"])
    assert read("records/quarantined_dev_artifacts.json") == [a.model_dump() for a in artifacts if a.split == "dev"]
    ref = json.loads((ROOT / "docs/data/reference/00_plant_and_relations.json").read_text(encoding="utf-8"))
    equipment = {e["equipment_id"]: e for e in ref["equipment"]}
    signals = {m["signal"] for e in equipment.values() for m in e.get("measurement_points", [])}
    known_sources = {p.name for p in (ROOT / "docs/data/sources").rglob("*.pdf")}
    existing = json.loads((HERE.parent / "kb_cards.json").read_text(encoding="utf-8"))["cards"]
    assert not {c.card_id for c in cards} & {c["card_id"] for c in existing}, "existing card collision"
    for a in artifacts:
        assert a.event_id in ev and a.split == ev[a.event_id].split, a.artifact_id
        assert ev[a.event_id].true_cause not in a.text, f"ground truth leak {a.artifact_id}"
        if a.kind == "handover":
            for marker in ["[현재 상태]", "[앞 근무자 조치]", "[시도했으나", "[미해결]", "[다음 조 확인]"]:
                assert marker in a.text, f"handover element {a.artifact_id}: {marker}"
    for e in events:
        assert e.restart_attempts, f"restart attempt missing {e.event_id}"
        assert set(e.measurements) <= signals, f"unknown measurement {e.event_id}"
        assert Counter(a.kind for a in artifacts if a.event_id == e.event_id) == {"handover": 1, "work_note": 1}
        for attempt in e.restart_attempts:
            if attempt.failure_reason is None:
                assert attempt.evidence_gap == "not_recorded", attempt.attempt_id
    for c in cards:
        slot = slots[c.card_id]
        assert (c.equipment, c.tacit_type) == (slot["equipment"], slot["tacit_type"]), c.card_id
        assert (c.status, c.grade) in {("draft", "L0"), ("accepted", "L1")}, c.card_id
        assert (c.split, c.confidence) == ("kb", 0.0), c.card_id
        assert c.version == "1.0-draft-KB-20260930-C", c.card_id
        assert c.provenance.seed_ids == ["KB-20260930-C:seed=20260930", f"slot:{slot['slot']}"], c.card_id
        assert c.provenance.index_version == f"docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:{manifest_hash}", f"policy manifest pin mismatch {c.card_id}"
        prompt_path, digest = c.provenance.prompt_version.rsplit("@sha256:", 1)
        assert hashlib.sha256((ROOT / prompt_path).read_bytes()).hexdigest() == digest, c.card_id
        assert c.provenance.sources and all(s.locator for s in c.provenance.sources), c.card_id
        for source in c.provenance.sources:
            assert source.source_id in registered_sources, f"unregistered source {c.card_id}: {source.source_id}"
            registered = registered_sources[source.source_id]
            original = registered["aliases"][0]
            assert original in known_sources or original in ev or original in ar, f"unknown original source {c.card_id}: {original}"
            assert source.locator.startswith(original + " | "), f"original locator missing {c.card_id}"
            snapshot = registered["local_snapshot"]
            if original.endswith(".pdf"):
                assert hashlib.sha256((ROOT / snapshot["path"]).read_bytes()).hexdigest() == snapshot["sha256"], f"source PDF changed {source.source_id}"
            else:
                item = next(x for x in kb_projection if x["event_id"] == original) if original.startswith("EV-") else next(x for x in kb_artifacts if x["artifact_id"] == original)
                assert hashlib.sha256(json.dumps(item, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest() == snapshot["item_sha256"], f"source observation changed {source.source_id}"
        permitted = signals
        if c.mes_equipment_id:
            assert c.mes_equipment_id in equipment, c.card_id
            permitted = {m["signal"] for m in equipment[c.mes_equipment_id].get("measurement_points", [])}
        for cond in c.conditions + c.exclusions:
            assert cond.signal.endswith("_state") and cond.signal[:-6] in permitted, f"condition signal {c.card_id}"
            assert cond.unit is None and cond.op in {"==", "!="} and cond.value in {"low", "normal", "high"}, c.card_id
        if c.tacit_type == "T2":
            assert c.conditions, f"T2 condition missing {c.card_id}"
        if c.tacit_type == "T6":
            assert c.type_payload.restart_type == slot["restart_type"], c.card_id
            ge = c.generalization_evidence
            assert ge and len(set(ge.supporting_event_ids)) >= 2, c.card_id
            cited = set(ge.supporting_event_ids + ge.contradicting_event_ids + c.provenance.event_ids)
            for attempt in c.type_payload.tried_and_failed:
                observed = [a for eid in ge.supporting_event_ids for a in ev[eid].restart_attempts
                            if a.attempt_id == attempt.attempt_id]
                assert len(observed) == 1 and observed[0].model_dump() == attempt.model_dump(), f"attempt differs from record {c.card_id}/{attempt.attempt_id}"
                for eid in attempt.evidence_ids:
                    if eid in ar:
                        cited.add(ar[eid].event_id)
                    elif eid.startswith("EV-"):
                        cited.add(eid)
                if attempt.failure_reason is None:
                    assert attempt.evidence_gap == "not_recorded", c.card_id
            for source in c.provenance.sources:
                for ref in registered_sources[source.source_id].get("reference_ids", []):
                    if ref in ev:
                        cited.add(ref)
                    elif ref in ar:
                        cited.add(ar[ref].event_id)
            assert all(eid in ev and ev[eid].split == "kb" for eid in cited), f"non-KB evidence {c.card_id}"
            assert all(ev[eid].equipment == c.equipment for eid in ge.supporting_event_ids), c.card_id
    issues = adoption_issues(cards_raw, HERE, ROOT)
    assert not {c.card_id for c in cards if c.status == "accepted"} & set(issues), "accepted card has unresolved policy gates"
    print("PASS: 19 cards, 20 historical events, 40 artifacts; registered source links and projections; active independent dev=0")
    print(f"KB policy readiness: {'READY' if not issues else 'PENDING'}; blocked cards={len(issues)}")
    if require_kb_ready and issues:
        print(json.dumps(issues, ensure_ascii=False, indent=1))
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kb-ready", action="store_true", help="Fail on pending source/lineage approval or independent evidence")
    args = parser.parse_args()
    raise SystemExit(main(require_kb_ready=args.kb_ready))
