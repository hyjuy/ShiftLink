"""Current-acquisition D16 contexts and a preregistered conditional D17 candidate."""
import argparse
import hashlib
import json
import platform
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import sklearn
from sklearn.ensemble import IsolationForest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_mes_fault_models import fit_normal, predict_ewma, score, valid_values
from scripts.mes_diagnostic_contract import classify_alarms, predict_signed_ewma
from scripts.mes_forest_models import SEED, build_features, predict_models, threshold_predictions
from scripts.mes_forest_comparison import check_run_manifest
from scripts.mes_model_benchmark import fit_robust, predict_robust
from scripts.mes_ewma_release_review import paired_events, safety_failures
from scripts.mes_location_replay import replay_validation
from scripts.mes_validation_candidate_review import load_train_validation
from scripts.mes_training_source import prefix_hashes


def fit_baselines(runs, config):
    specs, stats = fit_normal(runs, config)
    normal = [valid_values(frame, specs) for rows in runs.values() for frame, label in rows
              if not label["faults"] and frame.get("line_mode") == "running"]
    masks = {eq.equipment_id: [key for key in sorted(specs) if key[0] == eq.equipment_id
        and key in stats and sum(key in values for values in normal)/len(normal) >= .95]
        for eq in config.equipment if eq.active}
    features, coverage = build_features(runs, specs, stats, masks)
    models, diagnostic = {}, {}
    for eq, item in features.items():
        x = item["X"][item["healthy_windows"]]
        if not masks[eq] or len(x) < 100 or not np.isfinite(x).all():
            raise ValueError(f"{eq}: insufficient or invalid normal IF training windows")
        estimator = IsolationForest(n_estimators=200, max_samples=min(256, len(x)),
            contamination="auto", max_features=1.0, bootstrap=False, random_state=SEED, n_jobs=1)
        models[eq] = estimator.fit(x)
        diagnostic[eq] = {"selected_channels": [key[1] for key in masks[eq]],
            "healthy_windows": len(x), "dimensions": x.shape[1], "coverage": coverage[eq]}
    return {"specs": specs, "stats": stats, "masks": masks,
            "models": {"isolation_forest": models}}, fit_robust(runs, config), diagnostic


def pair_audit(full, weak):
    if full.keys() != weak.keys():
        raise ValueError("paired run IDs differ")
    checked, prefault, differences = 0, 0, 0
    for run_id, rows in full.items():
        if len(rows) != len(weak[run_id]):
            raise ValueError("paired row counts differ")
        seen = False
        for (frame, label), (other, other_label) in zip(rows, weak[run_id]):
            if ((frame["sequence"], frame["simulated_at"], frame["line_mode"], label) !=
                    (other["sequence"], other["simulated_at"], other["line_mode"], other_label)):
                raise ValueError("paired time/mode/fault schedule differs")
            different = frame["measurements"] != other["measurements"]
            if not seen and not label["faults"]:
                if different:
                    raise ValueError("paired prefault measurements differ")
                prefault += 1
            seen |= bool(label["faults"])
            checked += 1
            differences += int(not label["faults"] and different)
    return {"frames_checked": checked, "prefault_equal_frames": prefault,
            "label_free_measurement_differences": differences}


def review_signed(runs, baseline, candidate, baseline_records):
    if baseline.keys() != candidate.keys() or any(not candidate[k] <= baseline[k] for k in baseline):
        raise AssertionError("signed EWMA is not a framewise subset of absolute EWMA")
    before, after = score(runs, baseline), score(runs, candidate)
    failures = safety_failures(before, after)
    events = paired_events(runs, baseline, candidate, before, after)
    if events["lost"]:
        failures.append("individual event lost")
    delayed = [v for v in events["changed"] if v["baseline_delay_seconds"] is not None
        and v["candidate_delay_seconds"] is not None
        and v["candidate_delay_seconds"] > v["baseline_delay_seconds"]]
    if delayed:
        failures.append("individual event delayed")
    removed = [row for row in baseline_records
        if row["equipment_id"] not in candidate[row["run_id"], row["sequence"]]]
    response_lost = sum(row["seconds"] for row in removed if row["changed"])
    if response_lost:
        failures.append("twin response coverage lost")
    if not (after["detected_events"] > before["detected_events"] or
            after["wrong_alert_equipment_seconds"] < before["wrong_alert_equipment_seconds"]):
        failures.append("no strict improvement")
    retained_context = Counter()
    for row in baseline_records:
        if row["equipment_id"] in candidate[row["run_id"], row["sequence"]]:
            retained_context[row["context"]] += row["seconds"]
    return {"metrics": after, "failures": failures, "paired_events": events,
        "delayed_existing_events": delayed, "response_coverage_lost_equipment_seconds": response_lost,
        "removed_alarm_equipment_seconds": sum(r["seconds"] for r in removed),
        "retained_context_equipment_seconds": dict(retained_context)}


