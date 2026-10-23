# ShiftLink

베테랑의 현장 노하우와 MES 관측 데이터를 함께 활용하는 포터블 MES 보조 에이전트입니다. Jetson Orin Nano에서 검색과 모델 추론을 수행하고, 라즈베리파이 PDA에서 설비 확인·질의·조치 기록·인계를 이어갑니다. Unity 공장 씬과 모의 MES로 현장 흐름을 시연합니다.

## 주요 기능

- **설비 확인과 질의**: PDA의 얼굴 로그인·설비 촬영 분류 후, 선택한 설비의 관측값과 질문을 함께 전달합니다.
- **근거 기반 답변**: 지식카드와 매뉴얼을 검색하고 판정 모델로 적용 여부를 확인합니다. 적용 가능한 지식이 없는 경우와 모델 장애로 답변을 보류하는 경우를 구분합니다.
- **모의 MES**: 센서·알람·이벤트, 이상상황과 복구, 운전 기록 재생, 장비 구성 변경을 제공합니다.
- **현장 기록의 재사용**: 근무일지에서 지식 후보를 만들고, 검토 승인·검수·임베딩을 거친 지식을 후속 검색에 반영합니다.
- **인계와 동기화**: 작업·인계 기록을 로컬에 보관하고 업로드 대상 기록을 클라우드로 동기화합니다. 네트워크 장애 시 대기 기록을 유지하고 재시도합니다.

모의 MES의 수치·고장·조치는 합성 시연용입니다. 실제 설비의 운전·정비 절차나 현장 안전성을 검증한 결과를 의미하지 않습니다.

## 시스템 구성

```text
Unity PC ── 공장 씬·카메라 영상 ──▶ 라즈베리파이 PDA
                                      │ 설비 선택·질의·작업 기록
                                      ▼
                              Jetson Orin Nano
                              ├─ MES API·SQLite
                              ├─ 검색·판정·답변 (Ollama)
                              └─ 업로더 ──▶ 클라우드 DB (Aiven)
```

| 구성 | 역할 | 관련 코드 |
|---|---|---|
| Jetson | MES 서버, 지식 검색·답변, 기록 저장·업로드 | `shiftlink/mes/`, `shiftlink/rag2/`, `shiftlink/edge/` |
| 라즈베리파이 PDA | 작업자 화면, Jetson API 프록시, 얼굴 확인·설비 분류 | `shiftlink/pda/`, `shiftlink/face/`, `shiftlink/vision/` |
| Unity PC | 공장 시뮬레이션과 작업자 시점 영상 | `unity/ShiftLinkFactory/` |

전체 흐름과 모듈별 그림은 [아키텍처 문서](docs/architecture/README.md)를 참고하세요.

## 로컬에서 시작하기

장비 없이 모의 MES 대시보드를 확인할 수 있습니다. Python **3.10은 CI 기준 버전**이며, 아래 명령은 저장소 루트에서 실행합니다.

```bash
git clone https://github.com/hyjuy/ShiftLink.git
cd ShiftLink
python -m venv .venv
```

가상환경을 활성화합니다.

```bash
# macOS / Linux
source .venv/bin/activate
```

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

의존성을 설치한 뒤 서버를 시작합니다.

```bash
python -m pip install -r requirements.txt
python -m shiftlink.mes
```

