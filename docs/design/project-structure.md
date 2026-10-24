# ShiftLink 프로젝트 구조와 작업 시작점

기준일: 2026-10-21 (Asia/Seoul)
분석 대상: 현재 로컬 작업 트리. 커밋되지 않은 변경과 미추적 파일도 포함한다.
목적: 대화 컨텍스트가 초기화되어도 구조·진입점·확인 경로를 복원하는 공통 안내서.

공유 기준 주의: 이 문서는 로컬 작업 트리 분석을 바탕으로 작성되었다. 지식 그래프 공통 기준 커밋 `5167376b5ded1e33725394f2b65cb6977c121dec`는 이미 공유된 커밋 `000b9102a10914ca694852aa0ff92285e3cc2056`에 승인된 세 문서만 추가했다. 이후 PR #327의 CI 복구에는 기존 연구 테스트가 참조하는 누락 소스와 CI 의존성 설치를 포함한다. 그 밖의 미커밋 구현·미추적 자료는 공유 기준에 포함되지 않는다. 실제 파일이 없는 경로는 미공유 자료로 구분하고, 실행 동작은 체크아웃한 코드로 확인한다.

## 1. 읽는 순서와 사실의 우선순위

1. 루트 `AGENTS.md`와 작업 폴더의 하위 지침을 확인한다.
2. 이 문서를 읽고, 아래 작업별 시작점에서 필요한 파일만 연다.
3. 실행 코드·설정과 문서가 다르면 현재 파일을 확인해 구분한다.
4. 구조·진입점·실행 모드가 바뀌면 이 문서도 함께 갱신한다.

이 문서는 구조 지도이며 전체 코드, 배포 상태, 현재 테스트 결과를 대체하지 않는다.
과거 보고서의 성공 결과를 현재 작업 트리의 성공으로 간주하지 않는다.

## 2. 시스템 개요

ShiftLink는 베테랑 노하우와 설비 관측을 이용해 현장 질의·조치 기록·교대 인계를 돕는 MES 보조 에이전트다.
저장소에는 합성 MES, Python HTTP 서버, 정적 웹 화면, Raspberry Pi PDA 앱, 검색·추론,
얼굴·설비 인식, Unity 공장 시연 및 오프라인 평가 도구가 함께 있다.

```text
Unity PC: 공장 상태 시각화·작업자 이동·카메라 스트림
   │ MES 상태 조회                          │ 영상 / 촬영
   ▼                                        ▼
Jetson MES :8000  ◀── /api/* 프록시 ── Raspberry Pi PDA :8080
   │                                       얼굴 확인·설비 CNN
   ├─ 합성 엔진 → 센서·알람·이벤트
   ├─ 질의 → 현재 관측 근거 → 검색·판정·답변 → PDA
   ├─ 근무일지·조치·인계 → SQLite
   └─ uploader → Aiven MySQL (업로드 대상 기록만)
```

위 장비 배치는 [시연 가이드](../guides/run-demo.md)의 구성이다.
현재 장비가 이대로 실행 중인지는 별도 확인이 필요하다.
PC 로컬 시연과 Unity 두 PC 교대 시연에는 별도 실행 경로가 있다.

## 3. 주요 디렉터리

