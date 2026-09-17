"""F-02 추출 스키마 v0: 원문에서 요청·조건·부정·철회를 추출한 결과."""

from pydantic import BaseModel, Field, model_validator

from shiftlink.agent.schemas import Condition


class SourceSpan(BaseModel):
    start: int
    end: int
    text: str


class Negation(BaseModel):
    target: str
    scope: str | None = None
    span: SourceSpan


class Withdrawal(BaseModel):
    reason: str
    span: SourceSpan


class ExtractionResult(BaseModel):
    extraction_id: str = Field(pattern=r"^EX-\d{4}$")
    source_id: str
    request: str
    conditions: list[Condition] = Field(default_factory=list)
    negations: list[Negation] = Field(default_factory=list)
    withdrawn: bool = False
    withdrawal: Withdrawal | None = None
    source_span: SourceSpan

    @model_validator(mode="after")
    def validate_withdrawal(self) -> "ExtractionResult":
        if self.withdrawn and self.withdrawal is None:
            raise ValueError("withdrawn=True requires withdrawal")
        if not self.withdrawn and self.withdrawal is not None:
            raise ValueError("withdrawal set but withdrawn=False")
        return self
