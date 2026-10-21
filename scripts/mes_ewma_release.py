"""Fixed fast-release variant of the existing per-sensor MES EWMA."""
from collections import defaultdict

from scripts.evaluate_mes_fault_models import ALPHA, valid_values

FALL_ALPHA = .8
INACTIVE = {"paused", "stopped", "recovering", "quality_hold"}


def predict_fast_release_ewma(runs, specs, stats, threshold=3):
    alerts = {}
    for run_id, rows in runs.items():
        smoothed = {}
        for frame, _ in rows:
            key = (run_id, frame["sequence"])
            if frame.get("line_mode") in INACTIVE:
                smoothed.clear()
                alerts[key] = set()
                continue
            by_equipment = defaultdict(float)
            for channel, value in valid_values(frame, specs).items():
                if channel not in stats:
                    continue
                mean, scale = stats[channel]
                z = abs(value - mean) / scale
                previous = smoothed.get(channel, 0.0)
                alpha = FALL_ALPHA if z < previous else ALPHA
                smoothed[channel] = alpha * z + (1 - alpha) * previous
                by_equipment[channel[0]] = max(by_equipment[channel[0]], smoothed[channel])
            alerts[key] = {eq for eq, value in by_equipment.items() if value >= threshold}
    return alerts