def _manifest(path):
    value = json.loads((Path(path)/"manifest.json").read_text(encoding="utf-8"))
    check_run_manifest(value)
    return value


def _audit(splits, specs):
    expected = {(eq, signal, spec.unit) for (eq, signal), spec in specs.items()}
    fresh, quality, frames = Counter(), Counter(), 0
    for runs in splits.values():
        for rows in runs.values():
            for frame, label in rows:
                positions = [(m["equipment_id"], m["signal"], m["unit"]) for m in frame["measurements"]]
                if len(positions) != 69 or set(positions) != expected:
                    raise ValueError("current 69-position frame contract differs")
                fresh[len(valid_values(frame, specs))] += 1
                quality.update(m["quality"] for m in frame["measurements"])
                frames += 1
    return {"frames_checked": frames, "fresh_valid_positions_per_frame": dict(fresh), "quality": dict(quality)}


def _pack(alerts):
    output = defaultdict(list)
    for (run, seq), equipment in alerts.items():
        output[run].append([seq, sorted(equipment)])
    return dict(output)


def evaluate(full_path, weak_path):
    started = time.perf_counter()
    manifests = {name: _manifest(path) for name, path in (("full", full_path), ("weak", weak_path))}
    for name, scale in (("full", 1), ("weak", .2)):
        manifest = manifests[name]
        if (manifest["generator_version"] != 7 or manifest["profile"] != "independent"
                or manifest["response_scale"] != scale):
            raise ValueError("expected current independent v7 full/weak sources")
    if manifests["full"]["runs"] != manifests["weak"]["runs"]:
        raise ValueError("paired manifest runs differ")
    config, full = load_train_validation(full_path, profile="independent")
    other, weak = load_train_validation(weak_path, profile="independent")
    if config.config_id != other.config_id:
        raise ValueError("configuration differs")
    pairing = pair_audit(full["validation"], weak["validation"])
    verified = {}
    for name, path, runs in (("full", full_path, full["validation"]),
                              ("weak", weak_path, weak["validation"])):
        print(f"{name}: verify factual and no-fault replay before fitting", flush=True)
        replay = replay_validation(path, config, runs)
        verified[name] = {"no_faults": replay["no_faults"], "verification": replay["verification"]}
        del replay
    training_started = time.perf_counter()
    bundle, robust_stats, training = fit_baselines(full["train"], config)
    fit_seconds = time.perf_counter()-training_started
    specs, stats = bundle["specs"], bundle["stats"]
    acquisition = {name: _audit(data, specs) for name, data in (("full", full), ("weak", weak))}
    arms, candidate_alerts, baseline_alerts, records_by_arm = {}, {}, {}, {}
    for name, path, runs in (("full", full_path, full["validation"]),
                              ("weak", weak_path, weak["validation"])):
        twins = verified.pop(name)
        predictions = {"ewma": predict_ewma(runs, specs, stats, 3),
                       "robust_z": predict_robust(runs, specs, robust_stats, 6)}
        forest, coverage, timing = predict_models(runs, bundle)
        forest_alerts, _ = threshold_predictions(forest, .65)
        predictions["isolation_forest"] = forest_alerts["isolation_forest"]
        signed = predict_signed_ewma(runs, specs, stats, 3)
        if any(not signed[k] <= predictions["ewma"][k] for k in signed):
            raise AssertionError("signed-subset invariant failed")
        models = {}
        for model, alerts in predictions.items():
            strict = score(runs, alerts)
            context, records = classify_alarms(runs, alerts, twins["no_faults"], specs, stats)
            assert context["strict_wrong_equipment_seconds"] == strict["wrong_alert_equipment_seconds"]
            assert context["strict_wrong_union_seconds"] == strict["wrong_alert_seconds"]
            models[model] = {"strict_source": strict, "diagnostic_context": context}
            if model == "ewma":
                records_by_arm[name] = records
        baseline_alerts[name], candidate_alerts[name] = predictions["ewma"], signed
        dependent = [r for r in records_by_arm[name]
                     if not r["source_positive"] and r["equipment_id"] not in signed[r["run_id"], r["sequence"]]]
        dependent_seconds = sum(r["seconds"] for r in dependent)
        wrong_seconds = models["ewma"]["strict_source"]["wrong_alert_equipment_seconds"]
        arms[name] = {"models": models, "replay_verification": twins["verification"],
            "forest_coverage": coverage, "forest_timings": timing,
            "rectification_dependent_wrong_equipment_seconds": dependent_seconds,
            "rectification_dependent_wrong_fraction": dependent_seconds/wrong_seconds if wrong_seconds else 0,
            "ewma_context_records": records_by_arm[name],
            "alerts": {model: _pack(alerts) for model, alerts in predictions.items()},
            "signed_diagnostic_alerts": _pack(signed)}
        del twins
    eligible = any(arm["rectification_dependent_wrong_fraction"] >= .1 for arm in arms.values())
    candidate = {"selected_for_review": eligible, "decision": "not_selected", "arms": {}}
    if eligible:
        for name, runs in (("full", full["validation"]), ("weak", weak["validation"])):
            candidate["arms"][name] = review_signed(runs, baseline_alerts[name], candidate_alerts[name], records_by_arm[name])
        candidate["decision"] = ("hold" if any(v["failures"] for v in candidate["arms"].values())
                                 else "eligible_for_fresh_confirmation")
    provenance = json.loads((ROOT/"provenance.json").read_text(encoding="utf-8"))
    if any(hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != value
           for name, value in provenance["files"].items()):
        raise ValueError("frozen runtime source integrity changed")
    return {"experiment": "D16", "config_id": config.config_id,
        "datasets": {"full": str(full_path), "weak": str(weak_path)}, "acquisition_audit": acquisition,
        "pairing": pairing, "training": training, "fit_seconds": fit_seconds,
        "arms": arms, "conditional_D17": candidate, "strict_scorer_changed": False,
        "test_rows_read": 0, "source_test_rows_generated": sum(m["splits"]["test"]["frames"] for m in manifests.values()),
        "model_input": "causal valid measurement history; IF uses current and trailing eight-frame features; labels and twins used for fit-normal selection/evaluation, never prediction",
        "input_prefix_sha256": {name: prefix_hashes(path, manifests[name]) for name, path in (("full", full_path), ("weak", weak_path))},
        "runtime_provenance_sha256": hashlib.sha256((ROOT/"provenance.json").read_bytes()).hexdigest(),
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "sklearn": sklearn.__version__},
        "total_seconds": time.perf_counter()-started,
        "limits": "Synthetic replay response is exact numeric difference, not practical importance or single-fault physical causality. Contexts never excuse strict source mistakes. Current synthetic manual samples refresh each frame. Training normal selection uses private labels; modes remain running. Not field or deployment validation."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("full", "weak", "out"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("preserve earlier results; output exists")
    result = evaluate(args.full, args.weak)
    with args.out.open("x", encoding="utf-8") as target:
        json.dump(result, target, ensure_ascii=False, indent=2, allow_nan=False)
        target.write("\n")
    print(json.dumps({"D17": result["conditional_D17"]["decision"], "seconds": result["total_seconds"], "test_rows_read": 0}))


if __name__ == "__main__":
    main()