| 경로 | 책임과 경계 |
|---|---|
| `shiftlink/agent/` | 요청 라우팅, 공통 스키마, 고정 파이프라인, 답변 조합·검증 |
| `shiftlink/mes/` | MES 서비스 조립, HTTP API, 합성 엔진, 저장, 관측·조치·인계·계정 |
| `shiftlink/mes/web/` | 프레임워크 빌드 없이 제공하는 HTML/CSS/JavaScript 화면 |
| `shiftlink/pda/` | Pi 화면 서버·Jetson API 프록시·키오스크·Unity 영상 연동 |
| `shiftlink/communication/` | 재사용 HTTP 클라이언트와 통신 오류 처리 |
| `shiftlink/rag/` | 카드 로더·검색 공급자·추출 및 카드 기반 질의 CLI |
| `shiftlink/rag2/` | 매뉴얼 청크·임베딩 검색, 근거 점수, 생성, S30h 질의 경로 |
| `shiftlink/edge/` | Ollama 호출·프롬프트·모델 연결 및 픽스처 실행 CLI |
| `shiftlink/data/` | 카드·시나리오·내러티브 생성과 카드 린트 |
| `shiftlink/face/` | 얼굴 모델 준비·등록·검증·템플릿 저장 |
| `shiftlink/vision/` | 설비 사진 수집·데이터셋·학습·평가·양자화·ONNX 분류 |
| `unity/ShiftLinkFactory/` | Unity 프로젝트. C# 실행 코드, 장면·모델, 편집기 도구 |
| `scripts/` | 실행 보조, 장비·HTTP 점검, 데이터 준비, 모델 비교·연구 스크립트 |
| `tests/` | Python 회귀 테스트, Node DOM 검사, 실제 브라우저·장비 연동 검사 |
| `eval/` | 평가 하니스, 픽스처, QA 분할·채점 및 결과 위치 |
| `bench/` | Jetson 질의·Pi 분류·카메라 흐름 등의 성능 측정 |
| `db/` | Aiven SQL 스키마와 적용 도구 |
| `deploy/` | Jetson MES·업로더·Pi 설치 및 S30h 배포 안내 |
| `docs/` | 설계·실행 안내·데이터 계약·실험·검증·연구·실패 기록 |
| `seeds/`, `splits/` | 생성 기준·페르소나·출처 등록부와 데이터 분할 메타데이터 |
| `data/`, `mes_data/` | 로컬 데이터·모델 관련 산출물, MES 실행 DB. 문서 자료와 구분 |
| `output/`, `artifacts/`, `tmp/`, `graphify-out/` | 로컬 빌드·실험·임시 산출물. 구현의 기준 파일로 취급하지 않는다 |
| `third_party_licenses/` | 외부 모델·라이브러리의 라이선스 관련 자료 |

루트에 `package.json`이나 Python `pyproject.toml` 기반 패키지 설정은 발견되지 않았다.
핵심 Python 코드는 저장소 루트에서 `python -m shiftlink.<모듈>` 형식으로 실행한다.
웹 화면은 React/Vite 앱으로 가정하지 않는다.

## 4. MES 내부 책임

| 파일·묶음 | 역할 |
|---|---|
| `__main__.py` | host·port·DB·랜덤 고장 설정을 읽는 MES 실행 진입점 |
| `server.py` | `MesService`와 `_Handler`. 엔진·저장·질의·업무 API를 연결하는 중심 |
| `engine.py` | 시간·UI·DB와 분리된 결정적 합성 상태 엔진 `MesEngine` |
| `random_factory.py` | `RandomFactoryEngine`. 랜덤 합성 센서·고장 운전 경로 |
| `signal_dynamics.py`, `fault_schedule.py` | 신호 동역학·고장 스케줄 |
| `contracts.py`, `catalog.py`, `configuration.py` | 데이터 계약·카탈로그·활성 설비/시나리오 구성 |
| `signal_semantics.py`, `symptoms.py`, `scenarios/` | 신호 의미·증상·시나리오 기준 |
| `query.py`, `card_adapter.py` | 요청과 관측 근거를 검색·추론 경로에 연결 |
| `storage.py` | SQLite 기록·복원·내보내기와 업로드 상태 |
| `work_reports.py`, `handover_board.py` | 근무일지·교대 인계 업무 |
| `field_draft.py`, `candidate_review.py` | 현장 지식 초안·후보 검토 |
| `publication.py`, `rag/embedding.py` | 검수 산출물의 임베딩 작업·SQLite delta 검색 인덱스·공용 모델 prefix |
| `accounts.py` | 관리자·작업자 계정 관련 처리 |
| `analytics.py`, `uploader.py` | 집계와 별도 클라우드 업로드 프로세스 |

`MesService`는 엔진 한 개를 소유하고 일반 상태 조회 자체로 엔진을 진행시키지 않는다.
`--random-faults`가 켜지면 기본 `MesEngine` 대신 `RandomFactoryEngine`을 구성한다.
합성 데이터는 실측 또는 보정된 물리 모델의 출력으로 해석하지 않는다.

