"""Input-shape router for query and handover requests.

Contract (통합본 v1.1 §4.8 에이전트 구조 1단계, 계약 §4):
- The router is rule-based and makes **no model call**.
- Routing is decided by the wire format only. 4.8 also mentions keywords, but
  intent words are deliberately not used: identical Korean wording must not
  change the mode, and the routing test pins that down. Recorded as a wording
  deviation in docs/design/D26-29_계약_v1.0.md §4.7.
- This is the trust boundary for model-facing input. Malformed observations are
  rejected here rather than silently degraded, because §4.2 condition matching
  decides whether a safety card applies.
- Mode-specific fields never leak across modes (`extra="forbid"`).

Both request types expose the same accessors (`equipment_ids`, `search_text`,
`k`, `shift`, `observation_map()`) so the fixed pipeline does not need to know
which mode-specific field name holds what.
"""

from typing import Annotated, Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from shiftlink.agent.tools import MAX_K

Mode = Literal["query", "handover"]
Shift = Literal["A", "B", "C"]
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# The wire format is the discriminant: exactly one of these keys must be present.
FORMAT_KEYS: dict[str, Mode] = {"question": "query", "memo_text": "handover"}


class Observation(BaseModel):
    """
    One observed signal (§4.2 조건 판정 입력).

    ``value`` is required: a record without a value is not an observation, and
    letting it through as ``None`` would silently turn a definite condition into
    an unverified one. Report nothing instead of reporting an empty reading.
    """

    model_config = ConfigDict(extra="forbid")

    signal: NonBlank
    value: Any
    unit: str | None = None


def _deduplicate(values: list[str]) -> list[str]:
    """Order-preserving unique, so one equipment is not looked up twice."""
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: NonBlank
    line_id: NonBlank
    eq_id: NonBlank
    observations: list[Observation] = Field(default_factory=list)
    k: int = Field(default=MAX_K, ge=1, le=MAX_K)

    @model_validator(mode="after")
    def reject_duplicate_signals(self) -> "QueryRequest":
        # A repeated signal would silently overwrite the earlier reading and
        # could flip a safety card's condition from False to True.
        signals = [obs.signal for obs in self.observations]
        duplicates = sorted({s for s in signals if signals.count(s) > 1})
        if duplicates:
            raise ValueError(f"duplicate observation signals: {duplicates}")
        return self

    @property
    def equipment_ids(self) -> list[str]:
        return [self.eq_id]

    @property
    def search_text(self) -> str:
        return self.question

    @property
    def shift(self) -> None:
        """Query mode has no shift; handover lookup is not part of it."""
        return None

    def observation_map(self) -> dict[str, Any]:
        """Signal → value map for §4.2 condition matching."""
        return {obs.signal: obs.value for obs in self.observations}


class HandoverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memo_text: NonBlank
    shift: Shift
    eq_ids: list[NonBlank] = Field(min_length=1)

    @property
    def equipment_ids(self) -> list[str]:
        return _deduplicate(self.eq_ids)

    @property
    def search_text(self) -> str:
        return self.memo_text

    @property
    def k(self) -> int:
        """Handover mode takes no k; the 4.8 cap applies."""
        return MAX_K

    def observation_map(self) -> dict[str, Any]:
        """Handover input carries no readings — conditions stay unverified."""
        return {}


class RoutedRequest(BaseModel):
    mode: Mode
    request: QueryRequest | HandoverRequest
    # 4.12: the rule router's decision is recorded, not just its result.
    route_reason: str = ""


def route_request(payload: Mapping[str, object]) -> RoutedRequest:
    """Route by mutually exclusive format keys, never by natural-language intent."""
    if not isinstance(payload, Mapping):
        raise ValueError(
            f"[route_payload_invalid] request must be a mapping, got {type(payload).__name__}"
        )

    # Reject omitted and ambiguous formats before Pydantic validates mode-specific fields.
    present = [key for key in FORMAT_KEYS if key in payload]
    if len(present) != 1:
        raise ValueError(
            "[route_format_ambiguous] request must contain exactly one of "
            f"'question' or 'memo_text' (found {present or 'none'})"
        )

    key = present[0]
    mode = FORMAT_KEYS[key]
    # `extra=forbid` on both models prevents the other mode's fields leaking in.
    model = QueryRequest if mode == "query" else HandoverRequest
    return RoutedRequest(
        mode=mode,
        request=model.model_validate(payload),
        route_reason=f"format key '{key}'",
    )
