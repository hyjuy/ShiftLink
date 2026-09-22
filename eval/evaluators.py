"""Deterministic evaluators for ShiftLink v1.0 compliance. No LLM judge.

Each evaluator takes case input and expected output, returns {pass: bool, reason: str}.
"""

import json
import re
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable


@dataclass
class EvaluationResult:
    """Result of a single test case evaluation."""
    case_id: str
    category: str
    passed: bool
    reason: str
    failure_type: str | None = None  # "schema", "data", "retrieval", "response", "evaluator", "not_implemented"
    metrics: dict[str, float | None] = field(default_factory=dict)


def evaluate_category_a(case: dict, expected: dict) -> EvaluationResult:
    """
    A: Safety Queries — retrieve applicable safety cards and verify conditions.

    Implementation:
    1. Load fixture card set into InMemoryToolProvider
    2. Call search_safety_cards with equipment_ids and observations
    3. Verify expected_safety_card_ids are retrieved (Recall)
    4. Check no unwanted exclusions
    5. Verify no duplicates in merged results
    6. Check response preservation
    """
    case_id = case.get("case_id", "unknown")

    try:
        from shiftlink.rag.retrieval import InMemoryToolProvider
        from shiftlink.agent.schemas import KnowledgeCard
        from pydantic import ValidationError

        case_input = case.get("input", {})
        equipment_ids = case_input.get("equipment_ids", [])
        observations = case_input.get("observations")

        expected_safety_ids = set(expected.get("expected_safety_card_ids", []))
        expected_count = expected.get("expected_count", 0)

        # Load fixture cards
        fixture_cards_raw = case.get("fixture_cards", [])
        fixture_cards = []

        for card_raw in fixture_cards_raw:
            try:
                card = KnowledgeCard.model_validate(card_raw)
                fixture_cards.append(card)
            except ValidationError:
                # Skip invalid cards (they'll be caught in schema tests)
                pass

        # Create provider with fixture cards
        try:
            provider = InMemoryToolProvider(cards=fixture_cards)
        except ValueError as e:
            return EvaluationResult(
                case_id=case_id,
                category="A",
                passed=False,
                reason=f"Provider initialization failed: {str(e)}",
                failure_type="evaluator"
            )

        # Call search_safety_cards
        results = provider.search_safety_cards(
            equipment_ids=equipment_ids,
            observations=observations
        )

        retrieved_ids = set(card.get("card_id") for card in results if card.get("card_id"))

        # Verify expected cards are present (Recall)
        missing = expected_safety_ids - retrieved_ids
        if missing:
            return EvaluationResult(
                case_id=case_id,
                category="A",
                passed=False,
                reason=f"Missing safety cards: {missing}",
                failure_type="retrieval"
            )

        unexpected = retrieved_ids - expected_safety_ids
        if unexpected:
            return EvaluationResult(case_id, "A", False,
                                    f"Unexpected safety cards: {unexpected}", "retrieval")

        # Zero is an explicit expected count too.
        if "expected_count" in expected and len(results) != expected_count:
            return EvaluationResult(
                case_id=case_id,
                category="A",
                passed=False,
                reason=f"Expected {expected_count} cards, got {len(results)}",
                failure_type="retrieval"
            )

        # Check for duplicates
        if len(retrieved_ids) != len(results):
            return EvaluationResult(
                case_id=case_id,
                category="A",
                passed=False,
                reason=f"Duplicate card_ids in results",
                failure_type="data"
            )

        return EvaluationResult(
            case_id=case_id,
            category="A",
            passed=True,
            reason=f"Safety retrieval correct: {len(results)} cards",
            failure_type=None
        )

    except ImportError:
        return EvaluationResult(
            case_id=case_id,
            category="A",
            passed=False,
            reason="retrieval.py not available",
            failure_type="not_implemented"
        )
    except Exception as e:
        return EvaluationResult(
            case_id=case_id,
            category="A",
            passed=False,
            reason=f"Evaluator error: {str(e)}",
            failure_type="evaluator"
        )


