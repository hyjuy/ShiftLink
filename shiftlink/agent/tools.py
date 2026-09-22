"""Tool contracts. Storage-backed implementations are added later.

This module is the integration surface, not an implementation: every stub
deliberately fails until a storage adapter is wired (개발계획 §2 "도구 5종:
계약만 존재하며 모두 NotImplementedError").

What the contract fixes (통합본 v1.1 §4.8 도구 표, 계약 §4.1):
- Six tools, all **read only**. Registration only ever goes as far as a
  "후보 제안"; nothing here writes, accepts, or closes anything (3.1, 4.12).
- `safety.escalate` is not a tool (forced safety-card exposure + UI wording),
  `incident.create` is out of MVP scope, and `mes.write` needs human approval
  and an allowlist after MVP. A provider that exposes them breaks the contract.
- Card retrieval is capped at k ≤ 5; safety retrieval ignores k and returns
  every applicable card (4.8, D-26).

`TOOL_SPECS` carries the documented table so code and 4.8 can be checked
against each other, `verify_tool_provider` checks an adapter before it is
wired, and `check_tool_output` reports rows that miss documented fields.
"""

import inspect
import re
from dataclasses import dataclass
from typing import Any, Mapping

# 4.8 발열·지연 대응: 검색 결과 k ≤ 5.
MAX_K = 5


@dataclass(frozen=True)
class ToolSpec:
    """One row of the 4.8 tool table, as data."""

    name: str
    inputs: tuple[str, ...]
    storage: str
    optional_inputs: tuple[str, ...] = ()
    # Only filled where the field names are already fixed in code. Empty means
    # the documented output ("정식명·공정·관련 카드 ID" 등) has no settled field
    # names yet — they are not invented here.
    output_fields: tuple[str, ...] = ()
    read_only: bool = True
    note: str = ""

    @property
    def accepted_inputs(self) -> tuple[str, ...]:
        return self.inputs + self.optional_inputs


# Card rows carry the documented "카드 ID·본문·조건·등급". The 점수(score) field
# from 4.8 is not produced yet (ranking is deterministic token overlap), so it
# is not asserted here.
_CARD_OUTPUT_FIELDS = ("card_id", "know_how", "conditions", "grade")

TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="lookup_equipment",
        inputs=("equipment_ids",),
        storage="설비 사전 JSON",
        note="출력은 정식명·공정·관련 카드 ID. 필드명 미확정 [제안 단계]",
    ),
    ToolSpec(
        name="search_cards",
        inputs=("query", "equipment_ids"),
        optional_inputs=("k",),
        storage="sqlite-vec",
        output_fields=_CARD_OUTPUT_FIELDS,
        note=(
            "k ≤ 5. 4.8의 '유형 필터'와 점수 필드, 레지스트리의 scope_id·source_kind는 "
            "미결이라 시그니처에 넣지 않는다"
        ),
    ),
    ToolSpec(
        name="search_safety_cards",
        inputs=("equipment_ids",),
        optional_inputs=("observations",),
        storage="sqlite-vec (safety_flag=True 전수)",
        output_fields=_CARD_OUTPUT_FIELDS + ("safety_flag", "safety_basis"),
        note="D-26: top-k와 무관한 독립 전수 조회. 조건 판정은 §4.2",
    ),
    ToolSpec(
        name="list_handover",
        inputs=("equipment_ids",),
        optional_inputs=("shift",),
        storage="인계 CSV/JSON",
        note="미종료 인계 항목 조회만. 수락·종료는 도구 범위 밖 [필드명 미확정]",
    ),
    ToolSpec(
        name="propose_handover",
        inputs=("extraction_result",),
        storage="검토 큐",
        note="등록 후보(수락 대기)만 반환하고 저장하지 않는다 (3.4 F-04)",
    ),
    ToolSpec(
        name="get_checklist",
        inputs=("equipment_ids",),
        storage="체크리스트 JSON",
        note="4.8의 '작업 유형' 입력은 미결이라 시그니처에 넣지 않는다 [필드명 미확정]",
    ),
)

TOOL_STUBS = tuple(spec.name for spec in TOOL_SPECS)
# This declares the integration surface only; each stub deliberately fails until wired.

SPEC_BY_NAME = {spec.name: spec for spec in TOOL_SPECS}

