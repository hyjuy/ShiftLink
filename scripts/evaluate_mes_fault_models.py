"""Compare the MES symptom rule with a train-fitted EWMA on synthetic runs.

Example: python scripts/evaluate_mes_fault_models.py --dataset output/mes-fault-dataset
Labels are used for train-normal selection, validation selection, and scoring only.
Neither detector receives a label, fault target, split name, or future frame.
"""
import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shiftlink.mes.configuration import from_catalog
from shiftlink.mes.scenarios.priority import expand
from shiftlink.mes.symptoms import screen_symptoms
from scripts.build_mes_fault_dataset import CHALLENGE_MECHANISMS

CATALOG = ROOT / "docs/data/reference/00_plant_and_relations.json"
THRESHOLDS = (1.5, 2.0, 2.5, 3.0, 4.0, 5.0)
ALPHA = 0.4
CHALLENGE_EFFECTS = {name: {signal: lag for signal, _, _, lag in effects}
                     for options in CHALLENGE_MECHANISMS.values() for name, effects in options}


def load_dataset(path):
    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("is_synthetic") is not True:
        raise ValueError("expected a synthetic dataset")
    config = expand(from_catalog(json.loads(CATALOG.read_text(encoding="utf-8"))))
    if manifest.get("config_id") != config.config_id:
        raise ValueError("dataset configuration differs from the current catalog")
    expected_signals = {(eq.equipment_id, spec.signal): spec.unit
                        for eq in config.equipment if eq.active for spec in eq.signals}
    if len(expected_signals) != 69 or manifest.get("signal_count") != 69:
        raise ValueError("expected 69 configured signals across active equipment")

    def read_rows(name):
        rows = {}
        with (path / name).open(encoding="utf-8") as source:
            for line in source:
                row = json.loads(line)
                key = (row["run_id"], row["sequence"])
                if key in rows:
                    raise ValueError(f"duplicate {name} key {key}")
                rows[key] = row
        return rows

    features = read_rows(manifest["feature_file"])
    for key, frame in features.items():
        measurements = frame.get("measurements", [])
        observed = {(m["equipment_id"], m["signal"]): m["unit"] for m in measurements}
        if (len(measurements) != len(expected_signals) or observed != expected_signals):
            raise ValueError(f"frame {key} differs from configured signals and units")
    labels = read_rows(manifest["private_label_file"])
    if features.keys() != labels.keys():
        raise ValueError("feature and label keys differ")
    runs = {r["run_id"]: r["split"] for r in manifest["runs"]}
    if len(runs) != len(manifest["runs"]) or set(runs.values()) != {"train", "validation", "test"}:
        raise ValueError("manifest must contain distinct runs in all three splits")
    split_rows = {split: defaultdict(list) for split in ("train", "validation", "test")}
    for key, row in features.items():
        run_id, _ = key
        if run_id not in runs or row["split"] != runs[run_id]:
            raise ValueError(f"feature split/run mismatch at {key}")
        split_rows[row["split"]][run_id].append((row, labels[key]))
    if set(features) != {(run_id, sequence)
                        for split in split_rows.values() for run_id, rows in split.items()
                        for sequence in (r["sequence"] for r, _ in rows)}:
        raise ValueError("invalid feature run/sequence keys")
    for split in split_rows.values():
        for rows in split.values():
            rows.sort(key=lambda pair: pair[0]["sequence"])
            for (before, _), (after, _) in zip(rows, rows[1:]):
                if after["sequence"] != before["sequence"] + 1 or datetime.fromisoformat(after["simulated_at"]) <= datetime.fromisoformat(before["simulated_at"]):
                    raise ValueError("run frames must have consecutive sequence and increasing time")
    return config, split_rows


def valid_values(frame, specs):
    """Return only current, good, unique measurements with configured units."""
    values, duplicates = {}, set()
    for m in frame["measurements"]:
        key = (m["equipment_id"], m["signal"])
        if key in values:
            duplicates.add(key)
        spec = specs.get(key)
        value = m.get("value")
        if (spec is not None and m.get("quality") == "good" and m.get("unit") == spec.unit
                and m.get("observed_at") == frame["simulated_at"]
                and isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value)):
            values[key] = float(value)
    return {key: value for key, value in values.items() if key not in duplicates}


