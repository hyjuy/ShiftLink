# 모의 MES 구성 가이드: 장비 교체·추가·수정 방법

## 개요

구성(Configuration)은 특정 시점의 설비 배치, 신호, 연결, 시나리오를 정의하는 불변 문서다. 시간이 지나면서 설비가 추가·교체·제거되면 새로운 구성을 적용하고, 기존 운전 기록은 당시 구성과 함께 보존된다.

## 1. 기본 구성 A 이해

`configuration.py`의 `from_catalog()`는 `docs/data/reference/00_plant_and_relations.json`에서 기본 구성을 생성한다.

```
from shiftlink.mes.configuration import from_catalog
import json

with open('docs/data/reference/00_plant_and_relations.json', encoding='utf-8') as f:
    catalog = json.load(f)
    
config = from_catalog(catalog)
print(f"기본 구성: {config.config_id}")
print(f"설비: {len(config.equipment)}대")
print(f"주경로: {' → '.join(config.route)}")
```

기본 구성 A의 특징:

| 항목 | 값 |
| --- | --- |
| 설비 수 | 10대 (HPU-01, PDP-01, CAU-01, GR-01, GR-02, RT-01, RT-02, RT-03, CV-01, CV-02) |
| 주경로 | EQ-0006 → EQ-0007 → EQ-0008 → EQ-0009 |
| 분기 | EQ-0008 → EQ-0010 (20 m_min, branches로 기록) |
| 시나리오 | 활성 `config.scenarios` 기준. 2026-09-30 기본 구성은 기존 공정·복구 시연 9개 + 독립 센서 46개 + 증상 조합 22개 = 77개 |
| 특수 신호 | rt_speed/cv_speed는 비가동 시 0 (zero_when_stopped=True) |

## 2. 동일 기능 교체: HPU 자산 교체 (구성 B)

HPU-01(EQ-0001)을 새 유닛으로 교체하되, **동일 위치·기능·신호**를 유지한다.

### 변경 항목

| 필드 | 이전 | 새로운 |
| --- | --- | --- |
| equipment_id | EQ-0001 | EQ-0001 (불변 — 위치) |
| asset_id | AS-EQ-0001-001 | AS-EQ-0001-002 (신규 자산) |
| name | HPU-01 | HPU-01B (선택 사항) |
| normal_min(hpu_pressure) | 150 (가정) | 160 (새 유닛 사양) |
| normal_max(hpu_pressure) | 180 | 185 |

### 생성 코드

```python
import json
from shiftlink.mes.configuration import from_catalog, to_payload, from_payload, finalize

# 기본 구성 로드
with open('docs/data/reference/00_plant_and_relations.json', encoding='utf-8') as f:
    catalog = json.load(f)
config_a = from_catalog(catalog)

# 구성 B: HPU 자산 교체
payload = to_payload(config_a)

# EQ-0001 수정
for eq in payload['equipment']:
    if eq['equipment_id'] == 'EQ-0001':
        eq['asset_id'] = 'AS-EQ-0001-002'
        eq['name'] = 'HPU-01B'
        # 신호 범위 수정
        for sig in eq['signals']:
            if sig['signal'] == 'hpu_pressure':
                sig['normal_min'] = 160
                sig['normal_max'] = 185
        break

config_b = from_payload(payload)
config_b = finalize(config_b)  # config_id 재계산

# 검증
from shiftlink.mes.configuration import validate, diff
errors = validate(config_b)
if errors:
    print(f"검증 실패: {errors}")
else:
    print(f"구성 B 생성 완료: {config_b.config_id}")
    
# 변경 확인
changes = diff(config_a, config_b)
print(f"변경 항목: {changes}")
```

### 엔진 호환성

엔진은 `config.equipment_by_id()["EQ-0001"].capabilities`에서 "hydraulic_supply"를 찾는다. asset_id 변경은 시나리오 동작에 영향하지 않는다. 새로운 정상 범위(160~185)로 측정값이 생성된다.

## 3. 장비 추가: 입측 트랜스포트 설비 추가 (구성 C)

기존 transport 기능 설비를 주경로에 삽입. 새 장비 ID: EQ-0011.

### 변경 항목

- 신규 설비 EQ-0011 (RT-04, transport 기능)
- 신규 asset: AS-EQ-0011-001
- 신규 관계: EQ-0006 → EQ-0011 → EQ-0007 (material_flow)
- 기존 관계 EQ-0006 → EQ-0007 제거
- 신규 드라이브 관계: GR-01(EQ-0004) → EQ-0011
- 신규 유압 관계: HPU-01(EQ-0001) → EQ-0011
- 주경로: EQ-0006 → **EQ-0011** → EQ-0007 → EQ-0008 → EQ-0009

### 생성 코드 개요

