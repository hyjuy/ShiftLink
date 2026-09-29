"""MES observations must reach card retrieval without invented evidence."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

import pytest
from pydantic import ValidationError

from shiftlink.agent.schemas import Condition, KnowledgeCard
from shiftlink.mes.card_adapter import MesCardAdapter
from shiftlink.mes.adapters import ObserverAdapter
from shiftlink.mes.configuration import from_catalog
from shiftlink.mes.contracts import GroundTruth, Measurement, Run, Snapshot
from shiftlink.mes.storage import MesStorage
from shiftlink.rag.retrieval import InMemoryToolProvider


ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "docs/data/reference/00_plant_and_relations.json").read_text(encoding="utf-8"))
CARDS = json.loads((ROOT / "docs/data/knowledge_cards/kb/20260929-A/cards.json").read_text(encoding="utf-8"))
AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


class Observer:
    def __init__(self, measurements):
        self.measurements = measurements

    def observations(self, run_id, *, as_of=None):
        return {"run_id": run_id, "snapshot": {
            "line_id": "LN-0001", "simulated_at": AT, "measurements": self.measurements,
            "active_alarms": [{"equipment_id": "EQ-0004", "code": "AL-GR-HOT"}],
        }, "ground_truth": "SECRET"}


def measurement(value=85, quality="good", unit="degC", signal="gr_brg_temp", equipment_id="EQ-0004"):
    return dict(equipment_id=equipment_id, signal=signal, value=value, unit=unit,
                quality=quality, observed_at=AT)


def adapter(measurements):
    config = from_catalog(CATALOG)
    cards = [KnowledgeCard.model_validate(c) for c in CARDS if c["card_id"] in ("K-1024", "K-1025", "K-1006")]
    next(card for card in cards if card.card_id == "K-1025").conditions = [
        Condition(signal="gr_brg_temp_state", op="==", value="high")]
    provider = InMemoryToolProvider(cards, equipment_db=CATALOG["equipment"], equipment_types=CATALOG["equipment_types"])
    return MesCardAdapter(Observer(measurements), config, provider)


def test_high_boundary_and_other_equipment():
    subject = adapter([measurement(), measurement(200, equipment_id="EQ-0005")])
    result = subject.search("run", "GR", "bearing temperature")
    assert result["request"].eq_id == "EQ-0004"
    assert {o.signal: o.value for o in result["request"].observations}["gr_brg_temp_state"] == "high"
    assert next(c for c in result["cards"] if c["card_id"] == "K-1025")["condition_status"] == "verified"
    assert "SECRET" not in str(result)
    assert result["evidence"]["alarms"] == ["AL-GR-HOT"]
    assert result["evidence"]["measurements"][0]["observed_at"] == AT.isoformat()

    boundary = adapter([measurement(62)]).search("run", "GR-01", "bearing temperature")
    assert {o.signal: o.value for o in boundary["request"].observations}["gr_brg_temp_state"] == "normal"
    assert "K-1025" not in [c["card_id"] for c in boundary["cards"]]


@pytest.mark.parametrize("readings", [[], [measurement(quality="bad")], [measurement(unit="F")]])
def test_missing_bad_quality_or_wrong_unit_stays_unverified(readings):
    result = adapter(readings).search("run", "GR-01", "bearing temperature")
    assert not result["request"].observations
    assert next(c for c in result["cards"] if c["card_id"] == "K-1025")["condition_status"] == "unverified"
    assert "K-1025" in result["unverified_card_ids"]


def test_unknown_component_is_not_mapped():
    result = adapter([measurement()]).search("run", "GR-01", "bearing temperature")
    assert result["component_codes"] == {}


def test_existing_safety_card_stays_first():
    result = adapter([]).search("run", "HPU", "safety")
    assert result["cards"][0]["card_id"] == "K-1006"


def test_installation_specific_card_does_not_cross_to_second_gearbox():
    subject = adapter([measurement(equipment_id="EQ-0005")])
    card = next(c for c in subject.cards.cards if c.card_id == "K-1025")
    card.mes_equipment_id = "EQ-0004"
    assert any(c["card_id"] == "K-1025" for c in subject.search("run", "GR-01", "temperature")["cards"])
    assert all(c["card_id"] != "K-1025" for c in subject.search("run", "GR-02", "temperature")["cards"])


@pytest.mark.parametrize("field", ["mes_equipment_id", "mes_component_code"])
def test_blank_mes_mapping_is_rejected(field):
    raw = next(c for c in CARDS if c["card_id"] == "K-1025").copy()
    raw[field] = "  "
    with pytest.raises(ValidationError):
        KnowledgeCard.model_validate(raw)


def test_card_condition_unit_mismatch_is_unverified():
    subject = adapter([measurement()])
    card = next(c for c in subject.cards.cards if c.card_id == "K-1025")
    card.conditions = [Condition(signal="gr_brg_temp", op=">", value=80, unit="degF")]
    result = subject.search("run", "GR-01", "temperature")
    assert next(c for c in result["cards"] if c["card_id"] == "K-1025")["condition_status"] == "unverified"


def test_derived_state_has_no_physical_unit():
    subject = adapter([measurement()])
    card = next(c for c in subject.cards.cards if c.card_id == "K-1025")
    card.conditions = [Condition(signal="gr_brg_temp_state", op="==", value="high", unit="degC")]
    result = subject.search("run", "GR-01", "temperature")
    assert next(c for c in result["cards"] if c["card_id"] == "K-1025")["condition_status"] == "unverified"


@pytest.mark.parametrize("equipment", ["PDP", "CAU"])
def test_catalog_only_equipment_classes_stay_unsupported(equipment):
    with pytest.raises(ValueError, match="equipment"):
        adapter([]).search("run", equipment, "status")


def test_latest_reading_uses_absolute_time():
    earlier = measurement(85)
    earlier["observed_at"] = datetime(2026, 1, 1, 10, tzinfo=timezone(timedelta(hours=9)))
    later = measurement(62)
    later["observed_at"] = datetime(2026, 1, 1, 2, tzinfo=timezone.utc)
    result = adapter([earlier, later]).search("run", "GR-01", "temperature")
    assert {o.signal: o.value for o in result["request"].observations}["gr_brg_temp_state"] == "normal"


def test_real_observer_and_full_card_batch_preserve_safety_and_existing_conditions():
    config = from_catalog(CATALOG)
    cards = [KnowledgeCard.model_validate(card) for card in CARDS]
    provider = InMemoryToolProvider(cards, equipment_db=CATALOG["equipment"],
                                    equipment_types=CATALOG["equipment_types"])
    store = MesStorage()
    try:
        run = Run("real-run", 1, AT, config_id=config.config_id)
        store.create_run(run)
        store.save_tick(Snapshot(run.run_id, 0, AT, config.line_id, "running", "normal",
                                 measurements=(Measurement("EQ-0004", "gr_brg_temp", 85, "degC", AT),)))
        store.save_ground_truth(GroundTruth(run.run_id, "SECRET", AT, "impact", "action"))
        subject = MesCardAdapter(ObserverAdapter(store), config, provider)
        gr = subject.search(run.run_id, "GR", "감속기")
        hpu = subject.search(run.run_id, "HPU", "유압")
        assert "SECRET" not in str(gr)
        assert {o.signal: o.value for o in gr["request"].observations}["gr_brg_temp_state"] == "high"
        all_gr = provider.search_cards(query="감속기", equipment_ids=["EQ-0004"], k=30,
                                       observations={"gr_brg_temp_state": "high"})
        all_hpu = provider.search_cards(query="유압", equipment_ids=["EQ-0001"], k=30)
        assert next(c for c in all_gr if c["card_id"] == "K-1029")["condition_status"] == "unverified"
        assert next(c for c in all_hpu if c["card_id"] == "K-1007")["condition_status"] == "unverified"
        assert hpu["cards"][0]["safety_flag"] is True
        assert any(not c["safety_flag"] for c in hpu["cards"])
    finally:
        store.close()
