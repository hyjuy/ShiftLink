# 클라우드 인계 (2026-10-21 밤, Claude)

## 목표와 제약
- 목표 1: 시연 모델이 MES 값을 읽고 답하게 한다. 시연 구성은 ck176(또는 ck186) + MES 스위치다.
- 목표 2: 발표용 발전 지표를 측정한다. 대상은 hybrid(C1) → RAG v2 + ck106(C2) → S30h(C3) → S30h + ck176 + MES(C4), 추가로 C4b(ck186)다.
- 제약:
  - 봉인 60(`ShiftLink-sealed/`)은 Codex에 보여 주지 않는다. 해시와 집계만 공유한다.
  - 비밀값을 기록하지 않는다.
  - PR·push·배포는 사용자에게 묻고 한다. Jetson 재시작(sudo)은 사용자가 한다. `ollama rm`은 하지 않는다.
  - 결과를 본 뒤 지표 정의를 바꾸지 않는다(`METRICS.md` 고정).
  - 파이썬은 Edit 도구로만 고친다(heredoc·sed 금지).
  - 답은 한국어로 한다.

## 완료
- 브랜치 `feat/mes-answer-block-20261021`(worktree `Desktop/ShiftLink-wt-mesblock`), draft **PR #326**.
  - 커밋: 4b48423(MES_BLOCK), 64b43ff(EVENT_LABEL), d3a6cde(MES_ONLY), 585a71e(MES_PREFIX), **d4ff248(P_FIX)**.
  - 스위치는 모두 기본 꺼짐이다.
- **p_insuff 버그**: `generate.p_insufficient`가 strip() 키 충돌로 낮은 확률이 높은 확률을 덮어썼다. `SHIFTLINK_S30H_P_FIX=1`로 고친다.
- 테스트:
  - `tests/test_s30h.py` 20개 통과.
  - 전체 1274개 통과.
  - test_deploy_services 3건은 WSL 환경 오류로 실패한다.
  - test_pda_accounts는 기존 실패라 제외했다.
- Jetson에 `exaone-rag-mes-ck176`, `exaone-rag-mesv2-ck186`을 등록했다. ck106은 유지한다.
- Codex 최종 실행: `ShiftLink-records/experiments/mesfinal_20261021/`. AI 예비 판정은 `AI_PRELIM_REVIEW.md`.
  - 충분/보완/오류: ck176 7/17/6, ck186 11/14/5.
  - 개발 셋 거절: ck176 19, ck186 37.
- 발전 지표 실험: `ShiftLink-records/experiments/progress_20261021/`
  - 문서·스크립트: `METRICS.md`(사전 고정), `progress_run.py`(Jetson 실행), `metrics_table.py`(A~C 집계), `ragas_sheet.py` + `ragas_compact.py`(블라인드 RAGAS 시트).
  - Jetson `~/shiftlink/eval-20261021/out/`: `progress.jsonl`, `stages.log`, `run.mem`, `run_c4b.mem`.
  - **C1·C2·C3·C4 완료.** C4b는 대기 스크립트 `run_c4b.sh`가 실행했다. 끝나면 `stages.log`에 `C4B_DONE_RESTORED_C3`가 찍히고, C3 시연 모델이 다시 메모리에 올라간다.
  - PC 사본: `ShiftLink-sealed/progress_20261021/`(S1 포함 파일).
- 중간 결과(C4b 제외):

| | 봉인 60 올바른 행동률 | 개발 셋 올바른 행동률 | MES 현재값 반영 | 경보 구분 | 상태 모순 | p95 |
|---|---|---|---|---|---|---|
| C1 | 45% | 61% | 6/42 | 0/8 | 1 | 7.4초 |
| C2 | 52% | 57% | 0/42 | 0/8 | 3 | 7.7초 |
| C3 | 50% | 63% | 0/42 | 2/8 | 12 | 9.0초 |
| C4 | 48% | 44% | 42/42 | 8/8 | 0 | 10.4초 |

- RAGAS(Claude 블라인드 채점, faithfulness / relevancy):

| | 봉인 60 | MES 충돌 셋 |
|---|---|---|
| C1 | 0.79 / 0.48 | 0.75 / 0.41 |
| C2 | 0.96 / 0.70 | 0.94 / 0.36 |
| C3 | 0.96 / 0.74 | 0.99 / 0.32 |
| C4 | 0.93 / 0.70 | 0.94 / 0.81 |

  - 채점 파일: `ragas/s3_b1`, `s3_b2`, 그리고 `ShiftLink-sealed/progress_20261021/ragas_s1_b1`, `ragas_s1_b2`의 `judged.jsonl`. key는 `key.json`.

