"""Regression tests for eval.harness infrastructure.

Tests the harness itself, not the categories being evaluated.
"""

import json
import math
from pathlib import Path

import pytest

from eval.evaluators import (
    evaluate_case,
    EvaluationResult,
    evaluate_category_b,
    evaluate_category_c,
    evaluate_category_d,
    evaluate_category_e,
)
from eval.harness import (
    wilson_ci_95,
    load_fixtures,
    get_fixture_sha256,
)


class TestWilsonCI:
    """Test Wilson score interval calculation."""

    def test_wilson_ci_100_percent(self):
        """100% success rate."""
        lower, upper = wilson_ci_95(10, 10)
        # Wilson CI: for n=10, p=1.0, CI is [0.722, 1.0] approximately
        assert 0.7 < lower < 0.75, f"Lower bound {lower} for 100% with n=10"
        assert upper == 1.0, "Upper bound is 1.0 for 100%"

    def test_wilson_ci_50_percent(self):
        """50% success rate (maximum uncertainty)."""
        lower, upper = wilson_ci_95(5, 10)
        # At 50%, CI should be widest; lower ~0.27, upper ~0.73
        assert 0.2 < lower < 0.4, f"Lower bound {lower} out of expected range"
        assert 0.6 < upper < 0.8, f"Upper bound {upper} out of expected range"

    def test_wilson_ci_0_percent(self):
        """0% success rate."""
        lower, upper = wilson_ci_95(0, 10)
        assert lower == 0.0
        # Wilson CI: for n=10, p=0.0, CI is [0.0, 0.278] approximately (symmetric)
        assert 0.25 < upper < 0.3, f"Upper bound {upper} for 0% with n=10"

    def test_wilson_ci_single_case(self):
        """Single case (n=1)."""
        lower_pass, upper_pass = wilson_ci_95(1, 1)
        lower_fail, upper_fail = wilson_ci_95(0, 1)
        assert 0.2 < lower_pass < 0.8, f"Single pass: lower bound {lower_pass} mid-range"
        assert 0.2 < upper_fail < 0.8, f"Single fail: upper bound {upper_fail} mid-range"

    def test_wilson_ci_zero_total(self):
        """Zero total cases (edge case)."""
        lower, upper = wilson_ci_95(0, 0)
        assert lower == 0.0
        assert upper == 0.0


class TestFixtureLoading:
    """Test fixture file loading and validation."""

    def test_load_dev_fixtures(self):
        """Load dev fixtures successfully."""
        fixtures = load_fixtures("dev")
        assert "A" in fixtures, "Category A missing"
        assert "B" in fixtures, "Category B missing"
        assert len(fixtures["A"]) >= 8, "Category A should have ≥8 dev cases"
        assert len(fixtures["B"]) >= 8, "Category B should have ≥8 dev cases"

    def test_load_holdout_fixtures(self):
        """Load holdout fixtures successfully."""
        fixtures = load_fixtures("holdout")
        assert "A" in fixtures, "Category A missing"
        assert len(fixtures["A"]) >= 2, "Category A should have ≥2 holdout cases"

    def test_fixture_schema_has_required_fields(self):
        """Each fixture case has case_id, category, input, expected."""
        fixtures = load_fixtures("dev")

        for category, cases in fixtures.items():
            for case in cases:
                assert "case_id" in case, f"Missing case_id in {category}"
                assert "category" in case, f"Missing category in {category}"
                assert "input" in case, f"Missing input in {category}"
                assert "expected" in case, f"Missing expected in {category}"
                assert "description" in case, f"Missing description in {category}"

    def test_fixture_case_ids_unique_per_category(self):
        """No duplicate case_ids within a category."""
        fixtures = load_fixtures("dev")

        for category, cases in fixtures.items():
            case_ids = [c["case_id"] for c in cases]
            assert len(case_ids) == len(set(case_ids)), \
                f"Duplicate case_ids in category {category}: {case_ids}"

    def test_dev_holdout_case_ids_do_not_overlap(self):
        """No case_id appears in both dev and holdout."""
        dev_fixtures = load_fixtures("dev")
        holdout_fixtures = load_fixtures("holdout")

        dev_ids = set()
        for cases in dev_fixtures.values():
            for case in cases:
                dev_ids.add(case["case_id"])

        holdout_ids = set()
        for cases in holdout_fixtures.values():
            for case in cases:
                holdout_ids.add(case["case_id"])

        overlap = dev_ids & holdout_ids
        assert len(overlap) == 0, f"case_id overlap between dev and holdout: {overlap}"

    def test_fixture_has_canary_tokens(self):
        """Each case includes a canary_token."""
        fixtures = load_fixtures("dev")

        for category, cases in fixtures.items():
            for case in cases:
                assert "canary_token" in case, \
                    f"Missing canary_token in {case.get('case_id', '?')}"
                # Canary should NOT use zzk9 prefix (reserved for KB)
                canary = case["canary_token"]
                assert not canary.startswith("zzk9-"), \
                    f"Eval canary should not use zzk9- prefix: {canary}"