```python
payload_c = to_payload(config_a)

# 신규 설비 추가
new_eq = {
    'equipment_id': 'EQ-0011',
    'asset_id': 'AS-EQ-0011-001',
    'code': 'RT-04',
    'name': 'RT-04',
    'segment_id': 'SG-0002',
    'profile_id': 'roller',
    'capabilities': ['transport'],
    'signals': [
        {'signal': 'rt_speed', 'name': 'Roller Speed', 'unit': 'm/min',
         'normal_min': 20, 'normal_max': 30, 'required': True,
         'zero_when_stopped': True},
        {'signal': 'rt_clamp_press', 'name': 'Clamp Pressure', 'unit': 'bar',
         'normal_min': 8, 'normal_max': 12, 'required': True,
         'zero_when_stopped': False}
    ],
    'coil_capacity': 1,
    'dwell_seconds': 12.0,
    'active': True
}
payload_c['equipment'].append(new_eq)

# 관계 수정
# 1. 기존 EQ-0006→EQ-0007 제거 (찾아서 삭제)
payload_c['relations'] = [
    r for r in payload_c['relations']
    if not (r['from_id'] == 'EQ-0006' and r['to_id'] == 'EQ-0007')
]

# 2. 신규 관계 추가
payload_c['relations'].extend([
    {
        'relation_type': 'material_flow', 'from_id': 'EQ-0006', 'to_id': 'EQ-0011',
        'lag_seconds': 12, 'capacity_value': 120, 'capacity_unit': 'm_min'
    },
    {
        'relation_type': 'material_flow', 'from_id': 'EQ-0011', 'to_id': 'EQ-0007',
        'lag_seconds': 12, 'capacity_value': 120, 'capacity_unit': 'm_min'
    },
    {
        'relation_type': 'drive', 'from_id': 'EQ-0004', 'to_id': 'EQ-0011',
        'lag_seconds': 1, 'capacity_value': None, 'capacity_unit': None
    },
    {
        'relation_type': 'hydraulic_supply', 'from_id': 'EQ-0001', 'to_id': 'EQ-0011',
        'lag_seconds': 5, 'capacity_value': 12, 'capacity_unit': 'L_min'
    }
])

# 3. 주경로 수정
payload_c['route'] = ['EQ-0006', 'EQ-0011', 'EQ-0007', 'EQ-0008', 'EQ-0009']

config_c = from_payload(payload_c)
config_c = finalize(config_c)
```

## 4. 장비 제거

설비를 제거하려면 다른 장비의 관계 대상이 아니어야 한다.

```python
# 예: CV-02(EQ-0010) 제거 (브랜치이므로 가능)
payload_d = to_payload(config_a)

# 1. EQ-0010 제거
payload_d['equipment'] = [
    e for e in payload_d['equipment'] if e['equipment_id'] != 'EQ-0010'
]

# 2. EQ-0010 관련 관계 제거
payload_d['relations'] = [
    r for r in payload_d['relations']
    if r['from_id'] != 'EQ-0010' and r['to_id'] != 'EQ-0010'
]

# branches에서도 제거
payload_d['branches'] = [
    r for r in payload_d.get('branches', [])
    if r['from_id'] != 'EQ-0010' and r['to_id'] != 'EQ-0010'
]

# 제거 설비를 명시적으로 지정한 센서·증상 시나리오도 제거
payload_d['scenarios'] = [
    s for s in payload_d['scenarios'] if s.get('cause_equipment_id') != 'EQ-0010'
]
# 화면 배치에서도 제거
for group in payload_d['layout']:
    group['equipment_ids'] = [i for i in group['equipment_ids'] if i != 'EQ-0010']

config_d = from_payload(payload_d)
errors = validate(config_d)
```

## 5. 신호 변경

단위 변경 자체는 허용된다. `validate()`는 단위 누락, 중복 신호, 지정한 원인 설비에 없는 시나리오 효과 등을 검사한다. 필수 신호 삭제를 모든 profile에 대해 자동 차단하는 검증은 구현되어 있지 않다. `diff()`의 `signal_changed`를 검토하고 관련 카드 조건·시나리오 효과·단위를 함께 재검수한다.

### 단위 변경: bar → kPa

```python
# 1 bar = 100 kPa. 100 bar = 10 MPa = 10000 kPa.
for eq in payload['equipment']:
    if eq['equipment_id'] == 'EQ-0001':
        for sig in eq['signals']:
            if sig['signal'] == 'hpu_pressure':
                sig['unit'] = 'kPa'
                sig['normal_min'] *= 100
                sig['normal_max'] *= 100
# 동일 설비의 압력 효과값도 변환한다. 단위 문자열만 바꾸면 안 된다.
for scenario in payload['scenarios']:
    if (scenario['cause_capability'] == 'hydraulic_supply'
            and scenario.get('cause_equipment_id') in (None, 'EQ-0001')):
        for effect in scenario['signal_effects']:
            if effect['signal'] == 'hpu_pressure':
                effect['value'] *= 100
```

