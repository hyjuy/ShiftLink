# Optional schema 1.1 and structured retrieval — 2026-09-22

Source: user requested the reviewed metadata extensions, then clarified that performance and non-small-scale use matter. Extensions are optional for backward compatibility, not limited to small deployments.

## Delivered contracts

- GeneralizationEvidence: supporting/contradicting event references, applicability scope and confidence basis. Event IDs are validated for shape, uniqueness and disjoint roles, without fetching event ground truth.
- FailedAttempt: evidence-gap classification, next observations, required data and collection role. Unknown failure reasons stay null.
- ResolutionStep: verification, rollback and escalation information.
- SafetyReview: separately recorded review status, reviewer/role, review/expiry timestamps, evidence grade, safety level and review triggers. Approval metadata completeness and timestamp ordering are validated. This does not implement authorization, state transitions, expiry scheduling or runtime approval filtering.
- Provenance: source locations/document versions and extraction/model/prompt/index/schema versions. SCHEMA_VERSION is 1.1; legacy per-card versions are preserved. Eval reports use the live constant.
- Structured responses retain metadata; procedural/failure fields and useful evidence references are rendered. Generation prompts forbid invented metadata/approvals.
- Search uses structured knowledge fields, excluding reviewer/generator metadata. Query tokenization happens once, top-k selection uses `heapq.nsmallest`, and only selected cards are serialized. It still scans candidate cards; no production-scale indexed search claim is made.

## RED/GREEN

1. Metadata regression tests before implementation: **10 failed, 34 passed** (`tests/test_retrieval_response.py`). Failures demonstrated dropped fields and missing validation.
2. Structured-retrieval tests before search change: **4 failed, 45 passed**. Symptom, generalization scope, verification text and required-data-only matches lost to an unrelated lower ID.
3. Final command, with `.test-deps` on PYTHONPATH:

```powershell
python -m pytest tests/test_schemas.py tests/test_compat.py tests/test_retrieval_response.py tests/test_extraction.py tests/test_eval_harness.py tests/test_router_pipeline.py -q -p no:cacheprovider
python -m eval.harness --suite dev --run-id schema-extension-search-20260922
```

Result: **121 tests passed**, **46/46 dev cases passed**. Tests cover JSON round-trip, response/render preservation, invalid event relationships, incomplete approval metadata, timezone/date ordering, invalid evidence gaps, legacy conversion, structured ranking and exclusion of administrative metadata from relevance scoring. Statement coverage: schemas 100%, response 98%, retrieval 86%, combined 96% (499/522). `git diff --check` passed.

## Local search measurement

Same Windows/Python session environment, all cards equipment HPU, identical extended T3 content with unique IDs, top-5, one warm-up and 15 timed searches per size. Model calls, safety retrieval, ingestion, response rendering and network are excluded. Before/after returned the same top-five IDs for the timing workload. No external production corpus was used.

| Cards | Before median ms | After median ms | Before p95 ms | After p95 ms |
|---:|---:|---:|---:|---:|
| 100 | 2.3104 | 1.3573 | 11.4642 | 1.8707 |
| 1,000 | 28.5289 | 14.0768 | 50.4863 | 16.0356 |
| 5,000 | 281.1217 | 69.3734 | 296.0853 | 79.6248 |

The observed 5,000-card median improvement is about 4.05x for this synthetic workload only. Fifteen samples and homogeneous cards do not establish concurrent throughput, real-world search quality or production p95. Larger deployments still need indexed retrieval and representative relevance/load evaluation.

Reproduction body used for each measurement (before and after implementation):

```python
import runpy, statistics, time
from shiftlink.agent.schemas import KnowledgeCard
from shiftlink.rag.retrieval import InMemoryToolProvider

raw = runpy.run_path('tests/test_retrieval_response.py')['extended_card_data']()
raw['safety_flag'] = False
for n in (100, 1000, 5000):
    cards = [KnowledgeCard.model_validate(raw | {'card_id': f'K-{i:04d}'}) for i in range(n)]
    provider = InMemoryToolProvider(cards=cards)
    def search():
        return provider.search_cards(query='Inspect pump pressure', equipment_ids=['HPU'], k=5)
    search()
    samples = []
    for _ in range(15):
        start = time.perf_counter()
        result = search()
        samples.append((time.perf_counter() - start) * 1000)
    print(n, statistics.median(samples), sorted(samples)[14], [c['card_id'] for c in result])
```

The full repository suite was not repeated; the preceding task recorded MES fixture-path and temporary-file failures. Holdout inputs were not altered or used to tune this change. Real reviewer permissions, source/event referential integrity and live expiry enforcement remain outside this field-extension task.

## Authoring contract alignment — 2026-09-22

The user subsequently requested alignment of the authoring guide, generation prompt and schema contract. Updated all three descriptions to T1–T6 / v1.1 without changing validation behavior. The prompt title now reads SCHEMA_VERSION directly. Clarified T3 one-step/non-contiguous numbering, T4 reusable methods vs event records, all allowed known/unknown restart combinations, draft/L0 generation policy, metadata optionality and approval limitations. Original contract filename remains for link compatibility; historical v0.9 conversion references remain intentional.

Verification: `python -m pytest tests/test_schemas.py tests/test_compat.py tests/test_retrieval_response.py -q -p no:cacheprovider` → **84 passed**. An in-memory contract check validated **25 cases**: the 20 combinations of five card restart states (three known, unknown, omitted) and four attempt states, plus step orders `[2]`, `[2,5]`, `[0]`, `[2,2]`, `[5,2]`. Prompt version matches 1.1 and `git diff --check` passed. These checks establish schema behavior; they do not measure a live generation model's adherence to the prompt. Generation/storage and external evidence validation remain unfinished.
