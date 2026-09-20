"""Configuration schema, validation, and transformation for modular equipment setup."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .contracts import (
    Configuration, EquipmentConfig, SignalSpec, RelationConfig, ScenarioSpec,
    SignalEffect, LayoutGroup, RecoveryAction
)

# Permitted capabilities; derived from equipment code prefixes and actual relations.
KNOWN_CAPABILITIES = frozenset({
    "hydraulic_supply", "power_supply", "pneumatic_supply", "drive",
    "transport", "buffer", "discharge"  # buffer/discharge for handling block scenarios
})


def from_catalog(catalog_data: dict[str, Any]) -> Configuration:
    """Build baseline Configuration from JSON catalog (00_plant_and_relations.json)."""
    equipment_list = []
    eq_by_id = {}
    code_by_id = {}

    for eq in catalog_data.get("equipment", []):
        eq_id = eq["equipment_id"]
        code = eq.get("code", "")
        segment = eq.get("segment_id")
        code_by_id[eq_id] = code

        # Capabilities derived from code prefix and actual relations (set later).
        if code.startswith("HPU"):
            capabilities = ["hydraulic_supply"]
        elif code.startswith("PDP"):
            capabilities = ["power_supply"]
        elif code.startswith("CAU"):
            capabilities = ["pneumatic_supply"]
        elif code.startswith("GR"):
            capabilities = ["drive"]
        elif code.startswith(("RT", "CV")):
            capabilities = ["transport"]
            if code.startswith("CV"):
                capabilities.append("discharge")  # CV is the output buffer/discharge point
        else:
            capabilities = []

        signals = []
        for point in eq.get("measurement_points", []):
            signal = point["signal"]
            name = point.get("name", signal)
            unit = point.get("unit", "")
            normal_min = point.get("normal_min")
            normal_max = point.get("normal_max")

            # rt_speed, cv_speed return 0 when stopped per engine._measurement_value behavior.
            zero_stopped = signal in ("rt_speed", "cv_speed")

            signals.append(SignalSpec(
                signal=signal,
                name=name,
                unit=unit,
                normal_min=normal_min,
                normal_max=normal_max,
                required=True,
                zero_when_stopped=zero_stopped
            ))

        asset_id = f"AS-{eq_id}-001"  # Deterministic: AS-{equipment_id}-001
        config_eq = EquipmentConfig(
            equipment_id=eq_id,
            asset_id=asset_id,
            code=code,
            name=f"{code}",  # Use code as name; catalog has no explicit name field.
            segment_id=segment,
            profile_id=code.split("-")[0].lower() if "-" in code else code.lower(),
            capabilities=tuple(capabilities),
            signals=tuple(signals),
            coil_capacity=1,
            dwell_seconds=10.0,
            active=True
        )
        equipment_list.append(config_eq)
        eq_by_id[eq_id] = config_eq

    # Material flow route: topological from catalog relations.
    # Current behavior (preserved): EQ-0006→0007→0008→0009 (60 m_min main), EQ-0008→0010 (20 m_min) as branch.
    route = _compute_material_route(catalog_data, eq_by_id)

    # All relations from catalog (equipment-to-equipment only; skip equipment→line, etc.).
    all_relations = []
    branches = []
    for rel in catalog_data.get("relations", []):
        # Skip non-equipment relations.
        if rel.get("from_kind") != "equipment" or rel.get("to_kind") != "equipment":
            continue
        from_id = rel.get("from_id")
        to_id = rel.get("to_id")
        rel_type = rel.get("relation_type")
        capacity = rel.get("capacity", {})
        cap_value = capacity.get("value") if isinstance(capacity, dict) else None
        cap_unit = capacity.get("unit") if isinstance(capacity, dict) else None
        lag = rel.get("lag_seconds")

        config_rel = RelationConfig(
            relation_type=rel_type,
            from_id=from_id,
            to_id=to_id,
            lag_seconds=lag,
            capacity_value=cap_value,
            capacity_unit=cap_unit
        )

        # Branches: material_flow that is not in the main route.
        if rel_type == "material_flow":
            is_in_route = (
                len(route) > 1 and
                any(route[i] == from_id and route[i+1] == to_id for i in range(len(route)-1))
            )
            if not is_in_route:
                branches.append(config_rel)
            else:
                all_relations.append(config_rel)
        else:
            all_relations.append(config_rel)

    # Scenarios: current 3 types → ScenarioSpec.
    scenarios = [
        ScenarioSpec(
            scenario_id="drive_fault",
            cause_capability="drive",
            propagation_relation="drive",
            wait_reason="upstream_drive_fault",
            alarm_code="AL-DRV-VIB",
            signal_effects=(SignalEffect(capability="drive", signal="gr_vib_rms", value=5.0),),
            recovery_ticks=2
        ),
        ScenarioSpec(
            scenario_id="hydraulic_fault",
            cause_capability="hydraulic_supply",
            propagation_relation="hydraulic_supply",
            wait_reason="hydraulic_supply_low",
            alarm_code="AL-HYD-LOW",
            signal_effects=(SignalEffect(capability="hydraulic_supply", signal="hpu_pressure", value=120.0),),
            recovery_ticks=2
        ),
        ScenarioSpec(
            scenario_id="downstream_block",
            cause_capability="discharge",  # CV-01 (EQ-0009) is the discharge point
            propagation_relation="interlock",
            wait_reason="downstream_block",
            alarm_code="AL-DSB-QUE",
            signal_effects=(SignalEffect(capability="discharge", signal="cv_queue_len", value=95.0),),
            recovery_ticks=2
        ),
    ]

    # Layout: main material route + utility/supply.
    layout = [
        LayoutGroup(
            title="소재 주경로",
            equipment_ids=route
        ),
        LayoutGroup(
            title="구동·공급·보조 설비",
            equipment_ids=tuple(e.equipment_id for e in equipment_list if e.equipment_id not in route)
        )
    ]

    line_id = (catalog_data.get("production_lines") or [{"line_id": "LN-0001"}])[0].get("line_id", "LN-0001")

    config = Configuration(
        config_id="",  # Will be filled by finalize()
        version_label="baseline",
        source="catalog",
        line_id=line_id,
        equipment=tuple(equipment_list),
        relations=tuple(all_relations),
        route=route,
        branches=tuple(branches),
        scenarios=tuple(scenarios),
        layout=tuple(layout)
    )
    from .scenarios.priority import expand
    return expand(config)


def _compute_material_route(catalog_data: dict[str, Any], eq_by_id: dict) -> tuple[str, ...]:
    """Compute main material flow route preserving current behavior."""
    rels = catalog_data.get("relations", [])
    material_flows = [r for r in rels if r.get("relation_type") == "material_flow"]

    if not material_flows:
        return ("EQ-0006", "EQ-0007", "EQ-0008", "EQ-0009")  # fallback

    # Topological sort: start from node with no incoming material_flow.
    targets = {r["to_id"] for r in material_flows}
    start = next((r["from_id"] for r in material_flows if r["from_id"] not in targets), material_flows[0]["from_id"])

    route = [start]
    visited = {start}
    while True:
        outgoing = [r for r in material_flows if r["from_id"] == route[-1] and r["to_id"] not in visited]
        if not outgoing:
            break
        # Select largest capacity branch (preserves current behavior).
        next_rel = max(outgoing, key=lambda r: (r.get("capacity", {}).get("value") or 0))
        next_id = next_rel["to_id"]
        route.append(next_id)
        visited.add(next_id)

    return tuple(route)


def load_draft(payload: dict[str, Any], *, source: str) -> Configuration:
    """Load and validate schema of a user-provided configuration draft."""
    required = {"config_id", "version_label", "source", "line_id"}
    if not required.issubset(payload.keys()):
        missing = required - payload.keys()
        raise ValueError(f"Missing required fields: {missing}")

    if not isinstance(payload.get("equipment"), list):
        raise ValueError("equipment must be a list")
    if not isinstance(payload.get("relations"), list):
        raise ValueError("relations must be a list")
    if not isinstance(payload.get("route"), (list, tuple)):
        raise ValueError("route must be a list")

    # Reconstruct from raw dicts.
    equipment = []
    for eq_dict in payload.get("equipment", []):
        signals = tuple(
            SignalSpec(**sig) if isinstance(sig, dict) else sig
            for sig in eq_dict.get("signals", [])
        )
        equipment.append(EquipmentConfig(
            equipment_id=eq_dict["equipment_id"],
            asset_id=eq_dict["asset_id"],
            code=eq_dict["code"],
            name=eq_dict["name"],
            segment_id=eq_dict.get("segment_id"),
            profile_id=eq_dict["profile_id"],
            capabilities=tuple(eq_dict.get("capabilities", [])),
            signals=signals,
            coil_capacity=eq_dict.get("coil_capacity", 1),
            dwell_seconds=float(eq_dict.get("dwell_seconds", 10.0)),
            active=eq_dict.get("active", True)
        ))

    relations = tuple(
        RelationConfig(**rel) if isinstance(rel, dict) else rel
        for rel in payload.get("relations", [])
    )

    scenarios = tuple(
        ScenarioSpec(
            scenario_id=sc.get("scenario_id"),
            cause_capability=sc.get("cause_capability"),
            propagation_relation=sc.get("propagation_relation"),
            wait_reason=sc.get("wait_reason"),
            alarm_code=sc.get("alarm_code"),
            signal_effects=tuple(
                SignalEffect(**eff) if isinstance(eff, dict) else eff
                for eff in sc.get("signal_effects", [])
            ),
            recovery_ticks=int(sc.get("recovery_ticks", 2)),
            title=sc.get("title", ""), source_url=sc.get("source_url", ""),
            recovery_actions=tuple(RecoveryAction(**a) for a in sc.get("recovery_actions", [])),
            component_id=sc.get("component_id", ""), product_hold=sc.get("product_hold", False)
        )
        for sc in payload.get("scenarios", [])
    )

    layout = tuple(
        LayoutGroup(title=lg.get("title"), equipment_ids=tuple(lg.get("equipment_ids", [])))
        for lg in payload.get("layout", [])
    )

    config = Configuration(
        config_id=payload["config_id"],
        version_label=payload["version_label"],
        source=payload.get("source", source),
        line_id=payload["line_id"],
        equipment=tuple(equipment),
        relations=relations,
        route=tuple(payload.get("route", [])),
        branches=tuple(
            RelationConfig(**br) if isinstance(br, dict) else br
            for br in payload.get("branches", [])
        ),
        scenarios=scenarios,
        layout=layout
    )
    # A draft's config_id is always recomputed from content; a stale or spoofed id never survives.
    return finalize(config)


def validate(config: Configuration) -> list[str]:
    """Validate configuration semantics. Returns list of error messages."""
    errors = []

    # Duplicate equipment_id, asset_id, signal.
    eq_ids = [e.equipment_id for e in config.equipment]
    if len(eq_ids) != len(set(eq_ids)):
        errors.append("Duplicate equipment_id in configuration")

    asset_ids = [e.asset_id for e in config.equipment]
    if len(asset_ids) != len(set(asset_ids)):
        errors.append("Duplicate asset_id in configuration")

    eq_by_id = {e.equipment_id: e for e in config.equipment}

    for eq in config.equipment:
        sig_names = [s.signal for s in eq.signals]
        if len(sig_names) != len(set(sig_names)):
            errors.append(f"Duplicate signal in {eq.equipment_id}")

    # Unknown capability.
    for eq in config.equipment:
        for cap in eq.capabilities:
            if cap not in KNOWN_CAPABILITIES:
                errors.append(f"{eq.equipment_id}: unknown capability '{cap}'")

    # Route: all must exist and active.
    for route_id in config.route:
        if route_id not in eq_by_id:
            errors.append(f"Route: equipment {route_id} not found")
        elif not eq_by_id[route_id].active:
            errors.append(f"Route: equipment {route_id} inactive")

    # Route: adjacent pairs must have material_flow relation.
    material_rels = {(r.from_id, r.to_id) for r in config.relations if r.relation_type == "material_flow"}
    material_rels.update((r.from_id, r.to_id) for r in config.branches if r.relation_type == "material_flow")
    for i in range(len(config.route) - 1):
        from_id, to_id = config.route[i], config.route[i+1]
        if (from_id, to_id) not in material_rels:
            errors.append(f"No material_flow relation from {from_id} to {to_id} in route")

    # Signal: must have unit.
    for eq in config.equipment:
        for sig in eq.signals:
            if not sig.unit:
                errors.append(f"{eq.equipment_id}.{sig.signal}: missing unit")

    # Relation references must exist.
    for rel in config.relations + config.branches:
        if rel.from_id not in eq_by_id:
            errors.append(f"Relation from {rel.from_id}: equipment not found")
        if rel.to_id not in eq_by_id:
            errors.append(f"Relation to {rel.to_id}: equipment not found")

    # Branch ambiguity: material_flow not in route must be explicitly in branches.
    all_material = [(r.from_id, r.to_id) for r in config.relations + config.branches if r.relation_type == "material_flow"]
    route_material = {(config.route[i], config.route[i+1]) for i in range(len(config.route) - 1)}
    for from_id, to_id in all_material:
        if (from_id, to_id) not in route_material and (from_id, to_id) not in {(r.from_id, r.to_id) for r in config.branches}:
            errors.append(f"Material flow {from_id}→{to_id}: not in route and not in branches (ambiguous)")

    scenario_ids = [s.scenario_id for s in config.scenarios]
    if len(scenario_ids) != len(set(scenario_ids)):
        errors.append("Duplicate scenario_id")
    for scenario in config.scenarios:
        actions = scenario.recovery_actions
        if scenario.recovery_ticks < 1:
            errors.append(f"{scenario.scenario_id}: recovery_ticks must be positive")
        if len({a.action_id for a in actions}) != len(actions) or any(not a.action_id or not a.title for a in actions):
            errors.append(f"{scenario.scenario_id}: recovery actions need unique IDs and titles")
        if scenario.product_hold and not actions:
            errors.append(f"{scenario.scenario_id}: product hold requires release actions")
    return errors


def diff(old: Configuration, new: Configuration) -> dict[str, list[dict[str, Any]]]:
    """Compute configuration changes between old and new."""
    changes = {
        "renamed": [],
        "param_changed": [],
        "asset_replaced": [],
        "added": [],
        "removed": [],
        "signal_changed": [],
        "route_changed": [],
        "layout_changed": []
    }

    old_by_id = {e.equipment_id: e for e in old.equipment}
    new_by_id = {e.equipment_id: e for e in new.equipment}
    old_assets = {e.asset_id: e.equipment_id for e in old.equipment}
    new_assets = {e.asset_id: e.equipment_id for e in new.equipment}

    # Check for reused asset_ids (error).
    retired_assets = set(old_assets.keys()) - set(new_assets.keys())
    for reused_id in retired_assets:
        if reused_id in new_assets:
            changes["asset_replaced"].append({
                "equipment_id": new_assets[reused_id],
                "error": f"Reused retired asset_id {reused_id}"
            })

    # Added and removed equipment.
    for eq_id in new_by_id:
        if eq_id not in old_by_id:
            changes["added"].append({"equipment_id": eq_id, "code": new_by_id[eq_id].code})

    for eq_id in old_by_id:
        if eq_id not in new_by_id:
            changes["removed"].append({"equipment_id": eq_id, "code": old_by_id[eq_id].code})

    # For existing equipment: asset replacement, param changes, signal changes.
    for eq_id in old_by_id:
        if eq_id not in new_by_id:
            continue
        old_eq = old_by_id[eq_id]
        new_eq = new_by_id[eq_id]

        if old_eq.asset_id != new_eq.asset_id:
            changes["asset_replaced"].append({
                "equipment_id": eq_id,
                "old_asset_id": old_eq.asset_id,
                "new_asset_id": new_eq.asset_id
            })

        if old_eq.name != new_eq.name or old_eq.profile_id != new_eq.profile_id:
            changes["param_changed"].append({
                "equipment_id": eq_id,
                "old_name": old_eq.name,
                "new_name": new_eq.name,
                "old_profile": old_eq.profile_id,
                "new_profile": new_eq.profile_id
            })

        # Signal changes.
        old_sigs = {s.signal: s for s in old_eq.signals}
        new_sigs = {s.signal: s for s in new_eq.signals}
        for sig_id in old_sigs:
            if sig_id not in new_sigs:
                changes["signal_changed"].append({
                    "equipment_id": eq_id,
                    "signal": sig_id,
                    "change": "removed"
                })
            elif old_sigs[sig_id].unit != new_sigs[sig_id].unit:
                changes["signal_changed"].append({
                    "equipment_id": eq_id,
                    "signal": sig_id,
                    "change": "unit",
                    "old_unit": old_sigs[sig_id].unit,
                    "new_unit": new_sigs[sig_id].unit
                })

    # Route and layout changes.
    if old.route != new.route:
        changes["route_changed"].append({
            "old_route": old.route,
            "new_route": new.route
        })

    if old.layout != new.layout:
        changes["layout_changed"].append({
            "modified": True
        })

    # Clean empty lists.
    return {k: v for k, v in changes.items() if v}


def canonical_payload(config: Configuration) -> str:
    """Return normalized JSON string for hashing (sorted keys)."""
    payload = to_payload(config)
    # config_id is placeholder; will be recalculated by finalize.
    payload["config_id"] = "placeholder"
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def config_hash(payload: dict[str, Any] | str) -> str:
    """Compute sha256 hash of canonical payload."""
    if isinstance(payload, dict):
        canonical = canonical_payload(Configuration(**payload))
    else:
        canonical = payload
    return hashlib.sha256(canonical.encode()).hexdigest()


def to_payload(config: Configuration) -> dict[str, Any]:
    """Convert Configuration to dict for JSON serialization."""
    return {
        "config_id": config.config_id,
        "version_label": config.version_label,
        "source": config.source,
        "line_id": config.line_id,
        "equipment": [
            {
                "equipment_id": e.equipment_id,
                "asset_id": e.asset_id,
                "code": e.code,
                "name": e.name,
                "segment_id": e.segment_id,
                "profile_id": e.profile_id,
                "capabilities": list(e.capabilities),
                "signals": [
                    {
                        "signal": s.signal,
                        "name": s.name,
                        "unit": s.unit,
                        "normal_min": s.normal_min,
                        "normal_max": s.normal_max,
                        "required": s.required,
                        "zero_when_stopped": s.zero_when_stopped
                    }
                    for s in e.signals
                ],
                "coil_capacity": e.coil_capacity,
                "dwell_seconds": e.dwell_seconds,
                "active": e.active
            }
            for e in config.equipment
        ],
        "relations": [
            {
                "relation_type": r.relation_type,
                "from_id": r.from_id,
                "to_id": r.to_id,
                "lag_seconds": r.lag_seconds,
                "capacity_value": r.capacity_value,
                "capacity_unit": r.capacity_unit
            }
            for r in config.relations
        ],
        "branches": [
            {
                "relation_type": r.relation_type,
                "from_id": r.from_id,
                "to_id": r.to_id,
                "lag_seconds": r.lag_seconds,
                "capacity_value": r.capacity_value,
                "capacity_unit": r.capacity_unit
            }
            for r in config.branches
        ],
        "route": list(config.route),
        "scenarios": [
            {
                "scenario_id": s.scenario_id,
                "cause_capability": s.cause_capability,
                "propagation_relation": s.propagation_relation,
                "wait_reason": s.wait_reason,
                "alarm_code": s.alarm_code,
                "signal_effects": [
                    {"capability": eff.capability, "signal": eff.signal, "value": eff.value}
                    for eff in s.signal_effects
                ],
                "recovery_ticks": s.recovery_ticks,
                **({"title": s.title, "source_url": s.source_url,
                    "component_id": s.component_id, "product_hold": s.product_hold,
                    "recovery_actions": [{"action_id": a.action_id, "title": a.title, "detail": a.detail} for a in s.recovery_actions]}
                   if s.recovery_actions or s.title else {})
            }
            for s in config.scenarios
        ],
        "layout": [
            {"title": lg.title, "equipment_ids": list(lg.equipment_ids)}
            for lg in config.layout
        ]
    }


def from_payload(payload: dict[str, Any]) -> Configuration:
    """Reconstruct Configuration from dict (reverse of to_payload)."""
    return load_draft(payload, source=payload.get("source", "unknown"))


def finalize(config: Configuration) -> Configuration:
    """Compute and fill config_id hash; return new Configuration."""
    canonical = canonical_payload(config)
    hash_value = config_hash(canonical)
    return Configuration(
        config_id=hash_value,
        version_label=config.version_label,
        source=config.source,
        line_id=config.line_id,
        equipment=config.equipment,
        relations=config.relations,
        route=config.route,
        branches=config.branches,
        scenarios=config.scenarios,
        layout=config.layout
    )
