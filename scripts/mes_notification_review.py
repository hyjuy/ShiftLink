"""D18: label-free notification grouping; raw alarms remain untouched."""
from collections import Counter
from datetime import datetime

from scripts.evaluate_mes_fault_models import valid_values
from scripts.mes_ewma_release_review import event_starts


QUIET_SECONDS = 3


def group_notifications(frames_by_run, alerts, specs, masks):
    notifications, closures, suppressed, transitions = [], [], [], []
    raw_counts, candidate_counts = Counter(), Counter()
    eligible = 0
    for run, frames in frames_by_run.items():
        opened, quiet, previous, last = set(), {}, set(), None
        def close(eq, sequence, reason):
            row = {"run_id": run, "sequence": sequence, "equipment_id": eq, "reason": reason}
            closures.append(row)
            transitions.append({"action": "close", **row})
            opened.remove(eq)
            quiet.pop(eq, None)
        for frame in frames:
            sequence = frame["sequence"]
            at = datetime.fromisoformat(frame["simulated_at"])
            raw = alerts[run, sequence]
            if raw - masks.keys():
                raise ValueError("raw alarm equipment absent from frozen mask")
            starts = raw - previous
            raw_counts.update((run, eq) for eq in starts)
            gap = last is not None and (sequence != last[0]+1 or (at-last[1]).total_seconds() != 1)
            inactive = frame.get("line_mode") != "running"
            if gap or inactive:
                for eq in sorted(opened):
                    close(eq, sequence, "gap" if gap else "inactive")
            if inactive and raw:
                raise ValueError("raw alarm on inactive frame requires separate policy")
            values = valid_values(frame, specs)
            for eq, mask in sorted(masks.items()):
                if eq in raw:
                    if eq not in opened:
                        notifications.append({"run_id": run, "sequence": sequence,
                            "simulated_at": frame["simulated_at"], "equipment_id": eq})
                        transitions.append({"action": "open", **notifications[-1]})
                        candidate_counts[run, eq] += 1
                        opened.add(eq)
                    elif eq in starts:
                        eligible += int(quiet.get(eq, 0) in (1, 2))
                        suppressed.append({"run_id": run, "sequence": sequence, "equipment_id": eq})
                    quiet[eq] = 0
                elif eq in opened:
                    complete = bool(mask) and all(key in values for key in mask)
                    quiet[eq] = quiet.get(eq, 0)+1 if complete else 0
                    reason = "unknown" if not complete else "resolved" if quiet[eq] == QUIET_SECONDS else None
                    if reason:
                        close(eq, sequence, reason)
            previous, last = set(raw), (sequence, at)
        for eq in sorted(opened):
            close(eq, last[0], "run_end")
    return {"notifications": notifications, "closures": closures, "suppressed_raw_starts": suppressed,
            "transitions": transitions,
            "eligible_short_gap_restarts": eligible,
            "counts": [{"run_id": run, "equipment_id": eq, "raw_starts": raw_counts[run, eq],
                        "notifications": candidate_counts[run, eq]}
                       for run, eq in sorted(raw_counts.keys() | candidate_counts.keys())]}


def review_notifications(runs, alerts, grouped):
    """Match explicit notifications, without scoring pulse durations as alarms."""
    baseline = event_starts(runs, alerts)
    notified, matched, failures = {}, {}, []
    coordinates = set()
    for row in grouped["notifications"]:
        key = row["run_id"], row["sequence"], row["equipment_id"]
        if key in coordinates or key[2] not in alerts[key[:2]]:
            failures.append("invalid or duplicate notification")
        coordinates.add(key)
        notified.setdefault(key[:2], []).append(row)
    expected_raw, actual_notifications = Counter(), Counter((r[0], r[2]) for r in coordinates)
    for run, rows in runs.items():
        previous = set()
        for frame, _ in rows:
            raw = alerts[run, frame["sequence"]]
            expected_raw.update((run, eq) for eq in raw-previous)
            previous = raw
    expected_counts = {(run, eq): (expected_raw[run, eq], actual_notifications[run, eq])
                       for run, eq in expected_raw.keys() | actual_notifications.keys()}
    supplied_counts = {(r["run_id"], r["equipment_id"]): (r["raw_starts"], r["notifications"])
                       for r in grouped["counts"]}
    if supplied_counts != expected_counts or len(supplied_counts) != len(grouped["counts"]):
        failures.append("notification counts differ from trace")
    opened, trace_coordinates, trace_valid = set(), set(), True
    for row in grouped["transitions"]:
        key = row["run_id"], row["equipment_id"]
        if row["action"] == "open":
            trace_valid &= key not in opened
            opened.add(key)
            trace_coordinates.add((key[0], row["sequence"], key[1]))
        elif row["action"] == "close":
            trace_valid &= key in opened and row["reason"] in {"resolved", "unknown", "gap", "inactive", "run_end"}
            opened.discard(key)
        else:
            trace_valid = False
    if not trace_valid or opened or trace_coordinates != coordinates:
        failures.append("invalid incident transition trace")
    removed_same_episode = 0
    suppressed = {(r["run_id"], r["sequence"], r["equipment_id"])
                  for r in grouped["suppressed_raw_starts"]}
    for run, rows in runs.items():
        for frame, label in rows:
            seq, at = frame["sequence"], datetime.fromisoformat(frame["simulated_at"])
            for row in notified.get((run, seq), []):
                if row["simulated_at"] != frame["simulated_at"]:
                    failures.append("notification time differs from frame")
                match = next((f for f in label["faults"] if f["equipment_id"] == row["equipment_id"]
                    and f["intensity"] > 0 and baseline[run, f["id"]]["onset"] is not None
                    and baseline[run, f["id"]]["onset"] <= at and (run, f["id"]) not in matched), None)
                if match is not None:
                    matched[run, match["id"]] = at
            for eq in alerts[run, seq]:
                if (run, seq, eq) in suppressed and any(f["equipment_id"] == eq
                        and (run, f["id"]) in matched for f in label["faults"]):
                    removed_same_episode += 1
    changed = [{"run_id": run, "fault_id": fault_id, "equipment_id": row["equipment_id"],
                "baseline_at": row["detected"].isoformat(),
                "notification_at": matched[run, fault_id].isoformat() if (run, fault_id) in matched else None}
               for (run, fault_id), row in baseline.items()
               if row["detected"] is not None and matched.get((run, fault_id)) != row["detected"]]
    if changed:
        failures.append("individual source notification lost or delayed")
    if any(r["notifications"] > r["raw_starts"] for r in grouped["counts"]):
        failures.append("per-run equipment notifications increased")
    raw_matched = sum(r["detected"] is not None for r in baseline.values())
    raw_starts = sum(r["raw_starts"] for r in grouped["counts"])
    unmatched = len(grouped["notifications"])-len(matched)
    if unmatched >= raw_starts-raw_matched:
        failures.append("unmatched notifications did not decrease")
    return {"decision": "hold" if failures else "eligible_for_fresh_confirmation", "failures": failures,
            "raw_starts": raw_starts, "notifications": len(grouped["notifications"]),
            "baseline_matched_events": raw_matched, "notification_matched_events": len(matched),
            "raw_unmatched_starts": raw_starts-raw_matched, "unmatched_notifications": unmatched,
            "lost_or_changed_events": changed, "removed_same_episode_duplicates": removed_same_episode,
            "eligible_short_gap_restarts": grouped["eligible_short_gap_restarts"],
            "counts": grouped["counts"], "raw_alarm_duration_changed": False}


