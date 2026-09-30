"""Load knowledge-card JSON into InMemoryToolProvider."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from shiftlink.agent.schemas import KnowledgeCard
from shiftlink.rag.retrieval import KB_MIN_TOP_RELEVANCE, InMemoryToolProvider

_CARD_KEYS = ("knowledge_cards", "cards")
_STORE_KEYS = {
    "equipment": "equipment_db",
    "equipment_types": "equipment_types",
    "handover": "handover_db",
    "checklist": "checklist_db",
}
PLANT_CATALOG = Path(__file__).resolve().parents[2] / "docs/data/reference/00_plant_and_relations.json"


@dataclass(frozen=True)
class CardLoad:
    """Cards parsed from disk and the provider that kept the KB subset."""

    provider: InMemoryToolProvider
    seen: int

    @property
    def loaded(self) -> int:
        return len(self.provider.cards)


def load_card_provider(
    path: str | Path, *, include_draft: bool = False, min_top_relevance: int = KB_MIN_TOP_RELEVANCE,
    catalog: str | Path | None = PLANT_CATALOG,
) -> CardLoad:
    """Read a card JSON file or a directory of them.

    A file may be a card object, a list of cards, or an object with
    ``knowledge_cards`` or ``cards``. Optional ``equipment``,
    ``equipment_types``, ``handover``, and ``checklist`` lists are passed
    through to the provider. When the card files carry no equipment rows,
    ``equipment``/``equipment_types`` come from ``catalog`` so installation
    codes (HPU-01) and IDs (EQ-0001) resolve. Only accepted/kb/L1 cards stay loaded,
    unless ``include_draft`` is set, which also keeps draft/kb cards.
    ``min_top_relevance`` is the KB "no matching card" floor; pass 0 to always rank.
    """
    root = Path(path)
    files = _json_files(root)
    cards: list[KnowledgeCard] = []
    stores: dict[str, list[Any]] = {name: [] for name in _STORE_KEYS.values()}
    evidence: dict[str, str] = {}
    for file in files:
        file_cards, file_stores = _read_file(file)
        cards.extend(file_cards)
        evidence.update(file_stores.pop("evidence_text", {}))
        for name, rows in file_stores.items():
            stores[name].extend(rows)
    if catalog is not None and not stores["equipment_db"] and not stores["equipment_types"]:
        plant = json.loads(Path(catalog).read_text(encoding="utf-8"))
        stores["equipment_db"] = plant["equipment"]
        stores["equipment_types"] = plant["equipment_types"]
    provider = InMemoryToolProvider(cards=cards, include_draft=include_draft,
                                    min_top_relevance=min_top_relevance, evidence_text=evidence, **stores)
    return CardLoad(provider=provider, seen=len(cards))


def _json_files(path: Path) -> list[Path]:
    if path.is_dir():
        files = sorted(item for item in path.glob("*.json") if item.is_file())
        if not files:
            raise ValueError(f"{path}: 카드 JSON 파일이 없습니다")
        return files
    if not path.is_file():
        raise ValueError(f"{path}: 카드 JSON 경로가 없습니다")
    return [path]


def _read_file(path: Path) -> tuple[list[KnowledgeCard], dict[str, list[Any]]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: JSON 파싱 실패: {exc}") from exc
    items, stores = _card_items(data, path)
    cards = []
    for index, item in enumerate(items):
        try:
            cards.append(KnowledgeCard.model_validate(item))
        except ValidationError as exc:
            label = item.get("card_id") if isinstance(item, dict) else index
            raise ValueError(f"{path}: 카드 {label} 검증 실패: {exc}") from exc
    return cards, stores


def _card_items(data: Any, source: Path) -> tuple[list[Any], dict[str, list[Any]]]:
    if isinstance(data, list):
        return data, {}
    if isinstance(data, dict) and "card_id" in data:
        return [data], {}
    if isinstance(data, dict):
        for key in _CARD_KEYS:
            if key not in data:
                continue
            items = data[key]
            if not isinstance(items, list):
                raise ValueError(f"{source}: {key}는 목록이어야 합니다")
            stores = {}
            for raw_key, field in _STORE_KEYS.items():
                if raw_key not in data:
                    continue
                rows = data[raw_key]
                if not isinstance(rows, list):
                    raise ValueError(f"{source}: {raw_key}는 목록이어야 합니다")
                stores[field] = rows
            if isinstance(data.get("evidence_text"), dict):  # kb_cards.json: T4 evidence-event text
                stores["evidence_text"] = data["evidence_text"]
            return items, stores
    raise ValueError(f"{source}: 카드 목록을 찾을 수 없습니다")
