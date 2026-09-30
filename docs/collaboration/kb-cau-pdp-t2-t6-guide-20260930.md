# 업무 가이드: 지식 카드 배치 C(T2·T6)·D(CAU·PDP) 생성

> 작성 2026-09-30 최재영 · 담당 **배치 C 미정 · 배치 D 유현준**(Q7 (c) 결정, 9/30) · 목표 **10/7 accepted** · KB 목록 [`kb/kb_cards.json`](../data/knowledge_cards/kb/kb_cards.json)

## 한 줄 요약

지금 KB는 41장이다(배치 A 30 + T4 11). **배치 C**로 T2 10장·T6 9장을 더해 **60장**을 채우고, 새로 들어온 설비 **CAU(압축공기)·PDP(배전반)** 카드는 **배치 D**로 따로 만든다. 모든 카드는 승인 후 `kb_cards.json` 한 목록에 들어간다.

## 1. 지금 KB

| 유형 | 배치 A (K-1001~1030) | T4 (K-1101~1111) | 합계 | 배치 C로 |
|---|---|---|---|---|
| T1 증상 해석 | 11 | – | 11 | – |
| T2 조건부 요령 | 2 | – | 2 | **+10** |
| T3 확인 절차 | 10 | – | 10 | – |
| T4 인계 요령 | – | 11 | 11 | – |
| T5 안전 금기 | 7 | – | 7 | – |
| T6 재가동 | 0 | – | 0 | **+9** |
| **합계** | 30 | 11 | **41** | **60** |

설비: HPU·CV·RT·GR 4종 + COMMON(T4). CAU·PDP 카드는 0장.

### 통합 목록 유지 방법

- 카드는 **배치 폴더에서만** 고친다. 통합 목록은 [`kb/build_kb.py`](../data/knowledge_cards/kb/build_kb.py)가 만든다.
- 새 배치가 승인되면 `build_kb.py`의 `BATCHES`에 폴더 이름을 한 줄 넣고 `python docs/data/knowledge_cards/kb/build_kb.py`.
- `tests/test_kb_cards.py`가 목록과 배치 파일이 어긋나면 실패한다. 목록은 `{"_meta", "cards"}` 객체라 배치 `verify.py`의 ID 충돌 검사에 걸리지 않는다.

## 2. 공통 원칙

1. **평가셋을 보지 않는다.** 생성 에이전트는 `eval/` 폴더를 읽지 않는다. 평가 질문을 보고 카드를 쓰면 점수가 부풀려진다(9/29: 카드 기반 20문항 20/20 vs 블라인드 7/11).
2. **원문·기록에서만.** 원문에 없는 수치·절차·원인을 만들지 않는다. 근거가 없으면 슬롯을 skip하고 이유를 적는다.
3. **MES 조건은 상태 기호로.** `{"signal": "hpu_filter_dp_state", "op": "==", "value": "high", "unit": null}` 형식([`mes-card-signals.md`](../guides/mes-card-signals.md)). 매뉴얼 수치를 가상 설비의 경계로 옮기지 않는다.
4. **형식은 기존 카드와 같게.** 배치 A·T4 카드와 필드 구성이 같아야 한다(9/30 대조: 최상위 키·provenance 키·sources 키 일치. 차이는 유형별 선택 필드뿐 — T4에는 `symptom` 없음).
   - `version`=`1.0-draft-KB-<배치>`, 생성 직후 `grade=L0`·`status=draft`, `split=kb`, `confidence=0.0`
   - `provenance.seed_ids`=`["KB-<배치>:seed=<시드>", "slot:<Sxx>"]`, `prompt_version`=`<프롬프트 경로>@sha256:<해시>`
5. **생성자 본인 검수 금지.** 사람 검수를 거쳐 `accepted`/`L1`.
6. **원문 PDF는 로컬에만.** `docs/data/sources/<설비>/`에 두고 커밋하지 않는다(`.gitignore`). 카드에는 파일명·쪽만 적는다.

## 3. 배치 C — T2 10장 (조건부 요령)

