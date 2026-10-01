"""로컬 Ollama 어댑터: FixedPipeline이 호출하는 단일 ModelCall.

계약(① 합의 사항):
    model(mode=..., request=..., tool_results=..., retry=False)
        -> {"answer": str, "cited_card_ids": list[str]}

- mode는 query·handover. 출력 계약은 같고 시스템 프롬프트와 카드 문맥만 다르다.

- 이 어댑터는 호출 1건당 모델을 정확히 1회 부른다. 재시도는 파이프라인이 관리한다.
- 실패는 부분 결과를 돌려주지 않고 ModelCallError로 올린다.
- "검색 결과 없음" 게이트는 파이프라인이 모델 호출 전에 처리한다(D-26~29 §4.4).
"""

from __future__ import annotations

import copy
import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any

from shiftlink.agent.canary import CANARY_PREFIXES, has_canary

DEFAULT_MODEL = "qwen2.5:3b-instruct-q4_K_M"  # models.lock plan-B
DEFAULT_HOST = "http://localhost:11434"
# 호출 1건 상한 = 최초 로드(Jetson 29~31s 실측) + 입력 처리(~2s) + 출력 상한 생성(NUM_PREDICT/23tok/s ≈ 11s).
# 9/29 15W 측정에서 상한 없는 출력이 180s까지 멈춘 사례 3/20 — 오래 기다리지 않고 재시도·검토 큐로 넘긴다.
DEFAULT_TIMEOUT_S = 60.0
NUM_CTX = 2048
# 출력 토큰 상한. answer(ANSWER_MAX_CHARS자)+인용 JSON이 들어가고, 끝없이 이어지는 생성을 끊는다.
# 9/29 측정: 상한 없을 때 평균 243토큰 → 생성이 지연의 대부분(입력 처리는 1~2s).
NUM_PREDICT = 256
ANSWER_MAX_CHARS = 160
# 모델 상주, 재로딩 방지. 반드시 정수 -1 — 문자열 "-1"은 Ollama가 duration 파싱에 실패해 400을 낸다.
KEEP_ALIVE = -1
# 질의 모드에서 모델에 넘기는 답변 후보 수. 10/1 Jetson 실측(31문항, 카드 62장): 후보 5장을 주면
# 모델 1순위 인용 정답이 exaone 5~23/29, qwen 2~10/29로 검색 1위(28/29)보다 낮았다.
# 1장만 넘기면 인용 정답 = 검색 1위 정답이다. 인계 모드는 T4 실측 전이라 그대로 둔다.
QUERY_MAX_CANDIDATES = 1

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
# 호출마다 output_schema()가 복사본에 후보 ID enum을 건다. 이 원본은 바꾸지 않는다.
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        # maxLength: 문법 제약으로 answer가 스스로 닫히게 해 NUM_PREDICT에 잘려 JSON이 깨지지 않게 한다.
        "answer": {"type": "string", "minLength": 1, "maxLength": ANSWER_MAX_CHARS},
        "cited_card_ids": {
            "type": "array",
            "items": {"type": "string", "pattern": "^K-\\d{4}$"},
            "minItems": 1,
            "maxItems": 3,
            "uniqueItems": True,
        },
    },
    "required": ["answer", "cited_card_ids"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "너는 제조 현장 교대 인계 보조다. 아래 지식 카드에 적힌 내용만으로 답한다.\n"
    "규칙:\n"
    f"1. answer는 항상 한국어 두세 문장, {ANSWER_MAX_CHARS}자 이내로 채운다. 빈 문자열이나 공백만 두지 않는다.\n"
    "2. cited_card_ids에는 답변 후보 카드의 card_id를 최소 한 개 넣는다.\n"
    "   질문의 증상과 카드의 증상·제목이 가장 일치하는 카드를 먼저 인용하라.\n"
    "   후보에 없는 ID를 지어내지 않고, 같은 ID를 두 번 넣지 않는다. 질문과 덜 맞아도 가장 가까운 후보를 인용한다.\n"
    "   안전 참고 카드는 시스템이 따로 보여주므로 인용하지 않는다.\n"
    "3. 카드에 없는 내용은 절대 만들어내지 않는다. 카드 문구를 벗어난 추정·수치를 덧붙이지 않는다.\n"
    "4. 안전·단계·인계 방법 블록은 시스템이 카드에서 직접 만든다. 너는 요약 answer와 인용만 낸다.\n"
    "5. JSON 객체 하나만 출력한다. 설명·코드펜스를 붙이지 않는다."
)