def evaluate_cached(runtime, cache_path, paths):
    import hashlib
    import json
    from pathlib import Path
    import sys
    from scripts.evaluate_mes_fault_models import score
    from scripts.mes_validation_candidate_review import load_train_validation
    from scripts.mes_training_source import prefix_hashes

    runtime = Path(runtime).resolve()
    provenance = json.loads((runtime/"provenance.json").read_text(encoding="utf-8"))
    for module in ("scripts.evaluate_mes_fault_models", "scripts.mes_ewma_release_review",
                   "scripts.mes_validation_candidate_review", "scripts.mes_training_source"):
        if not Path(sys.modules[module].__file__).resolve().is_relative_to(runtime):
            raise ValueError("run with frozen runtime first on sys.path")
    def integrity():
        if any(hashlib.sha256((runtime/name).read_bytes()).hexdigest() != value
               for name, value in provenance["files"].items()):
            raise ValueError("frozen runtime integrity changed")
    integrity()
    cache = json.loads(Path(cache_path).read_text(encoding="utf-8"))
    arms = {}
    for arm, path in paths.items():
        manifest = json.loads((Path(path)/"manifest.json").read_text(encoding="utf-8"))
        if prefix_hashes(path, manifest) != cache["input_prefix_sha256"][arm]:
            raise ValueError("D16 consumed prefix differs")
        config, splits = load_train_validation(path, profile="independent")
        if config.config_id != cache["config_id"]:
            raise ValueError("D16 configuration differs")
        runs = splits["validation"]
        specs = {(eq.equipment_id, s.signal): s for eq in config.equipment for s in eq.signals if eq.active}
        masks = {eq: [(eq, signal) for signal in row["selected_channels"]]
                 for eq, row in cache["training"].items()}
        raw = {(run, seq): set(equipment) for run, rows in cache["arms"][arm]["alerts"]["ewma"].items()
               for seq, equipment in rows}
        preserved = {key: set(value) for key, value in raw.items()}
        strict = score(runs, raw)
        if strict != cache["arms"][arm]["models"]["ewma"]["strict_source"]:
            raise ValueError("D16 strict score differs before grouping")
        grouped = group_notifications({run: [frame for frame, _ in rows] for run, rows in runs.items()},
                                      raw, specs, masks)
        review = review_notifications(runs, raw, grouped)
        if raw != preserved or score(runs, raw) != strict:
            raise AssertionError("raw predictions or strict scores changed")
        arms[arm] = {**review, "raw_strict_source": strict, "grouping_trace": grouped}
    integrity()
    return {"experiment": "D18", "quiet_valid_consecutive_seconds": QUIET_SECONDS,
            "decision": "hold" if any(row["failures"] for row in arms.values()) else "eligible_for_fresh_confirmation",
            "arms": arms, "test_rows_read": 0, "raw_predictions_and_scores_unchanged": True,
            "cache_sha256": hashlib.sha256(Path(cache_path).read_bytes()).hexdigest(),
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "runtime_provenance_sha256": hashlib.sha256((runtime/"provenance.json").read_bytes()).hexdigest(),
            "limits": "Synthetic notification burden only; no pulse-duration accuracy claim or field validation."}


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("runtime", "cache", "full", "weak", "out"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("preserve earlier results; output exists")
    result = evaluate_cached(args.runtime, args.cache, {"full": args.full, "weak": args.weak})
    with args.out.open("x", encoding="utf-8") as target:
        json.dump(result, target, ensure_ascii=False, indent=2, allow_nan=False)
        target.write("\n")
    print(json.dumps({"D18": result["decision"], "arms": {name: {key: row[key] for key in
        ("raw_starts", "notifications", "raw_unmatched_starts", "unmatched_notifications", "failures")}
        for name, row in result["arms"].items()}}, ensure_ascii=False))
