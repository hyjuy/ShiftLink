# Condition policy and retrieval evaluation — 2026-09-22

User-authorized scope: retain the existing schema/status gates, correct condition filtering and merge behavior, expose uncertainty, and strengthen evaluation before speculative metadata expansion.

## Behavior

- Ranked and safety retrieval share one evaluator. False applicability or true exclusion removes a card before ranking. Any unknown check keeps the card unverified; no checks means verified.
- Query observations reach both searches. Unknown safety warnings and all their step stop conditions remain visible. Unknown cards do not contribute executable steps, handover methods, or restart attempts to the default structured response; their IDs appear in a condition-unverified warning.
- `ranked_cards` preserves the original top-k independently of the unlimited safety merge. A/F evaluators reject unexpected results, including when the expected set is empty.
- Reports include ranked Precision@k/Recall@k, unexpected merged card rate, safety notice missing rate, and local stub pipeline p95. Empty recall/safety denominators are null with explicit sample counts. New source/evidence/approval models remain deferred pending data and pilot evidence.

## Evidence

RED: `python -m pytest tests/test_retrieval_response.py tests/test_eval_harness.py -q -p no:cacheprovider --tb=short` → **12 failed, 46 passed**. Failures reproduced ignored observations, excluded-card reentry, incomplete verification, missing uncertainty policy, and permissive evaluators.

GREEN command (with `.test-deps` on `PYTHONPATH`):

```powershell
python -m pytest tests/test_schemas.py tests/test_compat.py tests/test_retrieval_response.py tests/test_extraction.py tests/test_eval_harness.py tests/test_router_pipeline.py -q -p no:cacheprovider
python -m eval.harness --suite dev --run-id condition-policy-20260922-final
```

- **106 tests passed**; **46/46 dev cases passed**.
- Coverage collected across the targeted tests and dev harness: **89%** across retrieval, pipeline, response, evaluators, and harness (621/701 statements). These are statement counts, not proof of all input combinations.
- Regression tests also verify that six safety cards remain visible while ranked Recall@5 remains 5/6, rather than being inflated by the safety merge.
- `git diff --check` passed.

The first strengthened dev run exposed an inconsistent oracle: F-e2e-002 supplied pressure 8 against `>= 10` while expecting inclusion. Its expected card and safety sets were corrected to empty under the existing condition contract. Inputs and holdout fixtures were unchanged. Initial evidence is in `eval/results/condition-policy-20260922/`; final output is in `eval/results/condition-policy-20260922-final/`.

## Limits

- Full `tests/` run: **194 passed, 9 failed, 27 errors**. MES configuration tests reference missing `docs/00_plant_and_relations.json`; MES storage/HTTP/integration tests encountered temporary-file permission/database-open errors. Those files were not changed in this task.
- Dev metrics are synthetic: Precision@5 mean 0.1333 (six cases, unfilled slots counted as misses), Recall@5 mean 1.0 (four nonempty relevance cases), unexpected-card rate 0, safety-missing rate 0 (three applicable cases). Do not interpret sparse-fixture precision as production retrieval quality.
- Measured p95 is local stub timing, not LLM/network/Jetson performance; coverage instrumentation also affects it. No speedup claim or field study of authoring/review cost is made.
- The condition policy governs the existing default structured response builder. A future production model-output parser or custom validator must enforce the same policy. Persisted card schemas and T4 requirements were not expanded in this task.
