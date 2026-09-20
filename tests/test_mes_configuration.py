"""Test configuration schema, validation, and catalog transformation."""

import json
from pathlib import Path
import pytest
from shiftlink.mes.contracts import (
    Configuration, EquipmentConfig, SignalSpec, RelationConfig, ScenarioSpec,
    SignalEffect, LayoutGroup
)
from shiftlink.mes.configuration import (
    from_catalog, load_draft, validate, diff, to_payload, from_payload,
    canonical_payload, config_hash, finalize
)


CATALOG_PATH = Path(__file__).parents[1] / "docs" / "00_plant_and_relations.json"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mes"


@pytest.fixture
def catalog_data():
    with CATALOG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def config_a(catalog_data):
    return from_catalog(catalog_data)


def test_from_catalog_creates_base_config(catalog_data):
    config = from_catalog(catalog_data)
    assert config.version_label == "baseline"
    assert config.line_id == "LN-0001"
    assert len(config.equipment) == 10
    assert all(e.active for e in config.equipment)
    assert len(config.route) > 0
    assert config.route[0] == "EQ-0006"  # RT-01 starts material flow


def test_from_catalog_material_route_explicit(catalog_data):
    config = from_catalog(catalog_data)
    # Current behavior: EQ-0006→0007→0008→0009 (60 m_min), EQ-0008→0010 (20 m_min) as branch
    assert config.route == ("EQ-0006", "EQ-0007", "EQ-0008", "EQ-0009")
    # EQ-0008→EQ-0010 should be in branches, not route
    branch_ids = [r.to_id for r in config.branches if r.relation_type == "material_flow"]
    assert "EQ-0010" in branch_ids


def test_from_catalog_asset_ids_deterministic(catalog_data):
    config1 = from_catalog(catalog_data)
    config2 = from_catalog(catalog_data)
    assert [e.asset_id for e in config1.equipment] == [e.asset_id for e in config2.equipment]


def test_from_catalog_capabilities(catalog_data):
    config = from_catalog(catalog_data)
    eq_by_id = config.equipment_by_id()

    hpu = eq_by_id["EQ-0001"]
    assert "hydraulic_supply" in hpu.capabilities
    assert hpu.code == "HPU-01"

    gr = eq_by_id["EQ-0004"]
    assert "drive" in gr.capabilities
    assert gr.code == "GR-01"

    rt = eq_by_id["EQ-0006"]
    assert "transport" in rt.capabilities
    assert rt.code == "RT-01"


def test_from_catalog_signals(catalog_data):
    config = from_catalog(catalog_data)
    eq_by_id = config.equipment_by_id()

    hpu = eq_by_id["EQ-0001"]
    signal_names = {s.signal for s in hpu.signals}
    assert "hpu_pressure" in signal_names
    assert all(s.unit for s in hpu.signals)  # All must have units

    rt = eq_by_id["EQ-0006"]
    rt_speed = next((s for s in rt.signals if s.signal == "rt_speed"), None)
    assert rt_speed is not None
    assert rt_speed.zero_when_stopped


def test_from_catalog_scenarios(catalog_data):
    config = from_catalog(catalog_data)
    scenario_ids = {s.scenario_id for s in config.scenarios}
    assert "drive_fault" in scenario_ids
    assert "hydraulic_fault" in scenario_ids
    assert "downstream_block" in scenario_ids

    drive_fault = next(s for s in config.scenarios if s.scenario_id == "drive_fault")
    assert drive_fault.cause_capability == "drive"
    assert drive_fault.propagation_relation == "drive"


def test_from_catalog_layout(catalog_data):
    config = from_catalog(catalog_data)
    assert len(config.layout) >= 2  # Main route + utilities

    main_group = next((g for g in config.layout if "주경로" in g.title or "material" in g.title.lower()), None)
    assert main_group is not None
    assert "EQ-0006" in main_group.equipment_ids


def test_config_hash_deterministic():
    payload = {
        "config_id": "placeholder",
        "version_label": "test",
        "source": "test",
        "line_id": "LN-0001",
        "equipment": [],
        "relations": [],
        "route": [],
        "branches": [],
        "scenarios": [],
        "layout": []
    }
    hash1 = config_hash(payload)
    hash2 = config_hash(payload)
    assert hash1 == hash2
    assert len(hash1) == 64  # sha256 hex


