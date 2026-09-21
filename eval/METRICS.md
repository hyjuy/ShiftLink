# Evaluation Metrics for ShiftLink v1.0

## Overview

All metrics are **deterministic** (no LLM judge). Each category A-F reports success count, total count, pass ratio, and 95% Wilson CI. Holdout suite uses same metrics as dev for final validation.

## Metric Definitions by Category

### Category A: Safety Queries (Rules-based Retrieval)

**Metric Name:** Safety Card Retrieval Accuracy

**Measurement Target:** Can the system retrieve all applicable safety cards and correctly exclude cards when conditions fail?

**Definition:**
- **Success criterion:** Retrieved card_ids match expected_safety_card_ids (set comparison, order-independent)
- **Computed as:** Count of cases where actual set == expected set / Total cases
- **Applicable to:** Query mode with safety_flag=True KB cards

**Limitations:**
- Requires full retrieval pipeline implementation (Team B: retrieval.py)
- Cannot validate signal observations without observations-to-dict conversion
- Condition matching rules depend on Condition.op evaluation (==, !=, >, >=, <, <=)

**Source / Formula:**
- Set membership: standard computer science, no external reference
- Retrieval baseline: TREC guidelines assume retrieved set size is unknown a priori; here we measure exact set match (stricter than Precision@k or Recall@k for this use case)

---

### Category B: T4 Handover Method Validation (Schema Enforcement)

**Metric Name:** Handover Method Schema Compliance

**Measurement Target:** Does the schema correctly enforce T4 requirements and reject incomplete/malformed handover methods?

**Definition:**
- **Success criterion:** Pydantic validation outcome (valid/invalid) matches expected outcome
- **Computed as:** Count of correct validation outcomes / Total cases
- **Applicable to:** Card payload schema validation, NOT retrieval or generation

**Test Types Included:**
- Valid complete HandoverMethod (5 required fields: required_context, recipient_role, timing, channel, acknowledgement)
- Missing or null fields
- NonBlank constraint violations (empty strings, whitespace-only strings)
- Type errors (e.g., required_context not a list, list not min_length=1)

**Source / Formula:**
- Pydantic model validation: https://docs.pydantic.dev/latest/concepts/models/
- NonBlank constraint: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
- Reference: D-27, schemas.py HandoverMethod

---

### Category C: T3 Resolution Steps Validation (Schema Enforcement)

**Metric Name:** Resolution Steps Schema Compliance

**Measurement Target:** Does the schema enforce step ordering, uniqueness, and precondition preservation?

**Definition:**
- **Success criterion:** Pydantic validation outcome matches expected outcome
- **Computed as:** Count of correct validation outcomes / Total cases
- **Applicable to:** Card payload schema validation

**Test Types Included:**
- Correct ascending order by `order` field (1, 2, 3, ...)
- Duplicate step_id detection (must be unique)
- Duplicate order detection (must be unique)
- Out-of-order step detection (list must be sorted)
- Empty steps list rejection (min 1 required)
- step_id pattern validation (^ST-\d{2,4}$)
- Preconditions and stop_conditions preservation (no truncation)

**Source / Formula:**
- Pydantic model validation: https://docs.pydantic.dev/latest/concepts/models/
- Pattern constraint: Field(pattern=r"^ST-\d{2,4}$")
- Reference: D-28, schemas.py ResolutionStep

---

### Category D: Restart Type Validation (Schema Enforcement)

**Metric Name:** Restart Attempt Consistency & Type Classification

**Measurement Target:** Does the schema correctly classify restart types and enforce consistency rules?

**Definition:**
- **Success criterion:** Pydantic validation outcome matches expected outcome
- **Computed as:** Count of correct validation outcomes / Total cases
- **Applicable to:** Card payload schema validation

**Test Types Included:**
- T6 card with known restart_type (3 types: normal_stop_restart, abnormal_stop_restart, maintenance_restart)
- T6 card with unknown restart_type (allows mixing attempt types)
- FailedAttempt with matching restart_type (valid under known cards)
- FailedAttempt with conflicting restart_type (invalid under known cards, valid under unknown)
- attempt_id pattern validation (^AT-\d{4}$)
- failure_reason None preservation (not auto-filled with "미상")
- evidence_ids format-only validation (no existence check)

**Key Rule (D-29, Rule 4):**
- If card.restart_type is known (≠ unknown) AND attempt.restart_type is known, they must match
- If card.restart_type is unknown, attempt can be any type

**Source / Formula:**
- Pydantic model validation: https://docs.pydantic.dev/latest/concepts/models/
- RestartType constraint: Literal["normal_stop_restart", "abnormal_stop_restart", "maintenance_restart", "unknown"]
- Reference: D-29, schemas.py FailedAttempt

---

### Category E: v0.9 Conversion (Data Migration)

**Metric Name:** Schema Version Conversion Success Rate

**Measurement Target:** Can v0.9 cards be converted or correctly marked as needing review/rejected?

**Definition:**
- **Success criterion:** Conversion outcome (converted/needs_review/rejected) matches expected outcome
- **Computed as:** Count of correct outcomes / Total cases
- **Applicable to:** convert_card_v09() function output

**Outcomes Defined:**
- **converted:** Card passes v1.0 validation; status forced to "draft" (never auto-accepted)
- **needs_review:** Card lacks required v1.0 fields (T4 handover_method, T3 steps, safety_basis for safety_flag=True) but structure is sound
- **rejected:** Input is not a dict OR card_id format is invalid (support boundary only)

