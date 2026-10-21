"""Offline synthetic-only comparison of four equipment-location detectors.

Example: python scripts/mes_model_benchmark.py --train-dataset output/pattern --test-dataset output/independent
All baselines fit on fault-free pattern train frames. Thresholds and the selected
model use pattern validation only. Independent test labels are used only to score.
"""
import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_mes_fault_models import (fit_normal, load_dataset, predict_ewma,
                                                predict_rule, score, selection_key, valid_values)


ROBUST_THRESHOLDS = (2.0, 3.0, 4.0, 5.0, 6.0)
EWMA_THRESHOLDS = (1.5, 2.0, 2.5, 3.0, 4.0, 5.0)
CUSUM_THRESHOLDS = (3.0, 5.0, 8.0, 12.0, 16.0)
CUSUM_DRIFT = .5
INACTIVE_MODES = {"paused", "stopped", "recovering", "quality_hold"}


def fit_robust(train_runs, config):
    specs = {(eq.equipment_id, spec.signal): spec for eq in config.equipment
             if getattr(eq, "active", True) for spec in eq.signals}
    samples = defaultdict(list)
    for rows in train_runs.values():
        for frame, label in rows:
            if not label["faults"] and frame.get("line_mode") not in INACTIVE_MODES:
                for key, value in valid_values(frame, specs).items():
                    samples[key].append(value)
    if not samples:
        raise ValueError("no fault-free training measurements")
    result = {}
    for key, values in samples.items():
        center = median(values)
        mad = median(abs(value - center) for value in values)
        spec = specs[key]
        band = (spec.normal_max - spec.normal_min
                if spec.normal_min is not None and spec.normal_max is not None else 0)
        result[key] = (center, max(1.4826 * mad, band * .05, .001))
    return result


def predict_robust(runs, specs, stats, threshold):
    alerts = {}
    for run_id, rows in runs.items():
        for frame, _ in rows:
            key = (run_id, frame["sequence"])
            if frame.get("line_mode") in INACTIVE_MODES:
                alerts[key] = set()
                continue
            alerts[key] = {equipment for (equipment, signal), value in valid_values(frame, specs).items()
                           if (equipment, signal) in stats
                           and abs(value - stats[(equipment, signal)][0]) /
                           stats[(equipment, signal)][1] >= threshold}
    return alerts


def predict_cusum(runs, specs, stats, threshold):
    """Two-sided Page CUSUM with per-signal state and no future observations."""
    alerts = {}
    for run_id, rows in runs.items():
        positive, negative = {}, {}
        for frame, _ in rows:
            key = (run_id, frame["sequence"])
            if frame.get("line_mode") in INACTIVE_MODES:
                positive.clear()
                negative.clear()
                alerts[key] = set()
                continue
            values = valid_values(frame, specs)
            positive = {signal: value for signal, value in positive.items() if signal in values}
            negative = {signal: value for signal, value in negative.items() if signal in values}
            equipment_scores = defaultdict(float)
            for signal, value in values.items():
                if signal not in stats:
                    continue
                center, scale = stats[signal]
                z = (value - center) / scale
                positive[signal] = max(0.0, positive.get(signal, 0.0) + z - CUSUM_DRIFT)
                negative[signal] = max(0.0, negative.get(signal, 0.0) - z - CUSUM_DRIFT)
                equipment_scores[signal[0]] = max(equipment_scores[signal[0]],
                                                  positive[signal], negative[signal])
            alerts[key] = {equipment for equipment, value in equipment_scores.items()
                           if value >= threshold}
    return alerts