class TestEvaluatorIntegration:
    """Test evaluators with known inputs."""

    def test_category_b_valid_handover_method(self):
        """Test B: Valid T4 card passes."""
        case = {
            "case_id": "test-b-valid",
            "input": {
                "card_id": "K-9999",
                "version": "1.0",
                "grade": "L1",
                "tacit_type": "T4",
                "equipment": "HPU",
                "component": "pump",
                "scenario": "S1",
                "title": "test",
                "know_how": "test",
                "rationale": "test",
                "conditions": [],
                "exclusions": [],
                "safety_flag": False,
                "confidence": 0.8,
                "provenance": {
                    "seed_ids": ["SD-1"],
                    "persona_id": "P-1",
                    "event_ids": [],
                    "generator": "test",
                    "generated_at": "2026-09-21T00:00:00+00:00"
                },
                "split": "dev",
                "status": "draft",
                "type_payload": {
                    "handover_method": {
                        "required_context": ["info"],
                        "recipient_role": "role",
                        "timing": "when",
                        "channel": "how",
                        "acknowledgement": "check"
                    }
                }
            }
        }
        expected = {"outcome": "valid"}
        result = evaluate_category_b(case, expected)
        assert result.passed, result.reason

    def test_category_b_missing_handover_method(self):
        """Test B: T4 without handover_method fails."""
        case = {
            "case_id": "test-b-missing",
            "input": {
                "card_id": "K-9998",
                "version": "1.0",
                "grade": "L1",
                "tacit_type": "T4",
                "equipment": "HPU",
                "component": "pump",
                "scenario": "S1",
                "title": "test",
                "know_how": "test",
                "rationale": "test",
                "conditions": [],
                "exclusions": [],
                "safety_flag": False,
                "confidence": 0.8,
                "provenance": {
                    "seed_ids": ["SD-1"],
                    "persona_id": "P-1",
                    "event_ids": [],
                    "generator": "test",
                    "generated_at": "2026-09-21T00:00:00+00:00"
                },
                "split": "dev",
                "status": "draft",
                "type_payload": {}
            }
        }
        expected = {"outcome": "invalid", "error_reason": "T4 cards require"}
        result = evaluate_category_b(case, expected)
        assert result.passed, result.reason

    def test_category_c_valid_steps(self):
        """Test C: Valid T3 steps pass."""
        case = {
            "case_id": "test-c-valid",
            "input": {
                "card_id": "K-9997",
                "version": "1.0",
                "grade": "L1",
                "tacit_type": "T3",
                "equipment": "HPU",
                "component": "pump",
                "scenario": "S1",
                "title": "test",
                "symptom": "sound",
                "know_how": "test",
                "rationale": "test",
                "conditions": [],
                "exclusions": [],
                "safety_flag": False,
                "confidence": 0.8,
                "provenance": {
                    "seed_ids": ["SD-1"],
                    "persona_id": "P-1",
                    "event_ids": [],
                    "generator": "test",
                    "generated_at": "2026-09-21T00:00:00+00:00"
                },
                "split": "dev",
                "status": "draft",
                "type_payload": {
                    "steps": [
                        {
                            "step_id": "ST-01",
                            "order": 1,
                            "action": "step1",
                            "preconditions": [],
                            "expected_result": "res1",
                            "stop_conditions": []
                        }
                    ]
                }
            }
        }
        expected = {"outcome": "valid"}
        result = evaluate_category_c(case, expected)
        assert result.passed, result.reason

    def test_category_c_out_of_order_steps(self):
        """Test C: Out-of-order steps fail."""
        case = {
            "case_id": "test-c-ooo",
            "input": {
                "card_id": "K-9996",
                "version": "1.0",
                "grade": "L1",
                "tacit_type": "T3",
                "equipment": "HPU",
                "component": "pump",
                "scenario": "S1",
                "title": "test",
                "know_how": "test",
                "rationale": "test",
                "conditions": [],
                "exclusions": [],
                "safety_flag": False,
                "confidence": 0.8,
                "provenance": {
                    "seed_ids": ["SD-1"],
                    "persona_id": "P-1",
                    "event_ids": [],
                    "generator": "test",
                    "generated_at": "2026-09-21T00:00:00+00:00"
                },
                "split": "dev",
                "status": "draft",
                "type_payload": {
                    "steps": [
                        {
                            "step_id": "ST-01",
                            "order": 2,
                            "action": "step1",
                            "expected_result": "res1"
                        },
                        {
                            "step_id": "ST-02",
                            "order": 1,
                            "action": "step2",
                            "expected_result": "res2"
                        }
                    ]
                }
            }
        }
        expected = {"outcome": "invalid", "error_reason": "ascending order"}
        result = evaluate_category_c(case, expected)
        assert result.passed, result.reason

    def test_category_d_restart_type_mismatch(self):
        """Test D: Known restart_type must match attempt."""
        case = {
            "case_id": "test-d-conflict",
            "input": {
                "card_id": "K-9995",
                "version": "1.0",
                "grade": "L1",
                "tacit_type": "T6",
                "equipment": "HPU",
                "component": "pump",
                "scenario": "S1",
                "title": "test",
                "know_how": "test",
                "rationale": "test",
                "conditions": [],
                "exclusions": [],
                "safety_flag": False,
                "confidence": 0.8,
                "provenance": {
                    "seed_ids": ["SD-1"],
                    "persona_id": "P-1",
                    "event_ids": [],
                    "generator": "test",
                    "generated_at": "2026-09-21T00:00:00+00:00"
                },
                "split": "dev",
                "status": "draft",
                "type_payload": {
                    "restart_type": "normal_stop_restart",
                    "tried_and_failed": [
                        {
                            "attempt_id": "AT-0001",
                            "restart_type": "maintenance_restart",
                            "action": "restart",
                            "observed_result": "fail",
                            "failure_reason": None,
                            "evidence_ids": []
                        }
                    ]
                }
            }
        }
        expected = {"outcome": "invalid", "error_reason": "conflicts with"}
        result = evaluate_category_d(case, expected)
        assert result.passed, result.reason

    def test_category_e_converted_status_forced_to_draft(self):
        """Test E: Converted cards forced to draft."""
        case = {
            "case_id": "test-e-status",
            "input": {
                "card_id": "K-9994",
                "version": "0.9",
                "grade": "L1",
                "tacit_type": "T1",
                "equipment": "HPU",
                "component": "pump",
                "scenario": "S1",
                "title": "test",
                "symptom": "sound",
                "know_how": "test",
                "rationale": "test",
                "conditions": [],
                "exclusions": [],
                "safety_flag": False,
                "confidence": 0.8,
                "provenance": {
                    "seed_ids": ["SD-1"],
                    "persona_id": "P-1",
                    "event_ids": [],
                    "generator": "test",
                    "generated_at": "2026-09-21T00:00:00+00:00"
                },
                "split": "dev",
                "status": "accepted"  # Will be forced to draft
            }
        }
        expected = {"outcome": "converted", "converted_status": "draft"}
        result = evaluate_category_e(case, expected)
        assert result.passed, result.reason


