"""Independent snapshot-level checks for the current synthetic MES configuration."""
from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shiftlink.mes.configuration import from_catalog, validate
from shiftlink.mes.contracts import Run
from shiftlink.mes.engine import MesEngine


def main():
    catalog = json.loads((ROOT / "docs/data/reference/00_plant_and_relations.json").read_text(encoding="utf-8"))
    config = from_catalog(catalog)
    failures = []
    counts = {"snapshots": 0, "measurements": 0, "normal_frames": 0, "scenario_frames": 0}
    definitions = {(eq.equipment_id, s.signal): s for eq in config.equipment if eq.active for s in eq.signals}

    def require(condition, context, detail):
        if not condition:
            failures.append({"context": context, "detail": detail})

    def inspect(snapshot, context):
        counts["snapshots"] += 1
        counts["measurements"] += len(snapshot.measurements)
        observed = {(m.equipment_id, m.signal): m for m in snapshot.measurements}
        require(set(observed) == set(definitions), context, "measurement installation coverage")
        for key, measurement in observed.items():
            require(isinstance(measurement.value, (int, float)) and math.isfinite(measurement.value), context, f"finite numeric {key}")
            require(measurement.unit == definitions[key].unit, context, f"unit {key}")
            require(measurement.quality in ("good", "unavailable"), context, f"quality {key}")
            semantics = getattr(definitions[key], "semantics", None) or {}
            if semantics.get("acquisition") == "manual_sample":
                age = (snapshot.simulated_at - measurement.observed_at).total_seconds()
                require(0 <= age < 60, context, f"sample age {key}")
            else:
                require(measurement.observed_at == snapshot.simulated_at, context, f"timestamp {key}")
            if measurement.quality == "unavailable":
                require(measurement.signal == "rt_lift_delay" and measurement.value == 0, context, f"unexpected unavailable channel {key}")
        return observed

    for error in validate(config):
        failures.append({"context": "configuration", "detail": str(error)})
    channels = []
    for eq in config.equipment:
        if not eq.active:
            continue
        for signal in eq.signals:
            metadata = getattr(signal, "semantics", None)
            require(isinstance(metadata, dict) and all(metadata.get(k) for k in ("acquisition", "location", "reference", "applicability", "model")), "metadata", f"incomplete semantics {eq.equipment_id}/{signal.signal}")
            channels.append({"equipment_id": eq.equipment_id, "equipment_code": eq.code, **asdict(signal)})

    for seed in (3, 17, 91):
        engine = MesEngine(Run.create(seed=seed, config_id=config.config_id), config)
        stopped = inspect(engine.snapshot, f"seed={seed}/initial_stopped")
        for signal in ("hpu_flow", "hpu_cooler_oil_flow", "hpu_filter_dp"):
            require(stopped[("EQ-0001", signal)].value == 0, f"seed={seed}/stopped", f"zero {signal}")
        engine.start()
        for index in range(60):
            engine.tick()
            context = f"seed={seed}/normal/{index + 1}"
            readings = inspect(engine.snapshot, context)
            counts["normal_frames"] += 1
            hpu = {key[1]: value.value for key, value in readings.items() if key[0] == "EQ-0001"}
            require(hpu["hpu_cooler_oil_in_temp"] > hpu["hpu_cooler_oil_out_temp"], context, "oil cooling direction")
            require(hpu["hpu_cooler_water_out_temp"] > hpu["hpu_cooler_water_in_temp"], context, "water heat pickup direction")
            require(hpu["hpu_accumulator_gas_pressure"] == hpu["hpu_accumulator_fluid_pressure"], context, "operating accumulator pressure equality")
            require(hpu["hpu_cooler_oil_flow"] == hpu["hpu_flow"], context, "single circulation flow consistency")
            for eq in config.equipment:
                key = (eq.equipment_id, "cv_queue_len")
                if key in readings:
                    occupied = sum(coil["equipment_id"] == eq.equipment_id for coil in engine.snapshot.coils)
                    expected = round(min(100, occupied / eq.coil_capacity * 100), 3)
                    require(readings[key].value == expected, context, f"occupancy percent {eq.equipment_id}")
        for scenario in config.scenarios:
            if scenario.scenario_id == "normal":
                continue
            engine = MesEngine(Run.create(seed=seed, config_id=config.config_id), config)
            engine.start()
            engine.set_scenario(scenario.scenario_id)
            engine.tick()
            context = f"seed={seed}/scenario/{scenario.scenario_id}"
            readings = inspect(engine.snapshot, context)
            counts["scenario_frames"] += 1
            cause = next((eq for eq in config.equipment if eq.active and
                          (eq.equipment_id == scenario.cause_equipment_id if scenario.cause_equipment_id
                           else scenario.cause_capability in eq.capabilities)), None)
            if cause:
                for effect in scenario.signal_effects:
                    key = (cause.equipment_id, effect.signal)
                    require(key in readings and readings[key].value == round(effect.value, 3), context, f"explicit effect {key}")
                    require(key in readings and readings[key].quality == "good", context, f"explicit effect usable {key}")
            if "precharge" in scenario.scenario_id:
                require(readings[("EQ-0001", "hpu_accumulator_gas_pressure")].value == 135, context, "discharged precharge gas135")
                require(readings[("EQ-0001", "hpu_accumulator_fluid_pressure")].value == 0, context, "discharged precharge fluid0")
    require(any("precharge" in s.scenario_id for s in config.scenarios), "configuration", "explicit precharge scenario exists")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "config_id": config.config_id,
        "seeds": [3, 17, 91], "equipment_count": len(config.equipment),
        "unique_signals": len({key[1] for key in definitions}), "measurement_positions": len(definitions),
        "scenario_count": len(config.scenarios), "counts": counts, "passed": not failures,
        "failures": failures, "channel_semantics": channels,
        "confirmed_original_defects": ["Independent cooler inlet/outlet generation", "Stopped cooler flow and filter differential pressure", "Precharge and operating accumulator pressure modes mixed"],
        "contextual_assumptions": ["Pump outlet zero with retained manifold pressure requires explicitly modeled check-valve isolation", "Normal cooler heat-transfer direction applies during circulation", "Operating accumulator pressure equality is a static demo approximation"],
        "residuals": ["Synthetic configuration validation does not certify physical sensor installation", "Explicit numeric anomaly injection intentionally overrides normal physical correlations", "Historical stored runs are not modified or validated", "Dynamic transients and measurement uncertainty are outside this static demo model"],
    }
    destination = ROOT / "artifacts/mes-sensor-semantics-validation-20261001.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"artifact": str(destination), "passed": report["passed"], "counts": counts, "failures": failures}, ensure_ascii=False))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
