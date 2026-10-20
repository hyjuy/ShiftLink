"""Fixed-IF training-source ablation on fresh synthetic validation, no test reads."""
import argparse
import hashlib
import json
import platform
import sys
import time
from collections import Counter, deque
from pathlib import Path

import numpy as np
import sklearn
from sklearn.ensemble import IsolationForest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_mes_fault_models import fit_normal, predict_ewma, score, valid_values
from scripts.mes_forest_comparison import check_run_manifest
from scripts.mes_forest_models import (SEED, WINDOW, build_features, predict_models,
                                       threshold_predictions)
from scripts.mes_model_benchmark import fit_robust, predict_robust
from scripts.mes_pca_candidate import check_pairing, gate_failures
from scripts.mes_location_replay import replay_validation
from scripts.mes_validation_candidate_review import load_train_validation

SALT = "mes-training-source-20261021"
IF_THRESHOLD = .65


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def check_sources(reference, aligned):
    for manifest in (reference, aligned):
        check_run_manifest(manifest)
    if reference["profile"] != "pattern":
        raise ValueError("expected pattern reference")
    if (aligned["profile"] != "independent" or aligned["generator_version"] != 7
            or aligned["response_scale"] != 1):
        raise ValueError("expected full v7 independent aligned source")
    for field in ("run_id", "seed"):
        if {r[field] for r in reference["runs"]} & {r[field] for r in aligned["runs"]}:
            raise ValueError(f"source {field} overlap")


def matched_samples(reference, aligned):
    if not reference or reference.keys() != aligned.keys():
        raise ValueError("equipment model coverage differs")
    output = {"reference": {}, "aligned": {}}
    diagnostics = {}
    for eq in sorted(reference):
        entries = {"reference": reference[eq], "aligned": aligned[eq]}
        if (reference[eq]["X"].ndim != 2 or aligned[eq]["X"].ndim != 2
                or reference[eq]["X"].shape[1] == 0
                or reference[eq]["X"].shape[1] != aligned[eq]["X"].shape[1]):
            raise ValueError(f"{eq}: feature dimension differs or is empty")
        if any(not np.isfinite(entry["X"]).all() for entry in entries.values()):
            raise ValueError(f"{eq}: nonfinite features")
        eligible = {name: np.flatnonzero(entry["healthy_windows"]).tolist()
                    for name, entry in entries.items()}
        count = min(map(len, eligible.values()))
        if count < 100:
            raise ValueError(f"{eq}: fewer than 100 matched healthy windows")
        diagnostics[eq] = {}
        for name, entry in entries.items():
            available = set(eligible[name])
            order = sorted(eligible[name], key=lambda i: digest([SALT, eq, entry["keys"][i]]))
            chosen = sorted(order[:count])
            keys = [list(entry["keys"][i]) for i in chosen]
            output[name][eq] = entry["X"][chosen]
            diagnostics[eq][name] = {"available_healthy_windows": len(eligible[name]),
                "matched_windows": count, "selected_keys": keys, "selected_keys_sha256": digest(keys),
                "selected_windows_by_run": dict(Counter(key[0] for key in keys)),
                "available_healthy_spans": sum(i == 0 or entry["keys"][i][0] != entry["keys"][i-1][0]
                    or entry["keys"][i][1] != entry["keys"][i-1][1] + 1
                    or i-1 not in available for i in eligible[name])}
    return output, diagnostics


def normal_background(runs, alerts, features):
    eligible = {eq: set(entry["keys"]) for eq, entry in features.items()}
    healthy, prefault = [], []
    counts, before_counts, run_counts = Counter(), Counter(), Counter()
    alert_frames, before_frames = 0, 0
    for run_id, rows in runs.items():
        window, seen_fault = deque(maxlen=WINDOW), False
        for frame, label in rows:
            key = run_id, frame["sequence"]
            window.append(not label["faults"])
            seen_fault = seen_fault or bool(label["faults"])
            if len(window) != WINDOW or not all(window):
                continue
            current = alerts.get(key, set())
            for eq in eligible:
                if key not in eligible[eq]:
                    continue
                healthy.append([*key, eq])
                if eq in current:
                    counts[eq] += 1
                    run_counts[run_id] += 1
                    alert_frames += 1
                if not seen_fault:
                    prefault.append([*key, eq])
                    if eq in current:
                        before_counts[eq] += 1
                        before_frames += 1
    return {"eligible_healthy_equipment_windows": len(healthy),
            "healthy_window_keys_sha256": digest(sorted(healthy)),
            "healthy_window_alert_equipment_frames": alert_frames,
            "prefault_eligible_equipment_windows": len(prefault),
            "prefault_window_keys_sha256": digest(sorted(prefault)),
            "prefault_alert_equipment_frames": before_frames,
            "by_equipment": dict(counts), "prefault_by_equipment": dict(before_counts),
            "alert_equipment_frames_by_run": dict(run_counts)}


