"""D14 frozen-alpha paired development validation, never reads test rows."""
import argparse
import csv
import hashlib
import json
import platform
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_mes_fault_models import (ALPHA, CHALLENGE_EFFECTS, fit_normal,
                                               predict_ewma, predict_rule, score)
from scripts.mes_ewma_release import FALL_ALPHA, predict_fast_release_ewma
from scripts.mes_forest_comparison import check_run_manifest
from scripts.mes_pca_candidate import check_pairing, gate_failures
from scripts.mes_response_scale_ablation import predict_normal_band
from scripts.mes_validation_candidate_review import load_train_validation

THRESHOLD = 3


def safety_failures(before, after):
    failures = gate_failures(before, after)
    for field in ("duplicate_alert_episodes", "premature_alert_episodes",
                  "alerts_on_inactive_equipment"):
        if after[field] > before[field]:
            failures.append(field)
    return failures


def alarm_changes(runs, before, after):
    """Disjoint label contexts for diagnosis only; do not change strict score."""
    context_before, context_after, removed_wrong, removed_positive = Counter(), Counter(), 0, 0
    added = 0
    for run_id, rows in runs.items():
        seen = {}
        for i, (frame, label) in enumerate(rows):
            key = (run_id, frame["sequence"])
            at = datetime.fromisoformat(frame["simulated_at"])
            seconds = ((datetime.fromisoformat(rows[i + 1][0]["simulated_at"]) - at).total_seconds()
                       if i + 1 < len(rows) else 1)
            faults = label["faults"]
            seen.update({fault["id"]: fault for fault in faults})
            positive = {f["equipment_id"] for f in faults if f["intensity"] > 0}
            added += seconds * len(after[key] - before[key])
            removed_positive += seconds * len((before[key] - after[key]) & positive)
            removed_wrong += seconds * len((before[key] - after[key]) - positive)
            for equipment in (before[key] | after[key]) - positive:
                if any(f["equipment_id"] == equipment for f in faults):
                    context = "episode_off"
                elif any(f["equipment_id"] == equipment and "end" in f
                         and 0 <= frame["sequence"] - f["end"] <= 7 for f in seen.values()):
                    context = "post_end"
                elif not faults:
                    # Not proof of physical normality: remote propagation/state can persist.
                    context = "no_current_injection_or_local_recovery"
                else:
                    context = "other_equipment_context"
                context_before[context] += seconds * (equipment in before[key])
                context_after[context] += seconds * (equipment in after[key])
    return {"wrong_before_by_context": dict(context_before), "wrong_after_by_context": dict(context_after),
            "wrong_removed_equipment_seconds": removed_wrong,
            "source_positive_removed_equipment_seconds": removed_positive,
            "added_alarm_equipment_seconds": added}


def event_starts(runs, alerts):
    """Expose score's matching decisions to prevent offsetting event wins/losses."""
    outcomes = {}
    for run_id, rows in runs.items():
        episodes, previous = {}, set()
        for frame, label in rows:
            at = datetime.fromisoformat(frame["simulated_at"])
            for fault in label["faults"]:
                episode = episodes.setdefault(fault["id"], {"equipment_id": fault["equipment_id"],
                    "mechanism": fault.get("pattern_id", "unspecified"), "onset": None, "detected": None})
                affected = fault.get("signal_targets")
                lags = CHALLENGE_EFFECTS.get(fault.get("pattern_id"), {}) if affected is None else {}
                measurements = frame.get("measurements")
                observable = measurements is None or any(
                    m["equipment_id"] == fault.get("source_equipment_id", fault["equipment_id"])
                    and (affected is None or m["signal"] in affected and affected[m["signal"]] is not None)
                    and (not lags or m["signal"] in lags and frame["sequence"] - fault["start"] >= lags[m["signal"]])
                    and m.get("quality") == "good" and m.get("observed_at") == frame["simulated_at"]
                    for m in measurements)
                if fault["intensity"] > 0 and observable and episode["onset"] is None:
                    episode["onset"] = at
            current = alerts[(run_id, frame["sequence"])]
            for equipment in current - previous:
                match = next((episodes[f["id"]] for f in label["faults"]
                              if f["equipment_id"] == equipment and f["intensity"] > 0
                              and episodes[f["id"]]["onset"] is not None
                              and episodes[f["id"]]["detected"] is None), None)
                if match is not None:
                    match["detected"] = at
            previous = current
        for fault_id, episode in episodes.items():
            outcomes[(run_id, fault_id)] = {**episode, "delay_seconds":
                (episode["detected"] - episode["onset"]).total_seconds() if episode["detected"] else None}
    return outcomes


def paired_events(runs, before, after, before_metrics, after_metrics):
    old, new = event_starts(runs, before), event_starts(runs, after)
    for values, metrics in ((old, before_metrics), (new, after_metrics)):
        assert sum(v["detected"] is not None for v in values.values()) == metrics["detected_events"]
        assert sum(v["onset"] is not None for v in values.values()) == metrics["events"]
    changes = []
    for key in old:
        if old[key]["delay_seconds"] != new[key]["delay_seconds"]:
            changes.append({"run_id": key[0], "fault_id": key[1],
                "equipment_id": old[key]["equipment_id"], "mechanism": old[key]["mechanism"],
                "baseline_delay_seconds": old[key]["delay_seconds"],
                "candidate_delay_seconds": new[key]["delay_seconds"]})
    return {"lost": [row for row in changes if row["candidate_delay_seconds"] is None],
            "gained": [row for row in changes if row["baseline_delay_seconds"] is None],
            "changed": changes}


