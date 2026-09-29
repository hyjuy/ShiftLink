"""Tool contracts backed by a bound in-memory card provider."""

from typing import Any

from shiftlink.rag.retrieval import InMemoryToolProvider


TOOL_STUBS = (
    "lookup_equipment",
    "search_cards",
    "search_safety_cards",
    "list_handover",
    "propose_handover",
    "get_checklist",
)

_provider: InMemoryToolProvider | None = None


def bind_tool_provider(provider: InMemoryToolProvider | None) -> None:
    """Attach the loader's provider. None clears the binding."""
    global _provider
    _provider = provider


def _provider_or_raise() -> InMemoryToolProvider:
    if _provider is None:
        raise RuntimeError(
            "카드 로더가 연결되지 않았습니다. load_card_provider 후 bind_tool_provider를 호출하세요."
        )
    return _provider


def lookup_equipment(*, equipment_ids: list[str]) -> list[dict[str, Any]]:
    """Return equipment metadata without changing equipment state."""
    return _provider_or_raise().lookup_equipment(equipment_ids=equipment_ids)


def search_cards(
    *,
    query: str,
    equipment_ids: list[str],
    k: int = 5,
    observations: dict[str, object] | None = None,
) -> list[dict[str, Any]]:
    """Return visible knowledge cards or published manual clauses."""
    return _provider_or_raise().search_cards(
        query=query,
        equipment_ids=equipment_ids,
        k=k,
        observations=observations,
    )


def list_handover(
    *, equipment_ids: list[str], shift: str | None = None
) -> list[dict[str, Any]]:
    """Return open handover items without accepting or closing them."""
    return _provider_or_raise().list_handover(equipment_ids=equipment_ids, shift=shift)


def propose_handover(
    *,
    extraction_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """Queue unsaved handover candidates from validated model extraction."""
    return _provider_or_raise().propose_handover(extraction_result=extraction_result)


def get_checklist(*, equipment_ids: list[str]) -> list[dict[str, Any]]:
    """Return applicable checklist rows without recording completion."""
    return _provider_or_raise().get_checklist(equipment_ids=equipment_ids)


def search_safety_cards(
    *,
    equipment_ids: list[str],
    observations: dict[str, object] | None = None,
) -> list[dict[str, Any]]:
    """Return all applicable safety cards (safety_flag=True) regardless of k limit."""
    return _provider_or_raise().search_safety_cards(
        equipment_ids=equipment_ids,
        observations=observations,
    )