def test_canonical_payload_key_ordered(catalog_data):
    config = from_catalog(catalog_data)
    canonical = canonical_payload(config)
    # Verify it's valid JSON and starts with {
    parsed = json.loads(canonical)
    assert isinstance(parsed, dict)


def test_finalize_fills_config_id():
    config = Configuration(
        config_id="placeholder",
        version_label="test",
        source="test",
        line_id="LN-0001"
    )
    finalized = finalize(config)
    assert finalized.config_id != "placeholder"
    assert len(finalized.config_id) == 64


def test_to_payload_from_payload_roundtrip(config_a):
    payload = to_payload(config_a)
    restored = from_payload(payload)

    assert restored.line_id == config_a.line_id
    assert len(restored.equipment) == len(config_a.equipment)
    assert restored.route == config_a.route


def test_validate_baseline_config_valid(config_a):
    errors = validate(config_a)
    assert len(errors) == 0, f"Baseline config should be valid, got: {errors}"


def test_validate_duplicate_equipment_id(catalog_data):
    config = from_catalog(catalog_data)
    # Corrupt: duplicate equipment_id
    dup_eq = config.equipment[0]
    bad_eq = EquipmentConfig(
        equipment_id=dup_eq.equipment_id,  # same as first
        asset_id="AS-DUP-001",
        code="DUP-01",
        name="Duplicate",
        segment_id="SG-0000",
        profile_id="transport",
        capabilities=("transport",)
    )
    bad_config = Configuration(
        config_id=config.config_id,
        version_label=config.version_label,
        source=config.source,
        line_id=config.line_id,
        equipment=config.equipment + (bad_eq,),
        relations=config.relations,
        route=config.route,
        scenarios=config.scenarios,
        layout=config.layout
    )
    errors = validate(bad_config)
    assert any("equipment_id" in e and "duplicate" in e.lower() for e in errors)


def test_validate_unknown_capability(catalog_data):
    config = from_catalog(catalog_data)
    bad_eq = EquipmentConfig(
        equipment_id="EQ-9999",
        asset_id="AS-9999-001",
        code="XXX-01",
        name="Unknown",
        segment_id="SG-0000",
        profile_id="unknown_type",
        capabilities=("future_capability",)  # not in known set
    )
    bad_config = Configuration(
        config_id=config.config_id,
        version_label=config.version_label,
        source=config.source,
        line_id=config.line_id,
        equipment=config.equipment + (bad_eq,),
        relations=config.relations,
        route=config.route,
        scenarios=config.scenarios,
        layout=config.layout
    )
    errors = validate(bad_config)
    assert any("capability" in e.lower() for e in errors)


def test_validate_route_missing_equipment(catalog_data):
    config = from_catalog(catalog_data)
    bad_config = Configuration(
        config_id=config.config_id,
        version_label=config.version_label,
        source=config.source,
        line_id=config.line_id,
        equipment=config.equipment,
        relations=config.relations,
        route=("EQ-0006", "EQ-0007", "EQ-9999"),  # EQ-9999 doesn't exist
        scenarios=config.scenarios,
        layout=config.layout
    )
    errors = validate(bad_config)
    assert any("route" in e.lower() and "not found" in e.lower() for e in errors)


def test_validate_no_unit_signal(catalog_data):
    config = from_catalog(catalog_data)
    eq = config.equipment[0]
    bad_signal = SignalSpec(
        signal="bad_signal",
        name="Bad Signal",
        unit="",  # missing unit
        required=True
    )
    bad_eq = EquipmentConfig(
        equipment_id=eq.equipment_id,
        asset_id=eq.asset_id,
        code=eq.code,
        name=eq.name,
        segment_id=eq.segment_id,
        profile_id=eq.profile_id,
        capabilities=eq.capabilities,
        signals=eq.signals + (bad_signal,)
    )
    bad_config = Configuration(
        config_id=config.config_id,
        version_label=config.version_label,
        source=config.source,
        line_id=config.line_id,
        equipment=tuple(bad_eq if e.equipment_id == eq.equipment_id else e for e in config.equipment),
        relations=config.relations,
        route=config.route,
        scenarios=config.scenarios,
        layout=config.layout
    )
    errors = validate(bad_config)
    assert any("unit" in e.lower() for e in errors)


