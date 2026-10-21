"""Compare paired independent fault amplitudes on validation rows only.

Fit and freeze four model settings on pattern train/validation. Never read
independent test rows; this is a development stress test, not a final score.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_mes_fault_models import (fit_normal, predict_ewma,
                                                predict_rule, score, selection_key,
                                                valid_values)
from scripts.mes_model_benchmark import (CUSUM_THRESHOLDS, EWMA_THRESHOLDS,
                                         ROBUST_THRESHOLDS, fit_robust,
                                         predict_cusum, predict_robust)
from scripts.mes_validation_candidate_review import load_train_validation


def _summary(metrics):
    summary = {key: metrics[key] for key in (
        "injected_events", "detected_events", "injected_event_f1",
        "unobservable_events", "false_alerts", "wrong_alert_seconds",
        "wrong_alert_equipment_seconds", "wrong_alert_time_fraction",
        "p95_onset_delay_seconds")}
    summary["missed_injected_events"] = metrics["injected_events"] - metrics["detected_events"]
    summary["by_equipment"] = metrics["by_equipment"]
    summary["by_mechanism"] = metrics["by_mechanism"]
    summary["by_kind"] = metrics["by_kind"]
    return summary


def predict_normal_band(runs, specs):
    """Fixed catalog-bound sanity baseline; no fitted parameters or labels."""
    alerts = {}
    for run_id, rows in runs.items():
        for frame, _ in rows:
            alerts[(run_id, frame["sequence"])] = {
                equipment for (equipment, signal), value in valid_values(frame, specs).items()
                if specs[(equipment, signal)].normal_min is not None
                and specs[(equipment, signal)].normal_max is not None
                and not specs[(equipment, signal)].normal_min <= value <= specs[(equipment, signal)].normal_max
            }
    return alerts


def evaluate(pattern_path, baseline_path, weak_path):
    config, pattern = load_train_validation(pattern_path)
    specs, mean = fit_normal(pattern["train"], config)
    robust = fit_robust(pattern["train"], config)
    predictors = {
        "existing_symptom_rule": (None, lambda runs, _: predict_rule(runs, config)),
        "normal_band_rule": (None, lambda runs, _: predict_normal_band(runs, specs)),
        "ewma": (EWMA_THRESHOLDS, lambda runs, threshold: predict_ewma(runs, specs, mean, threshold)),
        "robust_z": (ROBUST_THRESHOLDS, lambda runs, threshold: predict_robust(runs, specs, robust, threshold)),
        "cusum": (CUSUM_THRESHOLDS, lambda runs, threshold: predict_cusum(runs, specs, robust, threshold)),
    }
    thresholds = {"existing_symptom_rule": None, "normal_band_rule": None}
    for name, (options, predict) in predictors.items():
        if options is None:
            continue
        threshold, _ = max(((threshold, score(pattern["validation"], predict(pattern["validation"], threshold)))
                            for threshold in options), key=lambda pair: (selection_key(pair[1]), pair[0]))
        thresholds[name] = threshold

    reports = {}
    keys = None
    labels = None
    for name, path in (("baseline", baseline_path), ("weaker_response", weak_path)):
        other_config, splits = load_train_validation(path, profile="independent")
        manifest = json.loads((Path(path) / "manifest.json").read_text(encoding="utf-8"))
        if other_config.config_id != config.config_id:
            raise ValueError("equipment configuration differs")
        validation = splits["validation"]
        current_keys = {(run_id, frame["sequence"]) for run_id, rows in validation.items()
                        for frame, _ in rows}
        if keys is not None and current_keys != keys:
            raise ValueError("paired validation runs differ")
        keys = current_keys
        current_labels = {(run_id, frame["sequence"]): label["faults"]
                          for run_id, rows in validation.items() for frame, label in rows}
        if labels is not None and current_labels != labels:
            raise ValueError("paired fault schedules differ")
        labels = current_labels
        reports[name] = {
            "dataset": str(path), "response_scale": manifest.get("response_scale", 1.0),
            "validation_runs": len(validation), "validation_frames": len(current_keys),
            "models": {model: _summary(score(validation, predict(validation, thresholds[model])))
                       for model, (_, predict) in predictors.items()},
        }
    if reports["baseline"]["response_scale"] != 1.0 or not 0 < reports["weaker_response"]["response_scale"] < 1:
        raise ValueError("expected full and reduced response scales")
    return {"normal_training_dataset": str(pattern_path), "selection_split": "pattern validation",
            "comparison_split": "independent validation", "test_rows_read": 0,
            "model_thresholds": thresholds, "paired_fault_schedules_equal": True,
            "arms": reports,
            "limits": "All values are synthetic. Only fault-response amplitude changes between arms. "
            "The independent validation rows are now development data. Normal simulator, fault schedules, "
            "and equipment graph remain shared; no field performance claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pattern", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--weaker", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = evaluate(args.pattern, args.baseline, args.weaker)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