**왜**: 블라인드 평가셋의 MES 값 해석 질문 11건 중 8건이 답이 없다. 필터 차압·벨트 장력·클램프압처럼 카드가 없는 신호다. T2는 "이 상태면 이렇게, 저 상태면 저렇게"가 갈리는 요령이다. 조건이 단순한 적용 범위면 T2가 아니다.

| 설비 | 신호 | 칸 | 방향 (예시, 확정 아님) |
|---|---|---|---|
| HPU | `hpu_filter_dp` (+`hpu_oil_temp`) | 2 | 차압 high + 유온 low → 난기 후 재확인 / 유온 normal에서 high → 교체 계획 |
| HPU | `hpu_pressure` + `hpu_flow` | 1 | 압력만 low vs 둘 다 low → 확인 방향이 다름 |
| CV | `cv_belt_tension` | 2 | 장력 low + 부하 시 미끄럼 / 장력 normal인데 미끄럼 |
| CV | `cv_speed` (+`cv_queue_len`) | 1 | 속도 low + 대기열 증가 |
| RT | `rt_clamp_press` | 1 | 클램프압 low 상태의 반송 판단 |
| RT | `rt_motor_current` + `rt_lift_delay` | 1 | 전류 high + 지연 high 조합 |
| GR | `gr_vib_rms` + `gr_brg_temp` | 1 | 진동만 high vs 온도 동반 |
| GR | `gr_current` | 1 | 전류 high + 부하 조건 |

- 기존 T2(K-1007 점도, 1장 더)와 겹치지 않게 한다.
- **선행**: 유현준의 신호 표 보강(10/2)·RT 구조 결정(10/2). RT 2칸은 결정 전까지 반송·클램프 신호만 쓴다.

## 4. 배치 C — T6 9장 (재가동) · **1안: 기록 먼저, 카드는 기록에서**

T6 = 정지 후 재가동·상태 복귀 지식과 **실패 경험**. T4 근거 기록 30건 중 `restart_attempts`가 있는 건 2건(EV-0307·EV-0312, 둘 다 HPU 필터 교체 후 압력 미회복)뿐이라, T4 배치와 같은 2단계로 간다.

| 단계 | 내용 |
|---|---|
| A. 기록 합성 | 재가동 근무 기록 **20건** (KB용 15 + 평가용 5). 사건마다 `restart_attempts`(시도·관측 결과·실패 이유), 인계 메모. 평가용 5건은 카드 근거로 쓰지 않는다 |
| B. 카드 추출 | KB용 15건에서 **2건 이상 반복된** 재가동 요령·실패만 T6로. `type_payload.restart_type` 필수, `tried_and_failed`의 시도별 `restart_type`은 카드와 같거나 `unknown` |

| restart_type | 칸 | 방향 (예시) |
|---|---|---|
| `maintenance_restart` | 4 | HPU 필터·오일 교체 후 공기 빼기·무부하 운전 / GR 오일 교체 후 길들이기·온도 감시 / CV 스플라이스 수리 후 사행 확인 / RT 정비 잠금 해제 후 |
| `abnormal_stop_restart` | 3 | CV 당김줄 비상정지 해제 후 / GR 과열 트립 후 / RT 인터록 트립 후 |
| `normal_stop_restart` | 2 | 저온 기동(HPU) / 장기 정지 후 |

- 기록 설계는 T4 배치의 규칙을 따른다: MES 직접 연결 신호 위주, 인계 5요소, `true_cause`를 메모에 쓰지 않음, 평가용 사건 인용 0.
- 실패 이유가 기록에 없으면 `failure_reason=null`, `evidence_gap="not_recorded"`. 지어내지 않는다.

## 5. 배치 D — CAU·PDP 카드

### 설비와 자료