def normal_relations(data, masks):
    result = {}
    for eq, keys in masks.items():
        names = [key[1] for key in keys]
        pair = next(((speed, current) for speed, current in (
            ("rt_speed", "rt_motor_current"), ("cv_speed", "cv_motor_current"),
            ("gr_rpm", "gr_current")) if speed in names and current in names), None)
        if pair is None:
            continue
        entry = data[eq]
        x = entry["X"][entry["healthy_windows"]]
        i, j = (names.index(name) for name in pair)
        correlation = (float(np.corrcoef(x[:, i], x[:, j])[0, 1])
                       if len(x) > 1 and np.std(x[:, i]) > 0 and np.std(x[:, j]) > 0 else None)
        result[eq] = {"signals": list(pair), "healthy_windows": len(x),
                      "current_speed_current_pearson_r": correlation,
                      "speed_std8_median": float(np.median(x[:, 2 * len(keys) + i])) if len(x) else None}
    return result


def _manifest(path):
    return json.loads((Path(path) / "manifest.json").read_text(encoding="utf-8"))


def prefix_hashes(path, manifest):
    count = sum(run["frames"] for run in manifest["runs"] if run["split"] != "test")
    hashes = {}
    for field in ("feature_file", "private_label_file"):
        value = hashlib.sha256()
        with (Path(path) / manifest[field]).open("rb") as source:
            for _ in range(count):
                value.update(source.readline())
        hashes[field] = value.hexdigest()
    return {"rows_per_file": count, **hashes}


