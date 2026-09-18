"""Tool contracts. Storage-backed implementations are added later."""

from typing import Any, Literal


TOOL_STUBS = (
    "lookup_equipment",
    "search_cards",
    "list_handover",
    "propose_handover",
    "get_checklist",
)


def lookup_equipment(*, equipment_ids: list[str]) -> list[dict[str, Any]]:
    """Return equipment metadata without changing equipment state."""
    raise NotImplementedError("lookup_equipment storage adapter is not implemented")


def search_cards(
    *,
    query: str,
    equipment_ids: list[str],
    scope_id: str | None = None,
    source_kind: Literal["card", "clause"] = "card",
    k: int = 5,
) -> list[dict[str, Any]]:
    """Return visible knowledge cards or published manual clauses."""
    raise NotImplementedError("search_cards retrieval adapter is not implemented")


def list_handover(
    *, equipment_ids: list[str], shift: str | None = None
) -> list[dict[str, Any]]:
    """Return open handover items without accepting or closing them."""
    raise NotImplementedError("list_handover storage adapter is not implemented")


def propose_handover(
    *,
    extraction_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """Queue unsaved handover candidates from validated model extraction."""
    raise NotImplementedError("propose_handover adapter is not implemented")


def get_checklist(*, equipment_ids: list[str]) -> list[dict[str, Any]]:
    """Return applicable checklist rows without recording completion."""
    raise NotImplementedError("get_checklist storage adapter is not implemented")