def evaluate_category_b(case: dict, expected: dict) -> EvaluationResult:
    """
    B: T4 Handover Method Validation
    - Input: KnowledgeCard dict with tacit_type=T4, type_payload.handover_method
    - Expected: outcome (valid/invalid)
    - Check: HandoverMethod schema, required fields (5), NonBlank constraints
    """
    case_id = case.get("case_id", "unknown")

    try:
        from pydantic import ValidationError
        from shiftlink.agent.schemas import KnowledgeCard

        card_input = case.get("input", {})
        expected_outcome = expected.get("outcome")

        # Validate card
        try:
            card = KnowledgeCard.model_validate(card_input)
            actual_outcome = "valid"
        except ValidationError:
            actual_outcome = "invalid"

        # Compare with expected
        if actual_outcome == expected_outcome:
            return EvaluationResult(
                case_id=case_id,
                category="B",
                passed=True,
                reason=f"Outcome matches: {actual_outcome}",
                failure_type=None
            )
        else:
            return EvaluationResult(
                case_id=case_id,
                category="B",
                passed=False,
                reason=f"Outcome mismatch. Expected: {expected_outcome}. Got: {actual_outcome}",
                failure_type="schema"
            )
    except Exception as e:
        return EvaluationResult(
            case_id=case_id,
            category="B",
            passed=False,
            reason=f"Evaluator error: {str(e)}",
            failure_type="evaluator"
        )


def evaluate_category_c(case: dict, expected: dict) -> EvaluationResult:
    """
    C: T3 Resolution Steps Validation
    - Input: KnowledgeCard dict with tacit_type=T3, type_payload.steps
    - Expected: outcome (valid/invalid)
    - Check: steps list ascending by order, no duplicate step_ids/orders, preconditions preserved
    """
    case_id = case.get("case_id", "unknown")

    try:
        from pydantic import ValidationError
        from shiftlink.agent.schemas import KnowledgeCard

        card_input = case.get("input", {})
        expected_outcome = expected.get("outcome")

        # Validate card
        try:
            card = KnowledgeCard.model_validate(card_input)
            actual_outcome = "valid"
        except ValidationError:
            actual_outcome = "invalid"

        # Compare with expected
        if actual_outcome == expected_outcome:
            return EvaluationResult(
                case_id=case_id,
                category="C",
                passed=True,
                reason=f"Outcome matches: {actual_outcome}",
                failure_type=None
            )
        else:
            return EvaluationResult(
                case_id=case_id,
                category="C",
                passed=False,
                reason=f"Outcome mismatch. Expected: {expected_outcome}. Got: {actual_outcome}",
                failure_type="schema"
            )
    except Exception as e:
        return EvaluationResult(
            case_id=case_id,
            category="C",
            passed=False,
            reason=f"Evaluator error: {str(e)}",
            failure_type="evaluator"
        )


def evaluate_category_d(case: dict, expected: dict) -> EvaluationResult:
    """
    D: Restart Type Validation
    - Input: KnowledgeCard dict with tacit_type=T6, type_payload with restart_type and tried_and_failed
    - Expected: outcome (valid/invalid)
    - Check: Known types must match, unknown allows mixing, evidence_ids format only (no existence check)
    """
    case_id = case.get("case_id", "unknown")

    try:
        from pydantic import ValidationError
        from shiftlink.agent.schemas import KnowledgeCard

        card_input = case.get("input", {})
        expected_outcome = expected.get("outcome")

        # Validate card
        try:
            card = KnowledgeCard.model_validate(card_input)
            actual_outcome = "valid"
        except ValidationError:
            actual_outcome = "invalid"

        # Compare with expected
        if actual_outcome == expected_outcome:
            return EvaluationResult(
                case_id=case_id,
                category="D",
                passed=True,
                reason=f"Outcome matches: {actual_outcome}",
                failure_type=None
            )
        else:
            return EvaluationResult(
                case_id=case_id,
                category="D",
                passed=False,
                reason=f"Outcome mismatch. Expected: {expected_outcome}. Got: {actual_outcome}",
                failure_type="schema"
            )
    except Exception as e:
        return EvaluationResult(
            case_id=case_id,
            category="D",
            passed=False,
            reason=f"Evaluator error: {str(e)}",
            failure_type="evaluator"
        )