주요 API 예: `/api/state`, `/api/config`, `/api/catalog`, `/api/query`,
`/api/equipment/scan`, `/api/work-reports`, `/api/shift-handover`.
전체 HTTP 계약은 [MES 계약](mock-mes-contract.md)과 `server.py`의 라우트를 함께 확인한다.

## 5. 질의·검색 경로: hybrid와 S30h를 구분

공통 시작점은 `shiftlink/mes/query.py:build_query_pipeline`이다.

- 코드의 기본값은 `ANSWER_MODE = 'hybrid'`다. 카드 로더와 `FixedPipeline`,
  Ollama 답변 모델·판정기를 연결한다.
- `SHIFTLINK_ANSWER_MODE=s30h`일 때 `rag2/s30h.py:S30hPipeline`을 선택한다.
  매뉴얼 검색 인덱스, 임베딩, 청크 근거 점수·판정 및 답변 생성을 이용한다.
- 두 경로는 `run(payload) -> .output` 형태와 `AgentResponse` 계약을 공유한다.
- [S30h 배포 안내](../../deploy/s30h.md)는 10/16 시연 채택을 기록하지만,
  현재 Jetson의 환경 변수·서비스 설정을 이번 분석에서 조회하지는 않았다.
- `data/rag2/` 인덱스와 Ollama 모델은 외부 준비가 필요하다.
  기본 `requirements.txt`만으로 모든 S30h·비전·연구 환경이 갖춰진다고 가정하지 않는다.

`FixedPipeline`은 라우팅 → 도구/검색 → 모델 또는 추출/하이브리드 경로 → 응답 검증으로 구성된다.
검수된 현장 카드는 `knowledge_publications` SQLite delta 인덱스에서 질의용 뷰로 읽는다. S30h는 같은 모델의 벡터를 합치며, FixedPipeline은 게시된 카드만 기존 검색 방식으로 합친다. 정적 KB·인덱스 파일은 수정하지 않는다. [게시 흐름과 검증](../guides/knowledge-publication.md)을 참고한다.
무근거 응답 보류, 관측 조건, 인용 카드, 안전 고지 등의 처리는
`pipeline.py`, `response.py`, `compose.py`, `router.py`에서 확인한다.
최상단의 “one model call” 설명만 보고 판정·예열·재시도까지 호출 한 번이라고 단정하지 않는다.

2026-10-24 로컬 통합은 원격 main `99c334d`의 최신 이력 처리를 유지하면서 Jetson의 관계 검색·게시 카드 자동 연결 5파일을 통합한다. `rag/knowledge_graph.py`, `rag2/s30h.py`, `mes/publication.py`, `mes/query.py`, `rag/graph_explain.py`가 실행 변경 범위다. Pi PDA와 센서·AI 모델 설정, 운영 데이터는 변경하지 않으며 운영 미배포다. [런타임 온톨로지 계약](knowledge-graph-runtime.md)을 참고한다.

### 선택적 그래프 연결 설명 (2026-10-22)

`SHIFTLINK_KG_DEPTH=2`는 explain 결과에 허용된 2-hop 분류·참고 카드 경로만 추가한다. 기본 depth 1과 기존 답변·인용·센서는 유지하며 검색·생성에는 사용하지 않는다. 자세한 설정과 경계는 [explain 안내](../demo/kg/explain.md)를 따른다.

`SHIFTLINK_KG_MODE=explain`은 `rag/graph_explain.py`에서 kg-demo-v1을 읽고,
`mes/query.py`가 기존 파이프라인의 최종 인용 카드에만 `graph_context`를 추가한다.
`rag2/s30h.py`는 최종 청크를 내부 결과로 전달한다. 검색·생성·판정·센서 근거는 기존 경로를 따른다.
`mes/server.py`가 연결 설명을 질의 JSON에 보존하고 PDA가 접기/펼치기 영역으로 표시한다.
기본값은 `off`; 별도 검색 모드나 그래프 DB는 없다.
[설정·제약·검증](../demo/kg/explain.md), `tests/test_graph_explain.py`,
`tests/test_graph_explain_browser.py`, `tests/pda_graph_explain.cjs`를 함께 확인한다.

## 6. PDA·인식·Unity

- `pda/__main__.py`가 `mes/web/` 화면을 제공하고 `/api/*`를 Jetson으로 프록시한다.
  Unity 영상 프록시·촬영 분류도 이 경로에 있다.
