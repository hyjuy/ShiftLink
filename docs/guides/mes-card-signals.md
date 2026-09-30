# 가상 MES 신호 사전과 카드 작성 계약

기준: `docs/data/reference/00_plant_and_relations.json`의 `equipment[].measurement_points`와 `components[]`, `shiftlink/mes/configuration.py`. 카드와 신호의 의미 연결 후보는 [`mes_signal_map.md`](../data/knowledge_cards/kb/20260929-A/mes_signal_map.md)와 [`mes_signal_map.json`](../data/knowledge_cards/kb/20260929-A/mes_signal_map.json)의 **초안**을 참고했다. 아래 범위는 **가상 MES 정상 범위**다. 제조사 매뉴얼의 고장 임계값이나 정비 기준이 아니다. `alarm_low/high`도 여기의 상태 경계로 쓰지 않는다. 런타임 구성에 신호가 추가될 수 있으므로 카드에 조건을 붙이기 전 해당 run의 `config_id`와 구성 신호를 확인한다. 대응표의 신호 개수와 시나리오 목록은 작성 시점 기준이므로 현재 적용 구성의 정본으로 쓰지 않는다.

`quality=good`이고 카탈로그 단위가 정확히 같으며 유한한 숫자일 때만 원값과 `<signal>_state`를 검색 조건으로 전달한다. 카드의 `Condition.unit`도 원신호 단위와 맞아야 하며, 파생 `*_state`의 단위는 `null`이다. `value < normal_min`은 `low`, `normal_min <= value <= normal_max`는 `normal`, `value > normal_max`는 `high`다. **양쪽 경계값은 normal에 포함**된다. 값·품질·단위가 없거나 맞지 않으면 파생 상태도 없다. 이 경우 필요한 조건은 `unverified`다. `*_state`는 파생 검색 키이며 원본 MES 신호가 아니다. 정지 중 0 등도 임의의 정상값으로 보정하지 않는다. `rt_speed`·`cv_speed`처럼 정지 중 0을 내는 신호는 `low`가 설비 고장을 뜻하지 않으므로, 해당 조건을 카드에 붙이기 전에 운전 상태와 적용 범위를 검수한다.

| 설비 ID / 코드 | 실제 신호 | 단위 | 가상 MES 정상 범위 (양끝 포함) | 상태 경계 | 부품 코드 |
| --- | --- | --- | --- | --- | --- |
| EQ-0001 / HPU-01 | `hpu_pressure` | bar | 145–165 | <145 low; >165 high | 없음 |
| EQ-0001 / HPU-01 | `hpu_oil_temp` | degC | 35–58 | <35 low; >58 high | 없음 |
| EQ-0001 / HPU-01 | `hpu_filter_dp` | bar | 0–1.2 | <0 low; >1.2 high | 없음 |
| EQ-0001 / HPU-01 | `hpu_flow` | L_min | 38–46 | <38 low; >46 high | 없음 |
| EQ-0002 / PDP-01 | `bus_voltage` | pct | 97–103 | <97 low; >103 high | 없음 |
| EQ-0002 / PDP-01 | `bus_current` | A | 20–40 | <20 low; >40 high | 없음 |
| EQ-0002 / PDP-01 | `breaker_trip` | bool | 0 (정상); 1은 트립 | 0 normal; 1 high (수치 경계: <0 low; >0 high) | 없음 |
| EQ-0003 / CAU-01 | `air_pressure` | kPa | 550–700 | <550 low; >700 high | 없음 |
| EQ-0003 / CAU-01 | `air_flow` | L_min | 100–150 | <100 low; >150 high | 없음 |
| EQ-0003 / CAU-01 | `compressor_current` | A | 8–16 | <8 low; >16 high | 없음 |
| EQ-0004 / GR-01 | `gr_vib_rms` | mm_s | 0.5–2.8 | <0.5 low; >2.8 high | 없음 |
| EQ-0004 / GR-01 | `gr_brg_temp` | degC | 30–62 | <30 low; >62 high | 없음 |
| EQ-0004 / GR-01 | `gr_current` | A | 18–30 | <18 low; >30 high | 없음 |
| EQ-0005 / GR-02 | `gr_vib_rms` | mm_s | 0.5–2.8 | <0.5 low; >2.8 high | 없음 |
| EQ-0005 / GR-02 | `gr_brg_temp` | degC | 30–62 | <30 low; >62 high | 없음 |
| EQ-0005 / GR-02 | `gr_current` | A | 18–30 | <18 low; >30 high | 없음 |
| EQ-0006 / RT-01 | `rt_speed` | m_min | 20–120 | <20 low; >120 high | 없음 |
| EQ-0006 / RT-01 | `rt_clamp_press` | bar | 95–115 | <95 low; >115 high | 없음 |
| EQ-0007 / RT-02 | `rt_speed` | m_min | 20–120 | <20 low; >120 high | 없음 |
| EQ-0007 / RT-02 | `rt_clamp_press` | bar | 95–115 | <95 low; >115 high | 없음 |
| EQ-0007 / RT-02 | `rt_lift_delay` | min | 0–0.05 | <0 low; >0.05 high | 없음 |
| EQ-0008 / RT-03 | `rt_speed` | m_min | 20–120 | <20 low; >120 high | 없음 |
| EQ-0008 / RT-03 | `rt_clamp_press` | bar | 95–115 | <95 low; >115 high | 없음 |
| EQ-0008 / RT-03 | `rt_motor_current` | A | 8–16 | <8 low; >16 high | 없음 |
| EQ-0009 / CV-01 | `cv_speed` | m_min | 10–60 | <10 low; >60 high | 없음 |
| EQ-0009 / CV-01 | `cv_belt_tension` | kPa | 380–460 | <380 low; >460 high | 없음 |
| EQ-0009 / CV-01 | `cv_queue_len` | pct | 0–70 | <0 low; >70 high | 없음 |
| EQ-0010 / CV-02 | `cv_queue_len` | pct | 0–70 | <0 low; >70 high | 없음 |