**Test Types Included:**
- T1, T2, T5 converts with payload-independent fields
- T4/T3 without required payloads → needs_review (no auto-creation)
- safety_flag=True without safety_basis → needs_review
- Non-dict input → rejected
- Invalid card_id format → rejected
- Status forced to draft (original status preserved in original field)

**Source / Formula:**
- Pydantic model validation: https://docs.pydantic.dev/latest/concepts/models/
- Reference: D-3, compat.py convert_card_v09

---

### Category F: E2E Integration (Full Pipeline)

**Metric Name:** Recall@k (Information Retrieval Effectiveness) & Canary Token Leakage

**Measurement Target:** Does the full pipeline (routing, retrieval, model, validation) correctly find expected cards and preserve security (no token leakage)?

**Definition (Recall@k):**
- **Recall@k formula:** (cards_retrieved_in_top_k ∩ expected_cards) / |expected_cards|
- **k value:** Fixed at 5 per fixture
- **Computed as:** Average Recall@k across cases (measure each case, report mean + 95% CI)
- **Applicable to:** Query and Handover modes, post-retrieval result set

**Definition (Canary Leakage):**
- **Leakage detection:** Case includes canary_token (e.g., "qqz7-dev-f001-canary")
- **Check:** Canary token appears in rendered response text → **leakage=1**
- **Check:** Canary token appears in KB card renders → **leakage=1**
- **Pass criterion:** Total leakage count = 0 across F category
- **Computed as:** Count(leakage=0) / Total cases

**Test Types Included:**
- Query with safety cards and condition matching
- Query with unmatched observations
- Handover with equipment and shift
- Canary token injection and leakage detection

**Limitations:**
- Requires FixedPipeline, InMemoryToolProvider, and response.py (Team B)
- Recall denominator (|expected_cards|) comes from fixture, not ground truth external source
- Canary detection requires response rendering to text (response.py not yet implemented)

**Source / Formula:**
- Recall@k: https://en.wikipedia.org/wiki/Evaluation_measures_(information_retrieval)#Recall
- TREC Evaluation: https://trec.nist.gov/
- BEIR Benchmark: https://github.com/beir-cellar/beir (Recall as standard metric)

---

## Aggregation: Pass/Fail Decision Rules

### Mandatory Metrics (100% threshold)

- **Category B (T4 schema):** All cases must pass (0 defects)
- **Category C (T3 schema):** All cases must pass (0 defects)
- **Category D (Restart schema):** All cases must pass (0 defects)
- **Category E (v0.9 conversion):** All cases must pass (0 defects)
- **Category F (Canary leakage):** Leakage count = 0 (no token exposure)

### Optional / Proportional Metrics (95% threshold + Wilson CI)

- **Category A (Safety retrieval):** Recall@k mean ≥ 95% (with 95% Wilson CI lower bound ≥ 90%)
- **Category F (Recall@k mean):** Mean Recall@k ≥ 95% (separate from leakage metric)

---

## Wilson Score Interval (95% CI Calculation)

**Used for:** Proportional metrics (A, F Recall@k)

**Formula:**
```
p̂ = successes / n
z = 1.96 (for 95% confidence)

center = (p̂ + z²/(2n)) / (1 + z²/n)
margin = z * sqrt(p̂(1-p̂)/n + z²/(4n²)) / (1 + z²/n)

lower = center - margin
upper = center + margin
```

**Source:**
- Wilson, E. B. (1927). "Probable inference, the law of succession, and statistical inference." Journal of the American Statistical Association, 22(158), 209–212.
- https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval#Wilson_score_interval
- scikit-learn BinomialCI implementation: https://scikit-learn.org/stable/modules/model_evaluation.html

---

## Metric Limitations & Caveats

| Category | Limitation | Impact |
|----------|-----------|--------|
| A (Safety) | Requires retrieval.py implementation | Marked not_implemented if unavailable |
| B (T4) | Schema-only; does not test generation or UI | Real handover UI may render differently |
| C (T3) | Schema-only; does not test execution or UI | Real procedure execution not validated |
| D (Restart) | Schema-only; evidence refs not existence-checked | Stale evidence IDs not caught |
| E (v0.9) | Conversion rules are heuristic; no human QA | Semantically broken cards may convert |
| F (E2E) | Requires full pipeline + response.py | Marked not_implemented if unavailable |
| F (Recall@k) | Fixture expected_cards define ground truth | Not validated against external corpus |
| F (Canary) | Requires response.render() to text | HTML/UI rendering not checked |

---

## Reporting

**Output file:** `eval/results/<run_id>/report.json`

**Schema:**
```json
{
  "run_id": "timestamp-or-suite",
  "git_rev": "commit hash",
  "schema_version": "1.0",
  "fixture_sha256": {
    "dev": "hash of dev/ directory",
    "holdout": "hash of holdout/ directory"
  },
  "timestamp": "ISO 8601",
  "suite": "dev or holdout",
  "categories": {
    "A": {
      "metric_name": "Safety Card Retrieval Accuracy",
      "target": "100%",
      "success": 7,
      "total": 8,
      "ratio": 0.875,
      "wilson_ci_lower": 0.72,
      "wilson_ci_upper": 0.98,
      "passed": false,
      "not_implemented": 0,
      "n_a_reason": "retrieval.py not available"
    },
    ...
  }
}
```

**Failures file:** `eval/results/<run_id>/failures.jsonl`

**Schema (one line per failed case):**
```json
{"case_id": "A-safety-001", "category": "A", "expected": {...}, "actual": {...}, "failure_type": "retrieval", "reason": "Card K-0108 not in results"}
```
