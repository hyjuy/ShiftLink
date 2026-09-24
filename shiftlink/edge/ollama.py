"""로컬 Ollama 어댑터: FixedPipeline이 호출하는 단일 ModelCall.

계약(① 합의 사항):
    model(mode=..., request=..., tool_results=..., retry=False)
        -> {"answer": str, "cited_card_ids": list[str]}

- 이 어댑터는 호출 1건당 모델을 정확히 1회 부른다. 재시도는 파이프라인이 관리한다.
- 실패는 부분 결과를 돌려주지 않고 ModelCallError로 올린다.
- "검색 결과 없음" 게이트는 파이프라인이 모델 호출 전에 처리한다(D-26~29 §4.4).
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any

from shiftlink.agent.canary import CANARY_PREFIXES, has_canary

DEFAULT_MODEL = "qwen2.5:3b-instruct-q4_K_M"  # models.lock plan-B
DEFAULT_HOST = "http://localhost:11434"
# Jetson 최초 로드 30.7s 실측(docs/reports/Jetson_실측_PRE01-04.md) 때문에 넉넉히 잡는다.
DEFAULT_TIMEOUT_S = 120.0
NUM_CTX = 2048
# 모델 상주, 재로딩 방지. 반드시 정수 -1 — 문자열 "-1"은 Ollama가 duration 파싱에 실패해 400을 낸다.
KEEP_ALIVE = -1

# §4.4 모델 입력 격리: 카드에서 이 필드만 프롬프트로 나간다.
MODEL_CARD_FIELDS = (
    "card_id",
    "tacit_type",
    "equipment",
    "component",
    "title",
    "symptom",
    "know_how",
    "rationale",
    "safety_flag",
    "safety_basis",
    "condition_status",
)

# A의 validate_model_output(response.py)과 같은 제약을 모델 쪽에도 걸어 실패를 줄인다.
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string", "minLength": 1},
        "cited_card_ids": {
            "type": "array",
            "items": {"type": "string", "pattern": "^K-\\d{4}$"},
            "minItems": 1,
            "uniqueItems": True,
        },
    },
    "required": ["answer", "cited_card_ids"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "너는 제조 현장 교대 인계 보조다. 아래 지식 카드에 적힌 내용만으로 답한다.\n"
    "규칙:\n"
    "1. answer는 항상 한국어 두세 문장으로 채운다. 빈 문자열이나 공백만 두지 않는다.\n"
    "2. cited_card_ids에는 위 카드 목록에 실제로 있는 card_id를 최소 한 개 넣는다.\n"
    "   목록에 없는 ID를 지어내지 않고, 같은 ID를 두 번 넣지 않는다. 질문과 덜 맞아도 가장 가까운 카드를 인용한다.\n"
    "3. 카드에 없는 내용은 절대 만들어내지 않는다. 카드 문구를 벗어난 추정·수치를 덧붙이지 않는다.\n"
    "4. 안전·단계·인계 방법 블록은 시스템이 카드에서 직접 만든다. 너는 요약 answer와 인용만 낸다.\n"
    "5. JSON 객체 하나만 출력한다. 설명·코드펜스를 붙이지 않는다."
)

RETRY_PROMPT = (
    "\n\n[재시도] 직전 출력이 검증에 실패했다. "
    '{"answer": "...", "cited_card_ids": ["K-0000"]} 형태의 JSON 객체 하나만 출력하고, '
    "cited_card_ids에는 위 카드 목록에 실제로 있는 ID만 넣어라."
)


# 호출자가 잡을 오류 4종. A 계약 §3대로 표준 예외만 쓴다 — agent가 edge를 import할 필요가 없다.
MODEL_CALL_ERRORS = (NotImplementedError, TimeoutError, ConnectionError, ValueError)


def card_context(tool_results: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """카드를 화이트리스트 필드로 축약한다. 카나리가 섞인 카드는 빼고 ID를 함께 돌려준다."""
    context: list[dict[str, Any]] = []
    dropped: list[str] = []
    for card in tool_results.get("cards", []):
        trimmed = {
            field: card[field]
            for field in MODEL_CARD_FIELDS
            if card.get(field) is not None
        }
        if has_canary(card):
            dropped.append(card.get("card_id", "<no-id>"))
            continue
        context.append(trimmed)
    return context, dropped


def build_messages(
    mode: str,
    request: Any,
    tool_results: dict[str, Any],
    retry: bool = False,
) -> tuple[list[dict[str, str]], list[str]]:
    """Ollama /api/chat용 messages와, 카나리로 제외된 카드 ID 목록을 만든다."""
    cards, dropped = card_context(tool_results)
    dropped = sorted(set(dropped + tool_results.get("dropped_canary_card_ids", [])))
    # 질의는 question, 인계는 memo_text — 라우터가 둘 중 하나만 채운다.
    ask = getattr(request, "question", None) or getattr(request, "memo_text", "")
    # observations는 Observation 모델 목록이다(구 호출자는 dict를 넘길 수 있어 둘 다 받는다).
    observations = [
        obs.model_dump(mode="json") if hasattr(obs, "model_dump") else obs
        for obs in (getattr(request, "observations", None) or [])
    ]

    parts = [f"모드: {mode}", f"입력: {ask}"]
    if observations:
        parts.append(f"관측값: {json.dumps(observations, ensure_ascii=False)}")
    parts.append(f"지식 카드:\n{json.dumps(cards, ensure_ascii=False, indent=1)}")
    user = "\n\n".join(parts)
    if retry:
        user += RETRY_PROMPT

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ], dropped


class OllamaModel:
    """파이프라인에 넘기는 호출 가능 객체. 마지막 호출 정보는 last_call에 남긴다."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        host: str = DEFAULT_HOST,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        num_ctx: int = NUM_CTX,
    ) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self.timeout_s = timeout_s
        self.num_ctx = num_ctx
        self.last_call: dict[str, Any] = {}

    def __call__(
        self,
        *,
        mode: str,
        request: Any,
        tool_results: dict[str, Any],
        retry: bool = False,
    ) -> dict[str, Any]:
        # 계약 §2: 오늘 범위는 query뿐. handover를 query처럼 조용히 처리하지 않는다.
        if mode != "query":
            raise NotImplementedError(
                f"{mode!r} 모드는 아직 어댑터 범위 밖이다. query만 처리한다."
            )
        messages, dropped = build_messages(mode, request, tool_results, retry)
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": OUTPUT_SCHEMA,
            "keep_alive": KEEP_ALIVE,
            "options": {"temperature": 0, "num_ctx": self.num_ctx},
        }
        started = time.monotonic()
        body = self._post("/api/chat", payload)
        elapsed = time.monotonic() - started
        output = _parse_output(body)
        self.last_call = {
            "model": self.model,
            "retry": retry,
            "latency_s": round(elapsed, 3),
            "dropped_canary_card_ids": dropped,
            "load_duration_s": round(body.get("load_duration", 0) / 1e9, 3),
            "eval_count": body.get("eval_count"),
            "output": output,
        }
        return output

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            self.host + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as response:
                raw = response.read()
        except socket.timeout as exc:
            # 3.10부터 socket.timeout은 TimeoutError 자신이라 HTTPError보다 먼저 잡아야 한다.
            raise TimeoutError(f"{self.timeout_s}s 내 응답 없음: {exc}") from exc
        except urllib.error.HTTPError as exc:
            # Ollama는 4xx 본문에 실제 원인을 담는다. 본문 없이는 디버깅이 불가능하다.
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:300]
            except Exception:  # noqa: BLE001 - 본문 없는 오류도 그대로 올려야 한다
                pass
            raise ConnectionError(f"HTTP {exc.code} {exc.reason} {detail}".strip()) from exc
        except urllib.error.URLError as exc:
            # URLError는 타임아웃도 감싸므로 reason을 보고 갈라야 한다.
            if isinstance(exc.reason, TimeoutError):
                raise TimeoutError(f"{self.timeout_s}s 내 응답 없음") from exc
            raise ConnectionError(f"{self.host} 접속 실패: {exc.reason}") from exc
        except OSError as exc:
            raise ConnectionError(f"{self.host} 접속 실패: {exc}") from exc

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            # JSONDecodeError는 ValueError의 하위라 계약 §3의 "형식 오류"와 같은 갈래다.
            raise ValueError(f"Ollama 응답이 JSON이 아님: {raw[:200]!r}") from exc


def _parse_output(body: dict[str, Any]) -> dict[str, Any]:
    """Ollama 응답 본문에서 합의된 두 필드를 꺼내고 형식을 강제한다."""
    content = (body.get("message") or {}).get("content")
    if not isinstance(content, str):
        raise ValueError(f"message.content 없음: {str(body)[:200]}")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"모델 출력이 JSON이 아님: {content[:200]!r}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"모델 출력이 객체가 아님: {content[:200]!r}")

    answer = parsed.get("answer")
    cited = parsed.get("cited_card_ids")
    # 공백뿐인 answer도 형식 오류다 (계약 §5, A의 validate_model_output과 같은 기준).
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError(f"answer가 비어 있지 않은 문자열이 아님: {parsed!r}")
    if not isinstance(cited, list) or not all(isinstance(item, str) for item in cited):
        raise ValueError(f"cited_card_ids가 문자열 배열이 아님: {parsed!r}")
    # 인용 ID의 실존 대조는 파이프라인 검증기 몫이다. 여기서는 형식만 본다.
    return {"answer": answer, "cited_card_ids": cited}