def fit_normal(train_runs, config):
    specs = {(eq.equipment_id, s.signal): s for eq in config.equipment for s in eq.signals if eq.active}
    samples = defaultdict(list)
    for rows in train_runs.values():
        for frame, label in rows:
            if not label["faults"]:
                for key, value in valid_values(frame, specs).items():
                    samples[key].append(value)
    if not samples:
        raise ValueError("no fault-free training measurements")
    stats = {}
    for key, values in samples.items():
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        spec = specs[key]
        band = (spec.normal_max - spec.normal_min) if spec.normal_min is not None and spec.normal_max is not None else 0
        stats[key] = (mean, max(math.sqrt(variance), band * 0.05, 0.001))
    return specs, stats


def predict_ewma(runs, specs, stats, threshold):
    alerts = {}
    for run_id, rows in runs.items():
        smoothed = {}
        for frame, _ in rows:
            if frame.get("line_mode") in {"paused", "stopped", "recovering", "quality_hold"}:
                smoothed.clear()
                alerts[(run_id, frame["sequence"])] = set()
                continue
            by_equipment = defaultdict(float)
            for key, value in valid_values(frame, specs).items():
                if key not in stats:
                    continue
                mean, scale = stats[key]
                z = abs(value - mean) / scale
                previous = smoothed.get(key, 0.0)
                smoothed[key] = ALPHA * z + (1 - ALPHA) * previous
                by_equipment[key[0]] = max(by_equipment[key[0]], smoothed[key])
            alerts[(run_id, frame["sequence"])] = {eq for eq, score in by_equipment.items() if score >= threshold}
    return alerts


def predict_rule(runs, config, *, pattern=False):
    alerts = {}
    for run_id, rows in runs.items():
        window = []
        for frame, _ in rows:
            window = (window + [dict(frame, line_mode=frame.get("line_mode", "running"))])[-3:]
            records = screen_symptoms(window, config)
            alerts[(run_id, frame["sequence"])] = {
                (record["equipment_id"], record["pattern_id"]) if pattern else record["equipment_id"]
                for record in records if record["status"] == "candidate"
            }
    return alerts