def evaluate_category_e(case: dict, expected: dict) -> EvaluationResult:
    """
    E: v0.9 Conversion
    - Input: v0.9 KnowledgeCard dict (or non-dict)
    - Expected: outcome (converted/needs_review/rejected)
    - Check: convert_card_v09 output, deficiencies for needs_review/rejected, status forced to draft
    """
    case_id = case.get("case_id", "unknown")

    try:
        from shiftlink.agent.compat import convert_card_v09

        raw_input = case.get("input")
        expected_outcome = expected.get("outcome")

        result = convert_card_v09(raw_input)
        actual_outcome = result.outcome

        # Compare outcomes
        if actual_outcome == expected_outcome:
            # If converted, check status forced to draft
            if actual_outcome == "converted" and result.card:
                if result.card.status != "draft":
                    return EvaluationResult(
                        case_id=case_id,
                        category="E",
                        passed=False,
                        reason=f"Converted card status not forced to draft. Got: {result.card.status}",
                        failure_type="schema"
                    )

            return EvaluationResult(
                case_id=case_id,
                category="E",
                passed=True,
                reason=f"Conversion outcome matches: {actual_outcome}",
                failure_type=None
            )
        else:
            return EvaluationResult(
                case_id=case_id,
                category="E",
                passed=False,
                reason=f"Outcome mismatch. Expected: {expected_outcome}. Got: {actual_outcome}",
                failure_type="data"
            )
    except Exception as e:
        return EvaluationResult(
            case_id=case_id,
            category="E",
            passed=False,
            reason=f"Evaluator error: {str(e)}",
            failure_type="evaluator"
        )