def evaluate(train_dataset, test_dataset):
    train_dataset, test_dataset = Path(train_dataset), Path(test_dataset)
    train_manifest = json.loads((train_dataset / "manifest.json").read_text(encoding="utf-8"))
    test_manifest = json.loads((test_dataset / "manifest.json").read_text(encoding="utf-8"))
    if train_manifest.get("profile") != "pattern" or test_manifest.get("profile") != "independent":
        raise ValueError("expected pattern training and independent test profiles")
    config, pattern = load_dataset(train_dataset)
    other_config, independent = load_dataset(test_dataset)
    if config.config_id != other_config.config_id:
        raise ValueError("train/test equipment configuration differs")
    train_ids = {run_id for split in pattern.values() for run_id in split}
    test_ids = {run_id for split in independent.values() for run_id in split}
    if train_ids & test_ids:
        raise ValueError("train and test datasets share runs")
    specs, mean_stats = fit_normal(pattern["train"], config)
    robust_stats = fit_robust(pattern["train"], config)
    predictors = {
        "ewma": (EWMA_THRESHOLDS,
                 lambda runs, threshold: predict_ewma(runs, specs, mean_stats, threshold)),
        "robust_z": (ROBUST_THRESHOLDS,
                     lambda runs, threshold: predict_robust(runs, specs, robust_stats, threshold)),
        "cusum": (CUSUM_THRESHOLDS,
                  lambda runs, threshold: predict_cusum(runs, specs, robust_stats, threshold))}
    validation = {"existing_symptom_rule": {"threshold": None,
                   "metrics": score(pattern["validation"], predict_rule(pattern["validation"], config))}}
    selected_model = "existing_symptom_rule"
    selected_key = selection_key(validation[selected_model]["metrics"])
    for model_name, (thresholds, predictor) in predictors.items():
        candidates = [(threshold, score(pattern["validation"], predictor(pattern["validation"], threshold)))
                      for threshold in thresholds]
        threshold, metrics = max(candidates, key=lambda item: (selection_key(item[1]), item[0]))
        validation[model_name] = {"threshold": threshold, "metrics": metrics}
        if selection_key(metrics) > selected_key:
            selected_model, selected_key = model_name, selection_key(metrics)
    test_runs = independent["test"]
    test_alerts = {"existing_symptom_rule": predict_rule(test_runs, config)}
    for model_name, (_, predictor) in predictors.items():
        test_alerts[model_name] = predictor(test_runs, validation[model_name]["threshold"])
    test = {name: score(test_runs, alerts) for name, alerts in test_alerts.items()}
    run_fields = ("events", "injected_events", "unobservable_events", "detected_events",
                  "event_recall", "injected_event_recall", "event_f1", "injected_event_f1",
                  "p95_onset_delay_seconds", "wrong_alert_time_fraction")
    by_run = {name: {run_id: {field: metrics[field] for field in run_fields}
                     for run_id, rows in test_runs.items()
                     for metrics in (score({run_id: rows}, alerts),)}
              for name, alerts in test_alerts.items()}
    return {"train_dataset": str(train_dataset), "test_dataset": str(test_dataset),
            "normal_training_split": "train", "selection_split": "validation", "test_split": "test",
            "model_count": len(test),
            "selection_metric": "Validation-only diagnostic utility = injected-event F1 * (1 - wrong-alert time fraction); ties use injected-event F1, wrong-alert time, alert starts/run-hour, and mean detection delay. This is not a calibrated operating objective.",
            "validation": validation, "selected_model": selected_model, "test": test,
            "test_by_run": by_run,
            "limits": "All values and fault labels are synthetic. Thresholds and model were selected with a heuristic on pattern validation; independent test is a held-out synthetic mechanism check, not an operational acceptance test. Labels are used to choose healthy training frames and score only. All models locate equipment, not exact failure type. event_f1 uses observable-event recall and alert-start precision; injected_event_f1 includes unobservable injections. p95 onset delay includes detected events only and must be read with recall and coverage. No real-plant transfer claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-dataset", type=Path, required=True)
    parser.add_argument("--test-dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, help="Write the full JSON report to this local file")
    args = parser.parse_args()
    report = evaluate(args.train_dataset, args.test_dataset)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out is None:
        print(payload)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
        print(json.dumps({"out": str(args.out), "selected_model": report["selected_model"],
                          "test_events": report["test"][report["selected_model"]]["injected_events"]},
                         ensure_ascii=False))


if __name__ == "__main__":
    main()