- `mes/web/pda.html`, `pda.js`는 작업자 화면이다.
  `knowledge.css/js`는 `/api/knowledge-cards`의 기준 KB·후보 상태를 표시한다.
  이 목록은 검색 게시 경로와 별개이며 기존 대시보드에 진입부를 추가한다.
  Jetson/Pi 제공 범위와 동시 배포 주의사항은 [통합 기록](../testing/jetson-knowledge-sync-20261022.md)을 참고한다.
  `index.html`, `app.js`, `operator.js`, `accounts.js`와 후보 검토 화면도 별도로 존재한다.
- Pi 운영 통계 이상징후는 Timestral 없이 `scripts/mes_causal_pda_service.py`와
  `deploy/analytics/`의 별도 systemd 경로를 사용한다. 승인된 합성 MES 69채널 replay를 검사하고,
  Pi PDA 프록시의 `ai_insights.py`가 `/api/state`에 무음 참고 결과만 추가한다.
  기존 경보와 같은 알람창에서 설비별로 합치되 확인·진동 규칙은 유지한다.
  [배포·중지·복구 안내](../../deploy/analytics/README.md)와
  [Pi 검증 기록](../testing/mes-causal-pda-production-20261023.md)을 따른다.
- 2026-10-24 후속 통합본은 현재 Pi의 `normal-context-v1-pda-20261024-r5-manual-stop` 분석 결과를 질문 프록시에서 함께 전달한다.
  `agent/pi_analysis.py`가 Jetson의 질의 시점 MES 실행·설정·장비·시각·분석 지연을 검증하고, `mes/query.py`가
  허용한 결과만 S30h/하이브리드 답변 프롬프트의 참고 문맥에 넣는다. 과거 원문 조회·검색·judge·게시·센서 관측은
  변경하지 않는다. 최신 Pi의 수동 정지 유지 계약까지 격리 검증한 뒤 Jetson 5파일 → Pi 2파일을 순차 배포했다.
  실제 LLM과 Pi의 실제 UI 파일·현재 센서를 사용하되 질의 기록은 별도 DB에 저장해 검증했다.
  [계약](../guides/pi-analysis-query-context.md)과 [배포·보존 결과](../testing/pi-analysis-query-deployment-20261024.md)를 따른다.
- 운전·부하 정상 기준은 원본 v14c를 보존한 `scripts/mes_causal_context.py`의 선택적 profile이다.
  `mes_causal_context_run.py`가 정상 적합→개발→고정→미사용 평가를, `mes_causal_context_validate.py`가
  Pi 회귀·기존 자료 통지 일치·운영 replay·1Hz/얼굴/CNN 검증을 담당한다.
  MES speed는 재생 배속이므로 모델 입력에서 제외하고 코일의 빈 상태·이동·대기 기준을 사용한다.
  [사전 계획](../research/mes-context-v1-prereg-20261023.md),
  [검증·운영 경계](../testing/mes-normal-context-20261023.md)를 함께 확인한다.
- 고장 생애주기 후속은 별도 `scripts/mes_causal_lifecycle.py`의 `LifecycleSource`와
  `mes_causal_lifecycle_validate.py`다. 지속·점진·간헐의 정답 사건/수리 장부는 입력과 분리하고,
  Pi 개발→고정→새 평가로 원본과 비교한다. 운영 r5·episode 후보는 보존하며 후속 active 표시 릴리스에서 고정 생애주기 후보를 선택한다.
  [사전 계획](../research/mes-causal-lifecycle-prereg-20261024.md)과 [Pi 결과](../testing/mes-causal-lifecycle-20261024.md)를 따른다.
- PDA 30프레임 표시 제한 후속은 별도 `scripts/mes_causal_active_advisory.py`다.
  `ActiveAdvisorySession`은 생애주기 확정 상태가 회복될 때까지 최초 감지 ID를 유지한다.
  정지·워밍업은 회복으로 세지 않으며 새 run/누락 구간은 이력을 분리한다.
  2026-10-24 사용자 승인 후 별도 `active.service.in`으로 운영 r6에 적용했다. 기존 경보·질의 연결과 원본은 보존한다.
  [Pi 표시 검증](../testing/pda-active-advisory-20261024.md)과 [운영 배포·복구](../testing/pda-active-advisory-deploy-20261024.md)를 참고한다.
