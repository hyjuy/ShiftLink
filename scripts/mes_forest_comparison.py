"""Two independent forest candidates on fixed synthetic development splits."""
import argparse
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_mes_fault_models import predict_ewma, predict_rule, score, selection_key
from scripts.mes_pca_candidate import check_pairing, gate_failures
from scripts.mes_response_scale_ablation import predict_normal_band
from scripts.mes_validation_candidate_review import load_train_validation

GRIDS = {"isolation_forest": (.45, .50, .55, .60, .65, .70),
         "random_forest": (.20, .35, .50, .65, .80)}


def check_run_manifest(manifest):
    seen_ids, seen_seeds = set(), set()
    for run in manifest["runs"]:
        if run["run_id"] in seen_ids:
            raise ValueError("duplicate manifest run id")
        if run["seed"] in seen_seeds:
            raise ValueError("seed reused across dataset runs/splits")
        seen_ids.add(run["run_id"])
        seen_seeds.add(run["seed"])


def _manifest(path):
    value = json.loads((Path(path) / "manifest.json").read_text(encoding="utf-8"))
    check_run_manifest(value)
    return value


def summarize_types(runs, typed_alerts, training_classes):
    """Exact onset type score, with unsupported ontology explicitly separated."""
    typed_runs, known_runs = {}, {}
    unsupported, supported = set(), set()
    unseen = set()
    for run_id, rows in runs.items():
        typed_runs[run_id], known_runs[run_id] = [], []
        for frame, label in rows:
            transformed, known = [], []
            for fault in label["faults"]:
                eq, kind = fault["equipment_id"], fault["pattern_id"]
                row = dict(fault, source_equipment_id=eq, equipment_id=(eq, kind))
                transformed.append(row)
                supported_type = kind in training_classes.get(eq, set())
                if supported_type:
                    known.append(row)
                if fault["intensity"] > 0:
                    (supported if supported_type else unsupported).add((run_id, fault["id"]))
                    if not supported_type:
                        unseen.add(kind)
            typed_runs[run_id].append((frame, {"faults": transformed}))
            known_runs[run_id].append((frame, {"faults": known}))
    exact = score(typed_runs, typed_alerts)
    known = score(known_runs, typed_alerts)
    return {"exact_type_detected_events": exact["detected_events"],
            "observable_events": exact["events"],
            "raw_exact_type_event_recall": exact["event_recall"],
            "supported_events": len(supported), "unsupported_events": len(unsupported),
            "supported_type_event_recall": known["event_recall"],
            "unseen_types": sorted(unseen),
            "assessment": "unsupported_ontology" if unsupported and not supported else "closed_set_with_coverage_limits"}


def choose_candidate(reports):
    eligible = [name for name, report in reports.items() if not report["gate_failures"]]
    if not eligible:
        return None
    return min(eligible, key=lambda name: (
        sum(arm["metrics"]["wrong_alert_equipment_seconds"] for arm in reports[name]["arms"].values()),
        -reports[name]["arms"]["weak"]["metrics"]["detected_events"], name))


def _improved(before, after):
    return (after["detected_events"] > before["detected_events"] or
            after["wrong_alert_equipment_seconds"] < before["wrong_alert_equipment_seconds"])


