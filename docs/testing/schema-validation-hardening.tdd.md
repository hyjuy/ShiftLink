# Schema validation hardening — 2026-09-22

Scope: the three validation gaps identified in the schema review; no separate plan file.

| Guarantee | Regression test in `tests/test_schemas.py` |
|---|---|
| All six supported comparison operators remain valid | `test_condition_accepts_supported_operators` |
| Unsupported operators fail at the schema boundary | `test_condition_rejects_unsupported_operators` |
| Whitespace-only safety basis and symptom are rejected; non-T3 cards reject even empty steps | `test_card_rejects_validation_loopholes` |

RED: `python -m pytest tests/test_schemas.py -q -p no:cacheprovider --tb=short` produced **7 failed, 16 passed** before the schema changes. All seven failures were missing expected `ValidationError` exceptions.

GREEN: with `PYTHONPATH` set to the repository `.test-deps` directory and `COVERAGE_FILE` set to a temporary file:

```powershell
python -m coverage run --source=shiftlink.agent.schemas -m pytest tests/test_schemas.py tests/test_compat.py tests/test_retrieval_response.py tests/test_extraction.py tests/test_eval_harness.py tests/test_router_pipeline.py -q -p no:cacheprovider
python -m coverage report -m --fail-under=80
```

Result: **94 passed**, schema statement coverage **100% (127/127)**. This includes existing compatibility, retrieval/response, extraction, evaluation-harness and router/pipeline tests. The redundant T3 length check was also removed.

Compatibility: supplied `symptom` and `safety_basis` strings now have surrounding whitespace stripped and must be nonblank. `None` remains supported subject to the existing conditional-required rules. Historical datasets were not audited; the tests do not establish their compatibility. Coverage measures statements, not every possible input combination.