- 통지 중복 후속 후보는 `scripts/mes_causal_episode.py`의 `EpisodeDetector/EpisodeSource`다.
  기존 점수·첫 통지는 유지하고 설비별 통지 사건과 유효한 회복 근거를 저장한다.
  `mes_causal_episode_validate.py`가 Pi에서 개발→후보 고정→새 평가의 원본·후보 비교를 수행한다.
  운영 worker의 선택 경로는 바꾸지 않으며 원본 코드·profile·기존 결과를 보존한다.
  [사전 검증 계획](../research/mes-causal-episode-prereg-20261024.md)을 따른다.
- `face/`와 `vision/`는 각각 얼굴 확인과 설비 분류를 담당한다.
  모델 가중치·얼굴 템플릿·촬영 데이터는 소스와 구분해 관리한다.
- Unity의 `Assets/Scripts/FactoryDemo.cs`를 시작으로
  `FactorySensorMotion.cs`, `FactoryLogistics.cs`, `FactoryWorker.cs`,
  `FactoryCameraStream.cs` 등으로 공장 동작·작업자·영상을 나눈다.
- `FactoryShiftNetwork.cs`, `FactoryShiftMultiplayer.cs`와
  `scripts/start_unity_pda_shift.ps1`는 로컬의 두 PC 교대 시연 경로다.
  이 세 파일과 `docs/guides/unity-two-pc-handover.md`는 **미공유 로컬 자료**로, `codex/kg-base`에 포함되지 않는다. 해당 작업 소유자가 공유한 뒤 별도로 확인한다.
- Unity 편집기 도구는 `Assets/Editor/`에, 설정은 `Packages/`, `ProjectSettings/`에 있다.
  `Library/`, `Logs/`, `UserSettings/`를 소스 기준으로 분석하지 않는다.

**PDA UI 작업 전에는 반드시 `shiftlink/mes/web/AGENTS.md`를 읽는다.** 이 파일은 로컬 지침으로, 다른 PC에는 별도 전달이 필요하다.
외관 수정과 센서 수신·상태·질의 근거 변경의 경계가 명시되어 있다.

## 7. 데이터·연구·저장 경계

- KB 통합 위치: `docs/data/knowledge_cards/kb/kb_cards.json`.
  통합 생성기는 같은 폴더의 `build_kb.py`다. 카드 수는 파일을 다시 확인한다.
- 기준정보 예: `docs/data/reference/00_plant_and_relations.json`.
- `docs/data/`는 작성·검토 자료, `mes_data/`는 실행 DB 위치다.
- `scripts/mes_*.py`와 관련 `docs/research/`, `docs/experiments/`에는
  데이터셋 감사·모델 비교·위치 추정·EWMA·PCA·forest·Timestral 등의 연구 경로가 있다.
  파일 존재나 연구 보고서만으로 실시간 서버에 채택됐다고 단정하지 않는다.
- 로컬 `requirements-mes-research.txt`는 미공유 오프라인 연구 의존성이다.
  이 파일의 NumPy·SciPy 버전은 CI의 Python 3.10·비전 환경과 다르므로 무조건 합치지 않는다.
  공유 연구 테스트의 설치 버전은 `.github/workflows/ci.yml`을 따른다.
- `uploader.py`는 로컬 pending 기록을 업로드한다. 현재
  `HOLD_RESOLUTION_UPLOAD = True`이므로 조치 기록 및 관련 source_session_id가 있는
  인계 일부는 업로드를 보류한다. “모든 기록을 클라우드에 동기화”한다고 설명하지 않는다.
- `.env`, 인증서, 접속 코드, 얼굴 템플릿과 모델 파일의 내용을 문서에 복사하지 않는다.
  버전 관리 범위는 `.gitignore`와 해당 데이터 계약을 따른다.

## 8. 실행·검증 시작점

다음은 실행 위치와 명령을 찾기 위한 안내다. 이번 문서 작업에서 서비스를 시작하지 않았다.