| 설비 | MES (`00_plant_and_relations.json`) | 관계 | 로컬 원문 (`docs/data/sources/`) |
|---|---|---|---|
| **CAU-01** 압축공기 설비 (EQ-0003, 유틸리티실 A동 2층) | 기본 `air_pressure`, 보강 `air_flow`·`compressor_current` | CV-01 디버터에 공압 공급 | `CAU/compressed-air-ref-eng.pdf` — CEATI *Compressed Air Energy Efficiency Reference Guide* (118쪽) · `CAU/Manual-on-Energy-Efficiency.pdf` — UNEP/TERI *Energy Efficient Technologies and Best Practices in Steel Rolling Industries* (116쪽) |
| **PDP-01** 배전반 (EQ-0002, 유틸리티실 A동) | 기본 `bus_voltage`, 보강 `bus_current`·`breaker_trip` | GR-01·GR-02에 전력 공급 | `PDP/15001-20000_16339.pdf` — UNIDO 1987 세미나 *Electrical and Mechanical Maintenance in Rolling Mills* (210쪽, 스캔 OCR 품질 낮음) · `PDP/d2e0a4ea3d7e62b24193679803b73e6.pdf` — ABB *Electrical System Service* 소개 자료 (8쪽) |

**자료 한계**
- PDP 원문은 절차·수치 근거가 약하다. UNIDO 자료는 스캔본이라 쪽 단위로 직접 읽어 대조해야 하고, ABB 자료는 서비스 소개 브로슈어다. **T5(전기 작업 안전)는 KOSHA 전기작업 지침 같은 공식 안전 자료를 추가로 확보한 뒤** 쓴다(현재 로컬에 없음).
- CAU 자료는 에너지 효율 중심이라 고장 진단·재가동 근거는 부분적이다.

### 선행 조건 (없으면 카드를 못 싣는다)

