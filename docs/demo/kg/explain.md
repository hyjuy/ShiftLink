# 기존 답변에 연결 설명 추가

2026-10-22 구현. `codex/kg-integration`의 `10053831ea429ea9574b00d89c59fb5bf1e42ae7`에서 작업했다. 검증 당시 이 기능의 코드·테스트·문서는 미커밋 상태였다. 이후 사용자가 검증된 변경만 커밋·push하도록 승인했다. 실제 체크아웃의 SHA는 `git rev-parse HEAD`로 확인한다. 기존 통합 그래프와 KB·스키마·증상 매핑은 변경하지 않았다.

## 동작과 범위

`SHIFTLINK_KG_MODE=explain`이면 MES `/api/query`의 **최종 인용 카드**에 `graph_context`를 추가한다. 기존 S30h/FixedPipeline의 검색·순위·프롬프트·판정·답변 생성 이후에 실행한다. 답변 본문, `cited_card_ids`, 질의 당시 `evidence`, 센서 폴링을 변경하지 않는다. 질의 저장 JSON에도 같은 연결 설명을 보존한다. 기본값 `off`에서는 그래프 파일을 읽지 않고 기존 응답 형식을 유지한다.

```text
기존 MES 질의 스냅샷 → 기존 검색·판정·답변
                              ↓ 최종 인용 카드
                     graph_explain.explain
                              ↓ 선택적 graph_context
                     기존 게시 ticket 재검사·저장 → PDA 관련 지식 연결
```

PDA 답변의 접기/펼치기 영역에 카드 판본, 설비·부품 분류, 카드 참조 문서 판본·locator, 검수 전 증상 후보, 판본 누락 인용의 보류 상태를 표시한다. 문서 연결은 해당 카드의 참조 정보이며 답변에서 직접 인용한 추가 근거로 승격하지 않는다. 텍스트로 렌더링하며 locator를 임의 URL로 변환하지 않는다.

| 파일 | 역할 |
|---|---|
| `shiftlink/rag/graph_explain.py` | 요청별 그래프 로드·검사, 최종 카드 일치 확인, 설명 투영 |
| `shiftlink/rag2/s30h.py` | 기존 최종 선택 청크를 내부 결과의 `cited_chunks`로 전달 |
| `shiftlink/mes/query.py` | 현재 질의의 카드 뷰와 설비 유형을 사용해 설명 추가 |
| `shiftlink/mes/server.py` | 기존 질의 JSON에 선택적 설명 저장 |
| `shiftlink/mes/web/pda.js`, `pda.html` | 기존 답변에 접근 가능한 설명 영역과 최소 스타일 추가 |

별도 그래프 DB·검색 모드·API endpoint·DB 테이블·패키지 의존성을 추가하지 않았다. standalone S30h CLI에 별도 UI를 붙이지 않았으며 MES를 통한 S30h 응답에 연결한다.

## 로드 및 결합 조건

- 기본 그래프는 저장소의 `docs/demo/kg/build/graph.json`, 동반 검증서는 같은 디렉터리의 `validation.json`이다. `kg-demo-v1`, 검증서 오류 없음, graph SHA-256 일치를 확인한다.
- JSON 중복 키·비정상 상수, 중복 노드·관계, 누락 endpoint, 관계 타입/방향, 고아 노드, 타입별 수, 카드 출처와 CITES의 판본·locator·집계 불일치를 거부한다. 요청마다 독립적으로 읽으며 파일 오류 시 과거 캐시나 mock으로 대체하지 않는다. 빌더의 전체 계약 검증은 계속 별도로 필요하다.
- 현재 질의 뷰에 정확히 한 장 존재하고 `accepted/L1/kb`, 현재 설비 유형 또는 COMMON, 해당 `mes_equipment_id` 범위가 맞아야 한다. 그래프의 카드와 판본 및 전체 정규화 내용이 일치해야 설명한다.
- S30h는 판정 후 실제 최종 인용 청크의 카드 source, 명시된 version, 현재 카드의 전체 know_how 포함 여부까지 확인한다. version이 없는 기존 청크도 전체 know_how가 일치해야 한다. 부분 청크만 있으면 기존 답변은 유지하고 설명을 보류한다.
- 매뉴얼 단독 답변에서 파일명으로 카드 ID를 추정하지 않는다. 정적 그래프에 없는 새 게시 카드는 설명 대상에서 제외한다. 게시 취소·수정 중 질의를 차단하는 기존 ticket 재검사를 그대로 유지한다.
- `no_knowledge`, `review_queue`, `validation_errors` 응답은 설명을 보류한다. 안전 카드와 symptom=null 카드에서 새 증상을 추정하지 않는다. 후보는 계속 `needs_review`다.
- 합성 Asset은 현재 설치 자산으로 사용하지 않는다. `retrieval_used=false`, `synthetic_assets_used=false`를 명시한다. AssetPart는 이번에도 미구현이다.

## 설정과 실행

기존 모델·인덱스가 준비된 환경에서, **이 구현이 있는 작업트리 루트**에서 실행한다. 현재 서비스나 장비 설정은 변경하지 않았다.

