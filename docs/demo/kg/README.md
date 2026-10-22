# ShiftLink 지식 그래프 통합 결과

검증 기록: 2026-10-22 (Asia/Seoul), 계약 `kg-demo-v1`.

현재 PR은 완료 커밋 `1005383`·`853963a`를 main `7582378` 위에 통합했다. 아래 미커밋·PR 미수행 설명은 당시 이력이며, 이번 범위와 재검증 결과는 [PR 검증 기록](pr-validation-20261022.md)을 따른다.

사용자의 후속 수정 지시에 따라 증상 문구 R1–R6을 수정하고 생성기·빌더로 산출물을 갱신했다. 실제 증상 매핑을 사용하는 그래프는 노드 **289개**, 관계 **434개**, 스키마 오류 **0건**, 고아 노드 **0개**다. 모든 증상 연결은 검수 전 후보 상태를 유지한다.

## 기준과 현재 상태

| 항목 | 값 |
|---|---|
| 작업트리 | `C:/Users/hyjuy/.codex/worktrees/kg-integration/ShiftLink` |
| 통합 브랜치 | `codex/kg-integration` |
| B / 검증 당시 HEAD | `5167376b5ded1e33725394f2b65cb6977c121dec` |
| 변환 인계 SHA | `6df10055ca37d87f6db266a4a74021ab28ddebd8` |
| 증상 인계 SHA | `704c7b6c3ee96289822e30312a5a0c91e527e5d5` |
| 시각화 인계 SHA | `87438a9b5c964934470305e22eae6285664911e8` |

인수 기준은 사용자가 변경한 **지정 단일 커밋 parent diff**다. `git diff --name-only --no-renames "${KgSha}^" $KgSha`로 변환 4개·증상 5개·시각화 10개 파일과 소유 폴더 밖 변경 0개를 확인했다. 세 SHA 모두 B의 후손이다. 변환·증상은 원격 브랜치 끝과 일치했고 시각화는 브랜치가 없지만 origin에서 지정 SHA 직접 fetch에 성공했다. 확인되지 않은 최신 SHA로 바꾸지 않았다.

기존 `cherry-pick --no-commit` 적용 결과를 재인수했다. 이번 후속 수정으로 증상 생성기·HANDOFF·생성 매핑·검수 문서는 인계 SHA와 달라졌고, graph·validation은 빌더로 재생성했다. 검증 당시 변경은 모두 미커밋이고 staging은 비어 있었다. 이후 사용자가 검증된 KG 결과만 커밋하고 `codex/kg-integration`으로 push하도록 지시했다. 이 문서를 포함한 통합 결과가 공유 대상이며, 체크아웃한 정확한 커밋은 `git rev-parse HEAD`로 확인한다. PR·main 병합·배포는 이번 공유 범위에 포함하지 않는다.

## 반영한 수정

| 요청 | 반영 내용 |
|---|---|
| R1 / K-1004 | 동일 조건 비교와 MES 정상 범위·임계값 출처 복원. 소음 AND (유량 저하 OR 압력 저하) AND 거품 유지 |
| R2 / K-1105 | 보류 카드라는 요약을 기존 연결 유지 여부로 정정 |
| R3 / K-1301 | 출력 저하를 추가 관측으로 보존하고 별도 개념화 보류라고 설명 |
| R4 / K-1107 | 유지압·장력 관측을 인정하고 설비·단위·시각·공급원 확인 차이 때문에 보류함을 명시 |
| R5 / K-1307·K-1323 | 별도 개념 분류가 트립·정지의 동시 발생을 배제하지 않도록 정의·메모 보완 |
| R6 / K-1323 | 단일 복합 개념이 아닌 독립 후보 3개로 설명 |

수정 근거와 처리 상태는 [수정 요청 및 결과](revision-requests.md), 코드 차이는 통합 커밋 `10053831ea429ea9574b00d89c59fb5bf1e42ae7`에 기록돼 있다. 전체 K-1323 know_how·rationale에는 잘못된 윤활유 상표와 지정 유종 확인 근거가 있어 “지정 외 윤활유”를 원인 후보로 제외한 표현은 유지했다. 제품 간 호환성을 새로 판정하지 않았다.

## 실행

