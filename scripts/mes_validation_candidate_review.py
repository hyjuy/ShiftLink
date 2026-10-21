"""Review new MES detectors on pattern train/validation only; never read test rows.

Example: python scripts/mes_validation_candidate_review.py --dataset output/mes-fault-pattern-v4-20261020
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_mes_fault_models import (CATALOG, fit_normal, predict_ewma,
                                               predict_rule, score, selection_key)
from scripts.mes_model_benchmark import (CUSUM_THRESHOLDS, EWMA_THRESHOLDS,
                                         ROBUST_THRESHOLDS, fit_robust,
                                         predict_cusum, predict_robust)
from scripts.mes_additional_models import (predict_consensus_robust,
                                           predict_sustained_robust)
from shiftlink.mes.configuration import from_catalog
from shiftlink.mes.scenarios.priority import expand


def load_train_validation(path, *, profile="pattern"):
    """Read the prefix of ordered run files, stopping before the first test row."""
    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("profile") != profile or manifest.get("is_synthetic") is not True:
        raise ValueError(f"expected synthetic {profile} dataset")
    config = expand(from_catalog(json.loads(CATALOG.read_text(encoding="utf-8"))))
    if config.config_id != manifest.get("config_id") or manifest.get("signal_count") != 69:
        raise ValueError("dataset equipment contract differs")
    runs = manifest["runs"]
    prefix = [run for run in runs if run["split"] != "test"]
    if (not prefix or {run["split"] for run in prefix} != {"train", "validation"}
            or runs[:len(prefix)] != prefix or any(run["split"] != "test" for run in runs[len(prefix):])):
        raise ValueError("train/validation runs must precede test runs")
    count = sum(run["frames"] for run in prefix)
    expected = {run["run_id"]: run["split"] for run in prefix}
    selected = {"train": defaultdict(list), "validation": defaultdict(list)}
    with (path / manifest["feature_file"]).open(encoding="utf-8") as features, \
         (path / manifest["private_label_file"]).open(encoding="utf-8") as labels:
        for _ in range(count):
            frame_line, label_line = features.readline(), labels.readline()
            if not frame_line or not label_line:
                raise ValueError("train/validation rows are incomplete")
            frame, label = json.loads(frame_line), json.loads(label_line)
            run_id = frame["run_id"]
            if ((run_id, frame["sequence"]) != (label["run_id"], label["sequence"])
                    or frame["split"] != expected.get(run_id)):
                raise ValueError("train/validation rows differ from manifest")
            selected[frame["split"]][run_id].append((frame, label))
    for run in prefix:
        if len(selected[run["split"]][run["run_id"]]) != run["frames"]:
            raise ValueError("train/validation run frame count differs")
    return config, selected


def review(path):
    config, splits = load_train_validation(path)
    specs, mean_stats = fit_normal(splits["train"], config)
    robust_stats = fit_robust(splits["train"], config)
    validation = splits["validation"]
    predictors = {
        "ewma": (EWMA_THRESHOLDS, lambda t: predict_ewma(validation, specs, mean_stats, t)),
        "robust_z": (ROBUST_THRESHOLDS, lambda t: predict_robust(validation, specs, robust_stats, t)),
        "cusum": (CUSUM_THRESHOLDS, lambda t: predict_cusum(validation, specs, robust_stats, t)),
        "sustained_robust": ((3, 4, 5, 6, 7, 8), lambda t: predict_sustained_robust(
            validation, specs, robust_stats, t)),
        "consensus_robust": ((1.5, 2, 2.5, 3, 4, 5), lambda t: predict_consensus_robust(
            validation, specs, robust_stats, t)),
    }
    summaries = {"existing_symptom_rule": _summary(None, score(validation, predict_rule(validation, config)))}
    for name, (thresholds, predictor) in predictors.items():
        threshold, metrics = max(((threshold, score(validation, predictor(threshold)))
                                  for threshold in thresholds),
                                 key=lambda pair: (selection_key(pair[1]), pair[0]))
        summaries[name] = _summary(threshold, metrics)
    baseline_names = ("existing_symptom_rule", "ewma", "robust_z", "cusum")
    best = max(baseline_names, key=lambda name: summaries[name]["selection_key"])
    baseline_utility = summaries[best]["utility"]
    candidates = {name: {**summaries[name],
                         "delta_utility_vs_best_baseline": summaries[name]["utility"] - baseline_utility,
                         "beats_best_baseline": summaries[name]["selection_key"] > summaries[best]["selection_key"]}
                  for name in ("sustained_robust", "consensus_robust")}
    return {"dataset": str(path), "selection_split": "validation", "test_rows_read": 0,
            "normal_training_split": "train", "best_existing_baseline": best,
            "baselines": {name: summaries[name] for name in baseline_names},
            "candidates": candidates,
            "limits": "Validation-only research comparison on synthetic pattern faults. No independent or test rows were read. Repeated candidate search can overfit validation; no real-equipment performance claim."}


def _summary(threshold, metrics):
    key = selection_key(metrics)
    return {"threshold": threshold, "utility": key[0], "selection_key": list(key),
            "injected_events": metrics["injected_events"],
            "detected_events": metrics["detected_events"],
            "injected_event_f1": metrics["injected_event_f1"],
            "wrong_alert_time_fraction": metrics["wrong_alert_time_fraction"],
            "false_alert_starts": metrics["false_alerts"],
            "p95_onset_delay_seconds": metrics["p95_onset_delay_seconds"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    payload = json.dumps(review(args.dataset), ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
