"""Dependency-free equipment-location candidates for validation-only comparison.

The predictors use measurements and fitted normal statistics only. They do not
inspect fault labels, split names, or future frames.
"""
from collections import defaultdict

from scripts.evaluate_mes_fault_models import valid_values


INACTIVE_MODES = {"paused", "stopped", "recovering", "quality_hold"}


def _equipment_scores(frame, specs, stats):
    scores = defaultdict(list)
    for (equipment, signal), value in valid_values(frame, specs).items():
        fitted = stats.get((equipment, signal))
        if fitted is not None:
            center, scale = fitted
            scores[equipment].append(abs(value - center) / scale)
    return scores


def predict_sustained_robust(runs, specs, stats, threshold, *, consecutive=2,
                             release=3, release_fraction=0.65):
    """Robust max-z with consecutive onset and delayed release per equipment."""
    if consecutive < 1 or release < 1 or not 0 < release_fraction <= 1:
        raise ValueError("invalid persistence settings")
    alerts = {}
    for run_id, rows in runs.items():
        high_count, low_count, active = defaultdict(int), defaultdict(int), set()
        for frame, _ in rows:
            key = (run_id, frame["sequence"])
            if frame.get("line_mode") in INACTIVE_MODES:
                high_count.clear()
                low_count.clear()
                active.clear()
                alerts[key] = set()
                continue
            scores = _equipment_scores(frame, specs, stats)
            for equipment in set(scores) | active | set(high_count):
                values = scores.get(equipment)
                score = max(values) if values else None
                if equipment in active:
                    low_count[equipment] = (low_count[equipment] + 1 if score is None or
                                            score < threshold * release_fraction else 0)
                    if low_count[equipment] >= release:
                        active.remove(equipment)
                        high_count[equipment] = 0
                        low_count[equipment] = 0
                else:
                    high_count[equipment] = high_count[equipment] + 1 if score is not None and score >= threshold else 0
                    if high_count[equipment] >= consecutive:
                        active.add(equipment)
                        low_count[equipment] = 0
            alerts[key] = set(active)
    return alerts


def predict_consensus_robust(runs, specs, stats, threshold):
    """Alert when two distinct valid sensors on one equipment exceed robust z."""
    alerts = {}
    for run_id, rows in runs.items():
        for frame, _ in rows:
            key = (run_id, frame["sequence"])
            if frame.get("line_mode") in INACTIVE_MODES:
                alerts[key] = set()
                continue
            scores = _equipment_scores(frame, specs, stats)
            alerts[key] = {equipment for equipment, values in scores.items()
                           if sum(value >= threshold for value in values) >= 2}
    return alerts
