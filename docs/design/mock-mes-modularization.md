# 모의 MES 모듈화: 공통 계약·파일 소유권·구성 적용 설계

작성: 2026-09-20. 이 문서는 `docs/templates/mock-mes-claude-upgrade-template.md`의 실행 결과로, 병렬 개발의 기준 계약이다.

## 기준 상태 (2026-09-20 실측)

- 브랜치 `docs/day2-work-result`, 미커밋 변경: 이 문서와 템플릿 문서.
- Python **3.10.11** (winget 설치, venv: `%LOCALAPPDATA%/Temp/claude/mes310venv`).
- 기준 테스트: `tests/test_mes*.py` → **40 passed, 2 skipped, 10 subtests**, Python MES 커버리지 **91%** (3.10.11). 이전 문서의 "75개 통과(3.12.10)"는 현재 상태와 다르며 개수 자체를 합격 기준으로 삼지 않는다.
- 기준정보: `docs/data/reference/00_plant_and_relations.json` (설비 10대 EQ-0001~0010, material_flow 4건 — EQ-0006→0007→0008→{0009(60 m_min), 0010(20 m_min)} 분기).

## 식별자 의미 (합의, 조용히 바꾸지 않음)

| 개념 | 필드 | 의미 |
| --- | --- | --- |
| 논리 설치 위치 | `equipment_id` (기존, 예 EQ-0006) | 라인 내 역할 슬롯. **기존 의미 보존.** 교체돼도 위치 ID는 유지 가능 |
| 합성 자산 | `asset_id` (신규) | 특정 장비 인스턴스. 교체 시 새 ID 발급, 폐기 ID 재사용 금지 |
| 설비 프로필 | `profile_id` (신규) | 유형: 기능(capabilities), 신호 목록, 기본 특성 |
| 구성 버전 | `config_id` (신규) | 정규화된 구성 JSON의 sha256. 라벨은 `version_label` |

이름 변경·파라미터 조정·자산 교체·설치 위치 변경은 config diff에서 서로 다른 변경 유형으로 구분한다.

## 공유 데이터 계약 (`contracts.py`, 메인 소유)

`contracts.py`에 다음 frozen dataclass를 추가한다. 모든 담당은 이 형태만 참조한다.

- `SignalSpec(signal, name, unit, normal_min, normal_max, required=True, zero_when_stopped=False)`
- `EquipmentConfig(equipment_id, asset_id, code, name, segment_id, profile_id, capabilities: tuple[str,...], signals: tuple[SignalSpec,...], coil_capacity=1, dwell_seconds=10.0, active=True)`
- `RelationConfig(relation_type, from_id, to_id, lag_seconds=None, capacity_value=None, capacity_unit=None)`
- `ScenarioSpec(scenario_id, cause_capability, propagation_relation, wait_reason, alarm_code, signal_effects: tuple[SignalEffect,...], recovery_ticks=2)`
  - `SignalEffect(capability, signal, value)` — 대상은 capability로 선택, 코드명(GR-01 등) 결합 금지
- `Configuration(config_id, version_label, source, line_id, equipment, relations, route: tuple[str,...], branches, scenarios, layout)`
  - `route`: **명시적** 주경로 equipment_id 순서. capacity로 추정하지 않는다. `m_min`은 유량 단위이며 코일 개수 용량이 아니다(코일 수용은 `coil_capacity`).
  - `layout`: `LayoutGroup(title, equipment_ids)` 튜플 — 서버가 검증한 배치를 UI가 그대로 사용
- `Run`: `config_id: str | None = None` 필드 추가(기존 필드 유지, None = 당시 구성 미보존)

`config_id` 계산: `configuration.py`의 `canonical_payload(config)` (키 정렬 JSON) sha256. 계산 함수는 아키텍처 소유.

## 파일 소유권

| 담당 | 파일 |
| --- | --- |
| 메인·통합 | `contracts.py`, `server.py`, `storage.py`, `adapters.py`, `__main__.py`, `tests/test_mes_contracts.py`, `test_mes_storage.py`, `test_mes_server.py`, `test_mes_http.py`, 이 문서 |
| 산업 도메인 | `engine.py`, `scenarios/`, `tests/test_mes_engine.py`, `tests/test_mes_integration.py`(엔진 관련) |
| 모듈화 아키텍처 | `configuration.py`(신규), `catalog.py`, `tests/fixtures/mes/*.json`, `tests/test_mes_configuration.py`(신규) |
| UI/UX | `web/`, `tests/test_mes_web.py`, `tests/test_mes_ui_layout.py` |