HANDOVER_SYSTEM_PROMPT = (
    "너는 제조 현장 교대 인계 보조다. 입력은 넘기는 사람이 쓴 인계 메모다. "
    "아래 지식 카드의 인계 방법에 맞춰 다음 근무자에게 넘길 요지를 정리한다.\n"
    "규칙:\n"
    f"1. answer는 항상 한국어 두세 문장, {ANSWER_MAX_CHARS}자 이내로 채운다. 빈 문자열이나 공백만 두지 않는다.\n"
    "   메모에 적힌 사실 중 카드의 '인계할 정보'(required_context)에 해당하는 것을 담는다.\n"
    "   카드가 요구하는데 메모에 없는 항목은 '확인 필요'로 적는다.\n"
    "2. cited_card_ids에는 메모 상황에 가장 맞는 답변 후보 카드의 card_id를 최소 한 개 넣는다.\n"
    "   후보에 없는 ID를 지어내지 않고, 같은 ID를 두 번 넣지 않는다.\n"
    "   안전 참고 카드는 시스템이 따로 보여주므로 인용하지 않는다.\n"
    "3. 메모와 카드에 없는 사실(수치·원인·조치)은 절대 만들어내지 않는다.\n"
    "4. 인계 대상·시점·방법·확인 블록은 시스템이 카드에서 직접 만든다. 너는 요약 answer와 인용만 낸다.\n"
    "5. JSON 객체 하나만 출력한다. 설명·코드펜스를 붙이지 않는다."
)
SYSTEM_PROMPTS = {"query": SYSTEM_PROMPT, "handover": HANDOVER_SYSTEM_PROMPT}


def retry_prompt(candidate_ids: list[str]) -> str:
    """재시도 안내. 예시 ID 대신 이번 호출의 실제 후보 ID를 보여준다."""
    example = json.dumps({"answer": "...", "cited_card_ids": candidate_ids[:1]}, ensure_ascii=False)
    return (
        "\n\n[재시도] 직전 출력이 검증에 실패했다. "
        f"{example} 형태의 JSON 객체 하나만 출력하고, "
        f"cited_card_ids에는 답변 후보 ID({', '.join(candidate_ids)}) 중에서만 넣어라."
    )


def output_schema(candidate_ids: list[str]) -> dict[str, Any]:
    """OUTPUT_SCHEMA 복사본에 이번 후보 ID를 enum으로 건다. 모델이 후보 밖 ID를 낼 수 없다."""
    schema = copy.deepcopy(OUTPUT_SCHEMA)
    cited = schema["properties"]["cited_card_ids"]
    if candidate_ids:
        cited["items"] = {"type": "string", "enum": candidate_ids}
    else:
        # 후보가 없으면 인용을 강요하지 않는다. 빈 배열은 파이프라인 검증기가 검토 큐로 보낸다.
        cited["minItems"] = 0
    return schema


# 호출자가 잡을 오류 4종. A 계약 §3대로 표준 예외만 쓴다 — agent가 edge를 import할 필요가 없다.
MODEL_CALL_ERRORS = (NotImplementedError, TimeoutError, ConnectionError, ValueError)


def card_context(
    tool_results: dict[str, Any], mode: str = "query",
) -> tuple[list[dict[str, Any]], list[str]]:
    """카드를 화이트리스트 필드로 축약한다. 카나리가 섞인 카드는 빼고 ID를 함께 돌려준다.

    인계 모드에서는 T4 카드의 handover_method(5요소)도 함께 넘긴다.
    """
    context: list[dict[str, Any]] = []
    dropped: list[str] = []
    for card in tool_results.get("cards", []):
        trimmed = {
            field: card[field]
            for field in MODEL_CARD_FIELDS
            if card.get(field) is not None
        }
        method = (card.get("type_payload") or {}).get("handover_method")
        if mode == "handover" and method:
            trimmed["handover_method"] = method
        if has_canary(card):
            dropped.append(card.get("card_id", "<no-id>"))
            continue
        context.append(trimmed)
    return context, dropped


