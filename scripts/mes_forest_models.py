"""Independent, per-equipment Isolation Forest and Random Forest MES candidates."""
import math
import time
from collections import defaultdict, deque
from datetime import datetime

import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier

from scripts.evaluate_mes_fault_models import fit_normal, valid_values

INACTIVE = {"paused", "stopped", "recovering", "quality_hold"}
WINDOW = 8
SEED = 20261020


def build_features(runs, specs, stats, masks):
    """Build causal, complete eight-frame windows independently per run/equipment."""
    data = {eq: {"X": [], "keys": [], "labels": [], "healthy_windows": []} for eq in masks}
    coverage = {eq: {"frames": 0, "eligible_windows": 0, "warmup_frames": 0,
                     "missing_frames": 0, "inactive_frames": 0, "gap_frames": 0}
                for eq in masks}
    for run_id, rows in runs.items():
        windows = {eq: deque(maxlen=WINDOW) for eq in masks}
        previous = None
        for frame, label in rows:
            stamp = datetime.fromisoformat(frame["simulated_at"])
            key = (run_id, frame["sequence"])
            consecutive = previous is None or (frame["sequence"] == previous[0] + 1
                                                and (stamp - previous[1]).total_seconds() == 1)
            previous = (frame["sequence"], stamp)
            inactive = frame.get("line_mode") in INACTIVE
            values = {} if inactive else valid_values(frame, specs)
            for eq, channels in masks.items():
                count = coverage[eq]
                count["frames"] += 1
                window = windows[eq]
                if not consecutive:
                    window.clear()
                    count["gap_frames"] += 1
                if inactive:
                    window.clear()
                    count["inactive_frames"] += 1
                    continue
                if any(channel not in values for channel in channels):
                    window.clear()
                    count["missing_frames"] += 1
                    continue
                vector = np.array([(values[channel] - stats[channel][0]) / stats[channel][1]
                                   for channel in channels], dtype=float)
                window.append((vector, not label["faults"]))
                if len(window) < WINDOW:
                    count["warmup_frames"] += 1
                    continue
                history = np.stack([value for value, _ in window])
                slope = np.sum((np.arange(WINDOW) - 3.5)[:, None] * history, axis=0) / 42
                feature = np.concatenate((history[-1], history.mean(axis=0),
                                          history.std(axis=0, ddof=0), slope))
                data[eq]["X"].append(feature)
                data[eq]["keys"].append(key)
                data[eq]["labels"].append(label)
                data[eq]["healthy_windows"].append(all(healthy for _, healthy in window))
                count["eligible_windows"] += 1
    for entry in data.values():
        entry["X"] = np.array(entry["X"], dtype=float) if entry["X"] else np.empty((0, 0))
        entry["healthy_windows"] = np.array(entry["healthy_windows"], dtype=bool)
    return data, coverage