class TestCanaryTokens:
    """Test canary token infrastructure."""

    def test_dev_fixtures_have_different_canary_prefix(self):
        """Dev fixtures use different prefix than KB fixtures (zzk9)."""
        fixtures = load_fixtures("dev")

        for category, cases in fixtures.items():
            for case in cases:
                canary = case.get("canary_token", "")
                # Should start with qqz7 or similar (not zzk9)
                assert not canary.startswith("zzk9-"), \
                    f"Dev case {case['case_id']} uses KB canary prefix: {canary}"
                # Should have structure like qqz7-dev-XXXX
                assert "dev" in canary or "holdout" in canary, \
                    f"Case {case['case_id']} canary should indicate suite: {canary}"

    def test_holdout_fixtures_have_different_canary_prefix(self):
        """Holdout fixtures use different prefix than KB fixtures."""
        fixtures = load_fixtures("holdout")

        for category, cases in fixtures.items():
            for case in cases:
                canary = case.get("canary_token", "")
                assert not canary.startswith("zzk9-"), \
                    f"Holdout case {case['case_id']} uses KB canary prefix: {canary}"
                assert "holdout" in canary, \
                    f"Holdout case {case['case_id']} should indicate suite in canary: {canary}"


class TestFixtureSHA256:
    """Test fixture integrity hash computation."""

    def test_fixture_sha256_dev(self):
        """Compute SHA256 of dev fixtures (should be deterministic)."""
        hash1 = get_fixture_sha256("dev")
        hash2 = get_fixture_sha256("dev")
        assert hash1 == hash2, "Fixture hash should be deterministic"
        assert len(hash1) == 64, "SHA256 hash should be 64 hex chars"

    def test_fixture_sha256_holdout(self):
        """Compute SHA256 of holdout fixtures."""
        hash1 = get_fixture_sha256("holdout")
        assert len(hash1) == 64
        # Holdout hash should differ from dev
        hash_dev = get_fixture_sha256("dev")
        assert hash1 != hash_dev, "Dev and holdout hashes should differ"
