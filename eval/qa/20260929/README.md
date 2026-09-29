# 평가셋 20260929 (질문 → 인용·답변 품질)

분장·일정: [`docs/collaboration/eval-qa-set-assignment-20260930.md`](../../../docs/collaboration/eval-qa-set-assignment-20260930.md)

| 파일 | 내용 |
|---|---|
| `prompts/writer.md` | 질문 작성 지시문 (작성자는 카드 비공개) |
| `prompts/labeler.md` | 정답 라벨 지시문 (별도 에이전트, 검색 코드 미사용) |
| `questions_raw.json` | 질문 70건 (Q-001~070) |
| `labels.json` | 70건 라벨 — KB-20260929-A accepted 30장 기준 |
| `split.py` | 선별·분할 (SEED 20260929, 재실행 시 바이트 동일) |
| `qa_test.json` | **평가용 30 = 계획서의 평가셋 30건.** 최종 채점만 |
| `qa_dev.json` | 개발용 30. 검색·프롬프트·모델 조정용 |
| `reserve.json` | 예비 10 (검수에서 제외된 문항 보충용) |
| `review.md` | 검수표 (평가용 먼저) |

## 생성 기록

| 단계 | 도구 | 지시문 sha256 (LF) |
|---|---|---|
| 질문 작성 | Claude Code 서브에이전트 (Claude Opus 5.5), 2026-09-30 | `writer.md` 52176955b465… |
| 정답 라벨 | Claude Code 서브에이전트 (Claude Opus 5.5), 2026-09-30 | `labeler.md` c8d81c117893… |

## 9/30 기준 수치

- 답 있음 23/70 (HPU 8, CV 4, RT 3, GR 8). 현장 질문의 약 1/3만 현재 KB로 답할 수 있다.
- 선별: 답 없는 문항 중 10건을 시드로 빼 60건. 분할 층 = (답 유무, 설비), 층 안은 난이도 순으로 번갈아 배정.
- 평가용: 답 있음 12 / 없음 18. 개발용: 11 / 19.
- 한 번도 정답이 되지 않은 카드 15장 (K-1001·1003·1008·1009·1012·1013·1016·1019~1023·1028~1030).

## KB가 바뀌면

카드 배치 B·T4가 승인되면 `labels.json`만 다시 붙이고 `qa_dev.json`·`qa_test.json`의 라벨을 갱신한다. **질문 문구와 split은 바꾸지 않는다** (`split.py` 재실행 금지 — 선별이 9/30 라벨에 의존).