def evaluate(pattern_path, full_path, weak_path):
    import numpy as np
    import sklearn
    from scripts.mes_forest_models import fit_models, predict_models, threshold_predictions

    started = time.perf_counter()
    pattern_manifest = _manifest(pattern_path)
    config, pattern = load_train_validation(pattern_path)
    tick = time.perf_counter()
    bundle = fit_models(pattern["train"], config)
    fit_seconds = time.perf_counter() - tick
    scored, pattern_coverage, pattern_timings = predict_models(pattern["validation"], bundle)
    classes = {eq: set(model.classes_) for eq, model in bundle["models"]["random_forest"].items()}
    reports = {}
    for name, grid in GRIDS.items():
        options = []
        for threshold in grid:
            alerts, _ = threshold_predictions({name: scored[name]}, threshold)
            options.append((threshold, score(pattern["validation"], alerts[name])))
        selected, metrics = max(options, key=lambda pair: (selection_key(pair[1]), pair[0]))
        reports[name] = {"selected_threshold": selected,
                         "pattern_validation": metrics,
                         "threshold_candidates": [{"threshold": t, "metrics": m} for t, m in options],
                         "arms": {}, "gate_failures": []}
        if name == "random_forest":
            _, typed = threshold_predictions({name: scored[name]}, selected)
            reports[name]["pattern_type_classification"] = summarize_types(pattern["validation"], typed[name], classes)

    arms, paired = {}, None
    pattern_ids = set(pattern["train"]) | set(pattern["validation"])
    pattern_seeds = {r["seed"] for r in pattern_manifest["runs"]}
    for arm_name, path, scale in (("full", full_path, 1.0), ("weak", weak_path, .2)):
        manifest = _manifest(path)
        if manifest.get("generator_version") != 7 or manifest.get("response_scale") != scale:
            raise ValueError("expected paired v7 scales 1.0 and 0.2")
        if pattern_seeds & {r["seed"] for r in manifest["runs"]}:
            raise ValueError("challenge shares seeds with pattern dataset")
        challenge_config, splits = load_train_validation(path, profile="independent")
        if challenge_config.config_id != config.config_id or pattern_ids & set(splits["validation"]):
            raise ValueError("configuration differs or challenge overlaps training/validation runs")
        validation = splits["validation"]
        if paired is not None:
            check_pairing(paired, validation)
        paired = validation
        predictions, coverage, timings = predict_models(validation, bundle)
        tick = time.perf_counter()
        ewma_alerts = predict_ewma(validation, bundle["specs"], bundle["stats"], 3)
        ewma_seconds = time.perf_counter() - tick
        ewma = score(validation, ewma_alerts)
        rule = score(validation, predict_rule(validation, config))
        band = score(validation, predict_normal_band(validation, bundle["specs"]))
        arms[arm_name] = {"ewma": ewma, "existing_symptom_rule": rule, "normal_band_rule": band,
                          "coverage": coverage, "timings": timings,
                          "ewma_prediction_seconds": ewma_seconds,
                          "validation_frames": sum(map(len, validation.values()))}
        for name, report in reports.items():
            alerts, typed = threshold_predictions({name: predictions[name]}, report["selected_threshold"])
            metrics = score(validation, alerts[name])
            failures = gate_failures(ewma, metrics)
            if any(count.get(f"{name}_nonfinite_scores", 0) for count in coverage.values()):
                failures.append("nonfinite model scores")
            report["arms"][arm_name] = {"metrics": metrics, "gate_failures": failures}
            report["gate_failures"].extend(f"{arm_name}: {item}" for item in failures)
            if name == "random_forest":
                report["arms"][arm_name]["type_classification"] = summarize_types(validation, typed[name], classes)
    for name, report in reports.items():
        if set(bundle["models"][name]) != set(bundle["masks"]):
            report["gate_failures"].append("untrained equipment models")
        if not any(_improved(arms[arm]["ewma"], report["arms"][arm]["metrics"]) for arm in arms):
            report["gate_failures"].append("no improvement")
        report["decision"] = "eligible_for_one_fresh_test" if not report["gate_failures"] else "hold"
    selected = choose_candidate(reports)
    return {"datasets": {"pattern": str(pattern_path), "full": str(full_path), "weak": str(weak_path)},
            "models": reports, "baselines": arms, "selected_candidate_for_fresh_test": selected,
            "test_rows_read": 0, "final_test_evaluated": False,
            "pattern_coverage": pattern_coverage, "pattern_prediction_timings": pattern_timings,
            "fit_seconds": fit_seconds, "total_seconds": time.perf_counter() - started,
            "diagnostics": bundle["diagnostics"],
            "versions": {"python": platform.python_version(), "numpy": np.__version__, "sklearn": sklearn.__version__},
            "limits": "Synthetic development validation only. Normal covariance differs between pattern v4 and v7. RF v7 types are unseen. response_scale=0.2 is arbitrary stress. v6 weak experiment remains invalid. No field or deployment claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pattern", type=Path, required=True)
    parser.add_argument("--full", type=Path, required=True)
    parser.add_argument("--weak", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.pattern, args.full, args.weak)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print({name: report["decision"] for name, report in result["models"].items()})
    print("selected_for_fresh_test:", result["selected_candidate_for_fresh_test"])


if __name__ == "__main__":
    main()