1. **스키마** — **완료**: PR [#84](https://github.com/hyjuy/ShiftLink/pull/84)로 `KnowledgeCard.equipment`에 PDP·CAU가 들어갔고 검색이 `PDP-01`·`CAU-01`을 해당 유형으로 해석한다 (Q7 (c) 결정).
2. **신호 표**: `air_flow`·`compressor_current`·`bus_current`·`breaker_trip`이 [`mes-card-signals.md`](../guides/mes-card-signals.md) 표에 들어가야 T2 조건을 쓸 수 있다(유현준, 10/2).
3. **정답지·커버리지 매트릭스 개정** (유현준): 설비 6종 기준으로 바뀐 형식에 맞춰 배치 D 카드와 평가셋 라벨을 붙인다.

### 슬롯 (10장 제안)

| 설비 | T1 | T3 | T5 | T2 | 합 |
|---|---|---|---|---|---|
| CAU | 2 (압력 저하·이상음) | 1 (압력 저하 확인 순서) | 1 (압축공기 안전) | 1 (`air_pressure` + `compressor_current`) | 5 |
| PDP | 2 (차단기 동작·전압 변동) | 1 (차단기 트립 후 확인 순서) | 1 (충전부 작업 금기 — 공식 안전 자료 확보 후) | 1 (`bus_voltage` + `breaker_trip`) | 5 |

- 60장 목표와 별개로 **70장**이 된다. 60장 안에 넣으려면 배치 C에서 칸을 줄여야 한다 → 결정 필요 (7절).
- 관계를 이용한 카드(예: CAU 압력 저하 → CV 디버터 동작 이상)는 원인 확정 근거로 쓰지 않는다(`QC-CAUSE-02`). "같이 확인할 곳"까지만.

## 6. 작업 단계 (담당 미정)

| # | 할 일 | 입력 | 출력 | 완료 기준 | 목표일 |
|---|---|---|---|---|---|
| 0 | 자료 읽기 | 이 문서, 배치 A·T4 폴더, [카드 작성 가이드](../../seeds/카드_작성_가이드_초안.md), `mes-card-signals.md` | – | T2·T6 경계를 설명할 수 있다 | 10/1 |
| 1 | 슬롯 계획 | 3·4·5절 표 | `plan.py` → `plan.json` (시드 고정) | 재실행 시 바이트 동일, ID 충돌 0 (`K-1201~` C, `K-1301~` D 제안) | 10/1 |
| 2 | 프롬프트 고정 | 배치 A 템플릿 | `prompt_template.md` → `render_prompts.py` → `prompts/*.md` + `index.json`(sha256) | 파일 해시 = 기록값, LF | 10/1 |
| 3 | T2 생성 (C) | 2 + 원문 PDF + 신호 표 | `out/<설비>.json`, `out/<설비>_notes.md` | 스키마 통과, 조건 1개 이상·카탈로그 신호 | 10/2 (신호 표 확정 후) |
| 4 | T6 기록 합성 (C 단계 A) | T4 배치 `plan.py`·`stage-a-records.md` 방식 | `events.json`(20건), `artifacts.json` | kb 15 / 평가용 5, `true_cause` 누수 0 | 10/2 |
| 5 | T6 카드 추출 (C 단계 B) | KB용 기록 15건만 | `out/T6.json` | 카드마다 근거 기록 2건 이상, 평가용 인용 0 | 10/3 |
| 6 | CAU·PDP 생성 (D) | 선행 조건 1·2 완료 + 원문 | `kb/<날짜>-D/out/*.json` | 스키마 통과, 원문 쪽 대조 | 선행 조건 후 |
| 7 | 병합·검수표 | out/*.json | `merge.py` → `cards.json`, `README.md`(추적표), `review.md` | 카드 전부 판정 칸 | 10/3 |
| 8 | 사람 검수 | `review.md` | 판정 | 전 카드 accepted / rejected / 수정 | 10/5 |
| 9 | 승격 | 판정 | `apply_review.py` → accepted/L1, `build_kb.py`의 `BATCHES`에 추가 | `pytest` 통과, `kb_cards.json` 60장 | 10/6 |
| 10 | 효과 확인 | `kb_cards.json` | 평가셋 라벨만 다시 붙임, `route_score.py` | 개발용 답 있는 문항의 검색 1위가 떨어지지 않음 | 10/7 |

## 7. 재사용할 배치 A 스크립트

모두 `docs/data/knowledge_cards/kb/20260929-A/`에 있다. 새 배치 폴더로 복사한 뒤 아래만 바꾼다.

| 파일 | 하는 일 | 바꿀 곳 |
|---|---|---|
| `plan.py` | 시드로 슬롯(카드 ID·설비·유형)을 정해 `plan.json` 생성 | `SEED`, `BATCH`, `FIRST_ID`, `QUOTA`, `FILL` (T2·T6 고정 배정이면 표로 직접 지정) |
| `prompt_template.md` | 서브에이전트 지시문 틀 (슬롯·근거·작성 규칙·provenance 형식·검증 명령) | 배치 ID·시드·"T4는 만들지 않는다" 줄, 유형 규칙에 T2 조건 형식·T6 `restart_type` 추가 |
| `render_prompts.py` | 틀 + `plan.json` → `prompts/<설비>.md`, sha256을 `prompts/index.json`에 기록 | `REL`, `SOURCES` (**원문 경로를 `docs/data/sources/<설비>/`로** — 배치 A 당시 경로 `docs/data/events`·`docs/manual`은 지금 없다) |
| `merge.py` | `out/*.json` → `cards.json`, `prompt_version`에 해시 고정, 스키마 검증, README 추적표·`review.md` 생성 (판정 칸은 재생성해도 보존) | 배치 이름 문자열 |
| `apply_review.py` | 검수 판정 → accepted/L1, 수정본 반영 | 검수 파일 이름 |

T6 단계 A·B는 T4 배치(`kb/20260930-T4/`)의 `plan.py`(사건 설계표 + 난수는 페르소나·장면만), `prompts/stage-a-records.md`·`stage-b-cards.md`, `verify.py`를 틀로 쓴다.

**생성 실행 예시** (배치 A 방식):
```
python plan.py && python render_prompts.py
# 설비별 서브에이전트에게: "prompts/<설비>.md를 읽고 그대로 따르라" 한 줄만 준다
python merge.py            # cards.json · README.md · review.md
# 사람 검수 후
python apply_review.py && python merge.py
python ../build_kb.py      # kb_cards.json 갱신
python -m pytest -q && python eval/qa/route_score.py
```

## 8. 결정이 필요한 것

1. 담당 — 배치 C (배치 D는 유현준으로 결정, 9/30).
2. CAU·PDP를 60장 **안에** 넣을지(배치 C 칸 축소) **밖에**(70장) 둘지.
3. PDP T5 근거 자료 — 어떤 공식 안전 자료를 확보할지.
4. 선행 조건: PDP·CAU 스키마(유현준·Cursor), 보강 신호 표(유현준, 10/2).
