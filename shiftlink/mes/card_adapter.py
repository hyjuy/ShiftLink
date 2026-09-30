"""Bridge observable synthetic MES measurements to knowledge-card retrieval."""

from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any

from shiftlink.agent.router import Observation, QueryRequest
from shiftlink.rag.retrieval import InMemoryToolProvider

from .adapters import ObserverAdapter
from .contracts import Configuration


def _timestamp(value: object) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else str(value) if value is not None else None


def _instant(value: object) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            pass
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(timezone.utc)
    return datetime.min.replace(tzinfo=timezone.utc)


class MesCardAdapter:
    """Use only observer-visible values; preserve their source separately."""

    def __init__(self, observer: ObserverAdapter, config: Configuration,
                 cards: InMemoryToolProvider) -> None:
        self.observer, self.config, self.cards = observer, config, cards

    def search(self, run_id: str, equipment: str, question: str, *,
               as_of: datetime | None = None, k: int = 5) -> dict[str, Any]:
        # Class codes select the catalog's -01 installation; explicit codes/IDs
        # select their own installation. Never borrow another installation's values.
        identifier = f"{equipment}-01" if equipment in {"HPU", "GR", "RT", "CV", "PDP", "CAU"} else equipment
        matches = [eq for eq in self.config.equipment
                   if identifier in (eq.equipment_id, eq.code) and eq.active]
        if len(matches) != 1:
            raise ValueError(f"unknown or ambiguous MES equipment: {equipment}")
        eq = matches[0]
        observed = self.observer.observations(run_id, as_of=as_of)
        if observed.get("config_id") not in (None, self.config.config_id):
            raise ValueError("MES run configuration differs from signal catalog")
        snapshot = observed.get("snapshot") or {}
        specs = {spec.signal: spec for spec in eq.signals}
        latest: dict[str, dict[str, Any]] = {}
        for reading in snapshot.get("measurements", []):
            if reading.get("equipment_id") != eq.equipment_id or reading.get("signal") not in specs:
                continue
            signal = reading["signal"]
            if signal not in latest or _instant(reading.get("observed_at")) >= _instant(latest[signal].get("observed_at")):
                latest[signal] = reading

        observations: list[Observation] = []
        evidence = []
        for signal, reading in latest.items():
            spec = specs[signal]
            value = reading.get("value")
            valid = (reading.get("quality") == "good" and reading.get("unit") == spec.unit
                     and isinstance(value, (int, float)) and not isinstance(value, bool)
                     and isfinite(value) and (spec.unit != "bool" or value in (0, 1)))
            evidence.append({
                "equipment_id": eq.equipment_id, "signal": signal,
                "value": value, "unit": reading.get("unit"),
                "quality": reading.get("quality"),
                "observed_at": _timestamp(reading.get("observed_at")),
                "used_for_conditions": valid,
            })
            if not valid:
                continue
            observations.append(Observation(signal=signal, value=value, unit=spec.unit))
            if spec.normal_min is not None and value < spec.normal_min:
                state = "low"
            elif spec.normal_max is not None and value > spec.normal_max:
                state = "high"
            elif spec.normal_min is not None or spec.normal_max is not None:
                state = "normal"
            else:
                continue
            observations.append(Observation(signal=f"{signal}_state", value=state))

        request = QueryRequest(question=question, line_id=snapshot.get("line_id") or self.config.line_id,
                               eq_id=eq.equipment_id, observations=observations, k=k)
        values = {item.signal: {"value": item.value, "unit": item.unit}
                  for item in request.observations}
        safety = self.cards.search_safety_cards(equipment_ids=[eq.equipment_id], observations=values)
        ranked = self.cards.search_cards(query=question, equipment_ids=[eq.equipment_id],
                                         k=k, observations=values)
        cards = list({card["card_id"]: card for card in safety + ranked}.values())
        alarms = sorted({alarm["code"] for alarm in snapshot.get("active_alarms", [])
                         if alarm.get("equipment_id") == eq.equipment_id and alarm.get("code")})
        source = {"run_id": run_id, "equipment_id": eq.equipment_id, "equipment_code": eq.code,
                  "simulated_at": _timestamp(snapshot.get("simulated_at")),
                  "measurements": evidence, "alarms": alarms}
        unverified = [card["card_id"] for card in cards if card["condition_status"] == "unverified"]
        # The same source record can be attached to an answer or copied to a handover.
        answer = {"card_ids": [card["card_id"] for card in cards
                               if card["condition_status"] == "verified"],
                  "unverified_card_ids": unverified, "evidence": source}
        return {"request": request, "cards": cards, "unverified_card_ids": unverified,
                "component_codes": {}, "evidence": source, "answer": answer,
                "handover_record": answer.copy()}
