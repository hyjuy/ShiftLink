# 2-hop MES·PDA explain 구현·검증

2026-10-22 KST. 시작 15:39:40, 검증 마감 확인 15:58:10(약 18분 30초), 시간 상한 16:09:40. 기준 HEAD는 `89ee154bba6ca3c673f36ce5a9cd97ba3f571afb`, 검증 당시 작업 브랜치는 `codex/kg-completed-pr`이었다. 당시 구현은 로컬 미커밋이며 기존 PR에 반영하지 않았다.

## 구현 결과

`SHIFTLINK_KG_MODE=explain`과 `SHIFTLINK_KG_DEPTH=2`를 선택한 경우에만 기존 최종 인용 카드의 분류 계층과 같은 증상 후보·문서 판본을 공유하는 참고 카드를 설명한다. 기본 off/1-hop의 응답 형태를 보존한다. depth 미지정·잘못된 값은 1-hop으로 처리한다.

수정한 실행 코드는 `shiftlink/rag/graph_explain.py`와 `shiftlink/mes/web/pda.js`의 graphContextElement뿐이다. 새 MES endpoint·테이블·패키지·모델 호출은 없다. query/server/storage/publication/S30h와 PDA HTML·센서·요청 코드는 변경하지 않았다.

- 허용 경로는 card → component → equipment, card → symptom ← card, card → document version ← card의 세 가지다.
- 관련 카드도 현재 요청의 카드 뷰에 유일하게 존재하고 accepted/L1/kb·설비/자산 범위·판본·정규화 전체 내용이 그래프와 일치해야 한다. 루트의 S30h 최종 청크 결합을 유지한다.
- 기존 게시 snapshot과 응답 직전 ticket 재검사를 유지한다. 그래프만 보고 현재 게시 상태를 승인하지 않는다.
- 모든 최종 인용 카드를 참고 목록에서 제외하고 응답 전체에서 중복을 제거한다. 루트당 10장, 전체 20장, 참고 카드당 경로 3개로 제한하고 생략 수를 알린다. 정렬은 ID 기준이며 관련성 순위가 아니다.
- 경로에는 노드 3개·원래 방향의 관계 2개를 기록한다. 양쪽 문서 locator와 needs_review를 보존한다. 참고 카드를 cited_card_ids·답변·근거·조치 목록에 넣지 않는다.
- PDA는 '연결된 참고 카드'를 접힌 영역으로 표시하고 답변 근거에 추가하지 않았음을 명시한다. 모든 값은 textContent로 표시한다.

기존 graph.json·validation.json·매핑·KB·장비 마스터·schema와 독립 시각화는 HEAD와 바이트 동일하다. 노드 289·관계 434의 기존 산출물을 사용한다. 재생성이나 편집을 하지 않았다.

## TDD와 실제 실행 결과

테스트를 먼저 작성해 미구현 depth 인자·related_cards와 PDA 참고 표시가 없어 실패함을 확인했다. 최초 Python RED는 12 failed / 5 passed, Node는 새 참고 영역 표시 assertion 실패였다. 사용자 지시에 따라 TDD checkpoint 커밋이나 staging은 하지 않았다.

구현 후 상한 시험의 `K-TWO-*` ID가 기존 `K-숫자4자리` 계약에 맞지 않는 픽스처 오류를 직접 GraphSnapshot 호출로 확인하고 ID만 수정했다. 순서 독립성 검사는 기존 1-hop 목록의 파일 순서를 바꾸지 않기 위해 새 2-hop 경로·참고 필드만 비교하도록 정정했다. 기대 상한이나 카드 자격 조건을 완화하지 않았다.