```powershell
# 기존 SHIFTLINK_ANSWER_MODE를 유지한다. S30h 사용 환경은 기존 s30h 설정을 그대로 둔다.
$env:SHIFTLINK_KG_MODE = 'explain'
# 선택: graph.json과 동반 validation.json이 있는 경로
# $env:SHIFTLINK_KG_PATH = 'C:/path/to/graph.json'
python -m shiftlink.mes --host 127.0.0.1 --port 8000
# 브라우저: http://127.0.0.1:8000/pda.html
```

위 실행은 기존 MES의 모델 예열·데이터 준비 조건을 따른다. 테스트는 실제 모델 대신 결정적 fixture를 사용했다. Pi 프록시는 기존 API 응답을 전달하므로 수정하지 않았다.

끄려면 실행 환경을 `$env:SHIFTLINK_KG_MODE = 'off'`로 바꿔 다음 실행에 적용한다. 지원 모드는 `off`, `explain`뿐이며 `retrieve` 등 다른 값은 `unsupported_mode`로 처리한다.

## 응답 상태

`graph_context`에는 mode, schema_version, graph_sha256, status, reason, cards, unmatched, retrieval_used, synthetic_assets_used가 들어간다. off나 기존 인사 응답에는 필드가 없다.

| status | 의미 |
|---|---|
| `ok` | 최종 인용 카드 모두 설명 가능 |
| `partial` | 일부 카드만 일치, 나머지는 unmatched 목록에 사유 기록 |
| `unmatched` | 카드 판본·내용·범위 또는 S30h 실제 청크와 결합되지 않음 |
| `unavailable` | 그래프/검증서 누락·손상 또는 미지원 모드; 기존 답변 유지 |
| `empty` | 최종 인용 카드 없음; PDA 영역 생략 |
| `withheld` | 기존 응답이 보류됨; PDA 영역 생략 |

## 검증 기록

검증 환경: Windows, 기존 프로젝트 가상환경 Python 3.13·pytest·Playwright, 설치된 Chrome(headless), Node. 임시 DB·브라우저 응답·화면·테스트 출력은 로컬 `.explain-qa/`에 보존하며 커밋·push에서 제외한다. 공유 검증 기록의 해당 경로는 로컬 증거 위치다. [기계 판독 기록](explain-validation.json)을 참고한다.

- 그래프 단위·MES·S30h·게시 회귀 118개를 확인했다. 최초 묶음 실행은 117 passed/1 failed였으며, 신규 브라우저 테스트가 숨겨진 이전 센서 컨테이너를 대상으로 삼은 오류를 수정한 후 해당 테스트가 통과했다. 제품 센서 코드나 기존 테스트 기대값은 수정하지 않았다.
- 기존 게시 승인→검수→임베딩 fixture→검색 반영→재검토 제외 브라우저 회귀 1개도 통과했다. 출력 폴더만 `.explain-qa/`로 바꾼 검증용 복사본을 실행했다.
- 실제 Chrome PDA→MES HTTP→실제 graph.json→질의 저장을 확인했다. explain 전후 답변·evidence 동일, S30h 프롬프트·순위 추적 동일(시간 제외), 판정 거절 시 설명 없음, 실제 센서 영역 표시·텍스트 보존, 키보드 Enter, 1280/390 너비, 파일 누락 안내, 설비 전환 후 늦은 응답 차단을 확인했다.
- Node 8개 명령(문법 1개·동작 검사 7개), 게시 무결성 검사, `git diff --check` 통과.
- graph·validation·매핑·KB·장비 마스터·schema는 기존 HEAD와 바이트 동일하다. 그래프는 기존 289노드·434관계 그대로다.

재실행은 의존성이 있는 Python 환경에서 아래처럼 수행한다. 기존 게시 브라우저 검증의 출력 경로는 이번 검증용 복사본으로 제한했다.

```powershell
New-Item -ItemType Directory -Force docs/demo/kg/.explain-qa | Out-Null
python -B -m pytest tests/test_graph_explain.py tests/test_graph_explain_browser.py tests/test_s30h.py tests/test_mes_query.py tests/test_publication_s30h.py tests/test_publication_worker.py tests/test_knowledge_publication.py -q -p no:cacheprovider --basetemp=docs/demo/kg/.explain-qa/pytest-rerun
node --check shiftlink/mes/web/pda.js
node tests/pda_graph_explain.cjs
node tests/pda_sensor_display.cjs
node tests/pda_network_boot.cjs
node tests/unity_pda_link.cjs
node tests/pda_symptom_rank.cjs
node tests/mes_query_pda.cjs
node tests/pda_chat.cjs
python -B scripts/check_knowledge_publication.py
```

## 남은 범위

실제 Ollama/S30h 인덱스·Jetson·Pi·현장 센서·물리 키보드/터치 장비에서는 검증하지 않았다. 원본 카드의 현장 안전성, 판본 누락 인용 42건, 증상 후보 검수는 이번 기능으로 승인되지 않는다. 그래프를 이용한 검색·재순위화·답변 생성과 성능 향상은 구현하거나 주장하지 않는다. 그래프 조회는 질의마다 수행하며 별도 지연 성능 측정은 하지 않았다.

발표 문장: “기존 답변의 최종 인용 카드에 그래프의 분류·참조 문서·검수 전 증상 연결을 덧붙였습니다. 기존 답변과 센서 근거는 유지하며, 연결할 수 없는 카드는 설명을 보류합니다.”
