"""실행 진입점: 픽스처 카드를 InMemoryToolProvider에 얹고 실제 Ollama로 파이프라인 1건 실행.

    python -m shiftlink.edge --case F-e2e-001
    python -m shiftlink.edge --case F-e2e-002 --model qwen2.5-3b-ko:latest
    python -m shiftlink.edge --case F-e2e-001 --dry-run   # 모델 호출 없이 프롬프트만 출력

카드·질문은 eval/fixtures/dev/category_f_e2e.json의 E2E 케이스를 그대로 쓴다
(케이스의 input이 곧 파이프라인 payload).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from shiftlink.agent.pipeline import FixedPipeline
from shiftlink.agent.response import render_response
from shiftlink.agent.router import route_request
from shiftlink.agent.schemas import KnowledgeCard
from shiftlink.edge.ollama import (
    DEFAULT_HOST,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_S,
    MODEL_CALL_ERRORS,
    OllamaModel,
    build_messages,
)
from shiftlink.rag.retrieval import InMemoryToolProvider

DEFAULT_FIXTURE = Path("eval/fixtures/dev/category_f_e2e.json")


def load_case(fixture: Path, case_id: str | None) -> dict:
    cases = json.loads(fixture.read_text(encoding="utf-8"))
    if case_id is None:
        return cases[0]
    for case in cases:
        if case.get("case_id") == case_id:
            return case
    available = ", ".join(c.get("case_id", "?") for c in cases)
    raise SystemExit(f"케이스 {case_id} 없음. 사용 가능: {available}")


def build_provider(case: dict) -> InMemoryToolProvider:
    cards = [KnowledgeCard.model_validate(c) for c in case.get("fixture_cards", [])]
    return InMemoryToolProvider(cards=cards)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m shiftlink.edge")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--case", default=None, help="case_id (기본: 파일의 첫 케이스)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--dry-run", action="store_true", help="모델 호출 없이 프롬프트만 출력")
    args = parser.parse_args(argv)

    case = load_case(args.fixture, args.case)
    payload = case["input"]
    provider = build_provider(case)
    model = OllamaModel(model=args.model, host=args.host, timeout_s=args.timeout)

    print(f"# case {case.get('case_id')} — {case.get('description', '')}")
    print(f"# payload: {json.dumps(payload, ensure_ascii=False)}")

    if args.dry_run:
        routed = route_request(payload)
        # 실제 실행과 같은 도구 결과로 프롬프트를 만들어야 미리보기가 의미 있다.
        pipeline = FixedPipeline(model=model, tools=provider)
        tool_results = pipeline._run_tools(routed.request)
        messages, dropped = build_messages(routed.mode, routed.request, tool_results)
        for message in messages:
            print(f"\n--- {message['role']} ---\n{message['content']}")
        if dropped:
            print(f"\n# 카나리로 제외된 카드: {dropped}")
        return 0

    pipeline = FixedPipeline(model=model, tools=provider)
    started = time.monotonic()
    try:
        result = pipeline.run(payload)
    except MODEL_CALL_ERRORS as exc:
        print(f"\n[모델 호출 실패] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    wall_s = time.monotonic() - started

    measured = dict(model.last_call)
    output = measured.pop("output", None)
    print(f"\n# 모델 출력: {json.dumps(output, ensure_ascii=False)}")
    print(f"# 측정: {json.dumps(measured, ensure_ascii=False)} wall_s={wall_s:.3f}")
    print(f"\n{render_response(result.output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
