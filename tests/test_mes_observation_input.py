"""Current MES facts travel with an ordinary operator question."""

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from shiftlink.agent.response import AgentResponse
from shiftlink.mes.contracts import Measurement
from shiftlink.mes.query import query_service
from shiftlink.mes.server import MesService


class RecordingPipeline:
    def run(self, payload):
        self.payload = payload
        return SimpleNamespace(output=AgentResponse(mode="query", answer="recorded"))


def test_natural_filter_alarm_question_carries_current_mes_facts():
    service = MesService(Path("docs/data/reference/00_plant_and_relations.json"))
    try:
        at = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)
        snapshot = service.engine.snapshot
        current = Measurement("EQ-0001", "hpu_filter_dp", 2.1, "bar", at)
        service.engine._snapshot = replace(
            snapshot,
            simulated_at=at,
            measurements=tuple(m for m in snapshot.measurements
                               if not (m.equipment_id == current.equipment_id and m.signal == current.signal)) + (current,),
            active_alarms=({"equipment_id": "EQ-0001", "code": "AL-HPU-FILTER"},
                           {"equipment_id": "EQ-0004", "code": "AL-GR-HOT"}),
        )
        pipeline = RecordingPipeline()
        result = query_service(service, {"question": "필터 차압 경보가 들어왔는데 어떻게 확인하나요?",
                                         "equipment_id": "EQ-0001"}, pipeline=pipeline)
        payload = pipeline.payload
        observations = {item["signal"]: item for item in payload["observations"]}
        assert payload["question"] == "필터 차압 경보가 들어왔는데 어떻게 확인하나요?"
        assert payload["eq_id"] == "EQ-0001"
        assert observations["hpu_filter_dp"] == {"signal": "hpu_filter_dp", "value": 2.1, "unit": "bar"}
        assert observations["hpu_filter_dp_state"]["value"] == "high"
        assert payload["snapshot_at"] == at.isoformat()
        assert payload["active_alarms"] == ["AL-HPU-FILTER"]
        assert result["evidence"]["alarms"] == ["AL-HPU-FILTER"]
    finally:
        service.storage.close()


def test_range_excursion_does_not_invent_an_active_alarm():
    service = MesService(Path("docs/data/reference/00_plant_and_relations.json"))
    try:
        at = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)
        snapshot = service.engine.snapshot
        current = Measurement("EQ-0001", "hpu_filter_dp", 2.1, "bar", at)
        service.engine._snapshot = replace(snapshot, simulated_at=at, measurements=(current,), active_alarms=())
        pipeline = RecordingPipeline()
        query_service(service, {"question": "필터 차압 경보가 들어왔는데", "equipment_id": "EQ-0001"},
                      pipeline=pipeline)
        observations = {item["signal"]: item for item in pipeline.payload["observations"]}
        assert observations["hpu_filter_dp_state"]["value"] == "high"
        assert pipeline.payload["active_alarms"] == []
    finally:
        service.storage.close()


def test_natural_questions_carry_current_state_across_equipment_types():
    service = MesService(Path("docs/data/reference/00_plant_and_relations.json"))
    cases = (
        ("EQ-0001", "hpu_pressure", "유압 압력이 높아졌는데?"),
        ("EQ-0002", "bus_voltage", "버스 전압이 높아졌는데?"),
        ("EQ-0003", "air_pressure", "압축공기 압력이 높아졌는데?"),
        ("EQ-0005", "gr_brg_temp", "GR-02 베어링 온도가 높아졌는데?"),
        ("EQ-0007", "rt_clamp_press", "RT-02 클램프 압력이 높아졌는데?"),
        ("EQ-0009", "cv_belt_tension", "CV-01 벨트 장력이 높아졌는데?"),
    )
    try:
        at = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)
        for equipment_id, signal, question in cases:
            equipment = next(eq for eq in service.active_config.equipment if eq.equipment_id == equipment_id)
            spec = next(spec for spec in equipment.signals if spec.signal == signal)
            value = spec.normal_max + 1
            service.engine._snapshot = replace(
                service.engine.snapshot, simulated_at=at,
                measurements=(Measurement(equipment_id, signal, value, spec.unit, at),),
                active_alarms=({"equipment_id": "EQ-0004", "code": "AL-OTHER"},),
            )
            pipeline = RecordingPipeline()
            query_service(service, {"question": question, "equipment_id": equipment_id}, pipeline=pipeline)
            observations = {item["signal"]: item for item in pipeline.payload["observations"]}
            assert pipeline.payload["eq_id"] == equipment_id
            assert observations[signal]["value"] == value
            assert observations[signal]["unit"] == spec.unit
            assert observations[f"{signal}_state"]["value"] == "high"
            assert pipeline.payload["active_alarms"] == []
    finally:
        service.storage.close()


if __name__ == "__main__":
    test_natural_filter_alarm_question_carries_current_mes_facts()
    test_range_excursion_does_not_invent_an_active_alarm()
    test_natural_questions_carry_current_state_across_equipment_types()
    print("3 MES observation input checks passed")
