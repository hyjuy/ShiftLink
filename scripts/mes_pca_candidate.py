"""Preregistered equipment PCA detector; validation only, never reads test rows."""
import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_mes_fault_models import (fit_normal, predict_ewma, predict_rule,
                                               score, selection_key, valid_values)
from scripts.mes_validation_candidate_review import load_train_validation
from scripts.mes_response_scale_ablation import predict_normal_band

THRESHOLDS = (1, 2, 4, 8, 16)
INACTIVE = {"paused", "stopped", "recovering", "quality_hold"}
EIGEN_FLOOR = 1e-6
SCORE_FLOOR = 1e-6


def _scores(x, model):
    projected = x @ model["components"]
    t2 = np.sum(projected ** 2 / model["eigenvalues"])
    q = np.sum((x - projected @ model["components"].T) ** 2)
    return max(t2 / model["t2_quantile"], q / model["q_quantile"])


def fit_pca(train_runs, specs, stats):
    """Use only fault-free active train frames and each equipment's valid channels."""
    channels = defaultdict(list)
    for key in sorted(specs):
        channels[key[0]].append(key)
    samples = defaultdict(list)
    for rows in train_runs.values():
        for frame, label in rows:
            if label["faults"] or frame.get("line_mode") in INACTIVE:
                continue
            values = valid_values(frame, specs)
            for equipment in channels:
                samples[equipment].append(values)
    models, diagnostics = {}, {}
    for equipment, keys in sorted(channels.items()):
        frames = samples[equipment]
        selected = [key for key in keys if key in stats and frames and
                    sum(key in values for values in frames) / len(frames) >= .95]
        complete = [values for values in frames if all(key in values for key in selected)]
        diagnostic = {"healthy_active_frames": len(frames), "configured_channels": len(keys),
                      "selected_channels": [key[1] for key in selected],
                      "excluded_channels": [key[1] for key in keys if key not in selected],
                      "complete_rows": len(complete), "eigenvalue_floor": EIGEN_FLOOR,
                      "score_floor": SCORE_FLOOR}
        diagnostics[equipment] = diagnostic
        if len(selected) < 2 or len(complete) < 100:
            diagnostic["skip_reason"] = "fewer than 2 channels or 100 complete rows"
            continue
        x = np.array([[(values[key] - stats[key][0]) / stats[key][1] for key in selected]
                      for values in complete], dtype=float)
        center = x.mean(axis=0)
        x -= center
        _, singular, vectors = np.linalg.svd(x, full_matrices=False)
        eigenvalues = singular ** 2 / (len(x) - 1)
        numerical_rank = int(np.count_nonzero(eigenvalues > EIGEN_FLOOR))
        rank = min(int(np.searchsorted(np.cumsum(eigenvalues) / eigenvalues.sum(), .95) + 1)
                   if eigenvalues.sum() > 0 else 0, len(selected) - 1, numerical_rank)
        diagnostic.update({"eigenvalues": eigenvalues.tolist(), "numerical_rank": numerical_rank,
                           "retained_rank": rank})
        if rank == 0:
            diagnostic["skip_reason"] = "zero usable rank"
            continue
        model = {"keys": selected, "stats": [stats[key] for key in selected], "center": center,
                 "components": vectors[:rank].T, "eigenvalues": eigenvalues[:rank]}
        projected = x @ model["components"]
        t2 = np.sum(projected ** 2 / model["eigenvalues"], axis=1)
        q = np.sum((x - projected @ model["components"].T) ** 2, axis=1)
        raw_t2 = float(np.quantile(t2, .995, method="linear"))
        raw_q = float(np.quantile(q, .995, method="linear"))
        model["t2_quantile"] = max(raw_t2, SCORE_FLOOR)
        model["q_quantile"] = max(raw_q, SCORE_FLOOR)
        diagnostic.update({"t2_quantile": model["t2_quantile"],
                           "q_quantile": model["q_quantile"],
                           "raw_t2_quantile": raw_t2, "raw_q_quantile": raw_q,
                           "t2_floor_applied": raw_t2 < SCORE_FLOOR,
                           "q_floor_applied": raw_q < SCORE_FLOOR})
        models[equipment] = model
    return models, diagnostics