def score(runs, alerts):
    total_events = detected = delay_seconds = false_alerts = false_alert_frames = normal_seconds = total_seconds = wrong_alert_seconds = wrong_alert_equipment_seconds = 0
    inactive_alerts = duplicate_alerts = premature_alerts = 0
    onset_delays = []
    observable_episodes = []
    injected_episodes = []
    equipment_burden = defaultdict(lambda: {"false_alert_starts": 0,
        "wrong_alert_seconds": 0, "wrong_alert_equipment_seconds": 0})
    for run_id, rows in runs.items():
        episodes = {}
        previous = set()
        for index, (frame, label) in enumerate(rows):
            key = (run_id, frame["sequence"])
            current = alerts[key]
            at = datetime.fromisoformat(frame["simulated_at"])
            duration = ((datetime.fromisoformat(rows[index + 1][0]["simulated_at"]) - at).total_seconds()
                        if index + 1 < len(rows) else 1)
            total_seconds += duration
            active = {fault["equipment_id"] for fault in label["faults"] if fault["intensity"] > 0}
            wrong_equipment = current - active
            false_alert_frames += bool(wrong_equipment)
            wrong_alert_seconds += duration * bool(wrong_equipment)
            wrong_alert_equipment_seconds += duration * len(wrong_equipment)
            for equipment in wrong_equipment:
                equipment_burden[equipment]["wrong_alert_seconds"] += duration
                equipment_burden[equipment]["wrong_alert_equipment_seconds"] += duration
            if not label["faults"]:
                normal_seconds += duration
            for fault in label["faults"]:
                episode = episodes.setdefault(fault["id"], {"equipment": fault["equipment_id"],
                    "mechanism": fault.get("pattern_id", "unspecified"),
                    "mode": fault.get("mode", "unspecified"),
                    "kind": fault.get("kind", "unspecified"), "onset": None, "detected": None})
                affected = fault.get("signal_targets")
                lags = CHALLENGE_EFFECTS.get(fault.get("pattern_id"), {}) if affected is None else {}
                measurements = frame.get("measurements")
                observable = measurements is None or any(
                    m["equipment_id"] == fault.get("source_equipment_id", fault["equipment_id"])
                    and (affected is None or m["signal"] in affected and affected[m["signal"]] is not None)
                    and (not lags or m["signal"] in lags
                         and frame["sequence"] - fault["start"] >= lags[m["signal"]])
                    and m.get("quality") == "good" and m.get("observed_at") == frame["simulated_at"]
                    for m in measurements)
                if fault["intensity"] > 0 and observable:
                    if episode["onset"] is None:
                        episode["onset"] = at
            for equipment in current - previous:
                match = next((episode for fault in label["faults"]
                              if fault["equipment_id"] == equipment and fault["intensity"] > 0
                              for episode in (episodes[fault["id"]],)
                              if episode["onset"] is not None and episode["detected"] is None), None)
                if match is None:
                    false_alerts += 1
                    equipment_burden[equipment]["false_alert_starts"] += 1
                    if equipment not in active:
                        inactive_alerts += 1
                    elif any(episode["equipment"] == equipment and episode["detected"] is not None
                             for episode in episodes.values()):
                        duplicate_alerts += 1
                    else:
                        premature_alerts += 1
                else:
                    match["detected"] = at
            previous = current
        for episode in episodes.values():
            injected_episodes.append(episode)
            if episode["onset"] is None:
                continue  # Retain it in injection coverage, even when no signal was observable.
            observable_episodes.append(episode)
            total_events += 1
            if episode["detected"] is not None:
                detected += 1
                delay = (episode["detected"] - episode["onset"]).total_seconds()
                delay_seconds += delay
                onset_delays.append(delay)
    onset_delays.sort()
    def breakdown(field):
        groups = defaultdict(lambda: {"events": 0, "detected_events": 0})
        delays = defaultdict(list)
        for episode in observable_episodes:
            group = groups[episode[field]]
            group["events"] += 1
            group["detected_events"] += episode["detected"] is not None
            if episode["detected"] is not None:
                delays[episode[field]].append((episode["detected"] - episode["onset"]).total_seconds())
        return {name: {**counts, "event_recall": counts["detected_events"] / counts["events"],
                       "missed_observable_events": counts["events"] - counts["detected_events"],
                       "p95_onset_delay_seconds": sorted(delays[name])[math.ceil(.95 * len(delays[name])) - 1]
                       if delays[name] else None}
                for name, counts in sorted(groups.items())}
    def percentile(p):
        return onset_delays[math.ceil(p * len(onset_delays)) - 1] if onset_delays else None
    by_equipment = {}
    for equipment in sorted({episode["equipment"] for episode in injected_episodes} | set(equipment_burden), key=str):
        injections = [episode for episode in injected_episodes if episode["equipment"] == equipment]
        observable = [episode for episode in injections if episode["onset"] is not None]
        delays = sorted((episode["detected"] - episode["onset"]).total_seconds()
                        for episode in observable if episode["detected"] is not None)
        by_equipment[str(equipment)] = {
            "injected_events": len(injections), "observable_events": len(observable),
            "unobservable_events": len(injections) - len(observable),
            "detected_events": len(delays), "missed_observable_events": len(observable) - len(delays),
            "event_recall": len(delays) / len(observable) if observable else None,
            "p95_onset_delay_seconds": delays[math.ceil(.95 * len(delays)) - 1] if delays else None,
            **equipment_burden[equipment]}
    injected_events = len(injected_episodes)
    injected_f1_denominator = injected_events + detected + false_alerts
    alert_start_precision = detected / (detected + false_alerts) if detected + false_alerts else None
    return {"events": total_events, "detected_events": detected,
            "injected_events": injected_events,
            "unobservable_events": injected_events - total_events,
            "observable_event_fraction": total_events / injected_events if injected_events else None,
            "injected_event_recall": detected / injected_events if injected_events else None,
            "injected_event_f1": 2 * detected / injected_f1_denominator if injected_f1_denominator else None,
            "by_mechanism": breakdown("mechanism"), "by_mode": breakdown("mode"),
            "by_kind": breakdown("kind"), "by_equipment": by_equipment,
            "event_recall": detected / total_events if total_events else None,
            "event_precision": alert_start_precision,
            "alert_start_precision": alert_start_precision,
            "event_f1": 2 * detected / (total_events + detected + false_alerts) if total_events + detected + false_alerts else None,
            "mean_onset_delay_seconds": delay_seconds / detected if detected else None,
            "p50_onset_delay_seconds": percentile(0.50),
            "p95_onset_delay_seconds": percentile(0.95),
            "false_alerts": false_alerts,
            "alerts_on_inactive_equipment": inactive_alerts,
            "duplicate_alert_episodes": duplicate_alerts,
            "premature_alert_episodes": premature_alerts,
            "normal_operating_hours": normal_seconds / 3600,
            "run_hours": total_seconds / 3600,
            "frames_with_wrong_alert": false_alert_frames,
            "wrong_alert_seconds": wrong_alert_seconds,
            "wrong_alert_equipment_seconds": wrong_alert_equipment_seconds,
            "wrong_alert_frame_fraction": false_alert_frames / sum(len(rows) for rows in runs.values()) if runs else None,
            "wrong_alert_time_fraction": wrong_alert_seconds / total_seconds if total_seconds else None,
            "false_alerts_per_hour": false_alerts * 3600 / total_seconds if total_seconds else None}