## CAU·PDP 보강 신호와 T2 작성 기준

보강 신호 4개는 기준정보 JSON의 측정점이 아니라 [`ADDITIONAL_SIGNALS`](../../shiftlink/mes/scenarios/priority.py)의 가상 시연 정의에서 가져왔다. [`from_catalog()`](../../shiftlink/mes/configuration.py)가 확장한 구성에서 사용한다. 저장된 과거 run 구성에는 없을 수 있으므로 해당 run의 `config_id`와 실제 신호·단위·정상 범위를 우선 확인한다. 위 표의 범위를 다른 구성에 그대로 적용하지 않는다.

| 설비 / 카드 필드 | 보강 신호 | 의미 | 검색 조건 후보 | 적용 시 확인할 점 |
| --- | --- | --- | --- | --- |
| CAU-01 / `equipment="CAU"`, `mes_equipment_id="EQ-0003"` | `air_flow` | 압축공기 유량 | `air_flow_state == low` | 정지 중 0이 생성된다. 낮은 유량만으로 고장·누설을 확정하지 않는다. |
| CAU-01 / `equipment="CAU"`, `mes_equipment_id="EQ-0003"` | `compressor_current` | 압축기 전류 | `compressor_current_state == high` | 정지 중 0은 low로 분류될 수 있다. 전류만으로 과부하 원인을 확정하지 않는다. |
| PDP-01 / `equipment="PDP"`, `mes_equipment_id="EQ-0002"` | `bus_current` | 배전반 전류 | `bus_current_state == high` | 가상 정상 범위 초과이며 차단기 정격·설정값이나 전기작업 허가 기준이 아니다. |
| PDP-01 / `equipment="PDP"`, `mes_equipment_id="EQ-0002"` | `breaker_trip` | 차단기 트립 상태, 숫자 0/1 | `breaker_trip == 1`, `unit="bool"` | `true/false` 관측값은 현재 어댑터가 조건 입력에서 제외한다. 트립 표시만으로 무전압·작업 안전을 판정하지 않는다. |

파생 상태 조건의 `unit`은 `null`이다. `breaker_trip_state == high`도 현재 수치 판정으로 생성되지만, 트립 조건은 숫자 `1`과의 일치를 사용해 의도를 명시한다. 정상 범위 0–0을 처리하는 어댑터는 음수나 1 초과도 low/high로 분류할 수 있으므로, 작성·검수 시 트립 관측값이 0/1인지 확인한다. 신호가 없거나 품질·단위가 맞지 않으면 정상이나 미트립으로 대체하지 않고 `unverified`로 남긴다.