- 브라우저에서 [모의 MES 대시보드](http://127.0.0.1:8000/)에 접속합니다. 시작 → 이상상황 선택 → 복구 진행 순서로 확인할 수 있습니다.
- 기본 DB는 `mes_data/mock-mes.sqlite3`에 생성되며 Git에서 제외됩니다. 재시작해도 기존 기록을 보존합니다. 같은 DB를 여러 서버에서 동시에 운전하지 않습니다.
- 포트나 DB 경로를 바꾸려면 `python -m shiftlink.mes --port 8001 --db mes_data/local-demo.sqlite3`을 사용합니다. 종료는 터미널에서 `Ctrl+C`를 누릅니다.

**모델을 사용하는 질의는 별도 준비가 필요합니다.** 기본 질의 모드는 `hybrid`이며 Ollama와 SFT 판정·답변 모델을 사용합니다. 모델이 준비되지 않으면 경고가 표시되고 질의는 503으로 응답할 수 있습니다. 모델 등록은 [SFT 모델 가이드](docs/guides/sft-judge-model.md)를 참고하세요.

10/16 시연 채택 모드인 `s30h`는 매뉴얼·카드 청크 검색을 사용합니다. `SHIFTLINK_ANSWER_MODE=s30h` 설정 외에도 검색 인덱스와 임베딩·판정·답변 모델이 필요합니다. 인덱스와 모델 파일은 Git에 포함되지 않으므로 [S30h 배포 안내](deploy/s30h.md)에 따라 별도로 준비합니다. 얼굴 인식·설비 분류 의존성과 장비 설치는 아래 시연 가이드를 따릅니다.

## 문서와 실행 가이드

| 목적 | 문서 |
|---|---|
| 문서 전체 탐색 | [문서 목차](docs/README.md) |
| 장비 3대 설치·시작·확인·종료 | [시연 실행 가이드](docs/guides/run-demo.md) |
| 로컬 MES 운전·기록 재생 | [모의 MES 사용법](docs/guides/mock-mes-usage.md) |
| 설비 추가·교체·제거 | [구성 관리 가이드](docs/guides/mock-mes-configuration-guide.md) |
| 이상상황 조치·복귀 | [복구 가이드](docs/guides/mock-mes-recovery.md) |
| Unity 영상과 PDA 연결 | [카메라 스트림 가이드](docs/guides/unity-pda-camera-stream.md) |
| 근무일지 지식 후보 검수·검색 반영 | [지식 게시 가이드](docs/guides/knowledge-publication.md) |
| 데이터 출처·분할·관리 기준 | [데이터 안내](docs/data/README.md) |
| 검증 방법과 과거 결과 | [검증 문서 목차](docs/testing/README.md) |

장비별 주소·모델·설치 경로는 시연 가이드에서 확인합니다. 해당 가이드의 10/8 질의 구성과 이후 S30h 채택 설정은 시점이 다르므로, S30h 구성에는 배포 안내를 함께 확인하세요. 과거 실험 결과는 해당 시점의 기록이며 현재 코드의 재검증 결과와 구분합니다.

## 저장소 구조

```text
shiftlink/
  agent/          질의 라우팅·스키마·고정 파이프라인
  rag/            카드 적재·검색·추출·임베딩
  rag2/           청크 검색과 S30h 답변 엔진
  mes/            모의 MES·API·웹 화면·작업 기록·지식 게시
  pda/            PDA 화면 서버와 Jetson API 프록시
  edge/           Ollama 추론 연동
  face/           얼굴 등록·확인
  vision/         설비 영상 수집·학습·분류
  data/           합성 데이터·시나리오·카드 검증
deploy/           장비 서비스 설치와 배포 안내
docs/             설계·데이터·실행 가이드·검증 기록
eval/             평가 하니스·질문 세트·채점
tests/            Python·JavaScript 회귀 테스트
scripts/          실행·점검·연구 도구
unity/            공장 시뮬레이션
```

## 담당
| 영역 | 담당 | 디렉토리 |
|---|---|---|
| Lead / 에이전트·스키마·통합 | 유현준 | `shiftlink/agent/` |
| AI / RAG·추출·합성데이터 생성 | 최재영 | `shiftlink/rag/`, `shiftlink/rag2/`, `shiftlink/data/` |
| Embedded / Jetson·추론·저장 | 허재원 | `shiftlink/edge/` |
| 모의 MES | 유현준·허재원 | `shiftlink/mes/` (실행 DB `mes_data/`) |
| PM·QA / 검수·평가·시나리오 | 전혜민 | `eval/` |

## 지식 카드

통합 목록 `docs/data/knowledge_cards/kb/kb_cards.json`은 **86장**이다. 배치 A 30, T4 12(기존 11 + #148 인계 완료 K-1401, 배치 `20261001-handover-completion`), C 19, D 25(1~3차 21장 + 10/1 4차 K-1322~1324 + 5차 K-1325).

이 숫자는 정적 KB 기준이며, 근무일지에서 검수 후 DB에 게시한 지식은 별도로 관리합니다. 정적 통합 JSON은 직접 수정하지 않고 각 배치의 원본 카드를 수정한 뒤 `build_kb.py`로 재생성합니다. 검색 대상 기준은 `accepted / L1 / kb`입니다.

블라인드 2차 `eval/qa/20261001-blind2/qa_blind2.json`은 답 있음 6/25이다. `python eval/qa/route_score.py`의 `blind2_route_acc`는 이 셋의 보고 전용이라, 점수를 보고 검색을 맞추지 않는다.

## 브랜치 전략
자세한 내용은 [`docs/collaboration/branching.md`](docs/collaboration/branching.md) 참고.

## PR 올리기 전 확인

기본 의존성으로 카드 통합과 오프라인 검색 점수를 먼저 확인합니다. 이 검사는 Ollama나 실장비를 사용하지 않습니다.

```bash
python -m pytest -q tests/test_kb_cards.py tests/test_eval_qa_score.py
python docs/data/knowledge_cards/kb/build_kb.py
git diff --exit-code -- docs/data/knowledge_cards/kb/kb_cards.json
python eval/qa/route_score.py
```

[현재 CI](.github/workflows/ci.yml)는 `dev_route_acc`가 **21/30 미만**, `sanity_route_acc`가 **28/30 미만**이면 실패합니다. `route_score.py`는 점수를 출력하며, 임계값 판정은 CI에서 수행합니다. 이 점수는 검색 라우팅 지표이며 최종 생성 답변의 정확도를 뜻하지 않습니다.

전체 Python 회귀 테스트는 `python -m pytest -q`로 실행합니다. 전체 CI에는 기본 의존성 외에 비전·MES 연구용 패키지와 Node.js 테스트가 포함됩니다. 추가 의존성과 실행 명령은 CI 설정을 기준으로 준비하세요. 지식 게시의 브라우저 검증에는 Playwright가 필요하며 [별도 검증 절차](docs/guides/knowledge-publication.md#검증-명령)를 따릅니다.