```powershell
# 저장소 루트에서 실행
python -X utf8 -B docs/demo/kg/symptoms/build_symptom_concepts.py
python -X utf8 -B docs/demo/kg/symptoms/check_symptoms.py
python -X utf8 -B docs/demo/kg/build/build_graph.py --self-test
python -X utf8 -B docs/demo/kg/build/build_graph.py
node docs/demo/kg/viz/verify.cjs
python -X utf8 -B scripts/check_knowledge_publication.py
```

Python 표준 라이브러리를 사용한다. 브라우저 자동 검증은 Node 24와 설치된 Chrome을 사용하며 `KG_CHROME`으로 Chrome 경로를 지정할 수 있다. 기본 경로는 `C:/Program Files/Google/Chrome/Application/chrome.exe`다. 검증기는 로컬 HTTP 서버와 KG 폴더 안 임시 프로필을 만들고 종료·정리한다. headless Chrome 검증이며 실제 모바일 기기 시험은 아니다.

직접 화면을 열려면 다음 서버를 실행하고 <http://127.0.0.1:8766/viz/>로 접속한다. 사용 중인 포트라면 다른 포트를 선택한다.

```powershell
python -m http.server 8766 --bind 127.0.0.1 --directory docs/demo/kg
```

기본 주소 `../build/graph.json`이 실제 생성물을 읽는다. `?mock=1` 없이 시연하며 서버는 Ctrl+C로 종료한다. 이전에 열어 둔 다른 포트의 서버는 다른 작업트리일 수 있다.

## 실제 집계

| 노드 타입 | 수 | 관계 타입 | 수 |
|---|---:|---|---:|
| EquipmentType | 83 | PART_OF | 76 |
| Symptom | 18 | DESCRIBES_SYMPTOM | 20 |
| CardVersion | 86 | ABOUT | 172 |
| DocumentVersion | 92 | CITES | 156 |
| Asset | 10 | INSTANCE_OF | 10 |
| AssetPart | 0 | INSTALLED_ON | 0 |
| 합계 | 289 | 합계 | 434 |

- 원본 카드 86장 전 필드·값 보존. 86장 모두 검수 사유가 있다.
- 비안전·문자열 증상 28장 중 연결 18장·보류 10장. 수정 전후 card_map과 관계 434개는 동일하다.
- 안전 56장과 null 13장(중복 11장, 합집합 58장)의 증상 연결은 각각 0개다.
- 원문 인용 222건 중 판본 있는 180건을 CITES 156개로 집약했다. 판본 없는 42건은 원문을 보존하고 보류했다.
- Asset 10개는 합성 기본 구성이다. AssetPart와 INSTALLED_ON은 미구현이다.

## 최신 검증과 근거

[후속 수정 검증](revision-validation.json)이 현재 파일의 검증 기록이다. [빌더 검증](build/validation.json)을 함께 확인한다. 브라우저 로그·화면 사본은 PR에서 제외하며 `node docs/demo/kg/viz/verify.cjs`로 재실행할 수 있다.

- 생성기 assert, 독립 증상 검사, 빌더 assert 35개 통과.
- 스키마 오류 0, 고아 노드 `[]`. 카드 원문·인용 locator·판본 누락 원문 보존 검증 통과.
- 원본 KB·장비 마스터·schema 해시 불변. 수정된 매핑으로 두 번 재생성한 graph·validation이 바이트 동일.
- 그래프 변경은 증상 정의 3개뿐이다. 개념 ID·노드 수·카드 연결·전체 관계는 변하지 않았다.
- Chrome **42개 PASS**, Runtime 예외 0. 실제 그래프·필터·선택·이웃·원문·locator·후보/합성 표시·키보드·404 오류/재시도/자동 mock 대체 없음 확인.
- 게시 무결성 `ok: true`, `errors: []`, `staged_python_checked: true`.
- 전체 프로젝트 테스트, 실제 LLM·PDA/Jetson·현장 안전·성능 평가는 실행하지 않았다.

## 입력과 출력 해시

