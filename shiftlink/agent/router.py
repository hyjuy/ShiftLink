"""Input-shape router for query and handover requests."""

from typing import Annotated, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


Mode = Literal["query", "handover"]
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: NonBlank
    line_id: NonBlank
    eq_id: NonBlank
    observations: list[dict[str, object]] = Field(default_factory=list)
    scope_id: NonBlank | None = None
    source_kind: Literal["card", "clause"] = "card"
    k: int = Field(default=5, ge=1, le=5)


class HandoverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memo_text: NonBlank
    shift: Literal["A", "B", "C"]
    eq_ids: list[NonBlank] = Field(min_length=1)


class RoutedRequest(BaseModel):
    mode: Mode
    request: QueryRequest | HandoverRequest


def route_request(payload: Mapping[str, object]) -> RoutedRequest:
    """Route by mutually exclusive format keys, never by natural-language intent."""
    # The wire format is the discriminant: identical Korean wording must not alter routing.
    has_question = "question" in payload
    has_memo = "memo_text" in payload
    # Reject omitted and ambiguous formats before Pydantic validates mode-specific fields.
    if has_question == has_memo:
        raise ValueError("request must contain exactly one of 'question' or 'memo_text'")

    if has_question:
        # `extra=forbid` on QueryRequest prevents handover-only fields from leaking in.
        return RoutedRequest(mode="query", request=QueryRequest.model_validate(payload))
    return RoutedRequest(mode="handover", request=HandoverRequest.model_validate(payload))