def predict_pca(runs, specs, models, threshold):
    alerts = {}
    counts = {eq: {"eligible_frames": 0, "abstained_frames": 0, "inactive_frames": 0}
              for eq in models}
    for count in counts.values():
        count["nonfinite_score_frames"] = 0
    for run_id, rows in runs.items():
        for frame, _ in rows:
            key = (run_id, frame["sequence"])
            current = set()
            if frame.get("line_mode") in INACTIVE:
                for count in counts.values():
                    count["inactive_frames"] += 1
            else:
                values = valid_values(frame, specs)
                for eq, model in models.items():
                    if any(channel not in values for channel in model["keys"]):
                        counts[eq]["abstained_frames"] += 1
                        continue
                    counts[eq]["eligible_frames"] += 1
                    x = np.array([(values[channel] - mean) / scale
                                  for channel, (mean, scale) in zip(model["keys"], model["stats"])])
                    value = _scores(x - model["center"], model)
                    if not math.isfinite(value):
                        counts[eq]["nonfinite_score_frames"] += 1
                    elif value >= threshold:
                        current.add(eq)
            alerts[key] = current
    return alerts, counts


def gate_failures(baseline, candidate):
    failures = []
    if candidate["detected_events"] < baseline["detected_events"]:
        failures.append("detected_events")
    for name in ("false_alerts", "wrong_alert_seconds", "wrong_alert_equipment_seconds",
                 "p95_onset_delay_seconds"):
        before, after = baseline[name], candidate[name]
        if before is not None and (after is None or after > before):
            failures.append(name)
    for group in ("by_equipment", "by_mechanism"):
        for key in baseline[group].keys() | candidate[group].keys():
            before = baseline[group].get(key, {})
            after = candidate[group].get(key, {})
            for name in (("missed_observable_events", "p95_onset_delay_seconds",
                          "wrong_alert_equipment_seconds") if group == "by_equipment"
                         else ("missed_observable_events", "p95_onset_delay_seconds")):
                old = before.get(name, 0 if name != "p95_onset_delay_seconds" else None)
                new = after.get(name, 0 if name != "p95_onset_delay_seconds" else None)
                if old is not None and (new is None or new > old):
                    failures.append(f"{group}.{key}.{name}")
    return failures


def _manifest(path):
    return json.loads((Path(path) / "manifest.json").read_text(encoding="utf-8"))


def check_pairing(full, weak):
    def signature(runs):
        schedule = {(run_id, frame["sequence"]): (frame["simulated_at"],
                    frame.get("line_mode"), label["faults"])
                    for run_id, rows in runs.items() for frame, label in rows}
        normal = {(run_id, frame["sequence"]): frame["measurements"]
                  for run_id, rows in runs.items() for frame, label in rows if not label["faults"]}
        return schedule, normal
    full_schedule, full_normal = signature(full)
    weak_schedule, weak_normal = signature(weak)
    if full_schedule != weak_schedule:
        raise ValueError("full and weak arms are not paired on validation run, time, mode, and labels")
    if full_normal != weak_normal:
        raise ValueError("full and weak arms differ on fault-free validation measurements")


