"""One-time, auditable registration of pending sources and lineage; never approves."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[4]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, data, indent=1):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8", newline="\n")


def digest(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def main():
    import pymupdf

    changes_path = HERE / "policy_alignment_changes.json"
    if changes_path.exists():
        raise SystemExit("Already aligned; preserve the original change record and review subsequent edits separately.")
    registry_path = ROOT / "seeds/source_registry.json"
    policy_path = ROOT / "splits/prototype_split.json"
    registry, policy = read(registry_path), read(policy_path)
    cards = [c for p in sorted((HERE / "out").glob("*.json")) for c in read(p)]
    events, artifacts, plan = read(HERE / "events.json"), read(HERE / "artifacts.json"), read(HERE / "event_plan.json")
    original_cards = json.loads(json.dumps(cards))
    by_event = {e["event_id"]: e for e in plan["events"]}
    # Same generator template: equipment + restart type. Compound events join types.
    parent = {eid: eid for eid in by_event}

    def find(eid):
        while parent[eid] != eid:
            eid = parent[eid]
        return eid

    def join(a, b):
        a, b = find(a), find(b)
        parent[max(a, b)] = min(a, b)

    templates = {}
    for e in plan["events"]:
        for kind in e["restart_types"]:
            key = e["equipment"], kind
            if key in templates:
                join(e["event_id"], templates[key])
            templates[key] = e["event_id"]
    # Exact or ID/number-normalized copies cannot become separate lineage groups.
    texts = {}
    for a in artifacts:
        key = re.sub(r"\d+", "N", re.sub(r"(?:EV|AR|AT|K)-\d{4}", "ID", a["text"]))
        if key in texts:
            join(a["event_id"], texts[key])
        texts[key] = a["event_id"]
    event_groups = {eid: f"KB-20260930-C:{find(eid)}" for eid in parent}
    groups = []
    for gid in sorted(set(event_groups.values())):
        eids = sorted(eid for eid, group in event_groups.items() if group == gid)
        value = int.from_bytes(hashlib.sha256(f"shiftlink-split-v1:{gid}".encode()).digest(), "big") % 12
        candidate = "kb" if value <= 6 else "dev" if value <= 8 else "sealed"
        groups.append({"group_id": gid, "event_ids": eids,
                       "artifact_ids": sorted(a["artifact_id"] for a in artifacts if a["event_id"] in eids),
                       "original_splits": sorted({by_event[eid]["split"] for eid in eids}),
                       "lineage_review_status": "pending_review", "candidate_split": candidate,
                       "bucket": value, "assignment_active": False, "is_synthetic": True,
                       "basis": "same equipment/restart generator template; compound-event overlap; normalized text copies",
                       "independent_evaluation_eligible": False})
    source_ids = sorted({s["source_id"] for c in cards for s in c["provenance"]["sources"]})
    pdf_names = [sid for sid in source_ids if sid.endswith(".pdf")]
    mapping = {name: f"M-C-{i:03d}" for i, name in enumerate(pdf_names, 1)}
    mapping.update({sid: f"SC-C-{sid}" for sid in source_ids if not sid.endswith(".pdf")})
    assert not set(mapping.values()) & {s["source_id"] for s in registry["sources"]}
    assert not {g["group_id"] for g in groups} & {g["group_id"] for g in policy["assignments"]}
    pdf_paths = {p.name: p for p in (ROOT / "docs/data/sources").rglob("*.pdf")}
    event_projection = {e["event_id"]: e for e in read(HERE / "records/kb_events.json")}
    artifact_projection = {a["artifact_id"]: a for a in read(HERE / "records/kb_artifacts.json")}
    registrations = []
    for old in source_ids:
        refs = [(c, s) for c in cards for s in c["provenance"]["sources"] if s["source_id"] == old]
        row = {"source_id": mapping[old], "aliases": [old], "source_family": mapping[old],
               "title": old, "url": None, "url_role": None, "review_status": "pending_review",
               "approved_scope": [], "is_synthetic": not old.endswith(".pdf"),
               "document_version": refs[0][1].get("document_version"),
               "reviewed_notes": ["docs/data/knowledge_cards/kb/20260930-C/review_round2.md"],
               "registered_at": "2026-09-30", "registered_by": "Codex; registration only",
               "generation_gate": "No approved scope. Source/content/lineage approval must be recorded before generation or adoption.",
               "review_candidates": []}
        if old.endswith(".pdf"):
            file = pdf_paths[old]
            row["local_snapshot"] = {"path": file.relative_to(ROOT).as_posix(), "bytes": file.stat().st_size,
                                       "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
            row["purpose"] = "배치 C 원문 출처 식별 및 사용 절 검토 대기"
            row["identity_limitations"] = "기존 SD/M 문서와 동일 판본으로 병합하지 않음. 원문 URL·이용 범위 승인 미확정."
            with pymupdf.open(file) as pdf:
                for c, source in refs:
                    locator = source["locator"]
                    prefix = locator.split(" / ", 1)[0].split(",", 1)[0]
                    pages = []
                    for first, last in re.findall(r"(\d+)(?:[~–-](\d+))?", prefix):
                        pages.extend(range(int(first), int(last or first) + 1))
                    pages = sorted(set(pages))
                    assert pages and all(1 <= p <= len(pdf) for p in pages), (old, locator)
                    text = "\n".join(pdf[p - 1].get_text() for p in pages)
                    row["review_candidates"].append({"scope_id": f"{c['card_id']}-{len(row['review_candidates']) + 1}",
                         "card_id": c["card_id"], "locator": locator, "document_version": source.get("document_version"),
                         "pdf_pages": pages, "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                         "extraction_method": "PyMuPDF page text joined by LF; excerpt hash is not PDF file hash",
                         "approval_status": "pending_review"})
        else:
            item = event_projection[old] if old.startswith("EV-") else artifact_projection[old]
            eid = old if old.startswith("EV-") else item["event_id"]
            row.update({"purpose": "합성 KB 관측 투영; 현장 경험 아님", "group_id": event_groups[eid],
                        "reference_ids": [old], "lineage_review_status": "pending_review",
                        "local_snapshot": {"path": (HERE / ("records/kb_events.json" if old.startswith("EV-") else "records/kb_artifacts.json")).relative_to(ROOT).as_posix(),
                                           "item_id": old, "item_sha256": digest(item)}})
        registrations.append(row)
    registry["sources"].extend(registrations)
    policy.setdefault("pending_groups", []).extend(groups)
    manifest = {"contract": "docs/data/policies/source-and-split-contract.md", "policy_status": "pending_review",
                "source_id_map": mapping, "groups": groups, "event_groups": event_groups,
                "independent_dev_event_ids": [], "quarantined_dev_event_ids": [e["event_id"] for e in events if e["split"] == "dev"],
                "current_splits_are_historical": True, "cards": {}}
    for c in cards:
        support = (c.get("generalization_evidence") or {}).get("supporting_event_ids", [])
        gids = sorted({event_groups[eid] for eid in support})
        manifest["cards"][c["card_id"]] = {"source_ids": sorted({mapping[s["source_id"]] for s in c["provenance"]["sources"]}),
             "group_ids": gids, "status": "pending_review", "kb_adoption_allowed": False,
             "independent_supporting_group_count": len(gids),
             "required_reviews": ["source_scope_approval", "equipment_applicability"] + (["lineage_confirmation", "group_assignment", "independent_repeat_evidence"] if support else [])}
        for source in c["provenance"]["sources"]:
            original = source["source_id"]
            source["source_id"] = mapping[original]
            source["locator"] = f"{original} | {source['locator']}"
        ge = c["generalization_evidence"]
        ge["confidence_basis"] += " 출처 기준 ID 등록만 완료했으며 approved_scope는 미승인이다. KB 편입 보완 대기."
        if support:
            ge["confidence_basis"] += f" 근거 사건은 {len(gids)}개 합성 계보 후보({', '.join(gids)})에 속한다. 서로 다른 사건 ID를 독립 경험 반복으로 계산하지 않는다."
            ge["generalization_scope"] += " 독립 현장 반복을 입증하지 않은 합성 템플릿 범위에 한정한다."
    manifest_hash = hashlib.sha256((json.dumps(manifest, ensure_ascii=False, indent=1) + "\n").encode("utf-8")).hexdigest()
    for c in cards:
        c["provenance"]["index_version"] = f"docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:{manifest_hash}"
    changes = {"operation": "pending source and lineage registration; no approval", "date": "2026-09-30",
               "original_cards": original_cards, "updated_cards": cards,
               "original_registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
               "original_policy_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest()}
    # Everything above is computed before writing; existing approvals/assignments remain intact.
    write(changes_path, changes)
    write(registry_path, registry)
    write(policy_path, policy, indent=2)
    write(HERE / "policy_manifest.json", manifest)
    for file in sorted((HERE / "out").glob("*.json")):
        old_ids = {c["card_id"] for c in read(file)}
        write(file, [c for c in cards if c["card_id"] in old_ids])
    for kind in ("events", "artifacts"):
        active = HERE / f"records/dev_{kind}.json"
        write(HERE / f"records/quarantined_dev_{kind}.json", read(active))
        write(active, [])
    for e in plan["events"]:
        e["lineage_group_candidate"] = event_groups[e["event_id"]]
        e["evaluation_eligible"] = False
        e["split_assignment_status"] = "historical_only; pending lineage review"
    write(HERE / "event_plan.json", plan)
    print(f"Registered {len(registrations)} pending sources, {len(groups)} pending lineage groups; quarantined 5 dev events; no approvals.")


if __name__ == "__main__":
    main()
