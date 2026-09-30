# autoresearch 규칙 (ShiftLink 검색·프롬프트 개선)

[karpathy/autoresearch](https://github.com/karpathy/autoresearch) 방식: **고치는 파일 하나 · 평가 고정 · 지표 하나 · 실험마다 커밋 → 좋아지면 유지, 아니면 되돌림 · 결과 표 기록.**
사람은 이 파일만 고친다. 에이전트는 아래 규칙대로 반복한다.

## 시작

1. 태그를 정한다(예: `retr-1001`). `git worktree add -b autoresearch/<tag> ../ShiftLink-ar-<tag> origin/main`
2. 기준선을 잰다: `python eval/qa/route_score.py` → `bench/experiments.tsv`에 `baseline` 한 줄.
3. 아래 반복을 시작한다.

## 루프 A — 검색 (Jetson 불필요, 1회 5초 이내)

| 항목 | 내용 |
|---|---|
| 고칠 수 있는 파일 | `shiftlink/rag/retrieval.py` **하나** |
| 고정 (수정 금지) | `eval/qa/**`, `docs/data/knowledge_cards/**`, `shiftlink/agent/**`, `tests/**`, 이 파일 |
| 주 지표 | `dev_route_acc` (개발용 30: 답 있는 문항은 검색 1위가 정답, 답 없는 문항은 검색 결과 없음) |
| 보조 지표 | `sanity_route_acc` (9/29 20문항 + 예비 10) |
| 기준선 | main `f71a77f`, KB 41장: dev **18/30**, sanity **26/30** |

반복:
1. 가설 하나를 정하고 `retrieval.py`를 고친다.
2. `python -m pytest -q` — 실패하면 고치거나(오타 수준) 버린다.
3. 커밋 (`[claude] ar(<tag>): <가설 한 줄>`).
4. `python eval/qa/route_score.py`
5. 판정:
   - dev가 **1문항 이상** 오르고 sanity가 2문항 이상 떨어지지 않으면 **keep** (브랜치 유지).
   - dev가 같으면: 코드 줄 수가 줄었을 때만 keep. 아니면 discard.
   - 그 외 **discard**: `git reset --hard HEAD~1`.
6. `bench/experiments.tsv`에 한 줄 (variable=retrieval, primary_metric=dev_route_acc, notes에 커밋 해시·가설·sanity 값).

## 루프 B — 모델·프롬프트 (Jetson, 사람 확인 후에만)

| 항목 | 내용 |
|---|---|
| 고칠 수 있는 파일 | `shiftlink/edge/ollama.py` **하나** |
| 주 지표 | 31문항 선택 세트에서 정답 카드를 첫 번째로 인용한 수 (sel@1) |
| 게이트 | p95 ≤ 6초, 검토 대기 증가 없음 |
| 1회 시간 | 약 3분 |

Jetson은 팀 공유 장비다. 시작 전 `free -h`·`ollama ps` 확인, 모델은 한 번에 하나, 끝나면 `ollama stop`. 터널이 끊기면 멈추고 마지막 완료 실험을 표에 적는다.

## 금지

- **`eval/qa/20260929/qa_test.json`(평가용 30)을 읽거나 쓰지 않는다.** 10/14 최종 채점 1회용.
- 질문 문장, 질문에만 나오는 단어 목록, 카드 ID를 코드에 넣지 않는다 (`git diff`에서 확인).
- 패키지 설치 금지 (표준 라이브러리와 기존 의존성만).
- 한 커밋에 가설 하나.

## 단순함

같은 점수면 더 짧은 코드. 1문항 올리려고 코드를 크게 늘리는 변경은 되돌릴 이유다.

## 실험 후보 (루프 A)

현장어 동의어(기름→오일/작동유, 소리→소음, 끼익→끽) · 제목·증상 가중치 · 접두 음절 일치 길이 · 불용어 · 관련도 하한(현재 5) · IDF/BM25 · component 필드 가중.

## 루프를 멈추는 때

사람이 멈출 때, 또는 한 태그에서 연속 15회 discard. 끝나면 keep 커밋만 남은 브랜치로 PR을 올리고, 그때만 평가용 30이 아닌 **개발용·보조 지표**로 효과를 보고한다.
