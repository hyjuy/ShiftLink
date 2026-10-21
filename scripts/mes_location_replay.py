"""Read-only synthetic validation replay for location-alarm attribution.

The no-explicit-cross-links twin removes relation overlays and external
transport factors. Other simulator interactions can still propagate effects.
"""
import json
from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

from scripts.build_mes_fault_dataset import IndependentChallenge, IndependentFactoryEngine
from shiftlink.mes.contracts import Run


def _frame(snapshot, original):
    coil_counts = Counter(coil["equipment_id"] for coil in snapshot.coils)
    return {**original,
            "sequence": snapshot.sequence,
            "simulated_at": snapshot.simulated_at.isoformat(),
            "line_mode": snapshot.line_mode,
            "equipment_operating_states": [
                {"equipment_id": state.equipment_id,
                 "operating_state": state.operating_state,
                 "coil_count": coil_counts[state.equipment_id]}
                for state in snapshot.equipment],
            "measurements": [{"equipment_id": m.equipment_id,
                              "signal": m.signal, "value": m.value,
                              "unit": m.unit, "quality": m.quality,
                              "observed_at": m.observed_at.isoformat()}
                             for m in snapshot.measurements]}


def replay_validation(path, config, runs):
    """Regenerate supplied validation runs only; never open feature/label rows."""
    manifest = json.loads((Path(path) / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("generator_version") != 7 or manifest.get("profile") != "independent"
            or manifest.get("config_id") != config.config_id):
        raise ValueError("expected matching v7 independent synthetic manifest")
    records = {record["run_id"]: record for record in manifest["runs"]
               if record["split"] == "validation"}
    if set(runs) != set(records):
        raise ValueError("supplied runs must be exactly manifest validation runs")
    output = {name: {} for name in ("factual", "no_explicit_cross_links", "no_faults")}
    verification = {"factual_frames_checked": 0, "prefault_frames_identical": 0,
                    "changed_frames": {"no_explicit_cross_links": 0, "no_faults": 0},
                    "changed_readings": {"no_explicit_cross_links": 0, "no_faults": 0},
                    "test_rows_read": 0,
                    "limits": "Frozen-model attribution within this synthetic generator; explicit links removed, other simulator coupling may remain."}
    for run_id, rows in runs.items():
        record = records[run_id]
        if len(rows) != record["frames"] or not rows or rows[0][0]["sequence"] != 1:
            raise ValueError(f"{run_id}: validation frame count/sequence mismatch")
        started = datetime.fromisoformat(rows[0][0]["simulated_at"]) - timedelta(seconds=1)
        run = Run(run_id=run_id, seed=record["seed"], started_at=started,
                  config_id=config.config_id, split="validation")
        engines, challenges = {}, {}
        for name in output:
            engines[name] = IndependentFactoryEngine(
                run, config, run_nonce=record["run_nonce"], faults_enabled=False,
                hazard=manifest["hazard"], response_scale=manifest["response_scale"])
            engines[name].start()
            if name != "no_faults":
                challenge = IndependentChallenge(
                    config, f'{record["seed"]}:{record["run_nonce"]}',
                    manifest["hazard"], manifest["warmup_ticks"], manifest["response_scale"])
                if name == "no_explicit_cross_links":
                    challenge.relations = ()
                challenges[name] = challenge
            output[name][run_id] = []
        before_first_fault = True
        for original, label in rows:
            regenerated = {}
            for name, engine in engines.items():
                faults = challenges[name].step(engine.snapshot.sequence + 1) if name in challenges else []
                if name == "no_explicit_cross_links":
                    # bearing_drag contributes only downstream drive factors here.
                    engine.set_faults([fault for fault in faults
                                       if fault["pattern_id"] != "bearing_drag"])
                else:
                    engine.set_faults(faults)
                snapshot = engine.tick()
                engine.truth.clear()
                if name in challenges:
                    snapshot = replace(snapshot, measurements=challenges[name].overlay(
                        snapshot.measurements, faults, snapshot.sequence))
                frame = _frame(snapshot, original)
                regenerated[name] = frame
                output[name][run_id].append((frame, label))
                if name != "no_faults" and faults != label["faults"]:
                    raise ValueError(f"{run_id}/{original['sequence']}: {name} fault schedule mismatch")
                if name == "factual":
                    for field in ("sequence", "simulated_at", "line_mode",
                                  "equipment_operating_states", "measurements"):
                        if frame[field] != original[field]:
                            raise ValueError(f"{run_id}/{original['sequence']}: factual {field} mismatch")
                    verification["factual_frames_checked"] += 1
            if not label["faults"] and before_first_fault:
                if any(regenerated[name]["measurements"] != original["measurements"]
                       for name in output):
                    raise ValueError(f"{run_id}/{original['sequence']}: prefault twin mismatch")
                verification["prefault_frames_identical"] += 1
            if label["faults"]:
                before_first_fault = False
            for name in ("no_explicit_cross_links", "no_faults"):
                differences = sum(a != b for a, b in zip(regenerated[name]["measurements"],
                                                         original["measurements"]))
                verification["changed_readings"][name] += differences
                verification["changed_frames"][name] += bool(differences)
    return {**output, "verification": verification}