다른 담당 파일은 직접 수정하지 않는다. 공용 계약 변경 요청은 이유·호환성·영향 테스트와 함께 메인에 전달.

## 모듈 인터페이스

### `configuration.py` (아키텍처 소유)

- `from_catalog(catalog_data: dict) -> Configuration` — 기존 `docs/data/reference/00_plant_and_relations.json`에서 기본 구성 A 생성. 원본 파일은 불변. 주경로는 material_flow 위상 + **현행 동작 보존을 위해 문서화된 규칙**으로 한 번만 산출하고 Configuration에 명시 고정.
- `load_draft(payload: dict, *, source: str) -> Configuration` — 사용자 JSON 초안 로딩(스키마 검사 포함). eval 불가 순수 데이터만.
- `validate(config: Configuration) -> list[str]` — 의미 검증: 중복 ID(equipment/asset/signal), 알 수 없는 profile/capability, 끊긴 route(비활성·부재 설비 참조), 누락 공급 관계, 필수 신호 누락, 단위 없는 신호, 모호한 분기(route 밖 material_flow에 분기 규칙 없음), 폐기 asset_id 재사용. 오류는 위치·이유 포함 문자열.
- `diff(old: Configuration, new: Configuration) -> dict` — 유형별 변경 목록: `renamed / param_changed / asset_replaced / added / removed / signal_changed / route_changed / layout_changed`.
- `canonical_payload(config) -> str`, `config_hash(config) -> str`, `to_payload / from_payload` 직렬화.
- 알 수 없는 capability를 가진 profile은 `validate`가 거부(미지원 유형 케이스).

### `engine.py` (도메인 소유)

- `MesEngine(run: Run, config: Configuration)` — catalog dict 직접 소비 제거.
- 시나리오: `config.scenarios`에서 `cause_capability`로 대상 설비 선택(해당 capability 보유 + active). 대상 부재 시 해당 시나리오는 `set_scenario`에서 ValueError("이 구성에 적용 불가: ...").
- 영향 전파: `propagation_relation` 유형의 관계만 사용. `co_occurrence`는 전파에 사용 금지.
- 소재 이동: `config.route` 사용(추정 금지), `coil_capacity`/`dwell_seconds` 반영. 유닛 보존.
- 측정값: `SignalSpec` 기반, `zero_when_stopped` 신호는 비가동 시 0. `signal_effects`는 capability+signal로 적용.
- 알람 코드: `ScenarioSpec.alarm_code` 사용 (`SYN-{시나리오명}` 금지 — 원인명 누수).
- 이벤트 observation에 시나리오 원인명 노출 금지(중립 문구). `scenario_selected` 이벤트는 유지하되 관측 경계(adapters)에서 차단됨을 전제.
- 시나리오 등록: `scenarios/__init__.py`는 config의 scenario_id 집합을 받도록 변경 가능(도메인 재량, 계약 유지).

### `storage.py` (메인 소유)

- 신규 테이블(기존 테이블 불변, CREATE IF NOT EXISTS만):
  - `configurations(config_id PK, created_at, payload)` — 정규화 JSON 원문
  - `config_changes(change_id PK, requested_at, applied_at, base_config_id, new_config_id, reason, actor, actor_self_reported, status, detail, run_id)`
- `save_configuration / get_configuration / list_config_changes / record_config_change`.
- 기존 DB(구성 스냅샷 없는 run) → `Run.config_id is None` → "당시 구성 미보존". 자동 초기화·삭제 금지.

### `server.py` API (메인 소유)

기존 엔드포인트 유지 + 추가:

| 메서드 경로 | 동작 |
| --- | --- |
| GET `/api/config` | 활성 구성 payload + config_id |
| GET `/api/configs/{config_id}` | 저장된 구성(재생용). 없으면 404 |
| POST `/api/config/validate` | body `{draft}` → `{valid, errors, diff}` (활성 구성 대비) |
| POST `/api/config/apply` | body `{base_config_id, draft, reason, actor}` → 가동 중이면 409 거부(일시정지 필요), base 불일치 시 409 충돌, 검증 실패 400. 성공 시: 이전 런 종료 이벤트+잔여 코일 기록, 새 구성 저장, 새 런 생성. 실패 시 기존 활성 구성·이력 완전 유지 |
| GET `/api/runs/{id}/replay` | 기존 + `config_id`, `config_preserved` 필드 |

- config 관련 POST 본문 한도 256KB(기존 8KB는 control 전용 유지).
- `actor`는 자기기입(self-reported) 표시. 검증된 신원이라 주장하지 않음.
- 적용은 `_lock` 내에서 base_config_id 재확인(동시 적용 경쟁 차단).
- 상태 응답에 `config_id` 포함(클라이언트 버전 혼합 방지).

### `adapters.py` (메인 소유) — 관측 누수 경계

- 명시적 허용 목록: 이벤트 유형 `{started, paused, coil_entered, coil_exited, alarm_raised, alarm_cleared, recovered, run_closed}`. `scenario_selected`, `recovery_started`는 모델 관측에서 제외.
- 스냅샷에서 `scenario_id` 제거. `wait_reason`·알람 코드는 실제 관측 가능 항목으로 유지(문서화).
- GroundTruth는 계속 비공개. 관측에 `config_id`(당시 구성)·단위 포함, as_of 적용.

### `web/` (UI/UX 소유)

- `materialRoute()` 자체 계산 제거 → `/api/config`의 `route`·`layout` 사용.
- 상태/이벤트/구성 응답의 `run_id`·`config_id` 불일치 시 혼합 렌더 금지.
- 재생: 해당 런의 `config_id`로 `/api/configs/{id}` 조회, 당시 설비명·단위·경로·배치로 렌더. `config_preserved=false`면 "당시 구성 미보존" 표시. 현재 구성 정보 혼입 금지.
- 단위가 다른 측정 계열은 같은 그래프 계열로 결합하지 않음.
- 구성 관리 화면: 파일 선택 → 검증 → diff 확인 → (일시정지 상태에서) 적용 → 새 런. 실패 시 구체 오류 표시. 드래그 편집기·권한 관리 없음.
- 설비 상세: 표시명, 논리 위치(equipment_id), asset_id, profile, 단위 있는 신호, 현재 config 버전. 누락 신호는 "관측 없음"으로 표시(0·정상으로 위장 금지).

## fixture 계획 (아키텍처 소유, `tests/fixtures/mes/`)

- `config_a.json`: `from_catalog` 결과와 동일한 기본 10대 구성(파일 고정본).
- `config_b_hpu_swap.json`: A에서 HPU 자산 교체(asset_id 신규, 이름·프로필 수치 변경). 코드 수정 없이 새 런 운전 + 유압 시나리오가 capability로 적용돼야 함.
- `config_c_add_transport.json`: 기존 transport capability 설비를 주경로에 삽입.
- `config_d_remove.json`: 설비 제거(참조 남은 무효본 + 유효본 두 가지).
- `config_e_signal_change.json`: 단위 변경(bar→kPa)·선택 신호 삭제·필수 신호 삭제(무효).
- `config_f_unknown_profile.json`: 알 수 없는 capability(검증 거부용).
- `config_g_branch.json`: capacity 순서와 다른 명시 주경로(EQ-0008→EQ-0010 경유).

## 구성 적용 흐름 (런 경계 적용, hot swap 범위 밖)

1. 초안 로딩(파일) → 2. diff → 3. 의미 검증 → 4. 가동 중이면 차단(일시정지 요구) → 5. 적용 = 이전 런 보존·잔여 코일 기록·새 구성으로 새 런(코일 이관 없음, 초기 소재는 새 런 가정으로 표시) → 6. 실패·충돌 시 기존 구성 유지. 되돌리기 = 이전 구성을 참조하는 **새 런**(과거 덮어쓰기 금지).

## 데이터 경계 주의

- 시나리오 주입 정보·기대 결과는 as_of 모델 관측 입력에 포함하지 않는다(adapters 허용 목록이 유일한 통로).
- split 기본 dev. sealed 사건 파일 미사용.
