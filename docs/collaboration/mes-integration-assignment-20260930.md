# 업무 분장: MES → 카드 검색 → 답변 연결 (유현준)

> 작성 2026-09-30 최재영 · 기간 **9/30 ~ 10/8** (계획서 2주차 "카메라 → Jetson → 답변 흐름 동작") · 기준 main `c482a0c`

## 한 줄 요약
MES 쪽 부품은 다 들어왔다(모의 MES, 신호 카탈로그, `MesCardAdapter`, 카드↔신호 계약). 남은 건 **이어 붙이기**다: 설비 클래스명과 MES 관측값을 파이프라인에 넣어 **모델 답변과 인계 기록까지** 한 번에 나오게 한다.

## 이미 된 것 (#74 등)
| 항목 | 위치 |
|---|---|
| 모의 MES (SQLite 저장, 웹 화면, 시나리오) | `shiftlink/mes/` |
| 신호 카탈로그·정상 범위, 보강 신호 | `configuration.py`, `docs/design/mes-sensor-coverage.md` |
| MES 관측 → `<signal>_state` → 카드 검색 | `shiftlink/mes/card_adapter.py` (`MesCardAdapter.search`) |
| 카드 작성 계약 (`mes_equipment_id`, `mes_component_code`, `*_state` 조건) | `docs/guides/mes-card-signals.md` |

## 확인된 빈틈

2026-09-30 재검토: 아래는 분장 작성 시점의 목록이다. 4번 신호 표는 현재 10대·46개 센서 위치의 정상 범위·이상 수치가 기록되어 보완됐다. PDP·CAU는 현재 스키마·검색 지원을 유지하며 포함 여부를 다시 미정으로 취급하지 않는다. RT 승강 구조 확인과 모델 답변·평가 판정 함수 연결은 여전히 별도 작업이다. MES 증상 후보 화면은 승인 카드·모델 답변 연결의 완료를 뜻하지 않는다. [재검토 기록](../testing/scenario-criteria-review.md) 참고.
1. `MesCardAdapter`는 **검색까지만** 한다. `FixedPipeline`·`OllamaModel`을 부르는 경로와 화면 연결이 없다 (문서에도 "아직 없다"로 적혀 있음). 코드에서 이 어댑터를 쓰는 곳은 테스트뿐이다.
2. 카드 로더(`load_card_provider`)로 만든 provider에는 **설비 기준정보가 없다**. 그래서 `EQ-0001`·`HPU-01` 같은 설치 ID로 질의하면 `Unknown equipment identifier`가 난다. 지금은 `HPU` 같은 유형 코드만 된다.
3. 카메라는 설비 **유형**(HPU/GR/RT/CV)만 구분한다. GR-02, RT-02/03처럼 같은 유형의 설치가 여럿이면 어느 설치로 볼지 규칙이 없다 (어댑터는 `-01` 고정).
4. `mes-card-signals.md`의 신호 표에 보강 신호(`hpu_oil_level`, `hpu_pump_current`, `gr_oil_level`, `gr_rpm`, `rt_vib_rms`, `cv_motor_current`, `cv_vib_rms`, `bus_current`, `breaker_trip`, `air_flow`, `compressor_current`)가 없다. 허재원의 카드 배치 B·T4 사건이 이 표를 보고 신호 이름을 쓴다.
5. **RT** 구조는 미정이다. 카드 K-1018~1023은 코일카 시저 리프트이고, MES RT-02 승강은 HPU-01 공급이라 같은 구조로 볼지 확인 전이다. 새 카드에서 RT-02 승강 고장을 다룰 때 이 절차를 그대로 가져오지 않는다. **PDP·CAU**는 `KnowledgeCard.equipment`와 검색이 `PDP`·`CAU`를 받는다. `COMMON`으로 바꾸지 않는다. PDP-01·CAU-01은 가상 설비다.
6. `<signal>_state` 판정이 어댑터 안에만 있다. 평가셋 채점(`eval/qa/score.py`)도 같은 규칙으로 상태값을 만들어야 점수가 운영과 같아진다.

## 단계별 분장