```powershell
# 저장소 루트, 설치된 프로젝트 Python 환경에서
python -m shiftlink.mes --host 127.0.0.1 --port 8000
python -m shiftlink.pda --jetson http://127.0.0.1:8000 --port 8080 --no-window

# 카드 질의 CLI (모델 호출 없이 입력 구성 확인)
python -m shiftlink.rag --cards docs/data/knowledge_cards/kb/kb_cards.json --equipment HPU --question "압력이 떨어졌다" --dry-run

# 전체 회귀 / 검색 평가: 필요할 때 실행
python -m pytest -q
python eval/qa/route_score.py
```

`build_kb.py`는 파일을 다시 생성하므로 읽기 전용 구조 점검의 일부로 실행하지 않는다.
실제 장비 설치·예열·기동 순서는 [run-demo](../guides/run-demo.md),
[모의 MES 사용법](../guides/mock-mes-usage.md),
[S30h](../../deploy/s30h.md)를 대조한다.

현재 로컬 `.github/workflows/ci.yml`:
Python 3.10, pytest, 선택된 Node PDA 회귀, KB 재생성 diff 검사, route_score.
pytest 전에 비전 의존성과 scikit-learn, CPU PyTorch, 고정 커밋의 Timestral을 설치한다.
연구 테스트도 전체 pytest에 포함하며, Timestral 테스트는 작은 임시 모델로 실행한다.
기준은 `MIN_DEV_ROUTE=21`, `MIN_SANITY_ROUTE=28`이다.
루트 README의 dev 20/30 설명과 다르므로 CI 파일을 우선 확인한다.

## 9. 변경 작업별 빠른 지도

| 작업 | 시작 파일 | 관련 검증 예 |
|---|---|---|
| MES API·상태 | `mes/server.py`, `engine.py`, `storage.py` | `tests/test_mes_server.py`, `test_mes_engine.py`, `test_mes_storage.py` |
| 센서·고장 의미 | `signal_semantics.py`, `symptoms.py`, `random_factory.py` | `test_mes_sensor_semantics_ui.py`, `test_mes_random_factory.py`, `test_mes_signal_map_runtime.py` |
| 답변·보류·인용 | `mes/query.py`, `agent/`, `rag/`, `rag2/` | `test_router_pipeline.py`, `test_answer_guards.py`, `test_s30h.py` |
| PDA 화면 | `mes/web/pda.html`, `pda.js`와 하위 AGENTS | 하위 AGENTS의 최소 확인 명령 |
| 근무일지·교대 | `work_reports.py`, `handover_board.py`, `storage.py` | `test_work_report_api.py`, `test_shift_handover.py` |
| 영상·분류·얼굴 | `pda/`, `vision/`, `face/` | `test_vision.py`, `test_face.py`, `test_unity_camera_proxy.py` |
| Unity 동작 | `Assets/Scripts/`, `Assets/Editor/` | Unity Checks 및 `tests/test_unity_mes.py` |
| 모델 실험 | 해당 `scripts/mes_*.py`와 연구 프로토콜 | 같은 기능명의 `tests/test_mes_*.py` |

테스트 예시는 선택 지침이지 전체 필수 목록이 아니다. 변경 영향에 맞는 최소 검증부터 실행한다.

## 10. 이번 분석의 확인 범위와 갱신 규칙

- 확인: 루트와 주요 하위 파일 목록, README·문서 목차, 실행 진입점,
  MES 서비스 조립·질의 모드 선택·업로더 일부, CI와 Unity 교대 연결 코드.
- 실행 검증: 구조 문서의 상대 링크·코드 경로 존재, 지속 참조 지침, 문서 diff.
- 미확인: 전체 구현의 정확성·보안, 전체 테스트 통과, 실장비 상태, 모델/인덱스 존재,
  실측 성능, 연구 후보의 현재 채택 여부.
- 분석 시 여러 코드·문서가 이미 수정되거나 미추적 상태였다.
  이번 작업은 구조 문서와 안내 링크만 변경하며 기존 작업을 정리·되돌리지 않는다.
- 경로·계약·실행 모드·CI·데이터 경계 변경 시 해당 절과 기준일을 갱신한다.
  서비스가 실제로 확인되지 않았으면 “배포됨/가동 중”으로 바꾸지 않는다.