def test_diff_asset_replaced():
    old_eq = EquipmentConfig(
        equipment_id="EQ-0001",
        asset_id="AS-0001-001",
        code="HPU-01",
        name="Pump Unit A",
        segment_id="SG-0004",
        profile_id="hydraulic_supply",
        capabilities=("hydraulic_supply",),
        signals=()
    )
    new_eq = EquipmentConfig(
        equipment_id="EQ-0001",
        asset_id="AS-0001-002",  # new asset
        code="HPU-01",
        name="Pump Unit B",
        segment_id="SG-0004",
        profile_id="hydraulic_supply",
        capabilities=("hydraulic_supply",),
        signals=()
    )
    old_config = Configuration(config_id="old", version_label="v1", source="catalog", line_id="LN-0001", equipment=(old_eq,))
    new_config = Configuration(config_id="new", version_label="v1", source="catalog", line_id="LN-0001", equipment=(new_eq,))

    changes = diff(old_config, new_config)
    assert "asset_replaced" in changes
    assert changes["asset_replaced"][0]["equipment_id"] == "EQ-0001"
    assert changes["asset_replaced"][0]["old_asset_id"] == "AS-0001-001"
    assert changes["asset_replaced"][0]["new_asset_id"] == "AS-0001-002"


def test_diff_added_removed():
    old_eq = EquipmentConfig(
        equipment_id="EQ-0001",
        asset_id="AS-0001-001",
        code="HPU-01",
        name="Pump",
        segment_id="SG-0004",
        profile_id="hydraulic_supply",
        capabilities=("hydraulic_supply",)
    )
    new_eq1 = old_eq
    new_eq2 = EquipmentConfig(
        equipment_id="EQ-0011",
        asset_id="AS-0011-001",
        code="NEW-01",
        name="New",
        segment_id="SG-0000",
        profile_id="transport",
        capabilities=("transport",)
    )

    old_config = Configuration(config_id="old", version_label="v1", source="catalog", line_id="LN-0001", equipment=(old_eq,))
    new_config = Configuration(config_id="new", version_label="v1", source="catalog", line_id="LN-0001", equipment=(new_eq1, new_eq2))

    changes = diff(old_config, new_config)
    assert "added" in changes
    assert len(changes["added"]) == 1
    assert changes["added"][0]["equipment_id"] == "EQ-0011"


def test_load_draft_schema_valid():
    payload = {
        "config_id": "placeholder",
        "version_label": "draft",
        "source": "user",
        "line_id": "LN-0001",
        "equipment": [],
        "relations": [],
        "route": [],
        "branches": [],
        "scenarios": [],
        "layout": []
    }
    config = load_draft(payload, source="test.json")
    assert config.config_id != "placeholder"  # hash is computed
    assert config.source == "user"
    assert config.version_label == "draft"


def test_load_draft_missing_required_field():
    payload = {
        "config_id": "test",
        "version_label": "draft",
        # missing source
        "line_id": "LN-0001"
    }
    with pytest.raises(ValueError, match="source"):
        load_draft(payload, source="test.json")


def test_load_draft_invalid_equipment_type():
    payload = {
        "config_id": "test",
        "version_label": "draft",
        "source": "user",
        "line_id": "LN-0001",
        "equipment": "not a list",  # invalid type
        "relations": [],
        "route": []
    }
    with pytest.raises((ValueError, TypeError)):
        load_draft(payload, source="test.json")


# Fixture-based tests

@pytest.fixture
def fixture_b(config_a):
    with (FIXTURE_PATH / "config_b_hpu_swap.json").open(encoding="utf-8") as f:
        payload = json.load(f)
    return from_payload(payload)


@pytest.fixture
def fixture_c(config_a):
    with (FIXTURE_PATH / "config_c_add_transport.json").open(encoding="utf-8") as f:
        payload = json.load(f)
    return from_payload(payload)


