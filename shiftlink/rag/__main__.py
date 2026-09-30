"""PC CLI: equipment + question -> card-grounded answer via local Ollama.

    python -m shiftlink.rag --cards cards.json --equipment HPU --question "압력이 떨어졌다"
    python -m shiftlink.rag --cards cards.json --equipment HPU --question "..." --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from shiftlink.agent.pipeline import FixedPipeline
from shiftlink.agent.response import render_response
from shiftlink.agent.tools import bind_tool_provider
from shiftlink.edge.ollama import (
    DEFAULT_HOST,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_S,
    MODEL_CALL_ERRORS,
    OllamaModel,
    build_messages,
)
from shiftlink.rag.loader import load_card_provider
from shiftlink.rag.retrieval import KB_MIN_TOP_RELEVANCE


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(prog="python -m shiftlink.rag")
    parser.add_argument("--cards", required=True, help="카드 JSON 파일 또는 디렉터리")
    parser.add_argument("--equipment", required=True, help="설비 ID 또는 HPU/GR/RT/CV/PDP/CAU")
    parser.add_argument("--question", required=True)
    parser.add_argument("--line-id", default="L1")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--dry-run", action="store_true", help="모델 호출 없이 프롬프트만 출력")
    parser.add_argument(
        "--include-draft",
        action="store_true",
        help="accepted/kb/L1 외에 draft/kb 카드도 검색에 싣는다",
    )
    parser.add_argument("--min-relevance", type=int, default=KB_MIN_TOP_RELEVANCE,
                        help="1위 카드 관련도가 이보다 낮으면 '해당 지식 없음'(0이면 항상 검색)")
    args = parser.parse_args(argv)

    loaded = load_card_provider(args.cards, include_draft=args.include_draft,
                                min_top_relevance=args.min_relevance)
    bind_tool_provider(loaded.provider)
    payload = {
        "question": args.question,
        "line_id": args.line_id,
        "eq_id": args.equipment,
    }
    model = OllamaModel(model=args.model, host=args.host, timeout_s=args.timeout)
    print(
        f"# cards seen={loaded.seen} loaded={loaded.loaded} "
        f"equipment={args.equipment}"
    )
    print(f"# payload: {json.dumps(payload, ensure_ascii=False)}")

    if loaded.loaded == 0:
        print("\n[검색 결과 없음] accepted/kb/L1 카드가 없습니다.", file=sys.stderr)
        return 1

    pipeline = FixedPipeline(model=model, tools=loaded.provider)
    if args.dry_run:
        from shiftlink.agent.router import route_request

        routed = route_request(payload)
        tool_results = pipeline._run_tools(routed.request)
        messages, dropped = build_messages(routed.mode, routed.request, tool_results)
        for message in messages:
            print(f"\n--- {message['role']} ---\n{message['content']}")
        if dropped:
            print(f"\n# 카나리로 제외된 카드: {dropped}")
        return 0 if tool_results["cards"] else 1

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
    if result.output.no_knowledge or result.output.review_queue:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
