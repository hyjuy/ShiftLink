"""Additive replay contexts; injection labels never enter either predictor."""
from collections import Counter, defaultdict
from datetime import datetime

from scripts.evaluate_mes_fault_models import ALPHA, valid_values

INACTIVE = {"paused", "stopped", "recovering", "quality_hold"}


def predict_signed_ewma(runs, specs, stats, threshold=3):
    """Keep the baseline's state/validity semantics; preserve signed deviations."""
    alerts = {}
    for run_id, rows in runs.items():
        smoothed = {}
        for frame, _ in rows:
            key = run_id, frame["sequence"]
            if frame.get("line_mode") in INACTIVE:
                smoothed.clear()
                alerts[key] = set()
                continue
            equipment = defaultdict(float)
            for channel, value in valid_values(frame, specs).items():
                if channel not in stats:
                    continue
                mean, scale = stats[channel]
                z = (value - mean) / scale
                smoothed[channel] = ALPHA * z + (1 - ALPHA) * smoothed.get(channel, 0)
                equipment[channel[0]] = max(equipment[channel[0]], abs(smoothed[channel]))
            alerts[key] = {eq for eq, value in equipment.items() if value >= threshold}
    return alerts


def compare_pair(frame, clean, specs, stats):
    if (frame["sequence"], frame["simulated_at"]) != (clean["sequence"], clean["simulated_at"]):
        raise ValueError("replay pair time/key mismatch")
    factual, counterfactual = valid_values(frame, specs), valid_values(clean, specs)
    output = {}
    for eq in sorted({key[0] for key in specs}):
        left = {key for key in factual if key[0] == eq}
        right = {key for key in counterfactual if key[0] == eq}
        common = left & right
        changed = [key for key in sorted(common) if factual[key] != counterfactual[key]]
        output[eq] = {"changed": bool(changed),
            "comparable": bool(common) and (bool(changed) or left == right),
            "valid_sets_differ": left != right,
            "comparable_channels": len(common),
            "changed_signals": [key[1] for key in changed],
            "max_abs_difference": max((abs(factual[key]-counterfactual[key]) for key in changed), default=0),
            "max_train_scale_difference": max((abs(factual[key]-counterfactual[key])/stats[key][1]
                for key in changed if key in stats), default=0)}
    return output


def classify_alarms(runs, alerts, clean_runs, specs, stats):
    contexts = defaultdict(lambda: Counter(alarm_equipment_seconds=0,
        source_positive_equipment_seconds=0, strict_wrong_equipment_seconds=0))
    by_equipment = defaultdict(Counter)
    total, positive_total, wrong_total, wrong_union = 0, 0, 0, 0
    response_total, response_hit, remote_total, remote_hit = 0, 0, 0, 0
    records = []
    if runs.keys() != clean_runs.keys():
        raise ValueError("replay run keys differ")
    for run_id, rows in runs.items():
        if len(rows) != len(clean_runs[run_id]):
            raise ValueError("replay row counts differ")
        observed_ends, seen_fault = {}, False
        for index, ((frame, label), (clean, _)) in enumerate(zip(rows, clean_runs[run_id])):
            at = datetime.fromisoformat(frame["simulated_at"])
            seconds = ((datetime.fromisoformat(rows[index+1][0]["simulated_at"])-at).total_seconds()
                       if index+1 < len(rows) else 1)
            if seconds <= 0:
                raise ValueError("nonpositive frame duration")
            paired = compare_pair(frame, clean, specs, stats)
            key = run_id, frame["sequence"]
            current = alerts[key]
            faults = label["faults"]
            active = {f["equipment_id"] for f in faults if f["intensity"] > 0}
            local = {f["equipment_id"] for f in faults}
            for f in faults:
                if "end" in f:
                    observed_ends[f["id"]] = (f["equipment_id"], f["end"])
            prefault = not seen_fault and not faults
            seen_fault |= bool(faults)
            changed = {eq for eq, value in paired.items() if value["changed"]}
            remote = {eq for eq in changed-active if active-{eq}}
            response_total += seconds*len(changed)
            response_hit += seconds*len(changed & current)
            remote_total += seconds*len(remote)
            remote_hit += seconds*len(remote & current)
            wrong_union += seconds*bool(current-active)
            state_diverged = (frame.get("equipment_operating_states") != clean.get("equipment_operating_states")
                              or frame.get("line_mode") != clean.get("line_mode"))
            for eq in sorted(current):
                if eq not in paired:
                    raise ValueError("alert for unconfigured equipment")
                item = paired[eq]
                ends = [end for equipment, end in observed_ends.values()
                        if equipment == eq and end <= frame["sequence"]]
                end_age = frame["sequence"]-max(ends) if ends else None
                if not item["comparable"]:
                    context = "incomparable"
                elif eq in active:
                    context = "source_active"
                elif eq in local:
                    context = "episode_off"
                elif end_age is not None and 0 <= end_age <= 7:
                    context = "local_post_end"
                elif eq in remote:
                    context = "other_source_response"
                elif item["changed"]:
                    context = "persistent_twin_difference"
                else:
                    context = "unchanged_background"
                source_positive = eq in active
                total += seconds
                positive_total += seconds*source_positive
                wrong_total += seconds*(not source_positive)
                contexts[context]["alarm_equipment_seconds"] += seconds
                contexts[context]["source_positive_equipment_seconds"] += seconds*source_positive
                contexts[context]["strict_wrong_equipment_seconds"] += seconds*(not source_positive)
                by_equipment[eq][context] += seconds
                records.append({"run_id": run_id, "sequence": frame["sequence"],
                    "equipment_id": eq, "seconds": seconds, "context": context,
                    "source_positive": source_positive, "prefault": prefault,
                    "local_end_age": end_age, "remote_source_active": bool(active-{eq}),
                    "state_or_coil_count_diverged": state_diverged, **item})
    assert sum(v["alarm_equipment_seconds"] for v in contexts.values()) == total
    assert sum(v["strict_wrong_equipment_seconds"] for v in contexts.values()) == wrong_total
    return {"contexts": {key: dict(value) for key, value in sorted(contexts.items())},
        "by_equipment": {eq: dict(value) for eq, value in sorted(by_equipment.items())},
        "alarm_equipment_seconds": total, "source_positive_equipment_seconds": positive_total,
        "strict_wrong_equipment_seconds": wrong_total, "strict_wrong_union_seconds": wrong_union,
        "twin_response_equipment_seconds": response_total,
        "twin_response_detected_equipment_seconds": response_hit,
        "remote_response_equipment_seconds": remote_total,
        "remote_response_detected_equipment_seconds": remote_hit}, records