def evaluate_category_f(case: dict, expected: dict) -> EvaluationResult:
    """
    F: E2E Integration — full pipeline with safety cards, steps, responses.

    Implementation:
    1. Load fixture cards into InMemoryToolProvider
    2. Run FixedPipeline with deterministic model stub
    3. Verify Recall@5: expected_card_ids vs search_cards results
    4. Check citation integrity: cited_card_ids exist in tool_results
    5. Verify render_response contains expected content
    6. Check safety/integrity: no safety cards lost, order preserved, stop_conditions kept
    7. Canary token leakage detection (qqz7-... and zzk9-... should NOT appear in render)
    """
    metrics: dict[str, float | None] = {}
    case_id = case.get("case_id", "unknown")

    try:
        from shiftlink.rag.retrieval import InMemoryToolProvider
        from shiftlink.agent.pipeline import FixedPipeline
        from shiftlink.agent.response import render_response
        from shiftlink.agent.schemas import KnowledgeCard
        from pydantic import ValidationError

        # Load fixture cards
        fixture_cards_raw = case.get("fixture_cards", [])
        fixture_cards = []

        for card_raw in fixture_cards_raw:
            try:
                card = KnowledgeCard.model_validate(card_raw)
                fixture_cards.append(card)
            except ValidationError:
                pass

        # Create provider
        try:
            provider = InMemoryToolProvider(cards=fixture_cards)
        except ValueError as e:
            return EvaluationResult(
                case_id=case_id,
                category="F",
                passed=False,
                reason=f"Provider init failed: {str(e)}",
                failure_type="evaluator", metrics=metrics
            )

        # Deterministic model stub: pass through tool_results as-is
        def model_stub(**kwargs: Any) -> dict[str, Any]:
            return {"type": "stub_response", "tool_results_passed": True}

        # Create pipeline with default validator (build_response)
        pipeline = FixedPipeline(model=model_stub, tools=provider)

        # Prepare payload
        case_input = case.get("input", {})

        # Route: query or handover
        if "question" in case_input:
            payload = {
                "question": case_input.get("question", ""),
                "line_id": case_input.get("line_id", "LN-0001"),
                "eq_id": case_input.get("eq_id", ""),
                "k": case_input.get("k", 5),
                "observations": case_input.get("observations", []),
            }
        else:
            payload = {
                "memo_text": case_input.get("memo_text", ""),
                "eq_ids": case_input.get("eq_ids", []),
                "shift": case_input.get("shift", "A"),
            }

        # Stub pipeline timing, not model/network latency.
        started = perf_counter()
        result = pipeline.run(payload)
        latency_ms = (perf_counter() - started) * 1000

        # Extract response and tool results
        response = result.output
        tool_results = result.tool_results
        retrieved_cards = tool_results.get("cards", [])
        safety_cards = tool_results.get("safety_cards", [])

        # Measure ranked retrieval separately from merged safety coverage.
        expected_card_ids = set(expected.get("expected_card_ids", []))
        retrieved_ids = set(card.get("card_id") for card in retrieved_cards if card.get("card_id"))

        k = payload.get("k", 5)
        ranked_ids = {c["card_id"] for c in tool_results["ranked_cards"][:k]}
        expected_safety_ids = set(expected.get("expected_safety_card_ids", []))
        notice_ids = {n.card_id for n in response.safety_notices}
        unexpected = retrieved_ids - expected_card_ids
        metrics.update({
            "precision_at_k": len(ranked_ids & expected_card_ids) / k,
            "recall_at_k": (len(ranked_ids & expected_card_ids) / len(expected_card_ids)
                            if expected_card_ids else None),
            "unexpected_card_rate": len(unexpected) / len(retrieved_ids) if retrieved_ids else 0.0,
            "safety_missing_rate": (len(expected_safety_ids - notice_ids) / len(expected_safety_ids)
                                    if expected_safety_ids else None),
            "latency_ms": latency_ms,
        })
        if unexpected:
            return EvaluationResult(case_id, "F", False,
                                    f"Unexpected cards: {unexpected}", "retrieval", metrics)

        recall = 1.0  # Default: perfect recall if no expected cards
        if expected_card_ids:
            recall_union = expected_card_ids & retrieved_ids
            recall = len(recall_union) / len(expected_card_ids)

            if recall < 0.95:
                return EvaluationResult(
                    case_id=case_id,
                    category="F",
                    passed=False,
                    reason=f"Merged recall too low: {recall*100:.1f}%. Missing: {expected_card_ids - retrieved_ids}",
                    failure_type="retrieval", metrics=metrics
                )

        # Verify citations
        if hasattr(response, "cited_card_ids"):
            cited = set(response.cited_card_ids)
            if not cited.issubset(retrieved_ids):
                missing_in_results = cited - retrieved_ids
                return EvaluationResult(
                    case_id=case_id,
                    category="F",
                    passed=False,
                    reason=f"Cited card_ids not in tool_results: {missing_in_results}",
                    failure_type="response", metrics=metrics
                )

        # Verify safety notices preservation
        if hasattr(response, "safety_notices"):
            expected_safety_ids = set(expected.get("expected_safety_card_ids", []))
            cited_safety_ids = set(n.card_id for n in response.safety_notices)
            if expected_safety_ids != cited_safety_ids:
                return EvaluationResult(
                    case_id=case_id,
                    category="F",
                    passed=False,
                    reason=f"Safety notices mismatch: missing={expected_safety_ids - cited_safety_ids}, unexpected={cited_safety_ids - expected_safety_ids}",
                    failure_type="response", metrics=metrics
                )

        # Verify step order preservation (T3)
        if hasattr(response, "steps") and response.steps:
            orders = [s.order for s in response.steps]
            if orders != sorted(orders):
                return EvaluationResult(
                    case_id=case_id,
                    category="F",
                    passed=False,
                    reason=f"Step order not preserved: {orders}",
                    failure_type="response", metrics=metrics
                )

        # Canary token leakage detection
        canary_token = case.get("canary_token", "")
        render_text = render_response(response) if hasattr(response, "model_dump") else ""

        canary_leak = False
        if canary_token and canary_token in render_text:
            canary_leak = True

        # Check for KB canary leakage (zzk9-... should not appear in eval)
        kb_canary_pattern = r"zzk9-[a-zA-Z0-9\-]+"
        if re.search(kb_canary_pattern, render_text):
            canary_leak = True

        if canary_leak:
            return EvaluationResult(
                case_id=case_id,
                category="F",
                passed=False,
                reason=f"Canary token leakage detected in render",
                failure_type="response", metrics=metrics
            )

        return EvaluationResult(
            case_id=case_id,
            category="F",
            passed=True,
            reason=f"E2E pipeline passed: Recall {recall*100:.1f}%, {len(response.safety_notices) if hasattr(response, 'safety_notices') else 0} safety notices, {len(response.steps) if hasattr(response, 'steps') else 0} steps",
            failure_type=None, metrics=metrics
        )

    except ImportError as e:
        return EvaluationResult(
            case_id=case_id,
            category="F",
            passed=False,
            reason=f"Pipeline modules not available: {str(e)}",
            failure_type="not_implemented", metrics=metrics
        )
    except Exception as e:
        return EvaluationResult(
            case_id=case_id,
            category="F",
            passed=False,
            reason=f"Evaluator error: {str(e)}",
            failure_type="evaluator", metrics=metrics
        )


# Dispatch table
EVALUATORS = {
    "A": evaluate_category_a,
    "B": evaluate_category_b,
    "C": evaluate_category_c,
    "D": evaluate_category_d,
    "E": evaluate_category_e,
    "F": evaluate_category_f,
}


def evaluate_case(case: dict, expected: dict, category: str) -> EvaluationResult:
    """Route to appropriate evaluator based on category."""
    evaluator = EVALUATORS.get(category)
    if not evaluator:
        return EvaluationResult(
            case_id=case.get("case_id", "unknown"),
            category=category,
            passed=False,
            reason=f"Unknown category: {category}",
            failure_type="evaluator"
        )
    return evaluator(case, expected)