아래는 **검수용 T2 검색 조건 조합**이다. 원문 근거에서 해당 조건에 따라 요령이 달라지는 것이 확인된 카드에만 사용한다. 신호 조합 자체는 고장 원인이나 조치의 근거가 아니다. 같은 카드의 `conditions`는 모두 충족해야 하므로 두 신호 중 하나만 이상인 사례까지 다루려는 카드에 그대로 붙이지 않는다.

CAU: 압력 저하와 압축기 전류 상승이 함께 관측된 상황의 후보:

```json
[
  {"signal":"air_pressure_state","op":"==","value":"low","unit":null},
  {"signal":"compressor_current_state","op":"==","value":"high","unit":null}
]
```

PDP: 버스 전압 저하와 차단기 트립이 함께 관측된 상황의 후보:

```json
[
  {"signal":"bus_voltage_state","op":"==","value":"low","unit":null},
  {"signal":"breaker_trip","op":"==","value":1,"unit":"bool"}
]
```

`bus_voltage`의 단위 `pct`는 가상 백분율이다. 기준 전압이 확인되지 않은 상태에서 V로 환산하지 않는다. T2 카드 본문의 진단·조치에는 승인된 출처와 적용 범위가 별도로 필요하다. PDP T5 카드의 전기작업 금기·절차에는 공식 안전 자료의 적용 조항 검토가 필요하며, 이 신호 표로 안전 근거를 대신하지 않는다.

## 부품 코드

`부품 코드 없음`은 계측점에 부품 FK가 없다는 뜻이다. 별도 기준정보의 부품 코드는 다음과 같다.

| 부품 ID | 설비 ID | 부품 코드 | 기준정보 명칭 |
| --- | --- | --- | --- |
| CP-0001 | EQ-0001 | `HPU-01-PMP` | 주 베인펌프 |
| CP-0002 | EQ-0001 | `HPU-01-FLT` | 리턴 필터 |
| CP-0003 | EQ-0001 | `HPU-01-ACC` | 축압기 |
| CP-0004 | EQ-0001 | `HPU-01-RLV` | 릴리프 밸브 |
| CP-0005 | EQ-0001 | `HPU-01-CLR` | 오일 쿨러 |
| CP-0006 | EQ-0001 | `HPU-01-HOS` | 주 공급 호스 |
| CP-0007 | EQ-0004 | `GR-01-BRG` | 입력측 베어링 |
| CP-0008 | EQ-0004 | `GR-01-GBX` | 감속 기어박스 |
| CP-0009 | EQ-0004 | `GR-01-CPL` | 커플링 |
| CP-0010 | EQ-0004 | `GR-01-MTR` | 구동 모터 |
| CP-0011 | EQ-0004 | `GR-01-VIB` | 진동 센서 |
| CP-0012 | EQ-0004 | `GR-01-TMP` | 베어링 온도 센서 |
| CP-0013 | EQ-0008 | `RT-03-ROL` | 롤러 세트 |
| CP-0014 | EQ-0008 | `RT-03-CLP` | 유압 클램프 |
| CP-0015 | EQ-0009 | `CV-01-BLT` | 벨트 |
| CP-0016 | EQ-0009 | `CV-01-TNS` | 텐셔너 |
| CP-0017 | EQ-0007 | `RT-02-LFT` | 승강 실린더 |
| CP-0018 | EQ-0006 | `RT-01-CLP` | 유압 클램프 |

신호 이름이나 카드의 자유 텍스트 `component`만으로 부품 코드에 자동 연결하지 않는다. 카드 작성자가 출처와 설비를 확인한 경우에만 `mes_component_code`를 명시하고, 그렇지 않으면 `null`로 둔다. GR-02 등에서 GR-01 부품 코드를 복사하지 않는다.

## 카드 템플릿

기존 `KnowledgeCard` JSON을 그대로 사용한다. 필수 본문과 출처는 실제 자료로 채우고, 아래 두 MES 필드는 선택 사항이다. `mes_equipment_id`가 있으면 해당 설치 위치에서만 검색된다. 비워 두면 기존 `equipment` 유형 범위가 유지된다. `mes_component_code`는 작성자가 검수한 식별자 기록이며 검색 조건이 아니다.