## 다음 순서
1. Jetson `stages.log`에서 `C4B_DONE`을 확인한다. 이어서 `progress.jsonl`, `stages.log`, `run_c4b.mem`을 `ShiftLink-sealed/progress_20261021/`로 가져온다(scp, `jetson@<tailscale 주소>`, 주소는 `~/.ssh/config`).
2. `python metrics_table.py <sealed>/progress.jsonl --s1 ShiftLink-sealed/newq_20261019/questions_v2.jsonl --repo ../../../ShiftLink-wt-mesblock --stages-log <sealed>/stages.log --mem <sealed>/run.mem <sealed>/run_c4b.mem`
3. `ragas_sheet.py ... --stages C4b`로 `ragas/s3_b3`와 `<sealed>/ragas_s1_b3`를 만든다. 이어서 `ragas_compact.py`로 압축본을 만들고 채점해 `judged.jsonl`(UTF-8)에 쓴다.
4. Codex 2차 채점 `ragas/s3_b*/verdicts_codex.jsonl`이 오면 일치도를 계산한다. faithfulness는 상관, relevancy는 가중 카파.
5. 최종 표와 발표 요약을 쓴다. 사용자와 정할 것: 시연 모델(ck176 / ck186), MES_ONLY 범위 축소 여부.
6. Jetson에서 봉인 파일 `~/shiftlink/eval-20261021/data/s1.jsonl`을 삭제한다.
7. AGENTS.md(메인 폴더) 맨 위에 한 줄을 쓰고, AGENT_MEMORY에 절을 추가한다.

## 클라우드 세션에 줄 것 (사용자 준비)
클라우드 세션은 이 PC의 파일과 Jetson에 접근할 수 없다. 아래를 업로드하거나 저장소에 올려서 넘긴다. 봉인 60 관련 파일은 Codex가 볼 수 없는 곳에만 둔다.
1. 이 파일(`cloud-handoff.md`). 브랜치 `feat/mes-answer-block-20261021`(PR #326)에 커밋하면 클라우드가 바로 읽는다.
2. 코드: PR #326 브랜치(origin에 있음, d4ff248).
3. 실험 폴더 `ShiftLink-records/experiments/progress_20261021/` 전체를 zip으로 묶는다.
   - 스크립트: `METRICS.md`, `metrics_table.py`, `ragas_*.py`
   - `ragas/s3_b1`, `ragas/s3_b2`의 `judged.jsonl`과 `key.json`
4. 집계 입력:
   - `ShiftLink-records/experiments/mesconflict_20261021/`(situations.json, build.py)
   - `rag1013/dev.json`
   - `mesft_20261021/index/chunks_700.jsonl`
   - `mesft_20261021/finalcheck.py`
5. Jetson 결과(C4b 완료 후 PC에서 회수): `progress.jsonl`, `stages.log`, `run.mem`, `run_c4b.mem`
   - `progress.jsonl`에는 봉인 60의 질문과 답이 들어 있다. 클라우드에 올려도 되는지 사용자가 판단한다.
   - 안 되면 S1을 뺀 사본만 넘기고, S1 집계와 S1 RAGAS는 PC에서 한다.
6. 봉인 S1 파일(`ShiftLink-sealed/newq_20261019/questions_v2.jsonl`, `ShiftLink-sealed/progress_20261021/ragas_s1_*`)은 5와 같은 판단을 따른다.
7. Codex 2차 채점 결과 `verdicts_codex.jsonl`(도착하면)

**사용자 결정(10/21): 봉인 S1 포함 결과를 클라우드에 올려도 된다.**
클라우드가 Jetson 결과를 받지 못하면 Codex가 Jetson에서 직접 가져온다. 위치는 `~/shiftlink/eval-20261021/out/`이고, 파일은 progress.jsonl, stages.log, run.mem, run_c4b.mem이다. 받은 파일은 `ShiftLink-sealed/progress_20261021/`에 둔다. 읽기만 하고 서비스와 모델은 건드리지 않는다.

클라우드 세션 첫 지시 예시:
> cloud-handoff.md를 읽고 '다음 순서' 2~5를 진행해. 업로드한 progress_20261021.zip과 progress.jsonl을 써. 봉인 S1은 [포함/제외]. PR·push·배포는 묻고 해.

## 주의
- C4는 MES_ONLY 때문에 지식 질문 거절이 크게 줄었다(개발 셋 19/73). 발표에서 교환 관계로 함께 보여 준다.
- 사용자 판정이 필요한 안전 후보:
  - NQ-D14: C4가 "엎드려 눕히고 흉부압박"이라고 답했다(근거 문서 문장).
  - NQ-M01: Kaishan 일정을 GA37 값으로 제시했다(C1·C3·C4).
  - MX-C27: 관측이 없는 온도를 정상이라고 답했다.
- 인스턴스는 사용자가 destroy해도 된다고 확인했다(회수 완료).
- 이 파일은 커밋하지 않았다.
