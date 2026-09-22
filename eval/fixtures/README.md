# Evaluation Fixtures

Source eligibility, lineage grouping, split assignment and final-evaluation freezing follow [source-and-split-contract.md](../../docs/data/policies/source-and-split-contract.md). Existing fixtures retain their assignments. The [inventory](../../splits/inventory.json) records file hashes, not proof of an unopened holdout or a formal evaluation seal. Inline `kb` cards are isolated test setup, not approval to ingest fixture content into the runtime KB.

## Directory Structure

- `dev/` — Development iteration fixtures (tuning allowed, use for repeated testing)
- `holdout/` — Holdout fixtures (final validation only, NO tuning use)

## Fixture Format

Each fixture file (JSON) contains an array of test cases with:
- `case_id`: Unique identifier (e.g., "A-safety-001")
- `category`: Category letter A-F per contract §5
- `type`: Normal/"normal", Error/"error", Boundary/"boundary", or Indeterminate/"indeterminate" (C only)
- `input`: Input data (card dict, event dict, raw v0.9 card, etc.)
- `expected`: Independently-defined expected result (NOT copied from implementation output)
- `description`: Purpose of this test case
- `notes`: Optional implementation hints or caveats

## Canary Tokens

- Eval fixtures use canary tokens (e.g., `qqz7-dev-123`) to detect unintended leakage.
- Different prefix than KB tokens (`zzk9-*`).
- Harness checks that canary tokens do NOT appear in responses or KB renders.

## Minimum Coverage per Category

- **A (Safety Queries)**: ≥8 dev cases (safe retrieval, top-k boundary, condition matching, exclusions, dedup)
- **B (T4 Handover)**: ≥8 dev cases (complete method, missing fields, wrong type)
- **C (T3 Steps)**: ≥8 dev cases (correct order, step_id dup, order dup, sort violation, missing steps, preconditions)
- **D (Restart)**: ≥8 dev cases (type classification, evidence reference, restart type consistency)
- **E (v0.9 Conversion)**: ≥8 dev cases (converted, needs_review, rejected; canary leakage check)
- **F (E2E Integration)**: ≥6 dev cases (query/handover scenarios, safety, Recall@k)
- **Holdout**: 2-4 cases per category (different from dev, no value-swapped copies)
