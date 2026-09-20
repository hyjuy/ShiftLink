"""Reference-data loader for the synthetic MES catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Catalog:
    """Read-only indexes over the supplied synthetic plant reference data."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.version = data.get("_meta", {}).get("dataset_version", "unknown")
        self.lines = self._index(data.get("production_lines", []), "line_id")
        self.segments = self._index(data.get("process_segments", []), "segment_id")
        self.equipment = self._index(data.get("equipment", []), "equipment_id")
        self.relations = list(data.get("relations", []))

    @classmethod
    def load(cls, path: str | Path) -> "Catalog":
        with Path(path).open(encoding="utf-8") as source:
            return cls(json.load(source))

    @staticmethod
    def _index(records: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
        indexed = {record[key]: record for record in records}
        if len(indexed) != len(records):
            raise ValueError(f"duplicate {key} in catalog")
        return indexed

    def measurement_point(self, equipment_id: str, signal: str) -> dict[str, Any]:
        try:
            equipment = self.equipment[equipment_id]
        except KeyError as error:
            raise KeyError(f"unknown equipment_id: {equipment_id}") from error
        for point in equipment.get("measurement_points", []):
            if point["signal"] == signal:
                return point
        raise KeyError(f"unknown signal {signal!r} for {equipment_id}")