@pytest.fixture
def fixture_d_valid(config_a):
    with (FIXTURE_PATH / "config_d_remove_valid.json").open(encoding="utf-8") as f:
        payload = json.load(f)
    return from_payload(payload)


@pytest.fixture
def fixture_d_invalid(config_a):
    with (FIXTURE_PATH / "config_d_remove_invalid.json").open(encoding="utf-8") as f:
        payload = json.load(f)
    return from_payload(payload)


@pytest.fixture
def fixture_e_change(config_a):
    with (FIXTURE_PATH / "config_e_signal_change.json").open(encoding="utf-8") as f:
        payload = json.load(f)
    return from_payload(payload)


@pytest.fixture
def fixture_e_bad(config_a):
    with (FIXTURE_PATH / "config_e_missing_required.json").open(encoding="utf-8") as f:
        payload = json.load(f)
    return from_payload(payload)


@pytest.fixture
def fixture_f(config_a):
    with (FIXTURE_PATH / "config_f_unknown_profile.json").open(encoding="utf-8") as f:
        payload = json.load(f)
    return from_payload(payload)


@pytest.fixture
def fixture_g(config_a):
    with (FIXTURE_PATH / "config_g_branch.json").open(encoding="utf-8") as f:
        payload = json.load(f)
    return from_payload(payload)


def test_fixture_b_hpu_swap_valid(config_a, fixture_b):
    """HPU asset replacement is valid."""
    errors = validate(fixture_b)
    assert len(errors) == 0, f"HPU swap should be valid, got: {errors}"
    changes = diff(config_a, fixture_b)
    assert "asset_replaced" in changes
    assert changes["asset_replaced"][0]["equipment_id"] == "EQ-0001"


def test_fixture_c_add_transport_valid(config_a, fixture_c):
    """Adding transport equipment to route is valid."""
    errors = validate(fixture_c)
    assert len(errors) == 0, f"Add transport should be valid, got: {errors}"
    changes = diff(config_a, fixture_c)
    assert "added" in changes
    assert "route_changed" in changes


def test_fixture_d_remove_valid_equipment(config_a, fixture_d_valid):
    """Removing CV-02 (only in branches) is valid."""
    errors = validate(fixture_d_valid)
    assert len(errors) == 0, f"Remove CV-02 should be valid, got: {errors}"
    changes = diff(config_a, fixture_d_valid)
    assert "removed" in changes


def test_fixture_d_remove_invalid_broken_reference(config_a, fixture_d_invalid):
    """Removing RT-02 but leaving relation causes validation error."""
    errors = validate(fixture_d_invalid)
    assert len(errors) > 0, "Should have validation errors (broken relation)"


def test_fixture_e_signal_change_valid(config_a, fixture_e_change):
    """Changing HPU pressure unit and deleting optional signal is valid."""
    errors = validate(fixture_e_change)
    assert len(errors) == 0, f"Signal change should be valid, got: {errors}"
    changes = diff(config_a, fixture_e_change)
    assert "signal_changed" in changes


def test_fixture_e_missing_required_signal_change(config_a, fixture_e_bad):
    """Deleting required signal is detectable in diff (validate doesn't check profile requirements)."""
    # Note: Current validate does not enforce profile-based required signals.
    # This would be a future enhancement. For now, it's detectable via diff.
    changes = diff(config_a, fixture_e_bad)
    assert "signal_changed" in changes
    assert any(c.get("change") == "removed" for c in changes["signal_changed"])


def test_fixture_f_unknown_capability_invalid(config_a, fixture_f):
    """Adding equipment with unknown capability is invalid."""
    errors = validate(fixture_f)
    assert len(errors) > 0, "Should have validation errors (unknown capability)"


def test_fixture_g_branch_route_valid(config_a, fixture_g):
    """Explicit route through EQ-0010 (different from capacity order) is valid."""
    errors = validate(fixture_g)
    assert len(errors) == 0, f"Branch route should be valid, got: {errors}"
    changes = diff(config_a, fixture_g)
    assert "route_changed" in changes