## 근무일지 원문 조회 경계 (2026-10-23)

`shiftlink/rag2/field_history.py`는 기존 기록 조회만 `record_history`로 분류한다. S30h의 검색·judge를 통과한 해당 장비의 accepted/L1/kb 현장 카드 원문을 질의별로 사용하며 저장 카드·청크를 바꾸지 않는다. 독립된 현재·미래 요청은 원래 전체 질문과 MES를 생성 경로로 전달한다. 숫자 원출처 보호는 `generate.py`에 있다.

변경 시 `tests/test_field_history_integration.py`, `tests/test_s30h_publication_integrity.py`와 `scripts/check_knowledge_publication.py --history-scope closure`를 확인한다. 검증 범위·원문 보존 계약·하니스와 한계는 [안정화 보고서](../harness/history-stability-20261023.md)에 있다. UI·온톨로지 및 MES 저장 경로의 변경은 포함하지 않는다.


## 합성 센서 분석 v14c 검토 경로 (2026-10-23)

- `scripts/mes_causal_*.py`: 독립 로컬 합성 MES 생성, 정상 통계 보정, 실행 단위 분할, 후보 고정 및 사후 평가. v8~v13은 v14의 비교·회귀 의존성으로 보존한다.
- 최종 후보: `scripts/mes_causal_v14.py`와 `mes_causal_v14c.py`. 다중 온도 상승 증거와 정상 지속 구간 보정을 사용하며 Timestral 모델을 로딩하지 않는다.
- 프로토콜·결과: `docs/research/mes-causal-v14*-20261023.md`; 검토용 고정 설정·요약은 `docs/research/evidence/mes-causal-v14c-20261023/`에 있다. 이 사본은 전체 원자료·lock·캐시를 대체하지 않는다.
- 검증: `tests/test_mes_causal_v14.py`, `tests/test_mes_causal_v14c.py`와 기존 인과 분석 회귀. 기기 준비 및 SSH 인증 실패 기록은 `docs/testing/mes-causal-v14-device-readiness-20261023.md`를 따른다.
- 실행기는 이전 `output/mes-causal-*` 자료와 절대 경로 고정 정보를 요구한다. 새 체크아웃에서 전체 평가 CLI가 즉시 실행된다고 가정하지 않는다. 이 경로는 MES/PDA 서비스에 연결되지 않았고 기기에 배포하지 않았다.

## 질문 → 근무일지 → 같은 질문 재사용 (2026-10-23)

PDA 대화의 기존 근무일지 작성 버튼은 `questionRecord`로 질문 ID·발생시각을 가진 구조화 기록을 열고, 조치와 운전 확인은 작업자가 작성한다.

구조화된 근무일지(`capture_version=1`)의 `query_id`는 저장된 질문의 설비·자산·사건 문맥을 검증한 뒤 후보에 연결한다. 원질문은 후보의 증상 참조와 `query_log` 출처, `review_flags.origin_query`에 보존한다. 일지 원문과 이전 답변은 갱신하지 않는다. 관리자 검토 승인 → 검수 통과 → 임베딩 게시를 거쳐야 검색되며, 게시 후에도 조건·판정 모델이 관련성을 확인한다. 같은 문자열이라는 이유로 답변을 캐시하거나 판정을 건너뛰지 않는다.

`MesService.query`는 게시 버전 ticket을 마지막 잠금에서 재확인하고, 실제 인용한 현장 카드만 선택 필드 `cited_cards`로 반환·저장한다. PDA의 `responseCards`는 해당 응답의 인용 ID·설비와 일치하는 스냅샷을 사용한다. 초기 전역 카드 목록·센서 관측·정적 KB는 바꾸지 않는다. 검토 화면은 연결된 원질문과 기존 게시 상태를 함께 보여 준다.

회귀 검사: `tests/test_knowledge_gap_loop.py`(extract/S30h, 동일 질문·검토 게이트·원문 보존·판정 거절·반려), `tests/test_publication_browser.py`(실제 브라우저와 HTTP, 모델 fixture), `tests/mes_query_pda.cjs`(동적 카드·미인용·다른 설비·검토 보류 대조군). fixture 검사의 통과는 실제 모델 응답의 품질 보장을 뜻하지 않는다.