| 파일 | SHA-256 |
|---|---|
| `kb_cards.json` | `05cfc4e79a3087e3544fc01e6b830268b542f55ae3be31bd6ad7601fc1d6dd3a` |
| `00_plant_and_relations.json` | `aee891c5e5e2270e815080f22b153e9b64e9128951d2262240c1f41cdc5e1708` |
| `schema.md` | `ad460fc639146d17d448457a5c0a7908bf4aaca92f4098860456401fe0b81613` |
| `symptom_concepts.json` | `514f8cc20d4ac2546f5f49011811b9c60499dccc41f2e78edcf045fd2b209000` |
| `graph.json` | `594d2842b57849fddd68d00141635392fa262c652504d35ec9760f460fc75c94` |
| `validation.json` | `2cd2ee3b627dd74232fa31819e1b166def550a59ff1ad6186ad033d3af67151b` |

## AI 검토와 남은 사항

[/67 검토 보고서](ai-review-67.md)와 [86장 대장](ai-review-cards.json)에 원문 충실성 검토를 기록했다. 이번에는 그 수정 요청 R1–R6을 반영하고 기계 검증을 재실행했다. 6개 에이전트 검토를 새로 수행하거나 사람·제조사 승인을 취득한 것은 아니다.

판본 누락 인용 42건의 근거 확보, 현장 안전·제조사 기준 확인, 안전 카드 후보 승격 여부는 남아 있다. `needs_review`를 승인 상태로 바꾸지 않았고 null 카드에서 증상을 추정하지 않았다. 분류 PART_OF는 실제 부품 장착 관계가 아니다. 위 통합 검증에는 S30h·MES·PDA 답변 연결이 포함되지 않았다. 후속 explain 구현은 아래 별도 기록을 따른다.

발표 문장:

> 승인된 시연 스키마에 맞춰 카드·설비 분류·인용·증상 후보를 그래프로 구성했습니다. 원문과 연결을 함께 탐색할 수 있으며, 증상 연결은 검수 전 후보이고 장비는 합성 데이터입니다.

GraphRAG 구현, 검색·답변 성능 개선, 정식 온톨로지 달성을 주장하지 않는다.

## 이전 기록과 보존

[integration_validation.json](integration_validation.json), [recheck-validation.json](recheck-validation.json), [acceptance-validation.json](acceptance-validation.json)은 **문구 수정 전** 검증 스냅샷으로 보존했다. 그 출력·매핑 해시와 “담당자 파일 불변”은 당시 결과이며 현재 결과에는 적용하지 않는다. 이전 README와 수정 전 상태 사본은 원래 작업트리에 보존하고 PR에서는 제외했다. 변환·시각화 HANDOFF의 이전 계약 해시는 승인 상태 설명·공백 차이가 있는 당시 로컬 문서 값이며 현재 schema 해시는 위 표를 따른다.

별도 조사 clone `D:/obsd/Projects/ShiftLink-kg-integration-20261022`의 이전 변환 단독 merge `76e0531fbd9bf8d970e02cde1265d96860170095`는 이 통합 작업트리에 가져오지 않았다. 주 작업폴더의 이전 HEAD 이동 관찰은 과거 README에 남아 있으며 이번 후속 수정은 지정 통합 작업트리의 KG 경로에서만 수행했다. 최신 미커밋 파일 목록과 수정 범위는 revision-validation.json에 기록한다.

## 후속: 기존 답변 연결 설명

2026-10-22, 통합 결과 커밋 `10053831ea429ea9574b00d89c59fb5bf1e42ae7` 이후 별도 미커밋 작업으로 그래프 로더와 `SHIFTLINK_KG_MODE=explain`을 구현했다. 기존 최종 인용 카드에만 연결 설명을 붙이고 MES 응답·질의 저장·PDA에 표시한다. 기본값 off이며 기존 답변·검색·센서 동작을 유지한다. 그래프 산출물·원본·스키마는 변경하지 않았다.

실행 방법과 제한은 [explain 안내](explain.md), 이번 검증은 [explain 검증 기록](explain-validation.json)에 있다. 위 통합 검증 기록과 후속 실행 기능의 검증을 구분한다. 검증 당시에는 커밋·push·PR·배포하지 않았다. 이후 사용자가 검증된 구현·테스트·문서만 `codex/kg-integration`에 커밋·push하도록 승인했다. `.explain-qa/` 임시 증거는 공유에서 제외하고, PR·main 병합·배포는 수행하지 않는다.