# 4.8 codex 8.2 대응: 채택하지 않기로 한 도구와 그 사유. 이름이 바뀌어도 잡히도록
# 후보 표기를 함께 둔다.
EXCLUDED_TOOLS: dict[str, str] = {
    "safety_escalate": "도구 호출이 아니라 safety_flag 카드 강제 선두 노출 + 호출 조건 문구(UI)로 구현",
    "escalate": "safety.escalate와 동일 — 도구로 만들지 않는다",
    "incident_create": "MVP 제외",
    "create_incident": "MVP 제외",
    "mes_write": "MVP 이후 인간 승인·허용 목록 전제로 별도 검토",
    "write_mes": "MVP 이후 인간 승인·허용 목록 전제로 별도 검토",
}

# A read-only surface must not expose state-changing entry points (3.1, 4.12).
_WRITE_METHOD_RE = re.compile(
    r"^(create|update|delete|remove|insert|write|save|store|commit|apply|put|post|patch"
    r"|accept|approve|close|execute)(_|$)"
)


def lookup_equipment(*, equipment_ids: list[str]) -> list[dict[str, Any]]:
    """Return equipment metadata without changing equipment state."""
    raise NotImplementedError("lookup_equipment storage adapter is not implemented")


def search_cards(
    *,
    query: str,
    equipment_ids: list[str],
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
    # Candidate generation is post-validation, so it is not a pre-model retrieval tool.
    raise NotImplementedError("propose_handover adapter is not implemented")


def get_checklist(*, equipment_ids: list[str]) -> list[dict[str, Any]]:
    """Return applicable checklist rows without recording completion."""
    raise NotImplementedError("get_checklist storage adapter is not implemented")


def search_safety_cards(
    *,
    equipment_ids: list[str],
    observations: dict[str, object] | None = None,
) -> list[dict[str, Any]]:
    """Return all applicable safety cards (safety_flag=True) regardless of k limit."""
    raise NotImplementedError("search_safety_cards retrieval adapter is not implemented")


def verify_tool_provider(provider: Any) -> list[str]:
    """
    Check an adapter against the 4.8 contract before it is wired in.

    Returns "[code] message" strings (empty when the provider conforms):
    - tool_missing / tool_not_callable: one of the six tools is absent.
    - tool_input_unsupported: a documented input is not accepted.
    - excluded_tool_exposed: safety.escalate / incident.create / mes.write.
    - write_capable_method: a state-changing entry point on a read-only surface.

    Runtime values (k ≤ 5, condition matching) are not checked here — the
    pipeline and §4.2 own those.
    """
    errors: list[str] = []

    for spec in TOOL_SPECS:
        tool = getattr(provider, spec.name, None)
        if tool is None:
            errors.append(f"[tool_missing] {spec.name} is not provided")
            continue
        if not callable(tool):
            errors.append(f"[tool_not_callable] {spec.name} is not callable")
            continue
        missing = _unsupported_inputs(tool, spec.accepted_inputs)
        if missing:
            errors.append(
                f"[tool_input_unsupported] {spec.name} does not accept {missing}"
            )

    for name, reason in EXCLUDED_TOOLS.items():
        if callable(getattr(provider, name, None)):
            errors.append(f"[excluded_tool_exposed] {name} is out of scope — {reason}")

    for name in dir(provider):
        if name.startswith("_") or name in SPEC_BY_NAME:
            continue
        if _WRITE_METHOD_RE.match(name) and callable(getattr(provider, name, None)):
            errors.append(
                f"[write_capable_method] {name} looks state-changing; tools are read only"
            )

    return errors


def _unsupported_inputs(tool: Any, expected: tuple[str, ...]) -> list[str]:
    try:
        parameters = inspect.signature(tool).parameters
    except (TypeError, ValueError):
        return []  # Builtin or C-level callable: nothing to check.
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values()):
        return []
    return [name for name in expected if name not in parameters]


def check_tool_output(name: str, rows: Any) -> list[str]:
    """
    Report rows that miss the documented output fields (4.8 도구 표).

    Only tools whose field names are already fixed are checked; the rest carry
    `[필드명 미확정]` in their spec and are skipped rather than guessed at.
    """
    spec = SPEC_BY_NAME.get(name)
    if spec is None or not spec.output_fields:
        return []
    if not isinstance(rows, list):
        return [f"[tool_output_not_a_list] {name} returned {type(rows).__name__}"]

    missing: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            return [f"[tool_output_row_not_a_mapping] {name} row is {type(row).__name__}"]
        for required in spec.output_fields:
            if required not in row and required not in missing:
                missing.append(required)
    if missing:
        return [f"[tool_output_field_missing] {name} rows are missing {missing}"]
    return []