def fit_models(train_runs, config):
    specs, stats = fit_normal(train_runs, config)
    configured = defaultdict(list)
    for key in sorted(specs):
        configured[key[0]].append(key)
    healthy = defaultdict(list)
    for rows in train_runs.values():
        for frame, label in rows:
            if label["faults"] or frame.get("line_mode") in INACTIVE:
                continue
            values = valid_values(frame, specs)
            for eq in configured:
                healthy[eq].append(values)
    masks, diagnostics = {}, {}
    for eq, channels in sorted(configured.items()):
        frames = healthy[eq]
        selected = [key for key in channels if key in stats and frames
                    and sum(key in values for values in frames) / len(frames) >= .95]
        masks[eq] = selected
        diagnostics[eq] = {"configured_channels": len(channels),
                           "healthy_active_frames": len(frames),
                           "selected_channels": [key[1] for key in selected],
                           "excluded_channels": [key[1] for key in channels if key not in selected],
                           "feature_dimensions": 4 * len(selected)}
    data, coverage = build_features(train_runs, specs, stats, masks)
    models = {"isolation_forest": {}, "random_forest": {}}
    for eq, entry in data.items():
        diag = diagnostics[eq]
        diag["training_coverage"] = coverage[eq]
        normal = entry["X"][entry["healthy_windows"]]
        diag["if_healthy_windows"] = len(normal)
        if len(normal) >= 100 and len(masks[eq]) >= 1:
            model = IsolationForest(n_estimators=200, max_samples=min(256, len(normal)),
                                    max_features=1.0, bootstrap=False, contamination="auto",
                                    random_state=SEED, n_jobs=1)
            fit_started = time.perf_counter()
            model.fit(normal)
            diag["if_fit_seconds"] = time.perf_counter() - fit_started
            diag["if_tree_nodes"] = sum(tree.tree_.node_count for tree in model.estimators_)
            models["isolation_forest"][eq] = model
        else:
            diag["if_skip_reason"] = "fewer than 100 healthy windows or no selected channel"
        targets, ambiguous = [], 0
        class_runs, class_episodes = defaultdict(set), defaultdict(set)
        for (run_id, _), label in zip(entry["keys"], entry["labels"]):
            local = [fault for fault in label["faults"]
                     if fault["equipment_id"] == eq and fault["intensity"] > 0]
            types = {fault.get("pattern_id", "unspecified") for fault in local}
            if len(types) > 1:
                targets.append(None)
                ambiguous += 1
                continue
            target = next(iter(types)) if types else "normal"
            targets.append(target)
            class_runs[target].add(run_id)
            for fault in local:
                class_episodes[target].add((run_id, fault["id"]))
        normal_start = previous_key = None
        for key, target in zip(entry["keys"], targets):
            if target == "normal":
                if previous_key is None or key[0] != previous_key[0] or key[1] != previous_key[1] + 1:
                    normal_start = key
                class_episodes["normal"].add(normal_start)
                previous_key = key
            else:
                previous_key = None
        usable = [i for i, target in enumerate(targets) if target is not None]
        y = [targets[i] for i in usable]
        diag.update({"rf_ambiguous_windows": ambiguous, "rf_training_windows": len(usable),
                     "rf_class_windows": {name: y.count(name) for name in sorted(set(y))},
                     "rf_class_runs": {name: len(class_runs[name]) for name in sorted(class_runs)},
                     "rf_class_episodes": {name: len(class_episodes[name])
                                           for name in sorted(class_episodes)}})
        if len(usable) >= 100 and "normal" in y and len(set(y)) >= 2:
            model = RandomForestClassifier(n_estimators=200, max_depth=12, min_samples_leaf=4,
                                           max_features="sqrt", class_weight="balanced_subsample",
                                           random_state=SEED, n_jobs=1)
            fit_started = time.perf_counter()
            model.fit(entry["X"][usable], y)
            diag["rf_fit_seconds"] = time.perf_counter() - fit_started
            diag["rf_tree_nodes"] = sum(tree.tree_.node_count for tree in model.estimators_)
            models["random_forest"][eq] = model
        else:
            diag["rf_skip_reason"] = "fewer than 100 usable windows or normal/fault class absent"
    return {"specs": specs, "stats": stats, "masks": masks,
            "models": models, "diagnostics": diagnostics}


def predict_models(runs, bundle):
    started = time.perf_counter()
    data, coverage = build_features(runs, bundle["specs"], bundle["stats"], bundle["masks"])
    timings = {"feature_seconds": time.perf_counter() - started}
    keys = [(run_id, frame["sequence"]) for run_id, rows in runs.items() for frame, _ in rows]
    scored = {name: {key: {} for key in keys} for name in bundle["models"]}
    for name, estimators in bundle["models"].items():
        started = time.perf_counter()
        for eq, estimator in estimators.items():
            entry = data[eq]
            if not len(entry["keys"]):
                continue
            if name == "isolation_forest":
                scores = -estimator.score_samples(entry["X"])
                types = [None] * len(scores)
            else:
                probabilities = estimator.predict_proba(entry["X"])
                classes = list(estimator.classes_)
                normal_index = classes.index("normal")
                nonnormal = [i for i, item in enumerate(classes) if item != "normal"]
                scores = 1 - probabilities[:, normal_index]
                types = [classes[max(nonnormal, key=lambda j: row[j])]
                         for row in probabilities]
            count = coverage[eq].setdefault(f"{name}_nonfinite_scores", 0)
            for key, value, kind in zip(entry["keys"], scores, types):
                if math.isfinite(float(value)):
                    scored[name][key][eq] = (float(value), kind)
                else:
                    count += 1
            coverage[eq][f"{name}_nonfinite_scores"] = count
        timings[f"{name}_predict_seconds"] = time.perf_counter() - started
    return scored, coverage, timings


def threshold_predictions(scored, threshold):
    alerts, typed_alerts = {}, {}
    for name, frames in scored.items():
        previous, frozen = defaultdict(set), defaultdict(dict)
        alerts[name], typed_alerts[name] = {}, {}
        for (run_id, sequence), entries in frames.items():
            current = {eq for eq, (value, _) in entries.items() if value >= threshold}
            for eq in previous[run_id] - current:
                frozen[run_id].pop(eq, None)
            for eq in current - previous[run_id]:
                frozen[run_id][eq] = entries[eq][1]
            key = (run_id, sequence)
            alerts[name][key] = current
            typed_alerts[name][key] = {(eq, frozen[run_id][eq]) for eq in current
                                       if frozen[run_id][eq] is not None} if name == "random_forest" else set()
            previous[run_id] = current
    return alerts, typed_alerts