| 검사 | 결과 |
|---|---|
| 관련 Python 회귀 | 164개 통과, 53.04초. graph/explain/browser·S30h·MES·publication·source_conditions 포함 |
| 추가 최종 인용 제외 검사 포함 2-hop 단위/통합 | 23개 통과, 2.33초 |
| 그래프 핵심 + 하니스 + 실제 Chrome, 분기 coverage 실행 | 50개 통과, 24.62초. 위 최종 인용 추가 검사 전 측정 |
| 로더 coverage | 199문장 중 198 실행, 분기 포함 전체 표시 99%. 전체 저장소 커버리지를 뜻하지 않음 |
| Node | JS 문법 및 graph_explain·sensor_display·network_boot·unity_pda_link·symptom_rank·mes_query_pda·chat 7개 동작 검사 통과 |
| 최종 참고 영역 접근성 | 실제 Chrome depth 1·2 2개 통과, 22.95초. 1280/390px의 참고 제목·마지막 locator 가시성/가림 없음 확인 |
| 게시 무결성 | `ok: true`, `errors: []`, staged Python 확인. staging 변경 없음 |
| 보호 범위 | 원본·그래프·MES/S30h 바이트 동일, pda.js는 graphContextElement 밖 내용 동일 |

주요 재실행 명령(저장소 루트, 기존 의존성이 있는 Python):

```powershell
python -B -m pytest tests/test_graph_explain.py tests/test_graph_explain_two_hop.py tests/test_graph_explain_harness.py tests/test_graph_explain_browser.py tests/test_s30h.py tests/test_mes_query.py tests/test_publication_s30h.py tests/test_publication_worker.py tests/test_knowledge_publication.py tests/test_source_conditions.py -q -p no:cacheprovider --basetemp=docs/demo/kg/.pr-qa/two-hop-rerun
node --check shiftlink/mes/web/pda.js
node tests/pda_graph_explain.cjs
node tests/pda_sensor_display.cjs
node tests/pda_network_boot.cjs
node tests/unity_pda_link.cjs
node tests/pda_symptom_rank.cjs
node tests/mes_query_pda.cjs
node tests/pda_chat.cjs
python -B scripts/check_knowledge_publication.py
git diff --check
```

실제 Chrome 검사는 depth 1·2에서 PDA → 로컬 MES HTTP → 실제 graph.json → 사본 DB 질의 저장을 사용했다. 모델 답변은 결정적 fixture다. 답변·인용·센서 evidence 동일성, 센서 표시 보존, 키보드 펼침, 1280/390px, 그래프 누락, 보류 답변, 설비 변경 후 늦은 응답 차단을 확인했다. 장비·실제 모델 검증으로 세지 않는다. 임시 DB·응답·화면·coverage 자료는 docs/demo/kg 내부 무시 폴더에만 남겼다.

## /67 비교와 채택

동시에 실행 가능한 슬롯 제한으로 3명씩 두 묶음의 독립 읽기 전용 검토를 수행했다. 일곱 번째 판정자는 여섯 보고의 요약을 받아 평가했다. 아래 점수는 설계 검토의 상대 평가이며 테스트 통과율이나 현장 승인 점수가 아니다.

| 순위 | 관점 | 정확성 | 완결성 | 판단력 | 한 줄 판정 |
|---:|---|---:|---:|---:|---|
| 1 | Adversarial | 9 | 9 | 8 | 현재 게시 뷰·인용 루트 제외·사용자 합의 카드 상한을 가장 정확히 다룸 |
| 2 | Prior art | 8 | 9 | 9 | 기존 설명·저장·PDA·회귀 검사 구조 재사용에 가장 적합 |
| 3 | First principles | 8 | 9 | 8 | 공유 관계와 동등 조치·인과관계를 구분하는 의미 경계가 강함 |
| 4 | Minimalist | 8 | 8 | 9 | 기본 1-hop 보존과 세 경로로 제한하는 범위 통제가 강함 |
| 5 | Wildcard | 8 | 7 | 9 | 노드 3개·관계 2개의 검증 가능한 경로 표현 제안 |
| 6 | Maximalist | 7 | 9 | 7 | 생략 표시와 다양한 경계 검증은 유용하나 경로 수만 제한하는 제안은 수정 필요 |

