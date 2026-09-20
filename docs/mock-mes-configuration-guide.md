# 모의 MES 구성 가이드: 장비 교체·추가·수정 방법

## 개요

구성(Configuration)은 특정 시점의 설비 배치, 신호, 연결, 시나리오를 정의하는 불변 문서다. 시간이 지나면서 설비가 추가·교체·제거되면 새로운 구성을 적용하고, 기존 운전 기록은 당시 구성과 함께 보존된다.

## 1. 기본 구성 A 이해

`configuration.py`의 `from_catalog()`는 `docs/00_plant_and_relations.json`에서 기본 구성을 생성한다.

```
from shiftlink.mes.configuration import from_catalog
import json

with open('docs/00_plant_and_relations.json', encoding='utf-8') as f:
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
| 시나리오 | drive_fault, hydraulic_fault, downstream_block |
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
with open('docs/00_plant_and_relations.json', encoding='utf-8') as f:
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

config_d = from_payload(payload_d)
errors = validate(config_d)
```

## 5. 신호 변경

단위 변경, 신호 삭제는 validate()에서 오류를 보낸다.

### 단위 변경: bar → kPa

```python
# hpu_pressure: bar(100 = ~10 MPa) → kPa (1000 kPa ~ 10 MPa)
for eq in payload['equipment']:
    if eq['equipment_id'] == 'EQ-0001':
        for sig in eq['signals']:
            if sig['signal'] == 'hpu_pressure':
                sig['unit'] = 'kPa'
                sig['normal_min'] = 1000  # 10 MPa → 1000 kPa (근사)
                sig['normal_max'] = 1200
```

### 신호 삭제

선택 신호는 제거 가능. 필수 신호(required=True) 제거는 검증 실패.

```python
# cv_belt_tension (선택) 삭제
for eq in payload['equipment']:
    if eq['equipment_id'] == 'EQ-0009':
        eq['signals'] = [s for s in eq['signals'] if s['signal'] != 'cv_belt_tension']
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
- `config_c_add_rt.json`: RT-04 추가
- `config_d_remove_valid.json`: CV-02 제거 (유효)
- `config_d_remove_invalid.json`: 참조 남은 제거 시도 (오류)
- `config_e_signal_unit_change.json`: hpu_pressure bar→kPa
- `config_f_unknown_capability.json`: 알 수 없는 capability (검증 오류)
- `config_g_explicit_route.json`: EQ-0008→EQ-0010 경유 주경로

## 참고: 설비 시나리오 도출

### capability → 시나리오 매핑

| capability | 시나리오 | 원인 | 전파 방식 |
| --- | --- | --- | --- |
| drive | drive_fault | GR 진동 급증(gr_vib_rms=5.0) | drive 관계 따라 대상 설비 대기 |
| hydraulic_supply | hydraulic_fault | HPU 압력 저하(hpu_pressure=120 bar) | hydraulic_supply 관계 따라 전파 |
| discharge | downstream_block | CV 큐(cv_queue_len=95) 다찼음 | interlock 관계로 상류 설비 대기 |

### 신호 효과

signal_effects는 capability와 신호명으로 대상을 선택한다. 설비 코드명(GR-01 등)은 사용하지 않는다.

```python
ScenarioSpec(
    scenario_id='hydraulic_fault',
    cause_capability='hydraulic_supply',  # HPU-01, HPU-02 등 해당 capability 설비 모두 영향
    propagation_relation='hydraulic_supply',  # 이 유형의 관계로 연쇄
    ...
    signal_effects=(
        SignalEffect(
            capability='hydraulic_supply',  # 대상: hydraulic_supply capability를 가진 모든 설비
            signal='hpu_pressure',
            value=120.0  # 정상: 150~180 bar에서 비정상: 120 bar로 강제
        ),
    )
)
```

## 자산 ID 정책

- 새로운 자산: `AS-{equipment_id}-{序号}` (예: AS-EQ-0001-002)
- 폐기 자산의 ID는 절대 재사용하지 않는다.
- 설비 위치(equipment_id)가 바뀌지 않으면 같은 위치의 새로운 asset_id를 할당한다.