| # | 할 일 | 입력 | 출력(산출물) | 완료 기준 | 기한 |
|---|---|---|---|---|---|
| 1 | **구조 결정 2건** (빈틈 5) | 대응표 `kb/20260929-A/mes_signal_map.md`, 카탈로그 | 결정 메모 (`docs/design/`에 한 단락씩) | RT 승강부를 카드와 같은 구조로 볼지 / PDP·CAU를 스키마에 넣을지 뺄지. 허재원·최재영에게 공유 | **10/2** (배치 B·T4가 기다림) |
| 2 | 신호 표 최신화 (빈틈 4) | `configuration.py`, `mes-sensor-coverage.md` | `docs/guides/mes-card-signals.md` 표 갱신 | 런타임 기본 구성의 모든 신호가 표에 있음. 이름 확정 공지 → T4 분장표의 "유현준 확정 중" 해소 | **10/2** |
| 3 | 상태 판정 함수 공개 (빈틈 6) | `card_adapter.py` | `signal_state(spec, value) -> "low"/"normal"/"high"/None` 같은 공개 함수 1개, 어댑터가 이를 사용 | 기존 테스트 통과, 경계값(양끝 normal) 테스트 1개 | 10/5 |
| 4 | provider에 설비 기준정보 싣기 (빈틈 2) | `docs/data/reference/00_plant_and_relations.json` 또는 MES `Configuration` | 로더·어댑터가 같은 설비 기준정보로 provider를 만듦 | `EQ-0001`·`HPU-01`·`HPU` 세 가지로 질의해 같은 설비 카드가 나옴 | 10/5 |
| 5 | 클래스명 입력부 (빈틈 3) | CNN 출력 클래스명(허재원) | 클래스명 → 유형 코드 → 설치 ID 매핑 1곳, 같은 유형 여러 설치일 때 규칙(기본 설치 + 화면에서 변경) | 모르는 클래스명은 거부, 매핑 테스트 | 10/6 |
| 6 | **MES → 파이프라인 → 답변** (빈틈 1) | 4·5, `FixedPipeline`, `OllamaModel` | 설비 + 질문 + run_id → 관측값(`observations`) 포함 `QueryRequest` → 답변·인용·안전 공지·근거 측정값 | Ollama 목킹 테스트 1건 + Jetson(터널) 실호출 1건. ground truth 누수 0 | 10/7 |
| 7 | 응답 화면 | 6 | MES 웹(또는 PDA 목업)에 답변·인용 카드·안전 공지·근거 측정값 표시 | 안전 공지가 맨 위, "해당 지식 없음"도 표시 | 10/8 |
| 8 | 인계 기록 형식 맞추기 | 어댑터 `handover_record`, `db/aiven_schema.sql`의 `handover_record`·`handover_item` | 같은 필드 이름으로 인계 1건 생성 | 허재원의 로컬 SQLite 저장·클라우드 업로드가 그대로 받음 | 10/8 |

## 같이 하는 것 (최재영과)
- **카드에 MES 조건 붙이기**: 대응표 "직접" 6장(K-1001·1002·1004·1024·1025·1027)에 `*_state` 조건을 붙일지 카드별로 정한다. 최재영이 카드마다 후보 조건을 제안하고, 유현준은 **신호 의미만** 확인한다 (예: K-1002의 쿨러 출구 유온이 `hpu_oil_temp` 측정 위치와 같은지, K-1027의 `gr_oil_leak`가 기본 구성에 들어가는지). 1번 결정 후 10/5~6.

## 연계
| 누구 | 주는 것 / 받는 것 |
|---|---|
| 허재원 | CNN 클래스명 목록을 준다(5번 입력). 신호 이름 확정(2번)과 인계 기록 형식(8번)을 받는다 |
| 최재영 | 파이프라인·edge 변경(PR #78: 해당 지식 없음 처리)을 알린다. 3번 함수를 `score.py`에 쓴다 |
| 전혜민 | 7번 화면으로 평가 결과 시연 |

## 하지 않는 것
- 카드 본문·출처 작성 (카드는 허재원·최재영)
- 신호 이름·자유 텍스트 `component`로 부품 코드 자동 연결 (`mes-card-signals.md` 규칙 유지)
- MES ground truth(주입 원인)를 답변·인계에 복사
- `shiftlink/edge/` 프롬프트 수정 (필요하면 최재영에게 요청)

## 문의
- 파이프라인·검색·카드 조건: 최재영
- CNN 클래스명·인계 저장: 허재원