```json
{
  "card_id": "K-9001", "version": "1.1-draft-001", "grade": "L0",
  "tacit_type": "T1", "equipment": "GR", "component": "원문 부품 명칭",
  "mes_equipment_id": null, "mes_component_code": null,
  "scenario": "S1", "title": "출처로 확인한 제목", "symptom": "출처로 확인한 증상",
  "know_how": "매뉴얼에서 확인한 절차와 수치", "rationale": "근거 설명",
  "conditions": [], "exclusions": [], "safety_flag": false,
  "confidence": 0, "split": "kb", "status": "draft",
  "provenance": {"seed_ids": [], "persona_id": "작성자", "event_ids": [],
    "generator": "manual", "generated_at": "2026-09-29T00:00:00+09:00",
    "sources": [{"source_id": "확인한 원문 ID", "locator": "확인한 절/쪽", "document_version": "확인한 버전"}]}
}
```

복사 가능한 **가상 설비 검색 조건** 예시 (원문 절차의 임계값이 아님):

```json
{"signal":"gr_brg_temp_state","op":"==","value":"high","unit":null}
```

```json
{"signal":"hpu_pressure_state","op":"==","value":"low","unit":null}
```

첫 예시는 `K-1025`처럼 베어링부 온도 상승이 직접 관련된 카드의 **검수용 후보**다. 카드에 실제로 추가하면 온도가 정상인 경우 검색에서 제외되므로 적용 범위 검수가 필요하다. 원문 절차·수치·출처는 `know_how`와 `provenance.sources`에 그대로 둔다. `K-1029`의 300 ppm은 원문 수분 점검 수치이며 `gr_brg_temp_state`와 관계없다. `K-1025`에는 300 ppm 조건이 없다.

조건을 붙이면 안 되는 예: `K-1007`의 `fluid_viscosity > 2000 cSt`를 `hpu_oil_temp_state == low`로 바꾸기. 점도 측정점은 카탈로그에 없고, 저온만으로 점도를 추정할 수 없다. 기존 조건은 신호가 없을 때 `unverified`로 남는다.

## 어댑터 사용과 검수 대기

`MesCardAdapter(observer, config, provider).search(run_id, "GR", question)`은 `GR`을 실제 `GR-01` (`EQ-0004`)로 해석한다. `GR-02` 또는 `EQ-0005`는 명시적으로 지정한다. `PDP`·`CAU`도 `PDP-01`·`CAU-01`로 해석하고, 카드 `equipment`는 그 유형을 그대로 쓴다. `COMMON`으로 바꾸지 않는다. PDP-01·CAU-01은 가상 설비라 제조사 매뉴얼의 차단·검전·잔압 절차를 이 설비의 확정 절차로 쓰지 않는다. RT-02 승강이 K-1018~1023 코일카 시저 리프트와 같은 구조인지는 아직 확인되지 않았다. 결과의 `request.observations`는 검색용 원값과 상태값, `evidence`는 시각·원신호·값·단위·품질·활성 알람, `answer`와 `handover_record`는 같은 근거와 verified/unverified 카드 ID를 담는 구조화된 기록이다. 별도 모델 답변이나 MES 웹 화면에 자동으로 연결되는 경로는 아직 없다. ground truth는 어느 결과에도 복사하지 않는다. 기존 안전 카드는 검색 결과 앞에 둔다.

대응표가 **직접** 연결 후보로 표시한 카드는 `K-1001`, `K-1002`, `K-1004`, `K-1024`, `K-1025`, `K-1027` 여섯 장이다. 모두 **카드별 수동 검수 대상**이고 조건은 아직 붙이지 않았다. `K-1001`의 원문은 압력 *없음*인데 가상 고장 시나리오는 120 bar의 *low*일 뿐이다. `K-1002`의 냉각기 **출구** 유온은 `hpu_oil_temp`의 측정 위치와 같다고 확인되지 않았다. `K-1004`의 핵심 소음·거품은 관측 불가다. `K-1024`는 온도·진동 중 하나만 붙이면 적용 범위가 바뀐다. `K-1025`는 베어링 온도와 증상이 직접 대응하지만 원인과 복구 조치는 MES 시나리오와 다르다. `K-1027`의 `gr_oil_leak`는 기본 카탈로그에 없고 일부 런타임 구성에서만 추가되므로 해당 `config_id` 확인이 먼저다. 미매핑 유지: `K-1007`의 점도, `K-1029`의 설치 환경·오일 수분. 기존 30장에 조건을 일괄 추가하지 않는다.