def evaluate(pattern_path, full_path, weak_path):
    started = time.perf_counter()
    config, pattern = load_train_validation(pattern_path)
    specs, stats = fit_normal(pattern["train"], config)
    fit_started = time.perf_counter()
    models, diagnostics = fit_pca(pattern["train"], specs, stats)
    fit_seconds = time.perf_counter() - fit_started
    validation = pattern["validation"]
    candidates = []
    for threshold in THRESHOLDS:
        alerts, _ = predict_pca(validation, specs, models, threshold)
        candidates.append((threshold, score(validation, alerts)))
    threshold, pattern_metrics = max(candidates, key=lambda pair: (selection_key(pair[1]), pair[0]))
    arms, paired = {}, None
    for name, path, scale in (("full", full_path, 1.0), ("weak", weak_path, .2)):
        manifest = _manifest(path)
        if manifest.get("generator_version") != 7 or manifest.get("response_scale") != scale:
            raise ValueError(f"{name}: expected v7 response scale {scale}")
        challenge_config, splits = load_train_validation(path, profile="independent")
        if challenge_config.config_id != config.config_id:
            raise ValueError("training and validation configuration differs")
        validation = splits["validation"]
        if set(validation) & (set(pattern["train"]) | set(pattern["validation"])):
            raise ValueError("validation run overlaps pattern training or validation")
        if paired is not None:
            check_pairing(paired, validation)
        paired = validation
        tick = time.perf_counter()
        candidate_alerts, coverage = predict_pca(validation, specs, models, threshold)
        candidate_seconds = time.perf_counter() - tick
        active_frames = sum(frame.get("line_mode") not in INACTIVE
                            for rows in validation.values() for frame, _ in rows)
        inactive_frames = sum(len(rows) for rows in validation.values()) - active_frames
        for eq in diagnostics.keys() - models.keys():
            coverage[eq] = {"eligible_frames": 0, "abstained_frames": active_frames,
                            "inactive_frames": inactive_frames, "nonfinite_score_frames": 0,
                            "skipped_model": True}
        tick = time.perf_counter()
        baseline_alerts = predict_ewma(validation, specs, stats, 3.0)
        baseline_seconds = time.perf_counter() - tick
        baseline = score(validation, baseline_alerts)
        candidate = score(validation, candidate_alerts)
        tick = time.perf_counter()
        rule_alerts = predict_rule(validation, config)
        rule_seconds = time.perf_counter() - tick
        rule = score(validation, rule_alerts)
        tick = time.perf_counter()
        band_alerts = predict_normal_band(validation, specs)
        band_seconds = time.perf_counter() - tick
        band = score(validation, band_alerts)
        arms[name] = {"candidate": candidate, "ewma_alpha_0_4_threshold_3": baseline,
                      "existing_symptom_rule": rule, "normal_band_rule": band,
                      "coverage": coverage,
                      "candidate_prediction_seconds": candidate_seconds,
                      "ewma_prediction_seconds": baseline_seconds,
                      "rule_prediction_seconds": rule_seconds,
                      "normal_band_prediction_seconds": band_seconds,
                      "gate_failures_vs_ewma": gate_failures(baseline, candidate)}
    failures = [f"{name}: {failure}" for name, arm in arms.items()
                for failure in arm["gate_failures_vs_ewma"]]
    if not any(arm["candidate"]["detected_events"] > arm["ewma_alpha_0_4_threshold_3"]["detected_events"]
               or arm["candidate"]["wrong_alert_equipment_seconds"] < arm["ewma_alpha_0_4_threshold_3"]["wrong_alert_equipment_seconds"]
               for arm in arms.values()):
        failures.append("no improvement in either arm")
    if any(count["nonfinite_score_frames"] for arm in arms.values() for count in arm["coverage"].values()):
        failures.append("nonfinite PCA score")
    return {"candidate": "per-equipment PCA T2/Q", "threshold_grid": THRESHOLDS,
            "selected_threshold": threshold, "pattern_validation": pattern_metrics,
            "pattern_validation_candidates": [{"threshold": t, "metrics": m} for t, m in candidates],
            "diagnostics": diagnostics, "arms": arms, "gate_failures": failures,
            "decision": "eligible_for_one_fresh_test" if not failures else "hold",
            "normal_training_split": "pattern train", "threshold_selection_split": "pattern validation",
            "comparison_split": "paired v7 independent validation", "test_rows_read": 0,
            "fit_and_validation_seconds": time.perf_counter() - started,
            "fit_seconds": fit_seconds,
            "numpy_version": np.__version__,
            "limits": "Synthetic generator-distribution validation only; response_scale=0.2 is arbitrary stress. Earlier v6 weak result invalid. No real-equipment claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pattern", type=Path, required=True)
    parser.add_argument("--full", type=Path, required=True)
    parser.add_argument("--weak", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.pattern, args.full, args.weak)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(result["decision"], result["gate_failures"])


if __name__ == "__main__":
    main()