합성안은 Adversarial의 카드 상한·현재 뷰 검사에 Prior art의 기존 통합 재사용을 결합했다. First principles의 의미 경고, Minimalist의 기본 동작 보존, Wildcard의 방향 있는 경로, Maximalist의 생략 표시와 작은 payload를 채택했다. 일부 보고의 '경로 10/20개' 대신 사용자와 합의한 '카드 10/20장'을 유지하고, 별도로 참고 카드당 경로 3개를 제한했다. 잘못된 depth는 기존 1-hop으로 복귀하도록 일관되게 정했다.

구현 후 Adversarial이 실제 코드를 다시 읽고 정확성·보안 차단 문제를 발견하지 않았다. 게시 snapshot의 전체 ticket 재검사가 참고 게시 카드에도 적용됨을 확인했다. 단, 출력 상한 전에 현재 그래프의 후보 경로를 열거하므로 매우 큰 그래프에 대한 CPU·메모리 상한까지 보장하지는 않는다. 현재 289노드 시연의 범위이며 대규모 성능 평가는 수행하지 않았다.

## 하니스 적용

기존 Python/Node/Playwright 및 게시 무결성 검사를 재사용했다. 전체 저장소 하니스 개편이나 CI workflow 수정은 하지 않았다.

- `.github/instructions/kg-explain.instructions.md`: 기본값·허용 경로·현재 카드 결합·UI 경계·상한·검증 명령을 파일 범위 지침으로 추가.
- `docs/failures/kg-explain-boundary.md`: 그래프 일치와 현재 게시 자격의 혼동, 참고 연결의 근거 승격, 경로 수 증가 위험을 예방 기록으로 추가. 실제 운영 사고로 서술하지 않음.
- `tests/test_graph_explain_harness.py`: 실패 기억의 검사명이 실제 실행 가능한 함수에 연결되는지 검사해 문서 드리프트 탐지.
- 동작 제약은 `test_graph_explain_two_hop.py`, 기존 S30h 불변성 검사, Node·실제 Chrome에서 실행한다. 기존 pytest 수집에 포함되며 원격 CI 실행 결과를 주장하지 않는다.

## 구현 검증 종료 당시 로컬 상태

기준 HEAD는 그대로이며 staging은 비어 있다. 추적 파일 8개 수정과 새 파일 5개(총 13개)가 미커밋 상태다. 커밋·push·PR 업데이트는 하지 않았다. `git diff --check`, 문서 상대 링크 및 변경 Python AST 확인도 통과했다.

## 미검증·제외 범위

독립 그래프 화면의 1/2-hop 전환, Jetson·Pi·실제 모델, 물리 입력, 현장 안전성, 상세 지연·대규모 부하 시험은 제외했다. AI 검토는 사람·제조사 승인을 대신하지 않는다. GraphRAG·검색/생성 성능 향상을 구현하거나 주장하지 않는다. 구현 검증 단계에서는 커밋·push·PR·main 병합·배포·서비스 재시작을 하지 않았다.

## 검증 결과 공유

이후 사용자가 검증한 2-hop 변경과 하니스·문서만 커밋·push하도록 승인했다. PR #334는 이미 2026-10-22 14:51:15 KST에 병합되어, 병합 SHA `2b45d3b1fc61febe52af361e1026026bd7a7ef7f` 위의 `codex/kg-two-hop-explain`에서 후속 PR로 공유한다. 공유 대상은 실행 코드 2개, 테스트 5개, 지침·문서 6개로 총 13개다. 임시 DB·응답·화면·coverage 자료와 다른 작업 변경은 제외하며 main 병합·장비 배포·서비스 재시작은 수행하지 않는다.

공유 직전 최신 main 기반 브랜치에서 graph_explain·two_hop·harness Python 49개(5.54초), JS 문법·PDA graph DOM, staged Python을 포함한 게시 무결성 검사(`ok: true`), staged diff 공백 검사를 다시 통과했다. 기존 실제 Chrome·관련 전체 회귀 결과는 위 구현 검증 기록을 따른다.