def memory_releases(path, arm, runs, before, after):
    eligible, cleared, seen = 0, 0, set()
    lookup = {(run, frame["sequence"]): (frame, label) for run, rows in runs.items() for frame, label in rows}
    with Path(path).open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            if row["model"] != "ewma" or row["arm"] != arm:
                continue
            if row["intervention_pattern"] != "alert_without_links_only":
                continue
            key, equipment = (row["run_id"], int(row["sequence"])), row["equipment_id"]
            if (*key, equipment) in seen:
                raise ValueError("duplicate D13 memory coordinate")
            seen.add((*key, equipment))
            frame, label = lookup[key]
            assert frame["simulated_at"] == row["simulated_at"]
            assert equipment in before[key] and not any(
                f["equipment_id"] == equipment and f["intensity"] > 0 for f in label["faults"])
            assert float(row["ewma_max_current_z"]) < THRESHOLD
            seconds = float(row["duration_seconds"])
            eligible += seconds
            cleared += seconds * (equipment not in after[key])
    return {"eligible_equipment_seconds": eligible, "cleared_equipment_seconds": cleared,
            "retained_equipment_seconds": eligible - cleared}


def evaluate(pattern_path, full_path, weak_path, reference_path, memory_csv):
    started = time.perf_counter()
    reference = json.loads(Path(reference_path).read_text(encoding="utf-8"))
    config, pattern = load_train_validation(pattern_path)
    specs, stats = fit_normal(pattern["train"], config)
    pattern_manifest = json.loads((Path(pattern_path) / "manifest.json").read_text(encoding="utf-8"))
    check_run_manifest(pattern_manifest)
    training_seeds = {r["seed"] for r in pattern_manifest["runs"]}
    training_ids = {r["run_id"] for r in pattern_manifest["runs"]}
    arms, paired, failures = {}, None, []
    for arm, path, scale in (("full", full_path, 1), ("weak", weak_path, .2)):
        manifest = json.loads((Path(path) / "manifest.json").read_text(encoding="utf-8"))
        check_run_manifest(manifest)
        if manifest.get("generator_version") != 7 or manifest.get("response_scale") != scale:
            raise ValueError("expected v7 paired full/weak")
        if training_seeds & {r["seed"] for r in manifest["runs"]} or training_ids & {r["run_id"] for r in manifest["runs"]}:
            raise ValueError("challenge overlaps pattern runs/seeds")
        other_config, splits = load_train_validation(path, profile="independent")
        if other_config.config_id != config.config_id:
            raise ValueError("configuration mismatch")
        runs = splits["validation"]
        if paired is not None:
            check_pairing(paired, runs)
        paired = runs
        prediction_seconds, alerts = {}, {}
        for name, predictor in (("baseline", predict_ewma), ("candidate", predict_fast_release_ewma)):
            tick = time.perf_counter()
            alerts[name] = predictor(runs, specs, stats, THRESHOLD)
            prediction_seconds[name] = time.perf_counter() - tick
        before, after = (score(runs, alerts[name]) for name in ("baseline", "candidate"))
        if before != reference["baselines"][arm]["ewma"]:
            raise AssertionError("frozen D12 baseline metrics differ")
        events = paired_events(runs, alerts["baseline"], alerts["candidate"], before, after)
        arm_failures = safety_failures(before, after)
        if events["lost"]:
            arm_failures.append("previously_detected_events_lost")
        changes = alarm_changes(runs, alerts["baseline"], alerts["candidate"])
        assert changes["added_alarm_equipment_seconds"] == 0
        assert sum(changes["wrong_before_by_context"].values()) == before["wrong_alert_equipment_seconds"]
        assert sum(changes["wrong_after_by_context"].values()) == after["wrong_alert_equipment_seconds"]
        memory = memory_releases(memory_csv, arm, runs, alerts["baseline"], alerts["candidate"])
        if memory["eligible_equipment_seconds"] != {"full": 221, "weak": 23}[arm]:
            raise AssertionError("D13 memory reference differs")
        arms[arm] = {"baseline": before, "candidate": after, "gate_failures": arm_failures,
                     "paired_event_changes": events, "alarm_changes": changes,
                     "D13_memory_release": memory, "prediction_seconds": prediction_seconds,
                     "existing_symptom_rule": score(runs, predict_rule(runs, config)),
                     "normal_band_rule": score(runs, predict_normal_band(runs, specs))}
        failures.extend(f"{arm}: {item}" for item in arm_failures)
    if not any(a["candidate"]["wrong_alert_equipment_seconds"] < a["baseline"]["wrong_alert_equipment_seconds"]
               for a in arms.values()):
        failures.append("no_core_improvement")
    code = ("scripts/mes_ewma_release.py", "scripts/mes_ewma_release_review.py",
            "scripts/evaluate_mes_fault_models.py", "scripts/build_mes_fault_dataset.py",
            "docs/data/reference/00_plant_and_relations.json")
    return {"candidate": "fixed asymmetric abs-z EWMA", "alpha_up": ALPHA, "alpha_down": FALL_ALPHA,
            "threshold": THRESHOLD, "arms": arms, "gate_failures": failures,
            "decision": "hold" if failures else "eligible_for_one_fresh_test",
            "test_rows_read": 0, "final_test_evaluated": False,
            "python": platform.python_version(), "total_seconds": time.perf_counter() - started,
            "datasets": {"pattern": str(pattern_path), "full": str(full_path), "weak": str(weak_path)},
            "sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in code},
            "limits": "Synthetic generator-distribution development validation only; repeatedly used validation; .2 arbitrary stress; v6 weak invalid; no field/deployment claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pattern", "full", "weak", "reference", "memory-csv", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.pattern, args.full, args.weak, args.reference, args.memory_csv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(result["decision"], result["gate_failures"])


if __name__ == "__main__":
    main()
