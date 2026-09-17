import pytest
from pydantic import ValidationError

from shiftlink.agent.schemas import Condition
from shiftlink.rag.extraction import ExtractionResult, SourceSpan, Withdrawal


def test_extraction_v0_request_condition_negation() -> None:
    span = SourceSpan(start=0, end=20, text="압력이 10 이상이면 정지")

    result = ExtractionResult(
        extraction_id="EX-0001",
        source_id="EV-0001",
        request="압력 초과 시 설비 정지",
        conditions=[Condition(signal="pressure", op=">=", value=10)],
        negations=[],
        source_span=span,
    )
    assert result.withdrawn is False
    assert result.conditions[0].signal == "pressure"


def test_extraction_withdrawal_requires_payload() -> None:
    span = SourceSpan(start=0, end=5, text="철회함")
    with pytest.raises(ValidationError):
        ExtractionResult(
            extraction_id="EX-0002",
            source_id="EV-0001",
            request="요청 취소",
            withdrawn=True,
            source_span=span,
        )

    result = ExtractionResult(
        extraction_id="EX-0003",
        source_id="EV-0001",
        request="요청 취소",
        withdrawn=True,
        withdrawal=Withdrawal(reason="담당자 정정", span=span),
        source_span=span,
    )
    assert result.withdrawal is not None