def evaluate(pattern_path, full_path, weak_path, reference_path):
    started = time.perf_counter()
    pattern_manifest, full_manifest, weak_manifest = map(_manifest, (pattern_path, full_path, weak_path))
    check_sources(pattern_manifest, full_manifest)
    check_run_manifest(weak_manifest)
    if (weak_manifest["profile"] != "independent" or weak_manifest["generator_version"] != 7
            or weak_manifest["response_scale"] != .2
            or full_manifest["runs"] != weak_manifest["runs"]):
        raise ValueError("expected paired full/weak v7 runs")
    config, pattern = load_train_validation(pattern_path)
    other, full = load_train_validation(full_path, profile="independent")
    weak_config, weak = load_train_validation(weak_path, profile="independent")
    if config.config_id != other.config_id or config.config_id != weak_config.config_id:
        raise ValueError("configuration differs")
    check_pairing(full["validation"], weak["validation"])
    replay_checks = {}
    for name, path, runs in (("full", full_path, full["validation"]),
                              ("weak", weak_path, weak["validation"])):
        print(f"Verifying {name} factual replay before fitting", flush=True)
        replay_checks[name] = replay_validation(path, config, runs)["verification"]
    specs, stats = fit_normal(pattern["train"], config)
    reference = json.loads(Path(reference_path).read_text(encoding="utf-8"))
    masks = {eq: [(eq, signal) for signal in item["selected_channels"]]
             for eq, item in reference["diagnostics"].items()}
    normal_values = [valid_values(frame, specs) for rows in pattern["train"].values()
                     for frame, label in rows if not label["faults"] and frame.get("line_mode") == "running"]
    expected = {eq.equipment_id: {key for key in specs if key[0] == eq.equipment_id and key in stats
                and sum(key in values for values in normal_values) / len(normal_values) >= .95}
                for eq in config.equipment if eq.active}
    if (masks.keys() != expected.keys() or any(not masks[eq] or len(masks[eq]) != len(expected[eq])
                                             or set(masks[eq]) != expected[eq] for eq in expected)):
        raise ValueError("reference mask differs from original train-fitted coverage contract")
    source_data, source_coverage = {}, {}
    for name, runs in (("reference", pattern["train"]), ("aligned", full["train"])):
        source_data[name], source_coverage[name] = build_features(runs, specs, stats, masks)
    samples, training = matched_samples(source_data["reference"], source_data["aligned"])
    bundles, fit_seconds = {}, {}
    for name in samples:
        tick = time.perf_counter()
        estimators = {}
        for eq, x in samples[name].items():
            estimator = IsolationForest(n_estimators=200, max_samples=min(256, len(x)),
                max_features=1.0, bootstrap=False, contamination="auto", random_state=SEED, n_jobs=1)
            estimators[eq] = estimator.fit(x)
        bundles[name] = {"specs": specs, "stats": stats, "masks": masks,
                         "models": {"isolation_forest": estimators}}
        fit_seconds[name] = time.perf_counter() - tick
    arms, backgrounds = {}, {}
    for arm_name, path, runs in (("full", full_path, full["validation"]),
                                  ("weak", weak_path, weak["validation"])):
        features, coverage = build_features(runs, specs, stats, masks)
        predictions = {}
        backgrounds[arm_name] = {}
        for name, bundle in bundles.items():
            scored, model_coverage, timings = predict_models(runs, bundle)
            alerts, _ = threshold_predictions(scored, IF_THRESHOLD)
            metric = score(runs, alerts["isolation_forest"])
            background = normal_background(runs, alerts["isolation_forest"], features)
            backgrounds[arm_name][name] = background
            predictions[name] = {"metrics": metric, "background": background,
                "coverage": model_coverage, "timings": timings}
        ewma = score(runs, predict_ewma(runs, specs, stats, 3))
        robust = score(runs, predict_robust(runs, specs, fit_robust(pattern["train"], config), 6))
        candidate = predictions["aligned"]["metrics"]
        failures = [f"matched_if:{f}" for f in gate_failures(predictions["reference"]["metrics"], candidate)]
        failures += [f"ewma:{f}" for f in gate_failures(ewma, candidate)]
        if any(c.get("isolation_forest_nonfinite_scores", 0)
               for c in predictions["aligned"]["coverage"].values()):
            failures.append("nonfinite model scores")
        if predictions["aligned"]["coverage"] != predictions["reference"]["coverage"]:
            failures.append("changed coverage")
        arms[arm_name] = {"frames": sum(map(len, runs.values())), "models": predictions,
            "ewma": ewma, "robust_z": robust, "gate_failures": failures,
            "normal_relations": normal_relations(features, masks),
            "replay_verification": replay_checks[arm_name]}
    paired_background = all(backgrounds["full"][name] == backgrounds["weak"][name] for name in bundles)
    if not paired_background:
        raise ValueError("full/weak healthy-window background differs")
    normal_before = backgrounds["full"]["reference"]["healthy_window_alert_equipment_frames"]
    normal_after = backgrounds["full"]["aligned"]["healthy_window_alert_equipment_frames"]
    hypothesis = ("supported_on_label_free_windows" if normal_after < normal_before else
                  "floor_effect" if normal_after == normal_before == 0 else "not_supported")
    failures = [f"{arm}:{failure}" for arm, result in arms.items() for failure in result["gate_failures"]]
    improved = any(result["models"]["aligned"]["metrics"]["detected_events"] >
                   result["models"]["reference"]["metrics"]["detected_events"] or
                   result["models"]["aligned"]["metrics"]["wrong_alert_equipment_seconds"] <
                   result["models"]["reference"]["metrics"]["wrong_alert_equipment_seconds"]
                   for result in arms.values())
    if not improved:
        failures.append("no strict-source improvement")
    code_files = ["scripts/mes_training_source.py", "scripts/mes_forest_models.py",
                  "scripts/build_mes_fault_dataset.py", "scripts/evaluate_mes_fault_models.py",
                  "shiftlink/mes/random_factory.py", "scripts/mes_validation_candidate_review.py"]
    return {"experiment": "D15", "datasets": {"pattern": str(pattern_path), "full": str(full_path),
            "weak": str(weak_path)}, "config_id": config.config_id,
            "preprocessing_refitted": False, "threshold": IF_THRESHOLD,
            "sampling_salt": SALT, "training": training, "training_coverage": source_coverage,
            "training_normal_relations": {name: normal_relations(data, masks) for name, data in source_data.items()},
            "arms": arms, "paired_background_identical": paired_background,
            "diagnostic_hypothesis": hypothesis, "gate_failures": failures,
            "decision": "hold" if failures else "eligible_for_separate_preregistered_confirmation",
            "test_rows_read": 0, "source_test_rows_generated": full_manifest["splits"]["test"]["frames"]
                + weak_manifest["splits"]["test"]["frames"], "final_test_evaluated": False,
            "fit_seconds": fit_seconds, "total_seconds": time.perf_counter() - started,
            "versions": {"python": platform.python_version(), "numpy": np.__version__, "sklearn": sklearn.__version__},
            "reference_sha256": hashlib.sha256(Path(reference_path).read_bytes()).hexdigest(),
            "preprocessing_sha256": digest({"stats": [[*key, *value] for key, value in sorted(stats.items())],
                                             "masks": masks}),
            "input_prefix_sha256": {name: prefix_hashes(path, manifest) for name, path, manifest in (
                ("pattern", pattern_path, pattern_manifest), ("full", full_path, full_manifest),
                ("weak", weak_path, weak_manifest))},
            "code_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in code_files},
            "catalog_sha256": hashlib.sha256((ROOT / "docs/data/reference/00_plant_and_relations.json").read_bytes()).hexdigest(),
            "manifest_sha256": {name: hashlib.sha256((Path(path) / "manifest.json").read_bytes()).hexdigest()
                for name, path in (("pattern", pattern_path), ("full", full_path), ("weak", weak_path))},
            "limits": "Synthetic-only fixed-pipeline source sensitivity. Overlapping windows are not independent samples. Healthy selection uses private injection labels; postfault state may remain. Full/weak normal background is paired evidence, not replication. No type/root diagnosis, final test, or deployment claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pattern", "full", "weak", "reference", "out"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output exists; preserve earlier experiment results")
    result = evaluate(args.pattern, args.full, args.weak, args.reference)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as target:
        json.dump(result, target, ensure_ascii=False, indent=2, allow_nan=False)
        target.write("\n")
    print(json.dumps({"decision": result["decision"], "hypothesis": result["diagnostic_hypothesis"],
                      "test_rows_read": 0, "seconds": result["total_seconds"]}))


if __name__ == "__main__":
    main()
