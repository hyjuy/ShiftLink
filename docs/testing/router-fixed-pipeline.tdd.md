# Router and fixed pipeline TDD evidence

## Feature contract

- A payload containing `question` is query mode.
- A payload containing `memo_text` is handover mode.
- Both keys or neither key is rejected; natural-language keywords never select a mode.
- The pipeline order is route → fixed read-only tools → one model call → output validation.
- The five tool contracts are `lookup_equipment`, `search_cards`, `list_handover`,
  `propose_handover`, and `get_checklist`. Their current implementations are explicit stubs.

## Evidence

| Stage | Command | Result |
| --- | --- | --- |
| RED | `uv run --python 3.10 --with-requirements requirements.txt python -m pytest tests/test_router_pipeline.py -q` | Collection failed with `ModuleNotFoundError: No module named 'shiftlink.agent.pipeline'` |
| GREEN | Same focused command | `7 passed in 0.28s` |
| Regression and coverage | `uv run --python 3.10 --with-requirements requirements.txt --with pytest-cov python -m pytest -q --cov=shiftlink.agent.router --cov=shiftlink.agent.pipeline --cov=shiftlink.agent.tools --cov-report=term-missing` | `11 passed in 0.66s`; all three new modules 100%, 100% total |

## Guarantees

| What is guaranteed | Test type | Test target |
| --- | --- | --- |
| Input shape, not Korean wording, determines query or handover mode | Unit | `test_router_uses_input_shape_instead_of_text_keywords` |
| Missing, ambiguous, blank, and invalid-shift input is rejected | Unit | `test_router_rejects_missing_ambiguous_or_invalid_formats` |
| Query tools run in fixed order before exactly one model call | Integration | `test_query_pipeline_has_fixed_tool_order_and_one_model_call` |
| Handover adds an unsaved proposal before exactly one model call | Integration | `test_handover_pipeline_adds_proposal_before_one_model_call` |
| All five declared tools are non-persisting stubs | Unit | `test_five_read_only_tool_stubs_are_explicitly_unimplemented` |

## Known gap

Storage, retrieval, model, and response-schema validation adapters are intentionally outside this
pipeline skeleton. They are injected through the existing interfaces when implemented.
