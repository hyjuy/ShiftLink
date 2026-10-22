# 지식 그래프 완료 결과 PR 검증

2026-10-22 KST. 원래 완료 브랜치와 미커밋 자료를 보존하고 `codex/kg-completed-pr`에서 PR을 준비했다.

## 기준과 범위

- 공통 기준 B: `5167376b5ded1e33725394f2b65cb6977c121dec`.
- 완료된 통합: `10053831ea429ea9574b00d89c59fb5bf1e42ae7`.
- 완료된 explain·MES·PDA 연결: `853963a665d7e91058727f4e3d60bcae957f8b0a`.
- PR 기반 main: `75823786b44befc2b6fb75b531d6344a08bd82c0`.

main에는 최초 증상 인계 SHA의 파일이 이미 존재했다. 해당 폴더가 원 인계 `704c7b6c3ee96289822e30312a5a0c91e527e5d5`와 동일함을 확인하고, 완료 통합의 승인된 R1–R6 수정으로 충돌을 해결했다. 매핑 JSON은 생성기로 재생성했다. S30h 충돌에서는 main의 unit_guard와 출처 조건 처리를 유지하고 기존 반환값에 `cited_chunks` 전달만 추가했다. server·query의 게시 ticket 재검사와 저장 동작을 유지했다.

`.recheck-*`, `.revision-*`, `viz/.qa`, `.explain-qa`, `.explain-live-qa`의 임시 파일·화면·응답 사본은 포함하지 않는다. 기존 완료 커밋의 42항목 브라우저 검증기를 `viz/verify.cjs`로 옮겨 재실행 가능하게 유지했다. 새 결과 파일도 `.gitignore`로 제외한다. DB 백업·모델·인덱스·배포 기록 PR의 변경은 포함하지 않는다.

## 이번에 실행한 검증

| 검사 | 결과 |
|---|---|
| 증상 생성기·독립 검사 | 통과. 카드 86, 안전 56, null 13, 증상 개념 18, 연결 카드 18 |
| 빌더 self-test | 35개 통과 |
| 생성물 | 노드 289 / 관계 434, 스키마 오류 0, 고아 노드 0 |
| 원문·보류 | 원본 카드 필드 보존, 안전/null 증상 연결 각각 0, 판본 없는 인용 42건 보존·보류 |
| 결정성 | 재생성 graph.json·validation.json 바이트 동일, 기존 완료 커밋의 산출물과도 동일 |
| 원본 보호 | KB·장비 마스터·schema·분담 계획·publication.py·storage.py가 main과 바이트 동일 |
| Python 핵심 회귀 | graph_explain, 실제 Chrome explain, S30h, MES query, 게시 S30h/worker/knowledge_publication: **126개 통과** |
| main 출처 조건·게시 Chrome | **14개 통과**. 게시 브라우저 검증은 출력 경로만 KG 임시 폴더로 바꾼 사본으로 실행 |
| 게시 무결성·정적 검사 | `python scripts/check_knowledge_publication.py` 통과(스테이징 Python 포함), `git diff --cached --check` 통과 |
| PDA | JS 문법 및 graph_explain·sensor_display·network_boot·unity_pda_link·symptom_rank·mes_query_pda·chat 7개 동작 검사 통과 |
| 독립 그래프 Chrome | **42개 PASS**, Runtime 예외 0. mock 없는 실제 파일 로드·필터·선택·이웃·원문·locator·후보/합성 표시·키보드·404/재시도 확인 |

Python은 기존 프로젝트 가상환경을 사용했다. 핵심 재실행 명령은 [explain 안내](explain.md), 그래프 생성·브라우저 명령은 [README](README.md)에 있다. pytest 임시 파일은 `docs/demo/kg/.pr-qa/`, explain 브라우저 출력은 `.explain-qa/`, 그래프 브라우저 출력은 `viz/.qa/`에만 두고 PR에서 제외했다.

## 기존 실제 모델 확인과 한계

이전 장비 점검에서는 실행 중인 Jetson의 실제 S30h 응답 1건과 인용 K-1004 및 실제 선택 청크를 확보했다. 그 단일 생성 결과에 로컬 off/explain 후처리를 적용해 `status=ok`와 기존 답변·인용·센서 evidence 필드 보존을 확인했다. 당시 답변 모델은 exaone-rag-mes-ck176, judge는 exaone-sft-judge, 임베딩은 embeddinggemma:300m, 인덱스는 3,950행 × 768차원이었다. 장비 응답·색인 사본은 포함하지 않는다.

이는 독립된 두 번의 실제 생성 비교나 Jetson explain 배포 검증이 아니다. **이번 PR 준비에서는 장비·실제 모델을 호출하지 않았다.** 이번 Chrome 검사는 실제 브라우저·MES HTTP·그래프와 결정적 답변 fixture를 사용했다. 실제 Pi의 explain 화면·물리 입력과 현장 안전은 미검증이다.

기본 모드는 off다. explain은 최종 인용 카드에 설명만 붙이고 검색·순위·생성·센서 수신을 바꾸지 않는다. 검수 전 증상 후보, 합성 Asset 10개, AssetPart 미구현, 판본 없는 인용 보류는 그대로다. AI 검토는 사람·제조사 승인으로 간주하지 않는다. GraphRAG·성능 향상·정식 온톨로지 달성을 주장하지 않는다. main 병합·Jetson/Pi 배포·서비스 재시작은 수행하지 않았다.
