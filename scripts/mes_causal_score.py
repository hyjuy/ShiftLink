"""Generic event-ledger scoring; independent of all simulation equations."""
import math


def evaluate(runs, events, alerts, eligible=None):
    total = detected = duplicate = unmatched = normal_starts = 0
    delays, by_run = [], {}
    normal_seconds = wrong_seconds = operating = 0
    pristine_seconds = pristine_starts = 0
    for run, frames in runs.items():
        ledger = events[run]
        matched, previous = set(), set()
        local_delays = []
        local_duplicate = 0
        for frame in frames:
            t = frame['sequence']
            current = alerts[(run, t)]
            active = [e for e in ledger if e['start'] <= t < e['end']]
            running = frame.get('line_mode') == 'running' and (eligible is None or (run, t) in eligible)
            operating += int(running)
            normal_seconds += int(running and not active)
            pristine_seconds += int(running and not ledger)
            wrong_seconds += len(current - {e['equipment'] for e in active})
            for eq in current - previous:
                candidates = [e for e in active if e['equipment'] == eq and e['event_id'] not in matched]
                if candidates:
                    event = min(candidates, key=lambda e: (e['start'], e['event_id']))
                    matched.add(event['event_id'])
                    local_delays.append(t - event['start'])
                else:
                    unmatched += 1
                    if any(e['equipment'] == eq for e in active):
                        duplicate += 1
                        local_duplicate += 1
                    if running and not active:
                        normal_starts += 1
                    if running and not ledger:
                        pristine_starts += 1
            previous = current
        total += len(ledger)
        detected += len(matched)
        delays.extend(local_delays)
        by_run[run] = dict(events=len(ledger), detected=len(matched), missed=len(ledger) - len(matched),
                           duplicates=local_duplicate, delays=local_delays)
    ordered = sorted(delays)
    return dict(events=total, detected_events=detected, missed_events=total - detected,
                event_recall=detected / total if total else None,
                duplicate_notifications=duplicate, unmatched_starts_including_duplicates=unmatched,
                no_active_intervention_operating_seconds=normal_seconds, operating_seconds=operating,
                no_active_intervention_starts=normal_starts,
                pristine_normal_run_seconds=pristine_seconds, pristine_normal_false_starts=pristine_starts,
                pristine_normal_false_starts_per_line_hour=pristine_starts * 3600 / pristine_seconds if pristine_seconds else None,
                wrong_source_equipment_seconds=wrong_seconds,
                p95_injection_delay_seconds=ordered[math.ceil(.95 * len(ordered)) - 1] if ordered else None,
                within_10s_fraction=sum(d <= 10 for d in delays) / total if total else None, by_run=by_run)