def selection_key(metrics):
    # Diagnostic-only validation utility: coverage is measured against every
    # injection, while sustained wrong alarms reduce the value of a high F1.
    f1 = metrics.get("injected_event_f1") or 0
    wrong_fraction = metrics["wrong_alert_time_fraction"]
    far = metrics["false_alerts_per_hour"]
    delay = metrics["mean_onset_delay_seconds"]
    return (f1 * (1 - wrong_fraction) if wrong_fraction is not None else -math.inf,
            f1, -(wrong_fraction if wrong_fraction is not None else math.inf),
            -(far if far is not None else math.inf), -(delay if delay is not None else math.inf))


def evaluate(path, test_dataset=None):
    manifest = json.loads((Path(path) / "manifest.json").read_text(encoding="utf-8"))
    profile = manifest.get("profile", "pattern")
    config, runs = load_dataset(path)
    specs, stats = fit_normal(runs["train"], config)
    validation = [(threshold, score(runs["validation"], predict_ewma(runs["validation"], specs, stats, threshold)))
                  for threshold in THRESHOLDS]
    # Validation alone selects threshold and model; the test split is evaluated once.
    selected, selected_metrics = max(validation, key=lambda item: (selection_key(item[1]), item[0]))
    rule_validation = score(runs["validation"], predict_rule(runs["validation"], config))
    selected_model = "ewma" if selection_key(selected_metrics) > selection_key(rule_validation) else "existing_symptom_rule"
    test = runs["test"]
    test_profile = profile
    if test_dataset is not None:
        challenge_manifest = json.loads((Path(test_dataset) / "manifest.json").read_text(encoding="utf-8"))
        challenge_config, challenge_runs = load_dataset(test_dataset)
        if challenge_config.config_id != config.config_id:
            raise ValueError("test dataset configuration differs from training dataset")
        reference_ids = {run_id for split in runs.values() for run_id in split}
        challenge_ids = {run_id for split in challenge_runs.values() for run_id in split}
        if reference_ids & challenge_ids:
            raise ValueError("test dataset shares runs with training or validation")
        test = challenge_runs["test"]
        test_profile = challenge_manifest.get("profile", "pattern")
    pattern_recall = None
    if test_profile == "pattern":
        pattern_runs = {run_id: [(frame, {"faults": [dict(fault, source_equipment_id=fault["equipment_id"],
                                                           equipment_id=(fault["equipment_id"], fault["pattern_id"]))
                                                      for fault in label["faults"]]}) for frame, label in rows]
                        for run_id, rows in test.items()}
        pattern_recall = score(pattern_runs, predict_rule(test, config, pattern=True))["event_recall"]
        if pattern_recall is None and any(label["faults"] for rows in test.values() for _, label in rows):
            raise ValueError("pattern faults exist but no observable pattern events were scored")
    return {"dataset": str(Path(path)), "dataset_profile": profile,
            "test_dataset": str(Path(test_dataset)) if test_dataset is not None else str(Path(path)),
            "test_dataset_profile": test_profile,
            "selection": "Diagnostic-only validation utility: injected-event F1 multiplied by (1 minus wrong-alert time fraction); then injected-event F1, wrong-alert time, alert starts/run hour, and delay. Ties favor existing symptom rule. This is not a calibrated operating objective.",
            "ewma_alpha": ALPHA, "selected_ewma_threshold": selected,
            "validation_candidates": [{"threshold": threshold, **metrics} for threshold, metrics in validation],
            "validation_existing_symptom_rule": rule_validation, "selected_model": selected_model,
            "test": {"existing_symptom_rule": score(test, predict_rule(test, config)),
                     "ewma": score(test, predict_ewma(test, specs, stats, selected)),
                     "existing_rule_exact_pattern_event_recall": pattern_recall},
            "limits": "EWMA selects equipment location only; symptom type remains the existing screen_symptoms rule. event_precision is alert-start precision, and event_f1 combines observable-event recall with alert-start precision. injected_event_recall/F1 include unobservable injections. False alerts count unmatched alert episode starts, including duplicate starts while a fault is active; wrong-alert time counts alerts on inactive equipment. Synthetic injections only; final-frame duration assumes one second. Observable onset means an affected current good signal can respond, not proof of a measurable value change. No real-hardware calibration."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--test-dataset", type=Path,
                        help="Independent held-out dataset; train and select on --dataset only")
    args = parser.parse_args()
    print(json.dumps(evaluate(args.dataset, args.test_dataset), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