### 신호 삭제

신호를 제거할 때는 그 신호를 사용하는 지정 설비 시나리오도 함께 검토한다. `required=True`의 삭제를 일반적으로 차단하지 않으므로 필수 관측 계약을 사람이 확인해야 한다. 아래는 센서와 해당 센서를 사용하는 지정 설비 시나리오를 함께 제거하는 예다.

```python
# CV-01의 cv_belt_tension 삭제 (기본 구성에서는 required=True이므로 계약 재검수 필요)
for eq in payload['equipment']:
    if eq['equipment_id'] == 'EQ-0009':
        eq['signals'] = [s for s in eq['signals'] if s['signal'] != 'cv_belt_tension']
payload['scenarios'] = [s for s in payload['scenarios']
    if not (s.get('cause_equipment_id') == 'EQ-0009'
            and any(e['signal'] == 'cv_belt_tension' for e in s['signal_effects']))]
```

## 6. 검증과 diff

```python
from shiftlink.mes.configuration import validate, diff

# 검증
errors = validate(new_config)
if errors:
    for e in errors:
        print(f"오류: {e}")
else:
    print("검증 완료")

# 변경 내역
changes = diff(old_config, new_config)
print(f"추가됨: {[c['equipment_id'] for c in changes.get('added', [])]}")
print(f"제거됨: {[c['equipment_id'] for c in changes.get('removed', [])]}")
print(f"교체됨: {[(c['equipment_id'], c['old_asset_id'], c['new_asset_id']) for c in changes.get('asset_replaced', [])]}")
```

## 7. Fixture 파일 목록

- `config_a.json`: 기본 10대 구성
- `config_b_hpu_swap.json`: HPU 자산 교체
- `config_c_add_transport.json`: RT-04 추가
- `config_d_remove_valid.json`: CV-02 제거 (유효)
- `config_d_remove_invalid.json`: 참조 남은 제거 시도 (오류)
- `config_e_signal_change.json`: 신호 단위 변경
- `config_e_missing_required.json`: 필수 신호 삭제 검토 예
- `config_f_unknown_profile.json`: 알 수 없는 capability (`future_capability`, 검증 거부용). profile 이름이 미지원인 경우의 일반 설비 표현과 구분한다.
- `config_g_branch.json`: 분기 구성 예

## 참고: 설비 시나리오 도출

### capability → 시나리오 매핑

| capability | 시나리오 | 원인 | 전파 방식 |
| --- | --- | --- | --- |
| drive | drive_fault | GR 진동 급증(gr_vib_rms=5.0) | drive 관계 따라 대상 설비 대기 |
| hydraulic_supply | hydraulic_fault | HPU 압력 저하(hpu_pressure=120 bar) | hydraulic_supply 관계 따라 전파 |
| discharge | downstream_block | CV 큐(cv_queue_len=95) 다찼음 | interlock 관계로 상류 설비 대기 |

### 신호 효과

`cause_equipment_id`가 있으면 해당 설치를 지정하며 없으면 해당 capability의 첫 활성 설비를 원인 대상으로 선택한다. 없는·비활성·기능이 다른 지정 설비를 다른 설비로 대체하지 않는다. `signal_effects`는 원인 설비의 해당 신호만 바꾼다. 전파는 원인에서 `propagation_relation`으로 직접 연결된 설비에만 적용하며 연쇄 전파하지 않는다.

```python
ScenarioSpec(
    scenario_id='hydraulic_fault',
    cause_capability='hydraulic_supply',  # 해당 기능의 첫 활성 설비 선택
    propagation_relation='hydraulic_supply',  # 원인에서 이 유형으로 직접 연결된 설비만 대기
    ...
    signal_effects=(
        SignalEffect(
            capability='hydraulic_supply',  # 원인으로 선택된 설비만 측정값 변경
            signal='hpu_pressure',
            value=120.0  # 기본 정상 145~165 bar에 대한 가상 low; 변경 구성에서는 재검수
        ),
    )
)
```

## 자산 ID 정책

기본 시연 수치와 조합은 [신호 사전](mes-card-signals.md), [논문 조사](../research/mes-symptom-screening.md)를 따른다. `bool` 채널은 숫자 0/1만 사용한다. 정상 범위가 변경되어 요청한 low/high 조합을 만들 수 없으면 새 증상 시나리오 생성에서 제외하며, 저장된 기존 구성의 시나리오 값은 자동 재작성하지 않는다. 사용자 업로드 구성은 자동 보강하지 않는다.

- 새로운 자산: `AS-{equipment_id}-{序号}` (예: AS-EQ-0001-002)
- 폐기 자산의 ID는 절대 재사용하지 않는다.
- 설비 위치(equipment_id)가 바뀌지 않으면 같은 위치의 새로운 asset_id를 할당한다.