def split_context(
    tool_results: dict[str, Any], mode: str = "query",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """축약 카드를 답변 후보(검색 순위 순)와 안전 참고(검색에 안 걸린 안전 카드)로 나눈다.

    검색 결과에 든 안전 카드는 후보로 남는다. ranked_cards가 없는 구 호출자는 전부 후보다.
    질의 모드는 검색 상위 QUERY_MAX_CANDIDATES장만 후보로 둔다.
    """
    cards, dropped = card_context(tool_results, mode)
    ranked = tool_results.get("ranked_cards")
    if ranked is None:
        return cards, [], dropped
    ranked_ids = [card.get("card_id") for card in ranked]
    by_id = {card.get("card_id"): card for card in cards}
    candidates = [by_id[card_id] for card_id in ranked_ids if card_id in by_id]
    if mode == "query":
        candidates = candidates[:QUERY_MAX_CANDIDATES]
    references = [card for card in cards if card.get("card_id") not in ranked_ids]
    return candidates, references, dropped


def build_messages(
    mode: str,
    request: Any,
    tool_results: dict[str, Any],
    retry: bool = False,
) -> tuple[list[dict[str, str]], list[str]]:
    """Ollama /api/chat용 messages와, 카나리로 제외된 카드 ID 목록을 만든다."""
    candidates, references, dropped = split_context(tool_results, mode)
    candidate_ids = [card.get("card_id") for card in candidates]
    dropped = sorted(set(dropped + tool_results.get("dropped_canary_card_ids", [])))
    # 질의는 question, 인계는 memo_text — 라우터가 둘 중 하나만 채운다.
    ask = getattr(request, "question", None) or getattr(request, "memo_text", "")
    ask_label = "인계 메모" if mode == "handover" else "입력"
    # observations는 Observation 모델 목록이다(구 호출자는 dict를 넘길 수 있어 둘 다 받는다).
    observations = [
        obs.model_dump(mode="json") if hasattr(obs, "model_dump") else obs
        for obs in (getattr(request, "observations", None) or [])
    ]

    parts = [f"모드: {mode}", f"{ask_label}: {ask}"]
    if observations:
        parts.append(f"관측값: {json.dumps(observations, ensure_ascii=False)}")
    # 후보 한 줄 색인: 긴 JSON보다 먼저 제목·증상으로 질문과 맞춰 보게 한다.
    index = "\n".join(
        f"{card.get('card_id')}: {card.get('title', '')} / {card.get('symptom') or '-'}"
        for card in candidates
    )
    parts.append(f"답변 후보 색인:\n{index}")
    parts.append(f"답변 후보 카드:\n{json.dumps(candidates, ensure_ascii=False, indent=1)}")
    if references:
        # 제목만 준다. 본문을 주면 모델이 질문 대신 안전 카드를 요약했다(9/29 exaone 측정).
        titles = "\n".join(f"{card.get('card_id')}: {card.get('title', '')}" for card in references)
        parts.append(f"안전 참고 카드(시스템이 따로 보여준다. 인용하지 않는다):\n{titles}")
    user = "\n\n".join(parts)
    if retry:
        user += retry_prompt(candidate_ids)

    return [
        {"role": "system", "content": SYSTEM_PROMPTS[mode]},
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
        if mode not in SYSTEM_PROMPTS:
            raise NotImplementedError(
                f"{mode!r} 모드는 어댑터 범위 밖이다. query·handover만 처리한다."
            )
        messages, dropped = build_messages(mode, request, tool_results, retry)
        candidate_ids = [card.get("card_id") for card in split_context(tool_results, mode)[0]]
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": output_schema(candidate_ids),
            "keep_alive": KEEP_ALIVE,
            "options": {"temperature": 0, "num_ctx": self.num_ctx, "num_predict": NUM_PREDICT},
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
            "candidate_card_ids": candidate_ids,
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
    # Ollama 문법은 uniqueItems를 강제하지 못한다. 중복만으로 재시도하지 않게 순서를 지켜 한 번씩 남긴다
    # (9/29 exaone 재시도 8/20의 주원인). 인용 ID의 실존 대조는 파이프라인 검증기 몫이다.
    return {"answer": answer, "cited_card_ids": list(dict.fromkeys(cited))}
