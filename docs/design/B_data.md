# 전문가B — 합성 데이터·평가 파이프라인 고도화안

작성 2026-09-17 / 대상 문서 「최종 통합본(고도화 v1.1)(codex)」 4.7·4.9·4.10·3.2·3.5·6절 + 용어사전 + 사용자 2026-09-17 신규 요구.

## 0. 이 문서를 읽는 법 — 표기 규칙

- `[기존]` = 통합본에 이미 적힌 내용(사실·승인). 삭제·왜곡하지 않는다.
- `[기존 수정안]` = 기존 승인·기재 사항을 바꾸자는 제안. 반드시 이유·영향·결정 필요를 B12에 등록했다.
- `[신규 제안]` = 이번에 새로 만든 내용. 팀 승인 전이며 결정된 사실이 아니다.
- `[제안값]` / `[가정]` = 실측·근거 없는 수치. 달성 실적이 아니다.
- `[가상 값]` = 가상 라인 L1의 물리 수치. 실제 설비 수치가 아니다.
- `[잠정 제안 — 개발셋 측정 후 확정]` = 평가 목표치. 사용자 요구대로 개발셋 측정 후 봉인 평가 전에 고정한다.

**보존 확인(변경하지 않음)**
- `[기존]` MVP 최고 검증 등급은 L1(시뮬레이션 검증). L2·L3 승격 없음(4.10).
- `[기존]` "다수의 합성 답변이 같은 내용을 말한다는 사실을 정확성의 증거로 인정하지 않는다"(4.7.1 입력 격리 규칙). 이 원칙은 아래 모든 신규 검사·지표에 그대로 적용한다.
- `[기존]` P3 입력은 `seeds/`·`plant/`·`personas/`·시나리오 정의뿐. 생성물 되먹임 금지(4.7.1). B7에서 신규 엔티티를 추가해도 이 격리는 유지한다(B7-3 참조).
- `[기존]` 승인 #3(K-01 필수 필드 + `grade`), 승인 #5(규모), 승인 #8(생성 외부 API·judge 로컬)은 팀 결정 사항이다. 이 문서의 규모 제안은 승인 #5를 **대체하지 않고** B5의 결정 안건으로 올린다.
- `[기존]` 일정 9/29~10/21, 2주차 말(10/12) sealed 봉인. 오늘 9/17.

---

# B1. 데이터 사전 (data-dictionary)

## B1-0. ID 체계

### 접두어 규칙표

`[신규 제안]` 공통 형식 = `<접두어>-<4자리 zero-pad 정수>`. 기존 `EV-0031`·`K-0001` 형식과 동일하므로 기존 ID를 깨지 않는다.

| 접두어 | 엔티티 | 예시 | 자리수 | 상태 | 생성 규칙 |
| --- | --- | --- | --- | --- | --- |
| `LN-` | ProductionLine | `LN-0001` | 4 | 신규 | P1에서 수동 부여(라인 1개) |
| `SG-` | ProcessSegment | `SG-0001` | 4 | 신규 | P1, 라인 내 물류 순서(`sequence_no`) 오름차순으로 부여 |
| `EG-` | EquipmentGroup | `EG-0001` | 4 | 신규 | P1 수동 |
| `ET-` | EquipmentType | `ET-0001` | 4 | 신규 | P1 수동. 기존 `equipment` enum(HPU/GR/RT/CV/COMMON)과 1:1 매핑 필드 보유 |
| `EQ-` | Equipment | `EQ-0001` | 4 | 신규 | P1 수동. 현장 표기는 별도 `code`(예: `HPU-01`) |
| `CP-` | Component | `CP-0001` | 4 | 신규 | P1 수동 |
| `REL-` | Relation | `REL-0001` | 4 | 신규 | P1.5, `from_id`+`to_id`+`relation_type` 정렬 후 순차 |
| `CTX-` | OperatingContextSnapshot | `CTX-0001` | 4 | 신규 | P3, 사건 생성 시 1:1 동시 생성 |
| `EV-` | Event | `EV-0031` | 4 | **기존 유지** | P3. 기존 형식 그대로 |
| `OB-` | Observation | `OB-0001` | 4 | 신규 | P3, 사건별 3건 이상 |
| `EL-` | EventEquipmentLink | `EL-0001` | 4 | 신규 | P3 |
| `AC-` | ActionCandidate | `AC-0001` | 4 | 신규 | P3 |
| `AX-` | ActionExecuted | `AX-0001` | 4 | 신규 | P3 |
| `OC-` | Outcome | `OC-0001` | 4 | 신규 | P3 |
| `RC-` | RecurrenceCheck | `RC-0001` | 4 | 신규 | P3 |
| `K-` | KnowledgeCard | `K-0001` | 4 | **기존 유지** | P3. 기존 형식 그대로 |
| `MD-` | ManualDocument | `MD-0001` | 4 | 신규 | P1.5 |
| `MS-` | ManualSection | `MS-0001` | 4 | 신규 | P1.5. 절 번호는 별도 `section_no`(예: `4.2.1`) |
| `RV-` | RevisionProposal | `RV-0001` | 4 | 신규 | P3.5 |
| `AP-` | Approval | `AP-0001` | 4 | 신규 | P3.5 |
| `PB-` | PublishRecord | `PB-0001` | 4 | 신규 | P3.5 |
| `HO-` | HandoverRecord | `HO-0001` | 4 | 신규 | P3 |
| `PT-` | EventPrototype (원형 사건) | `PT-0001` | 4 | 신규 | P2.5. **B9 그룹 분할의 기준 키** |
| `AU-` | AuditLog | `AU-000001` | 6 | 신규 | 런타임 자동 증가(대량이므로 6자리) |
| `V-` | Persona | `V-01` | 2 | **기존 유지** | 기존 2자리 유지(V-01~V-03) |
| `R-` | Reviewer 코드 | `R-01` | 2 | **기존 유지** | 4.11 `human_review.reviewer` 규칙 유지 |
| `EVQ-` | EvalItem(평가 문항) | `EVQ-0001` | 4 | 신규 | P6. 사건 ID와 구분하기 위해 별도 접두어 |
| `DS-` | DatasetVersion | `DS-v1.0` | — | 신규 | 버전 문자열 그대로(`data-v1.0-sealed` 태그와 대응) |

**충돌 방지 규칙** `[신규 제안]`
1. ID 발급은 코드가 담당한다(사용자 요구 판단 원칙 "ID 검사는 코드"). LLM은 ID를 **생성하지 않고**, 프롬프트에 주어진 ID만 인용한다. LLM 출력의 새 ID 문자열은 파서에서 폐기한다.
2. 각 접두어별 `id_counter` 테이블(`prefix`, `last_seq`)을 SQLite에 두고 트랜잭션 내 증가. 재실행 시 같은 `--seed`·같은 입력이면 같은 순서로 부여되어 결정적이다(B7-5).
3. `EV-`와 `EVQ-`는 앞 3글자가 겹치므로 정규식은 `^EV-\d{4}$` / `^EVQ-\d{4}$`로 **끝 고정** 검사한다(검사 QC-ID-03).
4. 재생성 시 기존 ID를 재사용하지 않는다. 폐기 레코드도 ID를 회수하지 않는다(기존 "폐기 레코드도 원장에서 지우지 않는다" 원칙과 동일).
5. 표시용 `code`(예: `HPU-01`, `4.2.1`)는 ID가 아니다. FK로 쓰지 않는다.

### 참조 무결성 규칙표

`[신규 제안]` 위반은 전부 `rejected_rule`(P5 규칙 단계)로 처리한다. 기존 "참조 무결성 100%"(4.7.5) 합격 기준을 확장 적용한다.

| FK | 보유 엔티티 | 가리키는 곳 | 필수 | 위반 시 잡는 검사 |
| --- | --- | --- | --- | --- |
| `line_id` | ProcessSegment, Event, ManualDocument, OperatingContextSnapshot | ProductionLine.line_id | 예 | QC-REF-01 |
| `segment_id` | EquipmentGroup, Equipment | ProcessSegment.segment_id | 예 | QC-REF-01 |
| `equipment_group_id` | Equipment | EquipmentGroup.equipment_group_id | 예 | QC-REF-01 |
| `equipment_type_id` | Equipment | EquipmentType.equipment_type_id | 예 | QC-REF-01 |
| `equipment_id` | Component, Observation, EventEquipmentLink, ActionCandidate, ActionExecuted | Equipment.equipment_id | 예 | QC-REF-01 |
| `component_id` | Observation, KnowledgeCard.component_ref | Component.component_id | 아니오 | QC-REF-02 |
| `from_id` / `to_id` | Relation | Equipment 또는 ProcessSegment 또는 ProductionLine (`from_kind`/`to_kind`로 구분) | 예 | QC-REL-01 (다형 FK 검사) |
| `context_id` | Event | OperatingContextSnapshot.context_id | 예 | QC-REF-01 |
| `event_id` | Observation, EventEquipmentLink, ActionCandidate, ActionExecuted, Outcome, RecurrenceCheck, HandoverRecord, Artifact, RevisionProposal.basis_event_ids[] | Event.event_id | 예 | QC-REF-01 |
| `prototype_id` | Event | EventPrototype.prototype_id | 예 | QC-LEAK-01 (분할 그룹 검사의 기준) |
| `observation_ids[]` | ActionCandidate.supporting_observation_ids | Observation.observation_id | 예 | QC-CAUSE-01 |
| `action_candidate_id` | ActionExecuted | ActionCandidate.action_candidate_id | 아니오(제안 없이 실행한 경우 null) | QC-ACT-01 |
| `action_executed_id` | Outcome | ActionExecuted.action_executed_id | 예 | QC-ACT-02 |
| `outcome_id` | RecurrenceCheck | Outcome.outcome_id | 예 | QC-REC-01 |
| `card_ids[]` | Artifact, ActionCandidate.basis_card_ids, RevisionProposal.basis_card_ids | KnowledgeCard.card_id | 예 | QC-REF-01 |
| `cards_expected[]` | Event | KnowledgeCard.card_id | 예 | QC-REF-01 + QC-LEAK-03 |
| `manual_section_ids[]` | ActionCandidate.basis_section_ids, RevisionProposal.target_section_id, KnowledgeCard.manual_refs | ManualSection.section_id | 아니오 | QC-MAN-01 |
| `manual_document_id` | ManualSection, RevisionProposal.base_document_id | ManualDocument.document_id | 예 | QC-REF-01 |
| `base_version` | RevisionProposal | ManualDocument.version (해당 시점 존재 버전) | 예 | QC-REV-02 (기준 버전 일치) |
| `revision_id` | Approval, PublishRecord | RevisionProposal.revision_id | 예 | QC-REF-01 |
| `approval_id` | PublishRecord | Approval.approval_id | 예 | QC-PUB-01 |
| `rollback_of_publish_id` | PublishRecord | PublishRecord.publish_id | 아니오 | QC-PUB-02 |
| `persona_id` | KnowledgeCard.provenance, Artifact, HandoverRecord.author_persona_id | Persona.persona_id (V-01~V-03) | 예 | QC-REF-01 |
| `relation_ids[]` | Event.traversed_relation_ids, EvalItem.expected_relation_ids | Relation.relation_id | 아니오 | QC-REL-02 |
| `seed_ids[]` | KnowledgeCard.provenance, ManualDocument.seed_ids | seeds.yaml 항목 ID | 예 | QC-REF-03 |
| `split` | Event(결정) → Card·Artifact·Handover·Revision(상속) | `kb`/`dev`/`sealed` | 예 | QC-LEAK-02 |

### 단위·시간 규칙

`[신규 제안]` 단위는 enum으로 고정하고 값과 분리 저장한다(`value` + `unit`). 단위 문자열 자유 입력 금지.

| 계측 항목 예 | 단위 코드 | 표기 | 비고 |
| --- | --- | --- | --- |
| 유압 압력 | `bar` | bar | HPU 주 계측 |
| 유압 필터 차압 | `bar` | bar | 0.1 단위 |
| 오일·베어링 온도 | `degC` | ℃ | 소수 1자리 |
| 진동 속도(실효값) | `mm_s` | mm/s | ISO 10816 관례 참고, 수치는 `[가상 값]` |
| 모터 전류 | `A` | A | |
| 회전수 | `rpm` | rpm | |
| 라인 속도·이송 속도 | `m_min` | m/min | |
| 유량 | `L_min` | L/min | |
| 공압 압력 | `kPa` | kPa | bar와 혼용 금지 |
| 소음 | `dBA` | dB(A) | T1 감각 카드 보조 |
| 토크 | `Nm` | N·m | |
| 백분율·부하율 | `pct` | % | |
| 시간 길이 | `min` / `h` | 분 / 시간 | 관찰 기간은 `h` 기본 |
| 무단위 판정 | `none` | — | 상태·등급 |

**시간 규칙** `[신규 제안]`
1. 모든 시각 필드는 ISO 8601 + 오프셋 고정 `YYYY-MM-DDTHH:MM:SS+09:00`. 저장은 문자열 그대로 + 정렬용 epoch 정수 병행(SQLite 정렬 안정성).
2. 타임존은 `Asia/Seoul` 고정. DST 없음. UTC 변환 금지(교대조 경계 판정이 지역시 기준이기 때문).
3. 교대조 경계 `[제안값]` 3조 2교대: A조 06:00~14:00, B조 14:00~22:00, C조 22:00~06:00(익일). `shift_code` + `shift_date`(C조는 22:00 시작일 기준)로 저장한다. 경계 사건(±10분)은 `shift_boundary_flag=true`로 표시하고 인계 누락 평가에 우선 투입한다.
4. **시간 순서 제약(하드 규칙)**
   `context.captured_at ≤ event.occurred_at ≤ observation.observed_at ≤ action_candidate.proposed_at ≤ action_executed.executed_at ≤ outcome.recorded_at ≤ recurrence_check.checked_at`
   그리고 `handover.created_at ≥ 사건 내 최종 기록 시각`, `revision.created_at ≥ 근거 사건들의 최종 recurrence_check.checked_at`.
   동시 허용(=)은 되지만 역순은 `rejected_rule`. 검사 QC-TIME-01.
5. `observation.observed_at`은 사건별로 서로 달라야 한다(최소 1분 간격) — 동일 타임스탬프 3건은 "관측 3건 이상" 요건의 형식적 충족에 해당하므로 QC-TIME-02에서 거른다.
6. 관찰 기간(`observation_window_h`)은 `[제안값]` 4 / 8 / 24 / 72시간 중 하나. `outcome.recorded_at + observation_window_h ≤ recurrence_check.checked_at`을 만족해야 `recurrence_status`를 `no_recurrence`로 둘 수 있다. 만족하지 않으면 `observing`(관찰 중)으로만 둔다 — 사용자 요구 "결과 미확인·관찰 중은 성공 집계 안 함"의 구조적 장치.

## B1-1. 기준정보 엔티티 (사용자 요구 묶음 1)

### ProductionLine `[신규]`

| 필드명 | 의미 | 자료형 | 단위 | 필수 | 허용값(enum) | 기본값 | 출처 | 상태 | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `line_id` | 라인 ID | str | — | 예 | `^LN-\d{4}$` | — | 코드계산 | 신규 | |
| `code` | 현장 표기 | str | — | 예 | — | — | seed | 신규 | `L1` — 기존 라인명 L1 유지 |
| `name` | 라인명 | str | — | 예 | — | — | seed | 신규 | 가상 냉연 코일 처리 라인 |
| `plant_code` | 공장 코드 | str | — | 예 | — | `PL-A` | seed | 신규 | 공장 계층은 단일 값으로만 둔다(MVP) |
| `scope_note` | 범위 주석 | str | — | 예 | — | — | 사용자입력 | 신규 | `[기존 수정안]` 전문가1 D-32(보조설비 구간 표기·공정 본체 제외)를 여기에 기록. D-34/D-32는 승인 대기 |
| `nominal_speed_range` | 정격 라인 속도 범위 | obj{min,max,unit} | m/min | 예 | — | — | seed | 신규 | 전부 `[가상 값]` |
| `product_codes[]` | 생산 품목 코드 | list[str] | — | 예 | — | — | seed | 신규 | `[제안값]` 2~3종 |
| `is_synthetic` | 합성 표시 | bool | — | 예 | true | true | 코드계산 | 신규 | 사용자 요구 "합성 여부 표시" |

### ProcessSegment `[신규]`

| 필드명 | 의미 | 자료형 | 단위 | 필수 | 허용값 | 기본값 | 출처 | 상태 | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `segment_id` | 구간 ID | str | — | 예 | `^SG-\d{4}$` | — | 코드계산 | 신규 | |
| `line_id` | 소속 라인 | str | — | 예 | FK | — | 코드계산 | 신규 | |
| `code` | 현장 표기 | str | — | 예 | — | — | seed | 신규 | `ENTRY`,`CENTER`,`EXIT`,`UTIL` |
| `name` | 구간명 | str | — | 예 | — | — | seed | 신규 | |
| `sequence_no` | 물류 순서 | int | — | 예 | 1~99 | — | seed | 신규 | 유틸리티 구간은 `99`(물류 순서 없음) |
| `segment_kind` | 구간 성격 | enum | — | 예 | `material` / `utility` | `material` | seed | 신규 | 상·하류 판정에 사용 |
| `is_synthetic` | 합성 표시 | bool | — | 예 | true | true | 코드계산 | 신규 | |

### EquipmentGroup `[신규]` / EquipmentType `[신규]`

| 필드명 | 의미 | 자료형 | 필수 | 허용값 | 출처 | 상태 | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `equipment_group_id` | 설비군 ID | str | 예 | `^EG-\d{4}$` | 코드계산 | 신규 | |
| `segment_id` | 소속 구간 | str | 예 | FK | 코드계산 | 신규 | |
| `code` / `name` | 표기 / 이름 | str | 예 | — | seed | 신규 | 예 `EG-DRIVE` 구동 설비군 |
| `group_kind` | 설비군 성격 | enum | 예 | `transport`/`drive`/`hydraulic`/`electric`/`pneumatic`/`cooling` | seed | 신규 | |
| `equipment_type_id` | 장비 유형 ID | str | 예 | `^ET-\d{4}$` | 코드계산 | 신규 | |
| `type_code` | 유형 코드 | enum | 예 | **`HPU`/`GR`/`RT`/`CV`/`PDP`/`CAU`/`COMMON`** | seed | **확장** | `[기존]` HPU/GR/RT/CV/COMMON 보존 + `[신규 제안]` PDP(전력 배전반)·CAU(공압 유닛) 추가. K-01의 `equipment` enum과 매핑 규칙은 B1-5 참조 |
| `model_name` | 모델명 | str | 예 | — | seed | 신규 | 전부 가상 모델명. 제조사 실제 모델명 사용 금지 |
| `manufacturer_label` | 제조사 표기 | str | 예 | `가상-A`~`가상-C` | seed | 신규 | 실제 제조사명 금지(시드 라이선스 원칙) |
| `spec_ref_seed_ids[]` | 구조 참고 시드 | list[str] | 예 | FK(seeds) | seed | 신규 | 원문 미복제 확인용 |

### Equipment `[신규]`

| 필드명 | 의미 | 자료형 | 단위 | 필수 | 허용값 | 기본값 | 출처 | 상태 | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `equipment_id` | 장비 ID | str | — | 예 | `^EQ-\d{4}$` | — | 코드계산 | 신규 | |
| `code` | 현장 표기 | str | — | 예 | `^[A-Z]{2,3}-\d{2}$` | — | seed | 신규 | `HPU-01`,`RT-02` — 표시용, FK 아님 |
| `equipment_type_id` | 유형 | str | — | 예 | FK | — | 코드계산 | 신규 | |
| `equipment_group_id` | 설비군 | str | — | 예 | FK | — | 코드계산 | 신규 | |
| `segment_id` | 구간 | str | — | 예 | FK | — | 코드계산 | 신규 | 유틸리티 장비는 `SG`(UTIL) |
| `location_text` | 위치 서술 | str | — | 예 | — | — | seed | 신규 | 예 "입측 조작반 좌측 5 m" |
| `location_marker` | 마커 정보 | str | — | 아니오 | — | null | seed | 신규 | 사용자 요구 "마커 정보". MVP는 문자열 라벨만(AR·좌표 아님) |
| `status` | 장비 상태 | enum | — | 예 | `in_service`/`standby`/`under_maintenance`/`isolated_loto`/`out_of_service` | `in_service` | seed | 신규 | 컨텍스트 일관성 검사(QC-CTX-02)에 사용 |
| `install_date` | 설치일 | date | — | 아니오 | — | null | seed | 신규 | `[가상 값]` |
| `criticality` | 중요도 | enum | — | 예 | `A`/`B`/`C` | `B` | seed | 신규 | A=정지 시 라인 전체 정지 |
| `measurement_points[]` | 계측 항목 | list[obj] | — | 예 | 아래 | — | seed | 신규 | `signal`,`unit`,`normal_min`,`normal_max`,`alarm_low`,`alarm_high` — 전부 `[가상 값]` |
| `is_synthetic` | 합성 표시 | bool | — | 예 | true | true | 코드계산 | 신규 | |

`[기존]` 설비 사전 규모(4.7.7) "4 설비 × 부품 6~10개, 계측 항목 20개 이상, 금기 10개 이상"은 유지한다. `[신규 제안]` 장비 대수는 유형 4종을 유지한 채 개별 장비 10대로 확장한다(사용자 제안 6~10대 상한). 근거는 B2-3.

### Component `[신규]`

| 필드명 | 의미 | 자료형 | 필수 | 허용값 | 출처 | 상태 | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `component_id` | 부품 ID | str | 예 | `^CP-\d{4}$` | 코드계산 | 신규 | |
| `equipment_id` | 소속 장비 | str | 예 | FK | 코드계산 | 신규 | |
| `code` / `name` | 표기 / 이름 | str | 예 | — | seed | 신규 | `[기존]` K-01 `component` 값과 문자열 일치해야 함(QC-REF-02) |
| `component_kind` | 부품 성격 | enum | 예 | `pump`/`valve`/`filter`/`bearing`/`gearbox`/`motor`/`roller`/`belt`/`sensor`/`coupling`/`accumulator`/`hose` | seed | 신규 | ISO 15243(베어링)·시드 분류 체계의 **용어만** 참고 |
| `failure_modes[]` | 고장 유형 후보 | list[str] | 예 | — | seed | 신규 | 시드 분류 체계 용어만. 원문 표 복제 금지 |
| `measurement_points[]` | 부품 계측 항목 | list[obj] | 아니오 | Equipment와 동일 구조 | seed | 신규 | |

## B1-2. 관계 엔티티 (사용자 요구 묶음 2) — 상세는 B2

### Relation `[신규]`

| 필드명 | 의미 | 자료형 | 단위 | 필수 | 허용값 | 기본값 | 출처 | 상태 | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `relation_id` | 관계 ID | str | — | 예 | `^REL-\d{4}$` | — | 코드계산 | 신규 | |
| `from_kind` / `to_kind` | 양단 종류 | enum | — | 예 | `equipment`/`segment`/`line` | `equipment` | seed | 신규 | 다형 FK. 검사 QC-REL-01 |
| `from_id` / `to_id` | 양단 ID | str | — | 예 | FK | — | seed | 신규 | |
| `relation_type` | 관계 유형 | enum | — | 예 | `material_flow`/`drive`/`hydraulic_supply`/`power_supply`/`pneumatic_supply`/`cooling_supply`/`interlock`/`common_mode`/`co_occurrence` | — | seed | 신규 | 9종. B2-1 |
| `direction` | 방향성 | enum | — | 예 | `directed`/`bidirectional` | `directed` | seed | 신규 | `co_occurrence`만 `bidirectional` 허용 |
| `causality` | 인과 구분 | enum | — | 예 | `causal`/`co_occurrence`/`unknown` | — | seed | 신규 | **사용자 판단 원칙**: `co_occurrence`는 원인 확정 근거로 쓸 수 없다(QC-CAUSE-02) |
| `evidence_strength` | 인과 강도 | enum | — | 예 | `high`/`medium`/`low` | `medium` | seed | 신규 | 설계상의 구조적 강도. 통계 추정치가 아님 |
| `transfer_medium` | 전달 매체 | enum | — | 아니오 | `material`/`torque`/`oil`/`electric`/`air`/`water`/`signal`/`none` | `none` | seed | 신규 | |
| `lag_seconds` | 전파 지연 | int | s | 아니오 | 0~3600 | null | seed | 신규 | `[가상 값]`. 시간 순서 타당성 검사(QC-CAUSE-03)에 사용 |
| `capacity` | 용량·처리율 | obj{value,unit} | 다양 | 아니오 | — | null | seed | 신규 | 물류 관계의 병목 판정용 |
| `valid_from` / `valid_to` | 유효기간 | datetime | — | 예 / 아니오 | ISO8601 | `valid_to`=null | seed | 신규 | 사건 시각에 유효한 관계만 탐색(QC-REL-03) |
| `note` | 설명 | str | — | 예 | — | — | seed | 신규 | 왜 이 관계가 존재하는지 1문장 |
| `is_synthetic` | 합성 표시 | bool | — | 예 | true | true | 코드계산 | 신규 | |

## B1-3. 운전 컨텍스트 (사용자 요구 묶음 3)

### OperatingContextSnapshot `[신규]`

| 필드명 | 의미 | 자료형 | 단위 | 필수 | 허용값 | 기본값 | 출처 | 상태 | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `context_id` | 스냅샷 ID | str | — | 예 | `^CTX-\d{4}$` | — | 코드계산 | 신규 | |
| `line_id` | 라인 | str | — | 예 | FK | — | 코드계산 | 신규 | |
| `captured_at` | 스냅샷 시각 | datetime | — | 예 | ISO8601+09:00 | — | 생성 | 신규 | 사건 시각 이전·동시 |
| `op_mode` | 운전 모드 | enum | — | 예 | `running_normal`/`running_reduced`/`idle`/`stopped_planned`/`stopped_fault`/`restarting`/`maintenance_loto` | — | 생성 | 신규 | 7종 |
| `line_speed` | 라인 속도 | float\|null | m/min | 조건부 | ≥0 | — | 생성 | 신규 | **정지 모드에서는 null 또는 0만 허용** — QC-CTX-01 |
| `product_code` | 생산 품목 | str\|null | — | 조건부 | ProductionLine.product_codes | — | 생성 | 신규 | 정지 중 null 허용 |
| `segment_states[]` | 구간별 상태 | list[obj{segment_id,state}] | — | 예 | `state`∈`running`/`blocked`/`starved`/`stopped` | — | 생성 | 신규 | 하류 정체 시나리오의 핵심 필드 |
| `shift_code` | 교대조 | enum | — | 예 | `A`/`B`/`C` | — | 코드계산 | 신규 | `captured_at`에서 계산(교대 경계 규칙) |
| `shift_date` | 교대 기준일 | date | — | 예 | — | — | 코드계산 | 신규 | C조는 시작일 기준 |
| `shift_boundary_flag` | 교대 경계 여부 | bool | — | 예 | — | false | 코드계산 | 신규 | 경계 ±10분 |
| `stop_restart_state` | 정지·재가동 상태 | enum | — | 예 | `none`/`stopping`/`stopped`/`restart_prep`/`restarting`/`restarted` | `none` | 생성 | 신규 | 전문가1 D-29(T6_setup_restart)와 연결 — D-29는 승인 대기 |
| `active_alarms[]` | 활성 알람 | list[obj{code,equipment_id,raised_at,severity}] | — | 예 | severity∈`info`/`warn`/`trip` | `[]` | 생성 | 신규 | 알람 코드는 `plant/L1.yaml` 사전에 존재해야 함(QC-REF-01) |
| `measurements[]` | 측정값 | list[obj{equipment_id,component_id?,signal,value,unit,taken_at}] | 다양 | 예 | 단위 enum | — | 생성 | **확장** | `[기존]` Event.`measurements{}` 를 계측 지점 단위 리스트로 확장. 기존 `measurements{}`는 호환 필드로 유지(B1-5) |
| `utility_states[]` | 유틸리티 상태 | list[obj{equipment_id,state,value?,unit?}] | 다양 | 예 | state∈`normal`/`degraded`/`lost` | — | 생성 | 신규 | 공통 유틸리티 시나리오용 |
| `is_synthetic` | 합성 표시 | bool | — | 예 | true | true | 코드계산 | 신규 | |

## B1-4. 사건·관측 (사용자 요구 묶음 4)

### Event `[기존 확장]` — 기존 9필드 전부 유지

| 필드명 | 의미 | 자료형 | 단위 | 필수 | 허용값 | 기본값 | 출처 | 상태 | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `event_id` | 사건 ID | str | — | 예 | `^EV-\d{4}$` | — | 코드계산 | **기존** | 형식 유지 |
| `scenario` | 데모 시나리오 | enum | — | 예 | `S1`/`S2`/`S3` | — | 생성 | **기존** | `[기존 수정안]` 전문가1 D-30(S4·S5)은 승인 대기이므로 enum 확장하지 않음 |
| `equipment` | 주 발생 설비 유형 | enum | — | 예 | `HPU`/`GR`/`RT`/`CV`/`COMMON` | — | 생성 | **기존(유지)** | 기존 "단일" 의미 보존. 다중 장비는 아래 `EventEquipmentLink`로 표현 |
| `timeline[]` | 사건 경과 | list[obj{at,text,kind}] | — | 예 | kind∈`context`/`observation`/`action`/`outcome`/`handover` | — | 생성 | **기존 확장** | 자유 텍스트에 `kind`·`at` 추가. 기존 서술 보존 |
| `true_cause` | 실제 원인 | str | — | 예 | — | — | 생성 | **기존** | **ground_truth. 검색·프롬프트에 절대 노출 금지(B3-4)** |
| `true_actions[]` | 실제 조치(정답) | list[str] | — | 예 | — | — | 생성 | **기존** | ground_truth |
| `measurements{}` | 측정값(호환) | obj{signal:value} | 다양 | 예 | — | — | 코드계산 | **기존(유지)** | `[기존 수정안]` 원본은 `context.measurements[]`로 이동하고 이 필드는 그 파생 요약(평탄화)으로 자동 생성. 기존 코드·정답지 호환 유지 |
| `cards_expected[]` | 기대 카드 | list[str] | — | 예 | FK(K-) | — | 생성 | **기존** | ground_truth |
| `split` | 분할 | enum | — | 예 | `kb`/`dev`/`sealed` | — | 코드계산 | **기존** | 분할은 Event에서 결정, 하위 상속(기존 규칙 유지) |
| `prototype_id` | 원형 사건 ID | str | — | 예 | `^PT-\d{4}$` | — | 코드계산 | 신규 | **B9 그룹 분할 기준** |
| `line_id` / `context_id` | 라인 / 컨텍스트 | str | — | 예 | FK | — | 코드계산 | 신규 | |
| `primary_equipment_id` | 주 발생 개별 장비 | str | — | 예 | FK(EQ-) | — | 생성 | 신규 | `equipment`(유형)와 정합해야 함(QC-REF-04) |
| `segment_ids[]` | 관련 구간 | list[str] | — | 예 | FK(SG-) | — | 코드계산 | 신규 | 관계 탐색 결과로 코드가 채움 |
| `case_type` | 사례 유형 | enum | — | 예 | B4의 12종 | — | 생성 | 신규 | scenario-catalog 키 |
| `occurred_at` / `reported_at` | 발생 / 신고 시각 | datetime | — | 예 | ISO8601 | — | 생성 | 신규 | |
| `symptom_text` | 증상 서술 | str | — | 예 | — | — | 생성 | 신규 | 작업자 관점 1~3문장 |
| `severity` | 심각도 | enum | — | 예 | `low`/`medium`/`high` | — | 생성 | 신규 | |
| `production_impact` | 생산 영향 | obj{kind,value,unit} | 다양 | 예 | kind∈`none`/`speed_down`/`short_stop`/`line_stop` | — | 생성 | 신규 | 실제 생산성 주장 금지(가상 값) |
| `quality_impact` | 품질 영향 | enum | — | 예 | `none`/`suspected`/`confirmed_defect` | `none` | 생성 | 신규 | `confirmed_defect`는 최종 품질 판정이 아니라 사건 기록값 |
| `safety_impact` | 안전 영향 | enum | — | 예 | `none`/`near_miss`/`hazard_exposed` | `none` | 생성 | 신규 | |
| `cause_confidence` | 원인 확정도 | enum | — | 예 | `undetermined`/`hypothesis`/`determined` | — | 생성 | 신규 | 근거 부족 사건은 `undetermined` — 사용자 요구 "근거 부족 시 원인 미확정" |
| `traversed_relation_ids[]` | 탐색된 관계 | list[str] | — | 아니오 | FK(REL-) | `[]` | 코드계산 | 신규 | 평가 지표 "관련 공정·장비 범위 식별"의 정답 근거 |
| `is_recurrence_of` | 재발 원사건 | str\|null | — | 아니오 | FK(EV-) | null | 생성 | 신규 | 재발 사건 체인. 같은 `prototype_id` 강제 |
| `handover_ids[]` | 인계 기록 | list[str] | — | 아니오 | FK(HO-) | `[]` | 코드계산 | 신규 | |
| `revision_candidate_ids[]` | 개정 후보 | list[str] | — | 아니오 | FK(RV-) | `[]` | 코드계산 | 신규 | **ground_truth 취급(누수 주의)** |
| `is_synthetic` | 합성 표시 | bool | — | 예 | true | true | 코드계산 | 신규 | |

### EventEquipmentLink `[신규]` — 사건↔다중 장비 (사용자 판단 원칙 1)

| 필드명 | 의미 | 자료형 | 필수 | 허용값 | 기본값 | 출처 | 상태 | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `link_id` | 링크 ID | str | 예 | `^EL-\d{4}$` | — | 코드계산 | 신규 | |
| `event_id` / `equipment_id` | 사건 / 장비 | str | 예 | FK | — | 코드계산 | 신규 | (event_id, equipment_id, role) 유일 |
| `role` | 관여 역할 | enum | 예 | `primary_occurrence`/`cause_candidate`/`affected`/`checked_no_finding`/`common_cause_candidate`/`excluded_by_condition` | — | 생성 | 신규 | 사용자 요구 묶음4의 5개 항목 + 조건 제외 |
| `via_relation_id` | 경유 관계 | str\|null | 아니오 | FK(REL-) | null | 코드계산 | 신규 | `primary_occurrence` 외에는 관계 경유 근거 권장 |
| `hop_distance` | 관계 거리 | int | 예 | 0~3 | — | 코드계산 | 신규 | 0=주 발생 장비. 상한 3(B2-4) |
| `reason_text` | 판단 근거 | str | 예 | — | — | 생성 | 신규 | `checked_no_finding`·`excluded_by_condition`은 필수 서술 |
| `evidence_observation_ids[]` | 근거 관측 | list[str] | 조건부 | FK(OB-) | `[]` | 생성 | 신규 | `cause_candidate`는 1건 이상 필수(QC-CAUSE-01) |
| `visibility` | 노출 시점 | enum | 예 | `pre_action`/`post_action`/`ground_truth` | `pre_action` | 코드계산 | 신규 | `cause_candidate`는 `pre_action`, 실제 원인 확정은 Event.`true_cause`에만 둔다 |

### Observation `[신규]`

| 필드명 | 의미 | 자료형 | 단위 | 필수 | 허용값 | 기본값 | 출처 | 상태 | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `observation_id` | 관측 ID | str | — | 예 | `^OB-\d{4}$` | — | 코드계산 | 신규 | |
| `event_id` | 사건 | str | — | 예 | FK | — | 코드계산 | 신규 | 사건당 3건 이상(사용자 요구) |
| `equipment_id` / `component_id` | 장비 / 부품 | str | — | 예 / 아니오 | FK | — | 생성 | 신규 | |
| `observed_at` | 관측 시각 | datetime | — | 예 | ISO8601 | — | 생성 | 신규 | 사건 내 유일(최소 1분 간격) |
| `obs_kind` | 관측 종류 | enum | — | 예 | `measurement`/`sensory`/`alarm`/`visual`/`state` | — | 생성 | 신규 | `sensory`는 T1 카드와 연결 |
| `signal` | 계측 항목 | str | — | 조건부 | `plant/L1.yaml`의 signal | — | 생성 | 신규 | `obs_kind=measurement`면 필수 |
| `value` / `unit` | 값 / 단위 | float / enum | 다양 | 조건부 | 단위 enum | — | 생성 | 신규 | |
| `qualitative_text` | 정성 서술 | str | — | 조건부 | — | — | 생성 | 신규 | `sensory`/`visual`이면 필수 |
| `judgment_vs_normal` | 정상 대비 판정 | enum | — | 예 | `below`/`normal`/`above`/`unknown` | — | 코드계산 | 신규 | 설비 사전의 `normal_min/max`로 **코드가** 계산. LLM 판정 금지 |
| `observer_persona_id` | 관측자 | str | — | 예 | FK(V-) | — | 생성 | 신규 | 페르소나 판단 습관 반영 |
| `is_synthetic` | 합성 표시 | bool | — | 예 | true | true | 코드계산 | 신규 | |

## B1-5. 행동·결과 (사용자 요구 묶음 5)

### ActionCandidate `[신규]` — 제안 행동

| 필드명 | 의미 | 자료형 | 필수 | 허용값 | 기본값 | 출처 | 상태 | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `action_candidate_id` | 후보 ID | str | 예 | `^AC-\d{4}$` | — | 코드계산 | 신규 | |
| `event_id` | 사건 | str | 예 | FK | — | 코드계산 | 신규 | |
| `rank` | 제시 순위 | int | 예 | 1~5 | — | 생성 | 신규 | Top-k 적합도 평가 대상 |
| `action_kind` | 행동 종류 | enum | 예 | `check`/`measure`/`clean`/`adjust`/`replace`/`stop_line`/`call_supervisor`/`loto_request`/`no_action_observe` | — | 생성 | 신규 | 설비 제어·파라미터 자동 변경 값은 없음(MVP 비범위 준수) |
| `title` / `detail` | 제목 / 내용 | str | 예 | — | — | 생성 | 신규 | |
| `target_equipment_id` | 대상 장비 | str | 예 | FK | — | 생성 | 신규 | |
| `basis_card_ids[]` | 근거 카드 | list[str] | 조건부 | FK(K-) | `[]` | 생성 | 신규 | 카드·절 중 최소 1개 필수. 없으면 `withhold_reason` 필수 |
| `basis_section_ids[]` | 근거 매뉴얼 절 | list[str] | 조건부 | FK(MS-) | `[]` | 생성 | 신규 | |
| `supporting_observation_ids[]` | 지지 관측 | list[str] | 예 | FK(OB-) | — | 생성 | 신규 | **1건 이상. 인과 타당성 검사(QC-CAUSE-01)의 입력** |
| `applied_conditions[]` | 적용 조건 | list[obj{signal,op,value,unit}] | 예 | op∈`lt`/`lte`/`gt`/`gte`/`eq`/`in` | — | 생성 | 신규 | K-01 `conditions` 구조와 동일 |
| `requires_approval` | 승인 필요 | bool | 예 | — | false | 코드계산 | 신규 | `stop_line`/`replace`/`loto_request`/`adjust` → true (규칙) |
| `approval_role` | 필요 승인 역할 | enum | 조건부 | `supervisor`/`maintenance`/`safety` | — | 코드계산 | 신규 | 4.12 역할 라벨 사용 |
| `safety_flag` | 안전 관련 | bool | 예 | — | false | 코드계산 | 신규 | 카드의 `safety_flag` 전파 |
| `withhold_reason` | 보류 이유 | enum\|null | 조건부 | `no_basis`/`condition_mismatch`/`conflicting_basis`/`safety_requires_approval`/`data_insufficient` | null | 코드계산 | 신규 | 사용자 요구 "근거 없으면 보류"의 기록 필드 |
| `visibility` | 노출 시점 | enum | 예 | `pre_action` | `pre_action` | 코드계산 | 신규 | |

### ActionExecuted `[신규]` — 실제 조치 (제안과 구분)

| 필드명 | 의미 | 자료형 | 필수 | 허용값 | 출처 | 상태 | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `action_executed_id` | 실행 ID | str | 예 | `^AX-\d{4}$` | 코드계산 | 신규 | |
| `event_id` | 사건 | str | 예 | FK | 코드계산 | 신규 | |
| `action_candidate_id` | 대응 후보 | str\|null | 아니오 | FK(AC-) | 생성 | 신규 | **null 허용** = 제안에 없던 조치를 했음(사용자 요구 "제안·실제 구분") |
| `executed_at` | 실행 시각 | datetime | 예 | ISO8601 | 생성 | 신규 | `proposed_at` 이후 |
| `executor_persona_id` | 실행자 | str | 예 | FK(V-) | 생성 | 신규 | |
| `approval_status` | 승인 여부 | enum | 예 | `not_required`/`approved`/`rejected`/`bypassed`/`pending` | 생성 | 신규 | `bypassed`는 실패·위험 사례 데이터로만 사용 |
| `approver_role` / `approved_at` | 승인자 역할 / 시각 | enum / datetime | 조건부 | — | 생성 | 신규 | |
| `action_kind` / `detail` | 실제 행동 | enum / str | 예 | AC와 동일 enum | 생성 | 신규 | |
| `deviation_reason` | 제안과 다른 이유 | str\|null | 조건부 | — | 생성 | 신규 | `action_candidate_id`=null 또는 kind 불일치 시 필수 |
| `is_temporary_fix` | 임시 복구 여부 | bool | 예 | — | 생성 | 신규 | 사용자 요구 "임시 복구" |
| `visibility` | 노출 시점 | enum | 예 | `post_action` | 코드계산 | 신규 | t시점 검색 대상 아님 |

### Outcome `[신규]` / RecurrenceCheck `[신규]`

| 필드명 | 의미 | 자료형 | 단위 | 필수 | 허용값 | 출처 | 상태 | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `outcome_id` | 결과 ID | str | — | 예 | `^OC-\d{4}$` | 코드계산 | 신규 | |
| `action_executed_id` / `event_id` | 실행 / 사건 | str | — | 예 | FK | 코드계산 | 신규 | |
| `recorded_at` | 기록 시각 | datetime | — | 예 | ISO8601 | 생성 | 신규 | |
| `immediate_result` | 즉시 결과 | enum | — | 예 | `resolved`/`improved`/`no_change`/`worsened`/`unknown` | 생성 | 신규 | |
| `observation_window_h` | 관찰 기간 | int | h | 예 | 4/8/24/72 | 생성 | 신규 | |
| `result_status` | 결과 확정 상태 | enum | — | 예 | `confirmed`/`observing`/`unconfirmed` | 코드계산 | 신규 | **`observing`·`unconfirmed`는 성공 집계 제외** (사용자 판단 원칙) |
| `post_measurements[]` | 조치 후 측정값 | list[obj] | 다양 | 예 | Observation와 동일 구조 | 생성 | 신규 | 행동-결과 정합성 검사(QC-ACT-03) 입력 |
| `visibility` | 노출 시점 | enum | — | 예 | `post_action` | 코드계산 | 신규 | |
| `recurrence_check_id` | 재발확인 ID | str | — | 예 | `^RC-\d{4}$` | 코드계산 | 신규 | |
| `outcome_id`(RC) | 대상 결과 | str | — | 예 | FK(OC-) | 코드계산 | 신규 | |
| `checked_at` | 확인 시각 | datetime | — | 예 | ISO8601 | 생성 | 신규 | `recorded_at + window` 이후 |
| `recurrence_status` | 재발 판정 | enum | — | 예 | `no_recurrence`/`recurred`/`not_checked` | 코드계산 | 신규 | 판정은 **코드**가 계산(사용자 원칙 "통계 계산은 코드") |
| `recurred_event_id` | 재발 사건 | str\|null | — | 조건부 | FK(EV-) | 코드계산 | 신규 | `recurred`면 필수, 같은 `prototype_id` |
| `visibility`(RC) | 노출 시점 | enum | — | 예 | `post_action` | 코드계산 | 신규 | |

## B1-6. 지식·문서 (사용자 요구 묶음 6)

### KnowledgeCard (K-01) `[기존 확장]` — 승인 #3의 필수 필드 전부 유지

| 필드명 | 의미 | 자료형 | 필수 | 허용값 | 기본값 | 출처 | 상태 | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `card_id` | 카드 ID | str | 예 | `^K-\d{4}$` | — | 코드계산 | **기존** | |
| `version` | 카드 버전 | str | 예 | `v\d+\.\d+` | `v1.0` | 코드계산 | **기존** | |
| `grade` | 검증 등급 | enum | 예 | `L0`/`L1`/`L2`/`L3` | `L0` | 코드계산 | **기존(승인 #3)** | MVP는 L1 상한 |
| `tacit_type` | 암묵지 유형 | enum | 예 | `T1`~`T5` | — | 생성 | **기존** | `[기존 수정안]` 전문가1 D-29 `T6_setup_restart`는 승인 대기 → enum 확장하지 않고 `scope_level`/`context_tags`로 대체 표현(아래) |
| `equipment` | 설비 유형 | enum | 예 | `HPU`/`GR`/`RT`/`CV`/`COMMON` | — | 생성 | **기존(유지)** | `[신규 제안]` PDP·CAU 장비의 카드는 `COMMON`으로 매핑하고 `equipment_ids[]`에 실제 장비를 적는다(기존 enum 불변) |
| `component` | 부품 | str | 예 | Component.name과 일치 | — | 생성 | **기존** | |
| `scenario` | 시나리오 | enum | 예 | `S1`/`S2`/`S3` | — | 생성 | **기존** | |
| `title` | 제목 | str | 예 | — | — | 생성 | **기존** | |
| `symptom` | 증상 | str | 조건부 | — | — | 생성 | **기존** | T1·T3 필수 |
| `know_how` | 노하우 | str | 예 | — | — | 생성 | **기존** | |
| `rationale` | 근거 | str | 예 | — | — | 생성 | **기존** | |
| `conditions[]` | 적용 조건 | list[obj{signal,op,value}] | 조건부 | — | `[]` | 생성 | **기존** | T2 1개 이상 |
| `exclusions[]` | 제외 조건 | list[obj] | 예 | — | `[]` | 생성 | **기존** | |
| `safety_flag` | 안전 여부 | bool | 예 | — | false | 생성 | **기존** | T5 → true |
| `safety_basis` | 안전 근거 | str | 조건부 | 지침·조문 번호 | — | 생성 | **기존** | safety_flag → 필수 |
| `conflict_group` | 상충 묶음 | str\|null | 아니오 | — | null | 코드계산 | **기존** | |
| `confidence` | 확신도 | enum | 예 | `high`/`medium`/`low` | — | 생성 | **기존** | |
| `provenance` | 계보 | obj{seed_ids[],persona_id,event_ids[],generator,generated_at} | 예 | — | — | 코드계산 | **기존** | |
| `split` | 분할 | enum | 예 | `kb`/`dev`/`sealed` | — | 코드계산 | **기존** | Event에서 상속 |
| `status` | 처리 상태 | enum | 예 | `draft`/`accepted`/`rejected_rule`/`rejected_judge`/`rejected_human`/`rejected_safety` | `draft` | 코드계산 | **기존** | |
| `scope_level` | 지식 적용 계층 | enum | 예 | `line`/`segment`/`equipment_group`/`equipment`/`component` | `equipment` | 생성 | **신규 확장** | 사용자 요구 "라인 운전 절차 / 공정별 / 장비·부품별 절차" |
| `line_id` / `segment_ids[]` / `equipment_ids[]` / `component_ids[]` | 적용 대상 | str / list[str] | 조건부 | FK | — | 생성 | **신규 확장** | `scope_level`에 맞는 것만 채움(QC-REF-05) |
| `relation_ids[]` | 전제 관계 | list[str] | 아니오 | FK(REL-) | `[]` | 생성 | **신규 확장** | "상류 HPU 압력이 정상일 때만 적용" 같은 관계 전제 |
| `context_conditions[]` | 운전 컨텍스트 조건 | list[obj{field,op,value}] | 아니오 | field∈`op_mode`/`line_speed`/`product_code`/`stop_restart_state`/`shift_code` | `[]` | 생성 | **신규 확장** | 조건 불일치 제외 판정에 사용. 재가동 상황 지식은 `stop_restart_state` 조건으로 표현(D-29 대체) |
| `manual_refs[]` | 매뉴얼 절 참조 | list[str] | 아니오 | FK(MS-) | `[]` | 생성 | **신규 확장** | 절 참조 유효성 검사 QC-MAN-01 |
| `tried_and_failed[]` | 실패한 시도 | list[str] | 아니오 | — | `[]` | 생성 | **신규 확장(조건부)** | `[기존 수정안]` 전문가1 D-29의 절반. **승인 대기 항목이므로 선택 필드로만 추가**하고 필수화·채점 반영은 하지 않는다 |
| `stop_conditions[]` | 중지 조건 | list[str] | 아니오 | — | `[]` | 생성 | **신규 확장(조건부)** | `[기존]` 미결 #16 항목. 선택 필드로 두고 필수화는 #16 결정 후 |
| `expected_result` | 예상 결과 | str\|null | 아니오 | — | null | 생성 | **신규 확장(조건부)** | 미결 #16 |
| `valid_until` | 유효기간 | date\|null | 아니오 | — | null | 생성 | **신규 확장(조건부)** | 미결 #16 |
| `verifier` | 검증자 | str\|null | 아니오 | `R-\d{2}` | null | 코드계산 | **신규 확장(조건부)** | 미결 #16. L2 승격 속성이므로 MVP에서는 값이 있어도 L2 표기 금지 |
| `is_synthetic` | 합성 표시 | bool | 예 | true | true | 코드계산 | 신규 | |

`[기존]` 검증 규칙(T5→safety_flag, safety_flag→safety_basis, T1·T3→symptom, T2→conditions≥1) 전부 유지. `[신규 제안]` 추가 규칙: `scope_level=line` 카드는 `equipment` = `COMMON`이어야 한다 / `relation_ids`가 있으면 그 관계가 사건 시각에 유효해야 한다.

### ManualDocument `[신규]` / ManualSection `[신규]`

| 필드명 | 의미 | 자료형 | 필수 | 허용값 | 기본값 | 출처 | 상태 | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `document_id` | 문서 ID | str | 예 | `^MD-\d{4}$` | — | 코드계산 | 신규 | |
| `doc_kind` | 문서 종류 | enum | 예 | `manufacturer_original`/`org_supplement`/`line_procedure`/`segment_procedure`/`equipment_procedure` | — | seed | 신규 | 사용자 요구 묶음6 |
| `is_editable` | 개정 가능 | bool | 예 | — | — | 코드계산 | 신규 | **`manufacturer_original` → 항상 false** (사용자 원칙 "제조사 원문 직접 수정 금지"). QC-REV-01 |
| `title` / `version` | 제목 / 버전 | str | 예 | `v\d+\.\d+` | `v1.0` | seed | 신규 | |
| `line_id` / `segment_ids[]` / `equipment_type_ids[]` | 적용 범위 | str / list | 조건부 | FK | — | seed | 신규 | |
| `seed_ids[]` | 구조 참고 시드 | list[str] | 예 | FK(seeds) | — | seed | 신규 | **원문 미복제 확인용**. 제조사 원문은 "존재한다"는 메타만 두고 본문은 가상 요약 |
| `content_sha256` | 내용 해시 | str | 예 | 64 hex | — | 코드계산 | 신규 | 사용자 요구 묶음7 "내용 해시" |
| `status` | 문서 상태 | enum | 예 | `active`/`superseded`/`draft` | `active` | 코드계산 | 신규 | |
| `is_synthetic` | 합성 표시 | bool | 예 | true | true | 코드계산 | 신규 | 제조사 원문도 **가상 대체본**임을 명기 |
| `section_id` | 절 ID | str | 예 | `^MS-\d{4}$` | — | 코드계산 | 신규 | |
| `document_id`(MS) | 소속 문서 | str | 예 | FK | — | 코드계산 | 신규 | |
| `section_no` | 절 번호 | str | 예 | `^\d+(\.\d+)*$` | — | seed | 신규 | 표시용. FK 아님 |
| `heading` / `body` | 제목 / 본문 | str | 예 | — | — | 생성 | 신규 | 본문은 가상 서술 |
| `applies_conditions[]` / `excludes_conditions[]` | 적용·제외 조건 | list[obj] | 예 | K-01 conditions 구조 | `[]` | 생성 | 신규 | |
| `scope_level`(MS) | 절 적용 계층 | enum | 예 | K-01과 동일 | — | 생성 | 신규 | |
| `safety_flag`(MS) | 안전 절 | bool | 예 | — | false | 생성 | 신규 | true면 `safety_basis` 필수 |
| `version`(MS) | 절 버전 | str | 예 | — | `v1.0` | 코드계산 | 신규 | 사용자 요구 "문서 및 절 버전" — 절 단위 버전 별도 관리 |
| `content_sha256`(MS) | 절 해시 | str | 예 | 64 hex | — | 코드계산 | 신규 | 개정 충돌 차단용 |

## B1-7. 개정·승인·인계 (사용자 요구 묶음 7)

### RevisionProposal `[신규]`

| 필드명 | 의미 | 자료형 | 필수 | 허용값 | 기본값 | 출처 | 상태 | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `revision_id` | 개정 ID | str | 예 | `^RV-\d{4}$` | — | 코드계산 | 신규 | |
| `base_document_id` / `base_version` | 기준 문서·버전 | str | 예 | FK / 존재 버전 | — | 코드계산 | 신규 | 기준 버전 불일치 시 차단(QC-REV-02) |
| `target_section_id` / `base_section_sha256` | 대상 절 / 절 해시 | str | 예 | FK / 64 hex | — | 코드계산 | 신규 | 해시 불일치 = 그 사이 절이 바뀜 → 차단 |
| `change_kind` | 변경 종류 | enum | 예 | `add`/`modify`/`add_condition`/`add_exclusion`/`add_warning`/`reorder_steps` | — | 생성 | 신규 | `delete`는 MVP 비허용 |
| `before_text` / `after_text` | 변경 전·후 | str | 예 | — | — | 생성 | 신규 | before는 코드가 원문에서 추출(LLM 재작성 금지) |
| `reason_text` | 수정 이유 | str | 예 | — | — | 생성 | 신규 | LLM 초안 허용(사용자 원칙: 개정안 초안은 LLM) |
| `basis_event_ids[]` | 근거 사건 | list[str] | 예 | FK(EV-) | — | 코드계산 | 신규 | **2건 이상**(반복성 요건) `[제안값]`. QC-REV-03 |
| `basis_card_ids[]` | 근거 카드 | list[str] | 예 | FK(K-) | — | 코드계산 | 신규 | 1건 이상 |
| `basis_recurrence_ids[]` | 근거 재발확인 | list[str] | 조건부 | FK(RC-) | `[]` | 코드계산 | 신규 | 재발 근거 개정이면 필수 |
| `apply_scope` | 적용 범위 | obj{scope_level,ids[]} | 예 | — | — | 생성 | 신규 | |
| `affected_segment_ids[]` / `affected_equipment_ids[]` | 영향 공정·장비 | list[str] | 예 | FK | — | 코드계산 | 신규 | 관계 탐색으로 코드가 계산 |
| `verification_needed[]` | 검증 필요사항 | list[str] | 예 | — | — | 생성 | 신규 | |
| `risk_level` | 위험도 | enum | 예 | `low`/`medium`/`high` | — | 코드계산 | 신규 | 안전 절 개정은 항상 `high` |
| `state` | 개정 상태 | enum | 예 | `draft`/`submitted`/`under_review`/`approved`/`rejected`/`published`/`rolled_back` | `draft` | 코드계산 | 신규 | 상태 전이는 코드(전문가C 상태 머신과 연결) |
| `content_sha256` | 개정안 해시 | str | 예 | 64 hex | — | 코드계산 | 신규 | |
| `searchable_after_publish` | 검색 반영 조건 | bool | 예 | — | false | 코드계산 | 신규 | **승인·발행 전에는 항상 false** — 지표 "승인 전 개정 검색 반영 0건"의 구조적 장치 |
| `is_synthetic` | 합성 표시 | bool | 예 | true | true | 코드계산 | 신규 | |
| `visibility` | 노출 시점 | enum | 예 | `post_action` | 코드계산 | 신규 | 사건 t시점 검색 대상 아님 |

### Approval `[신규]` / PublishRecord `[신규]`

| 필드명 | 의미 | 자료형 | 필수 | 허용값 | 출처 | 상태 | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `approval_id` | 승인 ID | str | 예 | `^AP-\d{4}$` | 코드계산 | 신규 | |
| `revision_id` | 대상 개정 | str | 예 | FK | 코드계산 | 신규 | |
| `approver_role` | 승인자 역할 | enum | 예 | `supervisor`/`maintenance`/`safety`/`sysadmin` | 생성 | 신규 | `[기존]` 4.12 "MVP에서 역할별 인증 미구현, UI 라벨로만 구분" 유지 |
| `approver_code` | 승인자 코드 | str | 예 | `^R-\d{2}$` | 생성 | 신규 | 실명 금지(4.11 규칙 준용) |
| `decision` | 판정 | enum | 예 | `approved`/`rejected`/`needs_revision` | 생성 | 신규 | |
| `reason_text` | 승인·반려 이유 | str | 예 | — | 생성 | 신규 | |
| `decided_at` | 판정 시각 | datetime | 예 | ISO8601 | 생성 | 신규 | `revision.created_at` 이후 |
| `checked_base_version` | 확인한 기준 버전 | str | 예 | — | 코드계산 | 신규 | 승인 시점 기준 버전 재확인 기록 |
| `publish_id` | 발행 ID | str | 예 | `^PB-\d{4}$` | 코드계산 | 신규 | |
| `revision_id`(PB) / `approval_id` | 개정 / 승인 | str | 예 | FK | 코드계산 | 신규 | **승인 없는 발행 불가**(QC-PUB-01) |
| `new_version` | 발행 버전 | str | 예 | `v\d+\.\d+` | 코드계산 | 신규 | 버전 증가는 코드 |
| `published_at` | 발행 시각 | datetime | 예 | ISO8601 | 코드계산 | 신규 | `decided_at` 이후 |
| `published_sha256` | 발행 내용 해시 | str | 예 | 64 hex | 코드계산 | 신규 | |
| `publish_kind` | 발행 종류 | enum | 예 | `normal`/`rollback` | 코드계산 | 신규 | |
| `rollback_of_publish_id` | 복구 대상 | str\|null | 조건부 | FK(PB-) | 코드계산 | 신규 | `rollback`이면 필수 |
| `superseded_publish_id` | 대체된 발행 | str\|null | 아니오 | FK(PB-) | 코드계산 | 신규 | 이전 버전 보존(덮어쓰기 금지) |

### HandoverRecord `[신규]`

| 필드명 | 의미 | 자료형 | 필수 | 허용값 | 기본값 | 출처 | 상태 | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `handover_id` | 인계 ID | str | 예 | `^HO-\d{4}$` | — | 코드계산 | 신규 | |
| `event_ids[]` | 관련 사건 | list[str] | 예 | FK(EV-) | — | 코드계산 | 신규 | |
| `shift_from` / `shift_to` | 인계 교대조 | enum | 예 | `A`/`B`/`C` | — | 생성 | 신규 | `[기존]` 산출물 인계 로그 필드명 유지 |
| `shift_date` / `created_at` | 기준일 / 작성 시각 | date / datetime | 예 | — | — | 코드계산 | 신규 | |
| `author_persona_id` | 작성자 | str | 예 | FK(V-) | — | 생성 | 신규 | |
| `memo_text` | 원문 메모 | str | 예 | — | — | 생성 | 신규 | F-01 입력 원문 |
| `open_items[]` | 미완료 항목 | list[obj{item_id,text,status,due_shift,basis_ids[]}] | 예 | status∈`open`/`in_progress`/`done`/`withdrawn`/`needs_recheck` | — | 생성 | 신규 | `[기존]` F-05 "자동 종료 대신 재검토 표시" → `needs_recheck` |
| `linked_action_executed_ids[]` | 연결된 조치 | list[str] | 아니오 | FK(AX-) | `[]` | 코드계산 | 신규 | 오연결 평가 대상 |
| `expected_open_items[]` | 정답 미완료 항목 | list[str] | 예 | — | — | 생성 | 신규 | **ground_truth**. 인계 누락·오연결 채점용 |
| `is_synthetic` | 합성 표시 | bool | 예 | true | true | 코드계산 | 신규 | |

### AuditLog `[신규, 런타임]` / EventPrototype `[신규]` / DatasetVersion·SplitAssignment `[기존 확장]`

| 필드명 | 의미 | 자료형 | 필수 | 허용값 | 출처 | 상태 | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `audit_id` | 감사 ID | str | 예 | `^AU-\d{6}$` | 코드계산 | 신규 | `[기존]` 4.12 감사 로그 항목을 스키마화 |
| `occurred_at`/`user_label`/`device`/`tool_name`/`tool_args`/`retrieved_ids[]`/`model_version`/`result_summary`/`approver_code` | 4.12 지정 항목 | 다양 | 예 | — | 코드계산 | 신규 | 기존 문장을 필드로 고정한 것이며 내용 변경 아님 |
| `as_of` | 조회 기준 시각 | datetime | 예 | ISO8601 | 코드계산 | 신규 | **미래 누수 검사의 증거**(B3-4) |
| `prototype_id` | 원형 ID | str | 예 | `^PT-\d{4}$` | 코드계산 | 신규 | |
| `pattern_name` | 원형 이름 | str | 예 | — | seed | 신규 | 예 "상류 구동 이상의 하류 증상화" |
| `case_type`(PT) | 사례 유형 | enum | 예 | B4 12종 | seed | 신규 | |
| `root_equipment_type` / `relation_path_types[]` | 원인 유형 / 관계 경로 | enum / list | 예 | — | seed | 신규 | **두 원형이 같은 (case_type, root_equipment_type, relation_path_types) 조합이면 하나로 합친다** — 분할 누수 방지 |
| `derived_event_count` | 파생 사건 수 | int | 예 | ≥1 | 코드계산 | 신규 | |
| `assigned_split` | 원형 단위 분할 | enum | 예 | `kb`/`dev`/`sealed` | 코드계산 | 신규 | **분할은 원형에서 결정, 사건이 상속** — `[기존 수정안]` B9-1 |
| `version`(DS) | 데이터셋 버전 | str | 예 | `DS-v\d+\.\d+` | 코드계산 | **기존 확장** | 4.11 `dataset_version` 테이블과 동일 |
| `split`/`record_count`/`manifest_sha256`/`sealed_at`/`sealed_by` | 기존 컬럼 | 다양 | 예 | — | 코드계산 | **기존** | 변경 없음 |
| `entity_counts{}` | 엔티티별 건수 | obj | 예 | — | 코드계산 | 신규 | 신규 엔티티 13종 건수 추가 |
| `split_rule_version` | 분할 규칙 버전 | str | 예 | — | 코드계산 | 신규 | 분할 규칙이 바뀌면 재분할 이력을 남긴다 |

---

# B2. 생산시스템 관계 모델의 데이터 표현

`[기존]` 전제 유지: 그래프 DB 도입하지 않음. SQLite 관계 테이블 + JSONL 원본(4.5·4.11, 사용자 권장 기술 구조와 일치).

## B2-1. relation_type enum 정의표 `[신규 제안]`

| relation_type | 의미 | 방향 | 기본 causality | transfer_medium | lag_seconds `[제안값]` | 탐색 시 쓰임 |
| --- | --- | --- | --- | --- | --- | --- |
| `material_flow` | 소재가 A→B로 전달 | directed | causal | material | 5~60 | 상류·하류 판정의 기준. 역방향 탐색 = "상류 의심" |
| `drive` | A가 B를 구동 | directed | causal | torque | 0~2 | 구동 이상 → 이송 증상 |
| `hydraulic_supply` | A가 B에 유압 공급 | directed | causal | oil | 1~10 | 공통 유틸리티 시나리오 |
| `power_supply` | A가 B에 전력 공급 | directed | causal | electric | 0~1 | 동시 다발 이상 |
| `pneumatic_supply` | A가 B에 공압 공급 | directed | causal | air | 1~5 | |
| `cooling_supply` | A가 B에 냉각 공급 | directed | causal | water | 60~600 | 온도 상승은 지연이 길다 |
| `interlock` | A의 상태가 B의 운전을 구속 | directed | causal | signal | 0~3 | **하류 정체가 전단 이상처럼 보이는 경로** |
| `common_mode` | A와 B가 같은 운전 모드·조건을 공유 | directed | causal | signal | 0 | 라인 전체 모드 변화 |
| `co_occurrence` | 함께 이상이 나타나는 경향만 관측됨 | bidirectional | **co_occurrence** | none | null | **원인 확정 근거로 사용 금지**. 후속 확인 질문 생성에만 사용 |

## B2-2. 인과 vs 동시 발생 구분 (사용자 판단 원칙) `[신규 제안]`

1. `Relation.causality`가 `co_occurrence`인 관계는 `EventEquipmentLink.role`에 `cause_candidate`를 부여할 수 없다. `common_cause_candidate`까지만 허용한다. 위반 시 QC-CAUSE-02 → `rejected_rule`.
2. `cause_candidate`로 올리려면 다음 3조건을 모두 만족해야 한다.
   (a) `causality=causal`인 관계 경로가 존재한다.
   (b) 원인 후보 장비의 관측값 중 최소 1건이 `judgment_vs_normal ∈ {below, above}`다(관측이 원인 후보를 **지지**).
   (c) 시간 순서가 관계의 `lag_seconds`와 모순되지 않는다(원인 관측 시각 ≤ 결과 관측 시각, 차이가 `lag_seconds`의 0.5~20배 범위 `[제안값]`).
   → 검사 QC-CAUSE-01(b) / QC-CAUSE-03(c).
3. 조건 (b)를 만족하지 못하면 `Event.cause_confidence`는 `undetermined`로 강제하고 `ActionCandidate`는 `check`/`measure` 종류만 생성한다. 이것이 사용자 요구 "압력이 정상인데 유압 원인 확정 금지"의 구조적 구현이다(B3-3).
4. `Relation.evidence_strength`는 **설계상의 구조적 강도**이며 데이터에서 추정한 통계량이 아니다. 발표·문서에서 확률·기여도로 표현하지 않는다.

## B2-3. 관계 개수 제안값과 근거 `[신규 제안]`

장비 10대(유형 4종 유지 + PDP·CAU 추가) 구성에서 각 관계 유형의 최소 필요 개수를 시나리오 요건에서 역산했다.

| 유형 | 개수 | 산출 근거 |
| --- | --- | --- |
| `material_flow` | 4 | 물류 경로 RT-01→RT-02→RT-03→CV-01 (3) + 스크랩 분기 RT-03→CV-02 (1) |
| `drive` | 4 | GR-01이 RT-01·RT-02, GR-02가 RT-03·CV-01 구동 |
| `hydraulic_supply` | 4 | HPU-01 → RT 3대 + CV-01 텐셔너 |
| `power_supply` | 3 | PDP-01 → GR-01, GR-02, HPU-01 |
| `pneumatic_supply` | 1 | CAU-01 → CV-01 디버터 |
| `interlock` | 2 | CV-01→RT-03(정체 시 감속), CV-02→RT-03(스크랩 만적) |
| `common_mode` | 1 | HPU-01 압력 저하 → 라인 LN-0001 저속 모드 |
| `co_occurrence` | 1 | RT-02 ↔ RT-03(동일 유압 분기 공유로 함께 증상, 인과 아님) |
| **핵심 소계** | **20** | 사용자 제안 "핵심 관계 10~20개"의 상한 |
| `cooling_supply` (선택) | 1 | 냉각은 HPU-01의 부품(CP)으로 표현하면 0. 별도 장비로 두면 1 |

- **`[신규 제안]` 결론: 핵심 관계 18건을 필수, 2건(`co_occurrence` 1 + `cooling_supply` 1)을 선택으로 두어 총 18~20건.** 3개 필수 시나리오를 모두 성립시키는 최소 집합이며, 이보다 줄이면 "하류 정체가 전단 이상처럼 보이는" 경로(`interlock`)나 "여러 장비 동시 영향"(`hydraulic_supply` 4건)이 성립하지 않는다.
- 관계 1건당 검수 `[제안값]` 3분 → 20건 = 1.0시간. B5의 공수 계산에 포함했다.

## B2-4. N-hop 탐색 설계 (SQLite 재귀 CTE) `[신규 제안]`

- 저장: 단일 `relation` 테이블. 인덱스 `(from_kind, from_id, relation_type, valid_from)`, `(to_kind, to_id, relation_type, valid_from)`.
- 탐색 방향은 목적에 따라 다르다.
  - **상류 의심** = `material_flow`·`drive`·`*_supply`의 **역방향**(to → from) 탐색.
  - **하류 영향** = 같은 유형의 **정방향** 탐색.
  - **인터록 영향** = `interlock` 정방향(구속하는 쪽 → 구속받는 쪽)이므로, 하류 정체를 찾으려면 `interlock`의 역방향을 본다.
- **깊이 상한 `[제안값]` 3 hop.** 근거: 위 20건 관계 그래프에서 임의의 두 장비 간 최단 경로 최대값이 3이다(예: CAU-01 → CV-01 → RT-03 → GR-02). 4 hop 이상은 라인 전체가 후보가 되어 "범위 식별 정확도" 지표가 의미를 잃는다.
- 노드 수 상한 `[제안값]` 12(장비 10 + 라인 1 + 구간 4 중 관련 4 → 상한 12로 절단). 초과 시 `hop_distance` 오름차순 + `evidence_strength` 내림차순으로 잘라낸다.
- 재귀 CTE 골격(구현은 Codex 담당, 여기서는 계약만 고정):

```sql
WITH RECURSIVE reach(node_kind, node_id, depth, path_rel_ids, min_strength) AS (
  SELECT 'equipment', :start_equipment_id, 0, '', 'high'
  UNION ALL
  SELECT r.from_kind, r.from_id, reach.depth + 1,
         reach.path_rel_ids || ',' || r.relation_id,
         MIN(reach.min_strength, r.evidence_strength)
  FROM relation r JOIN reach
    ON r.to_kind = reach.node_kind AND r.to_id = reach.node_id
  WHERE reach.depth < :max_hop            -- 상한 3
    AND r.relation_type IN (:allowed_types)
    AND r.causality = 'causal'            -- co_occurrence 는 별도 질의
    AND r.valid_from <= :as_of
    AND (r.valid_to IS NULL OR r.valid_to > :as_of)
    AND instr(reach.path_rel_ids, r.relation_id) = 0   -- 사이클 방지
)
SELECT * FROM reach WHERE depth > 0 ORDER BY depth, min_strength DESC LIMIT :node_cap;
```

- `:as_of` 파라미터 필수. 관계 유효기간을 사건 시각 기준으로 적용한다(QC-REL-03).
- 사이클 방지: 경로에 이미 쓴 `relation_id` 재사용 금지. `co_occurrence`(bidirectional)는 이 CTE에서 제외하고 별도 1-hop 질의로만 가져온다.
- `[신규 제안]` 탐색 결과는 `Event.traversed_relation_ids`·`EventEquipmentLink.hop_distance`에 저장하여 **평가 정답과 실행 결과를 같은 형식으로 비교**할 수 있게 한다.

---

# B3. 시간 흐름 재현 규칙 (scenario 생성 규칙)

사용자 요구 시간축 10단계를 생성 단계로 고정한다. 각 단계는 **직전 단계의 출력만** 입력으로 받는다(단계 간 미래 정보 차단).

## B3-1. 단계별 생성 규칙 `[신규 제안]`

| 순서 | 단계 | 입력 | 출력 | 생성 주체 | 분기·확률 `[제안값]` |
| --- | --- | --- | --- | --- | --- |
| 1 | 라인 상태 | `plant/`, 원형(PT) | `OperatingContextSnapshot` | 템플릿(코드) + 난수 | op_mode: running_normal 55 / running_reduced 20 / restarting 10 / idle 5 / stopped_fault 5 / stopped_planned 3 / maintenance_loto 2 (%) |
| 2 | 다중 장비 사건 | 1 + 관계 그래프 | `Event`, `EventEquipmentLink` | 코드가 골격, LLM이 `symptom_text` | 관여 장비 수: 1대 25 / 2대 35 / 3대 30 / 4대 이상 10 (%) |
| 3 | 관측 | 2 + 설비 사전 | `Observation` 3~6건 | 코드가 수치, LLM이 정성 서술 | obs_kind: measurement 45 / sensory 25 / alarm 15 / visual 10 / state 5 (%) |
| 4 | 행동 후보 | 3 + 카드·매뉴얼 | `ActionCandidate` 2~5건 | LLM(표현) + 코드(조건·승인 판정) | 보류 발생: 근거 부족 15 / 조건 불일치 10 / 안전 승인 대기 10 (%) |
| 5 | 실제 조치 | 4 | `ActionExecuted` 1~3건 | 코드가 선택 규칙, LLM이 서술 | 후보 1순위 채택 55 / 하위 순위 20 / 후보 외 조치 15 / 미실행(관찰) 10 (%) |
| 6 | 결과 | 5 | `Outcome` | 코드 | resolved 45 / improved 20 / no_change 15 / worsened 8 / unknown 12 (%) |
| 7 | 관찰 | 6 | `Outcome.result_status` | 코드 | confirmed 60 / observing 25 / unconfirmed 15 (%) |
| 8 | 재발 | 7 | `RecurrenceCheck` | 코드 | no_recurrence 60 / recurred 22 / not_checked 18 (%) |
| 9 | 교대 인계 | 2~8 중 **인계 시점까지만** | `HandoverRecord` | LLM(메모) + 코드(open_items 정답) | 인계 발생 비율 45 %; 그중 누락 유발 설계 30 % |
| 10 | 매뉴얼 개정 후보 | 같은 `prototype_id`의 사건 2건 이상 + 재발 | `RevisionProposal` | LLM(초안) + 코드(근거·해시·범위) | 개정 후보 생성 조건: 같은 원형 재발 2회 이상 AND 결과 `confirmed` |

- 확률 배분은 전부 `[제안값]`이며 B4의 유형별 최소 건수를 만족하도록 **층화 추출**로 보정한다(단순 난수만으로는 희소 유형이 0건이 될 수 있다).
- 결정성: 각 단계는 `hash(run_seed, prototype_id, step_no)`로 독립 난수 스트림을 만든다. 단계 하나를 재생성해도 다른 단계의 난수가 흐트러지지 않는다.

## B3-2. 분기 조건 (하드 규칙) `[신규 제안]`

1. `op_mode ∈ {stopped_planned, stopped_fault, maintenance_loto}`이면 4단계에서 `action_kind=stop_line`을 생성하지 않는다(이미 정지).
2. `op_mode = maintenance_loto`이면 모든 `ActionCandidate`는 `requires_approval=true`이고 `safety_flag=true`다(안전보건규칙 제92조·LOTO 취지).
3. `ActionExecuted.approval_status=pending`이면 `Outcome.result_status`는 `unconfirmed`만 허용한다.
4. `Outcome.immediate_result ∈ {no_change, worsened}`이면 `ActionExecuted.is_temporary_fix`는 false여야 한다(임시 복구가 악화를 뜻하지 않게).
5. `recurrence_status = recurred`인 사건 체인은 `Event.is_recurrence_of`로 연결하고 두 사건은 같은 `prototype_id`를 갖는다.
6. `RevisionProposal`은 `basis_event_ids`가 2건 이상, 그중 최소 1건의 `Outcome.result_status=confirmed`여야 생성한다. 조건 미달이면 생성하지 않는다(사용자 원칙 "AI 답변·개정안을 현장 성공 사례로 재집계 금지"의 입구 차단).

## B3-3. 물리적 모순 방지 규칙 `[신규 제안]`

| ID | 규칙 | 위반 예 |
| --- | --- | --- |
| PH-01 | 정지 상태(`stopped_*`,`maintenance_loto`)에서 `line_speed > 0` 금지 | `[기존]` 4.7.5 "정지 상태에서 압력 상승 등 불가 조합"의 확장 |
| PH-02 | 압력 계측이 정상 범위인데 `true_cause`가 유압 공급 부족 계열이면 금지 | 사용자 요구 명시 항목 |
| PH-03 | 원인 후보 장비에 이상 관측이 하나도 없으면 `cause_candidate` 부여 금지 → `checked_no_finding`으로 강등 | B2-2 조건(b) |
| PH-04 | 냉각 상실 → 온도 상승은 `lag_seconds ≥ 60`. 10초 내 급상승 서술 금지 | 열용량 상식 |
| PH-05 | `interlock`으로 정지한 하류 장비의 전류·회전수는 0 또는 감소여야 하며 증가 금지 | 하류 정체 시나리오 오류 방지 |
| PH-06 | 재가동(`restarting`) 중에는 정상 범위 판정을 하지 않는다(`judgment_vs_normal=unknown`) | 과도 상태 오판 방지 |
| PH-07 | 부품 교체(`replace`) 조치는 해당 장비 상태가 `under_maintenance` 또는 `isolated_loto`여야 한다 | 운전 중 교체 금지 |
| PH-08 | 동일 signal의 사건 내 값 변화율이 설비 사전 `max_rate_of_change`를 초과하면 금지 | `[신규 제안]` 설비 사전에 `max_rate_of_change` 필드 추가 필요 |

## B3-4. 미래 정보 누수 차단 — 구조적 장치 `[신규 제안]`

사용자 요구 "미래 결과나 평가 정답이 과거 시점의 검색과 답변에 유입되지 않도록 한다"를 **3중 구조**로 구현한다.

**(1) 필드 단위 visibility 분류 — 모든 필드에 라벨 부여**

| visibility | 대상 필드 | t시점 검색·프롬프트 노출 |
| --- | --- | --- |
| `pre_action` | 컨텍스트, 관측, 사건 증상·심각도, 행동 후보, 관계, 카드(kb), 매뉴얼(발행된 버전) | 허용 |
| `post_action` | `ActionExecuted`, `Outcome`, `RecurrenceCheck`, `RevisionProposal`, `Approval`, `PublishRecord`, `HandoverRecord`(해당 사건 이후분) | **금지** |
| `ground_truth` | `Event.true_cause`, `true_actions`, `cards_expected`, `HandoverRecord.expected_open_items`, `EvalItem.*` 정답 필드 | **금지(영구)** |

**(2) as_of 파라미터 + 뷰 분리**

- 검색 계층은 원본 테이블을 직접 읽지 않고 `v_retrieval_asof(:as_of)` 뷰만 읽는다. 뷰 정의에 `post_action` 테이블을 **조인하지 않는다**(누락이 아니라 구조적 불가능).
- 매뉴얼은 `published_at <= :as_of AND publish_kind`에 따라 그 시점의 발행 버전만 노출한다. `state != published`인 `RevisionProposal`은 뷰에 존재하지 않는다 → 지표 "승인 전 개정 검색 반영 0건"이 코드로 보장된다.
- `AuditLog.as_of`에 실제 사용한 기준 시각을 기록한다. 기록 없는 검색 호출은 테스트 실패로 처리한다.

**(3) 필드 화이트리스트 직렬화**

- LLM 프롬프트에 넣는 문서는 `SELECT *`가 아니라 **명시적 화이트리스트 함수** `to_prompt_doc(record)`로만 만든다. 함수는 허용 필드명 집합을 상수로 갖고, 집합에 없는 키는 조용히 버리지 않고 **예외를 던진다**(새 필드 추가 시 반드시 분류를 강제).

**검사 방법** `[신규 제안]`
- QC-LEAK-04(정적): `to_prompt_doc` 화이트리스트 ∩ `post_action`/`ground_truth` 필드 집합 = ∅ 을 단위 테스트로 검사.
- QC-LEAK-05(동적·카나리): `true_cause` 문장에만 등장하는 **카나리 토큰**(예: `zzk9`로 시작하는 무의미 접미사)을 사건별로 1개 삽입하고, 검색·프롬프트·응답 로그 전체를 grep 한다. 1건이라도 발견되면 누수 0건 지표 실패. 카나리 토큰은 봉인 전 제거하지 않고 유지하되, 최종 데이터 카드에 존재를 명시한다.
- QC-LEAK-06(시간): 모든 검색 호출의 `AuditLog.as_of`와 반환된 레코드의 최대 타임스탬프를 비교. 반환 레코드 시각 > as_of 이면 실패.
- QC-LEAK-07(정답지): `EvalItem`의 정답 필드가 들어 있는 파일이 `kb` 분할 경로에 존재하지 않음을 경로·해시로 확인.

---

# B4. 사례 유형 균형 설계 (scenario-catalog)

`[신규 제안]` 12유형. 목표 비율은 옵션3(B5 추천안, 사건 72건) 기준. 옵션 변경 시 비율은 유지하고 건수만 비례 조정한다.

| case_type | 정의 | 목표 비율 `[제안값]` | 최소 건수 `[제안값]` | 검증하는 지표 | 생성 난점 |
| --- | --- | --- | --- | --- | --- |
| `normal` | 이상 없음. 정상 순회·정상 재가동 | 10 % | 7 | 지식 없음 처리율, 과잉 경보 억제 | 정상인데 카드가 나오면 안 됨 → `cards_expected=[]` 처리 규칙 필요 |
| `single_equipment_fault` | 단일 장비 국소 이상 | 15 % | 11 | Recall@5, 인용 정확도 | 가장 쉬움. 과다 생성 주의 |
| `upstream_cause` | 상류 이상이 하류 증상으로 | 14 % | 10 | **관련 공정·장비 범위 식별 정확도**, 관계 탐색 효과 | 상류 관측이 "약하게" 비정상이어야 함(강하면 문제가 쉬워짐) |
| `downstream_block` | 하류 정체가 전단 이상처럼 관측 | 12 % | 9 | 범위 식별, 오적용 회피 | `interlock` + `segment_states`의 `blocked`/`starved` 정합 필요 |
| `common_utility` | 공통 유틸리티 이상이 다수 장비 동시 영향 | 12 % | 9 | 범위 식별, 공통 원인 후보 식별 | 동시 이상이 "우연 동시 발생"과 구별되게 설계해야 함 |
| `compound_fault` | 원인 2개 이상 동시 | 6 % | 4 | 원인 미확정 처리, 추가 질문 | 정답 정의가 어려움 → `cause_confidence=hypothesis` 허용 |
| `action_failed` | 조치했으나 미해결·악화 | 8 % | 6 | 결과·재발 통계 정확도, 성공 과대집계 방지 | 사용자 요구 "실패 5건 이상" 충족 |
| `recurrence` | 같은 원형이 재발 | 8 % | 6 | 재발 판정 일관성, 개정 근거 | 원형 체인 + 분할 귀속 주의(B9) |
| `outcome_unconfirmed` | 결과 미확인·관찰 중 | 8 % | 6 | 성공 집계 제외 정확도 | 사용자 요구 "미확인 5건 이상" 충족 |
| `condition_mismatch` | 유사 사례가 있으나 조건이 달라 제외해야 함 | 7 % | 5 | **조건 불일치 제외율** | 짝이 되는 kb 카드가 반드시 있어야 함(쌍 설계) |
| `conflicting_knowledge` | 페르소나 간 상충 | 5 % | 4 | 복수 의견 제시, 상충 출처 노출 | `[기존]` conflict_group 규칙 준수. 안전 상충은 보수적 쪽만 |
| `safety_withhold` | 안전상 보류가 정답 | 5 % | 4 | **안전 보류율, 안전 금기 누락 0** | T5 카드·safety_basis 필수, 100 % 사람 검수 |
| 합계 | | 110 %→정규화 100 % | 81 → 72로 조정 | | |

- `[신규 제안]` 비율 합이 100 %를 넘는 것은 **한 사건이 두 유형에 해당할 수 있기** 때문이다(예: `recurrence` AND `action_failed`). `case_type`은 주 유형 1개만 저장하고, 보조 유형은 `case_tags[]`(신규 선택 필드)에 둔다. 최소 건수는 주 유형 기준으로 센다.
- `[기존]` 규모 목표의 "실패·재발·결과 미확인 각 5건 이상"(사용자 제안)은 위 최소 건수(6/6/6)로 충족한다.
- `[기존]` 커버리지 매트릭스 요건(T1~T5 × 설비 4종, 빈칸 0)은 유지한다. `[신규 제안]` 여기에 **case_type × 관계 유형** 매트릭스를 추가하고, `upstream_cause`·`downstream_block`·`common_utility` 세 행은 빈칸 0을 요구한다.
- `normal` 유형의 채점 규칙 `[신규 제안]`: `cards_expected=[]`이고 기대 응답은 "해당 지식 없음" 또는 "정상 범위" 진술. T5 카드는 정상 사건에서도 노출될 수 있으며 이는 오류가 아니다(기존 T5 선두 노출 원칙 유지).

---

# B5. 데이터 규모 3개 옵션 비교 (핵심 결정 자료)

## B5-0. 충돌의 정확한 내용

- `[기존·승인 #5]` 사건 120(kb 70 / dev 20 / sealed 30), 카드 채택 150+ (생성 250, 채택률 60 % `[추정]`; T별 최소 20, T5 최소 25), 산출물 채택 400+, 봉인 평가셋 60(질의 36 + 인계 24, 안전 서브셋 12), 개발셋 30. 설비 사전 4설비 × 부품 6~10, 계측 20+, 금기 10+.
- `[신규 제안 — 사용자]` 사건 30~50, 카드 20~40, 개발 평가 10~15, 봉인 평가 15~20, 매뉴얼 4~7, 개정 후보 3~5, 관계 10~20, 구간 3~5, 장비 6~10대. 사용자는 "고정 요구사항이 아니라 MVP 제안값"이라고 명시했다.
- **주의(용어 혼동)**: 기존 "사건 120"과 "봉인 평가셋 60"은 다른 축이다. 사건 120 중 sealed 사건이 30건이고, 그 30건에서 평가 문항 60개를 뽑는다(사건당 2문항). 사용자 제안의 "봉인 평가 15~20"이 **문항 수**인지 **사건 수**인지가 미확정이다 → B13 Q1의 하위 질문.

## B5-1. 검수 공수 모델 (계산 과정 공개)

**단가 `[제안값]`** — 학생 4인 팀, 도메인 비전문가 검수 기준.

| 대상 | 1건당 검수 시간 | 근거 |
| --- | --- | --- |
| 일반 카드 | 4분 | 스키마·조건·근거 확인. 300자 내외 |
| T5 안전 카드 | 8분 | `safety_basis` 법령·지침 번호 대조 포함 |
| 사건 1건 | 12분 | 컨텍스트·관측 3~6건·행동·결과·재발의 정합성 확인 |
| 산출물 1건 | 2분 | 카드 파생물, 역참조 ID만 확인 |
| 평가 문항 1건(정답지 포함) | 15분 | 문항 작성 + 정답 카드 ID·조건·T5 포함 여부 결정 |
| 매뉴얼 1건(문서 + 절) | 20분 | 절 5개 내외 |
| 개정 후보 1건 | 15분 | 근거 사건 2건 이상 대조 + 기준 버전·해시 확인 |
| 관계 1건 | 3분 | 방향·인과 구분·유효기간 |

**검수 범위** — `[기존]` 4.7.5 규칙 그대로 적용: 봉인·개발 평가 문항 100 %, T5 카드 100 %, 나머지 카드 20 % 층화, 산출물 20 % 층화. `[신규 제안]` 사건은 35 % 층화(사건이 신규 엔티티 6종을 묶는 허브이므로 카드보다 높게), 관계·매뉴얼·개정 후보는 100 %(건수가 적고 전부 구조의 뼈대).

**가용 공수 `[가정]`**

| 인원 | 주당 검수 전용 | 기간 | 소계 |
| --- | --- | --- | --- |
| 전혜민(PM/QA, 검수 주담당) | 15시간 | 1.5주(1주차 후반 ~ 2주차) | 22.5시간 |
| 팀 보조(최재영 이중 검수) | 8시간 | 1.5주 | 12.0시간 |
| **합계 상한** | | | **34.5시간** |

전혜민의 주당 총 가용을 25시간 `[가정]`으로 보고, 일정·문서 정합성·시드·라이선스·봉인 절차·정답지 형식 등 나머지 PM/QA 업무에 10시간을 배분한 뒤 남는 15시간을 검수 전용으로 잡았다. 2주차 말(10/12) 봉인이므로 검수 가능 창은 실질 1.5주다.

## B5-2. 세 옵션의 구성과 공수

| 항목 | 옵션1 (승인 #5 유지) | 옵션2 (사용자 제안 중앙값) | **옵션3 (절충 — 추천)** |
| --- | --- | --- | --- |
| 구간 / 장비 / 관계 | 4 / 10 / 18~20 | 4 / 8 / 16 | 4 / 10 / 18 |
| 사건 | 120 (kb 70 / dev 20 / sealed 30) | 45 (kb 27 / dev 8 / sealed 10) | **72 (kb 42 / dev 12 / sealed 18)** |
| 원형(PT) 수 | 24 `[제안값]` | 12 | **18** |
| 카드 생성 → 채택 | 250 → 150 | 55 → 33 | **130 → 80** |
| 산출물 채택 | 400 | 120 | **220** |
| 매뉴얼 문서 / 절 | 6 / 30 | 5 / 25 | **6 / 30** |
| 개정 후보 | 4 | 4 | **5** |
| 개발 평가 문항 | 30 | 12 | **18** |
| 봉인 평가 문항 | 60 (질의 36 + 인계 24, 안전 12) | 18 (질의 11 + 인계 7, 안전 6) | **42 (질의 28 + 인계 14, 안전 15)** |
| **검수 공수 (계산)** | **42.9시간**(신규 엔티티 포함 시 **46.7시간**) | **17.4시간** | **30.5시간** |
| 가용 34.5시간 대비 | **124 % (135 %)** — 초과 | 50 % — 여유 | **88 %** — 빠듯하지만 가능 |

**옵션1 계산 상세**: 카드 T5 50건×8분 + 일반 200건의 20 %(40건)×4분 = 560분 / 사건 120의 35 %(42건)×12분 = 504분 / 산출물 400의 20 %(80건)×2분 = 160분 / 평가 문항 (60+30)×15분 = 1350분 / 신규 엔티티(매뉴얼 6×20 + 개정 4×15 + 관계 16×3) = 228분 → 합계 2802분 = **46.7시간**.
**옵션3 계산 상세**: 카드 T5 26건×8분 + 일반 104건의 20 %(21건)×4분 = 292분 / 사건 72의 35 %(25건)×12분 = 300분 / 산출물 220의 20 %(44건)×2분 = 88분 / 평가 문항 (42+18)×15분 = 900분 / 매뉴얼 120 + 개정 75 + 관계 54 = 249분 → 합계 1829분 = **30.5시간**.

**민감도**

| 가정 변경 | 옵션1 | 옵션2 | 옵션3 |
| --- | --- | --- | --- |
| 기준(전혜민 15h + 보조 8h × 1.5주 = 34.5h) | 124 % | 50 % | 88 % |
| 가용이 20h + 10h로 늘면(45.0h) | 95 % | 39 % | 64 % |
| 검수 창이 2.0주로 늘면(46.0h) | 93 % | 38 % | 63 % |
| 가용이 12h + 6h로 줄면(27.0h) | **159 %** | 64 % | **107 %** |
| 평가 문항 단가 12분/건이면(옵션3) | — | — | 26.3시간 = 76 % |

→ **옵션1은 어떤 낙관 가정에서도 90 % 이상을 검수에만 쓰는 구성이다.** 검수 외 업무(정답지 형식, 봉인 절차, 데이터 카드, 대시보드, 인수 테스트)가 전혜민 담당이라는 점(4.7.1·5절)을 감안하면 2주차 말 봉인 일정과 충돌한다.

## B5-3. 봉인셋 크기와 지표 신뢰구간 (계산 결과)

Wilson 95 % 신뢰구간, 관측 비율 0.8 가정.

| 봉인 평가 문항 수 | Recall@5 = 0.8 관측 시 95 % CI | 폭 | 해석 |
| --- | --- | --- | --- |
| 15 | [0.548, 0.930] | 0.381 | **±19 pp.** "0.8 달성"과 "0.55"가 구별되지 않는다 |
| 18 | [0.548, 0.910] (관측 14/18 = 0.778) | 0.362 | ±18 pp |
| 20 | [0.584, 0.919] | 0.335 | ±17 pp |
| 30 | [0.627, 0.905] | 0.278 | ±14 pp |
| **42** | **[0.667, 0.900]** (관측 34/42 = 0.810) | **0.233** | **±12 pp** |
| 60 | [0.682, 0.882] | 0.200 | ±10 pp |

"0건" 목표 지표(안전 금기 누락, 미래 누수, 근거 없는 위험 조치)는 **0건을 관측해도 참 실패율의 95 % 상한이 남는다**(Clopper-Pearson 단측).

| 서브셋 크기 | 0건 관측 시 참 실패율 95 % 상한 |
| --- | --- |
| 8 | 31.2 % |
| 12 (기존 안전 서브셋) | 22.1 % |
| **15** | **18.1 %** |
| 20 | 13.9 % |
| 24 | 11.7 % |
| 30 | 9.5 % |

조건 불일치 오적용 목표(기존 #6: ≤ 5 %)는 위반 k건 관측 시 상한이 다음과 같다.

| n | k=0 | k=1 | k=2 |
| --- | --- | --- | --- |
| 18 | 15.3 % | 23.8 % | 31.0 % |
| 20 | 13.9 % | 21.6 % | 28.3 % |
| 36 | 8.0 % | 12.5 % | 16.5 % |
| 42 | **6.9 %** | 10.8 % | 14.2 % |
| 60 | **4.9 %** | 7.7 % | 10.1 % |

**중요한 발견 `[신규 제안]`**: 기존 #6의 "조건 불일치 오적용 ≤ 5 %"를 **통계적으로 주장할 수 있는 최소 봉인셋 크기는 59건**(위반 0건 관측 전제)이다. 즉 **기존 승인 #5의 봉인 평가셋 60건은 우연이 아니라 이 목표치와 정합한 크기**다. 사용자 제안 15~20건에서는 위반 0건이어도 상한이 13.9~15.3 %이므로 "≤ 5 %"라는 문장을 쓸 수 없다. 이 사실은 규모를 줄이는 결정과 **목표치 문장을 함께 고쳐야 한다**는 뜻이다(B10-3).

기준선 비교(1) 매뉴얼만 vs (2) 카드 포함의 쌍대 비교는 부호검정 기준으로 **불일치 쌍 6개가 모두 한 방향**이면 양측 p = 0.031로 유의하다. 봉인 문항이 42건이면 불일치 쌍 6개 확보가 현실적이지만, 18건에서는 불일치 쌍이 2~3개만 나올 가능성이 높아 **"카드가 효과 있다"를 통계적으로 말할 수 없다**. 이것이 봉인셋을 20건 미만으로 줄이면 안 되는 가장 강한 이유다.

## B5-4. 옵션별 종합 평가

| 항목 | 옵션1 | 옵션2 | 옵션3 (추천) |
| --- | --- | --- | --- |
| 검수 공수 | 46.7h / 34.5h = **초과** | 17.4h = 여유 | 30.5h = 88 %, 가능 |
| Recall@5 오차 | ±10 pp (최선) | ±18 pp | ±12 pp |
| 조건 불일치 ≤5 % 주장 | 가능(0건 시 4.9 %) | **불가**(13.9 %) | 불가. **위반 0건일 때만 ≤10 % 주장 가능**(0건 6.9 %, 1건 10.8 %) |
| 안전 누락 0건의 설명력 | 서브셋 12 → 상한 22 % (약함) | 서브셋 6 → 상한 39 % (매우 약함) | 서브셋 15 → 상한 18 % |
| 기준선 (1)vs(2) 유의성 | 확보 가능 | **확보 곤란** | 확보 가능(경계) |
| 신규 엔티티 7묶음 커버 | 사건 수는 충분하나 공수 초과로 **신규 엔티티가 후순위로 밀릴 위험** | 커버 가능, 유형별 최소 건수는 빠듯 | 커버 가능 + 12유형 최소 건수 충족 |
| 2주차 말(10/12) 봉인 | **위험 높음** | 충족 | 충족(버퍼 약 4시간) |
| 주 위험 | 검수 미완 → 봉인 연기 → 3주차 채점 압축 | 지표를 숫자로 말할 수 없음 → 발표 주장 약화 | 버퍼가 작아 1주차 지연 시 즉시 영향 |

## B5-5. 추천과 축소 순서

**`[기존 수정안]` 추천 = 옵션3.** 승인 #5를 다음과 같이 조정하자는 제안이며, 팀 결정 없이는 적용하지 않는다.

| 승인 #5 항목 | 기존 | 옵션3 제안 | 이유 |
| --- | --- | --- | --- |
| 사건 | 120 | **72** | 신규 엔티티 13종이 사건마다 붙으면서 사건 1건의 검수 시간이 기존 가정보다 커졌다. 유형 12종 × 최소 건수 합(72)이 하한 |
| 카드 채택 | 150+ | **80+** (생성 130) | T별 최소 20 → **T별 최소 14, T5 최소 16** `[제안값]`. 커버리지 매트릭스 빈칸 0은 유지 |
| 산출물 채택 | 400+ | **220+** (Q&A 80 / 메모 45 / 인계 35 / 트러블슈팅 35 / 조건부 규칙 25) | 산출물은 카드 파생물이라 지표 기여가 가장 낮다. 가장 먼저 줄일 항목 |
| 봉인 평가셋 | 60 (질의 36 + 인계 24, 안전 12) | **42 (질의 28 + 인계 14, 안전 서브셋 15)** | 통계적 하한 고려. 안전 서브셋은 오히려 12→15로 **늘린다**(상한 22 %→18 %) |
| 개발셋 | 30 | **18** | |
| 신규 | — | 관계 18, 매뉴얼 6, 개정 후보 5, 컨텍스트 72, 관측 250+ | 사용자 요구 7묶음 커버 |

**시간이 부족할 때의 축소 순서 `[신규 제안]`** (기존 미결 #15 "T5만 축소" 옵션과 충돌하지 않게: T5는 마지막까지 줄이지 않는다)
1. 산출물 220 → 150 (지표 영향 가장 작음)
2. 카드 80 → 65 (T별 최소는 유지, 여유분만 삭감)
3. 사건 72 → 60 (`single_equipment_fault`부터 삭감)
4. 개발셋 18 → 12
5. **봉인 평가셋과 안전 서브셋, T5 카드는 삭감 대상에서 제외.** 여기를 줄이면 평가 자체가 무의미해진다.

---

# B6. 페르소나 고도화

`[기존]` V-01 박 반장(28년, HPU·GR, 감각 우선, T1 다수, 짧고 단정적) / V-02 김 기장(19년, RT·CV, 계측 우선, T2·T3, 조건문 많음) / V-03 이 주임(12년, 공용·교대 조장, T4·T5, 안전 보수적, 인계 문서체). 변수 `years`/`equipment_focus`/`judgment_style`/`risk_posture`/`speech`/`known_biases`. 상충 처리 규칙(병합 금지, `conflict_group`, 안전 상충은 보수적 쪽만) 전부 유지.

## B6-1. 생산시스템 관점 확장 필드 `[신규 제안]`

| 필드 | 의미 | 자료형 | V-01 | V-02 | V-03 |
| --- | --- | --- | --- | --- | --- |
| `segment_focus[]` | 담당 구간 | list[FK SG-] | UTIL + ENTRY | ENTRY + CENTER + EXIT | 전 구간(교대 조장) |
| `relation_bias` | 관계 지식 편향 | enum | `utility_first` — 증상이 보이면 유압·전력을 먼저 의심 | `local_first` — 해당 장비 자체와 계측을 먼저 확인, 상류는 나중 | `downstream_first` — 하류 정체·인터록을 먼저 확인(교대 인수 시 정체 경험 많음) |
| `hop_habit` | 탐색 깊이 습관 | int | 2(공급원까지 바로) | 1(국소) | 2(하류 2단계) |
| `stop_restart_experience` | 정지·재가동 경험 | enum | `high` — 재가동 과도 상태 판단 경험 다수, 과도값을 이상으로 오판하지 않음 | `medium` | `high` — 야간 정지·재가동 인계 경험 |
| `handover_style` | 인계 서술 습관 | enum | `terse_risky` — "HPU 봤다, 이상없음" 식으로 축약해 **정보 누락을 유발**(누락 평가 데이터의 원천) | `checklist` — 항목형, 수치 포함 | `narrative_complete` — 길고 맥락 포함, 중복 서술 |
| `known_biases` | 과신 영역 | list[str] | 감각 판단 과신, 하류 정체를 상류 문제로 단정 | 계측값 정상이면 이상 없다고 단정 | 안전 보류 과다(불필요한 보류) |
| `co_occurrence_confusion` | 동시발생↔인과 혼동 경향 | enum | `high` | `low` | `medium` | 

- `[신규 제안]` `relation_bias`는 **오답을 만드는 장치**다. 같은 사건에서 V-01은 "HPU 압력을 먼저 보라", V-02는 "RT-03 베어링을 보라"는 서로 다른 행동 후보를 말하고, 정답(`true_cause`)은 하나다. 이 구조가 `conflicting_knowledge` 유형과 "조건 불일치 제외" 지표의 재료가 된다.
- `[기존]` "사건 원장에서 사실(ground truth)은 하나다. 페르소나 차이는 해석·요령 층에만 존재" 규칙은 그대로 유지한다. `relation_bias`는 해석 층이다.

## B6-2. 페르소나 추가 필요성 판단 `[신규 제안]`

| 판단 | 내용 |
| --- | --- |
| 필요성 | 신규 장비 PDP-01(전력)·CAU-01(공압)과 `power_supply`·`pneumatic_supply` 관계가 추가되면서 담당자 없는 설비가 생긴다. V-01의 `equipment_focus`가 HPU·GR이므로 전력·공압 지식은 현재 어느 페르소나에도 귀속되지 않는다. |
| **추천** | **V-04를 신설하지 않고 V-03의 `equipment_focus`를 `공용(HPU·PDP·CAU 포함)`으로 확장한다.** V-03은 이미 "공용·교대 조장"이므로 의미상 자연스럽고, 기존 승인 사항(V-01~V-03 3명)을 건드리지 않는다. |
| V-04 신설 시 비용 | 페르소나 1명 추가 = 카드 생성량 +약 20 % (같은 사건에 의견이 하나 더 붙음) → 옵션3 기준 카드 생성 130 → 156, 검수 공수 +약 2.5시간. `conflict_group` 조합 수가 3쌍 → 6쌍으로 늘어 상충 검수 시간이 2배. **옵션3의 버퍼(4시간)를 거의 소진하므로 MVP에서는 비추천.** |
| 후속 범위 | `[기존]` 4.7.7 "향후 확장: 페르소나 5명"과 일치. 유틸리티 담당 V-04, 정비 담당 V-05는 확장 항목으로 둔다. |

## B6-3. 전문가1 D-34와의 연결 `[기존, 승인 대기]`

- D-34(`persona_id`·판단 습관·상충 출처 노출)는 승인 대기다. 이 문서는 D-34를 승인된 것으로 취급하지 않는다.
- `[신규 제안]` 다만 위 확장 필드(`relation_bias`, `handover_style`, `co_occurrence_confusion`)는 **D-34가 승인되면 곧바로 노출 문구에 쓸 수 있는 형태**로 설계했다. D-34가 승인되면 응답에 "V-01(감각 우선·유틸리티 우선 판단 습관)의 의견"처럼 표기하고, 미승인이면 `persona_id`만 계보(`provenance`)에 남기고 노출하지 않는다. 두 경우 모두 스키마 변경이 필요 없다.
- `[기존]` "가상 페르소나를 실제 전문가 출처로 오인하지 않게 표시"(D-34 처리 메모) 취지는 `is_synthetic=true`와 `grade=L1` 표기로 이미 충족한다.

---

# B7. 파이프라인 P0~P6 확장안

`[기존]` P0~P6 번호와 담당은 유지한다. 신규 엔티티는 **소수점 단계**로 삽입해 기존 번호를 깨지 않는다. `[기존]` CLI `python -m shiftlink.data all --seed 42 --version v0.x`, `from P3` 재개 인터페이스도 유지한다.

## B7-1. 단계표 (확장) `[신규 제안]`

| # | 단계 | 입력 | 출력 파일 | CLI 서브커맨드 | 담당 | 상태 |
| --- | --- | --- | --- | --- | --- | --- |
| P0 | 공개 시드 수집 | 시드 목록 | `seeds/seeds.yaml`, `seeds/notes/*.md` | `data seeds` | 전혜민 | 기존 |
| P1 | 가상 설비 사전 | 시드 노트 | `plant/L1.yaml` (기존) + `plant/lines.yaml`, `plant/segments.yaml`, `plant/equipment_groups.yaml`, `plant/equipment_types.yaml`, `plant/equipment.yaml`, `plant/components.yaml` | `data plant` | 유현준·전혜민 | **확장** |
| **P1.5** | **관계·매뉴얼 기준정보** | P1 | `plant/relations.yaml`, `manuals/documents.yaml`, `manuals/sections.jsonl` | `data structure` | 유현준·전혜민 | **신규** |
| P2 | 베테랑 페르소나 | P1 | `personas/*.yaml` (확장 필드 포함) | `data personas` | 전혜민·유현준 | **확장** |
| **P2.5** | **원형 사건 카탈로그 + 분할 사전 배정** | P1·P1.5·P2 + B4 | `prototypes/prototypes.yaml`, `splits/prototype_split.json` | `data prototypes` | 전혜민 | **신규 (누수 방지 핵심)** |
| P3 | 사건·지식 원장 | P1·P1.5·P2·P2.5·시나리오 정의 | `ledger/contexts.jsonl`, `ledger/events.jsonl` (기존), `ledger/observations.jsonl`, `ledger/event_equipment_links.jsonl`, `ledger/cards.jsonl` (기존) | `data ledger` | 최재영(생성)·전혜민(검수) | **확장** |
| **P3.5** | **행동·결과·인계·개정 후보** | P3 | `ledger/action_candidates.jsonl`, `ledger/actions_executed.jsonl`, `ledger/outcomes.jsonl`, `ledger/recurrence_checks.jsonl`, `ledger/handovers.jsonl`, `revisions/proposals.jsonl`, `revisions/approvals.jsonl`, `revisions/publishes.jsonl` | `data flow` | 최재영·전혜민 | **신규** |
| P4 | 산출물 생성 | P3·P3.5 원장 역참조 | `artifacts/*.jsonl` | `data artifacts` | 최재영 | 기존 |
| P5 | 품질 검증 | P1~P4 전체 | `qc/report.json`, `qc/violations.jsonl`, `qc/review_queue.csv` | `data qc` | 전혜민(주)·최재영 | **확장** |
| P6 | 분할·버전·데이터 카드 | 채택 레코드 + P2.5 분할 사전 | `splits/{kb,dev,sealed}.json`, `eval/dev_items.jsonl`, `eval/sealed_items.jsonl`, `DATASET_CARD.md`, `manifest.json` | `data split` | 유현준·허재원 | **확장** |

`all`은 P0→P6 전체, `from P3`는 P3·P3.5·P4·P5·P6을 뜻한다(소수점 단계는 앞 정수 단계에 종속). `[신규 제안]` 재개 지점은 정수 단계 경계 7개 + 소수점 3개 = `P0 P1 P1.5 P2 P2.5 P3 P3.5 P4 P5 P6`.

## B7-2. 결정성(seed) 보장 범위 `[기존 유지 + 신규 제안]`

| 구간 | 결정성 | 근거 |
| --- | --- | --- |
| P1·P1.5·P2·P2.5 | **완전 결정적** (LLM 호출 없음, 사람이 쓴 YAML + 코드 계산) | 관계·원형·분할은 LLM이 만들지 않는다 |
| P3·P3.5의 코드 부분(수치, ID, 시각, 판정) | **완전 결정적** — `hash(run_seed, prototype_id, step_no)` 난수 스트림 | B3-1 |
| P3·P3.5의 LLM 부분(서술문) | **비결정적**. `[기존]` "seed 고정만으로 새 생성의 바이트 동일성을 보장하지 않는다"(4.7.10) 원칙 유지 | `raw/` 원본 보존 + 결정적 후처리 재생으로 해시 검증 |
| P4·P5·P6 | 결정적(입력이 같으면 동일 출력). judge 호출은 `raw/judge/`에 보존 | 기존과 동일 |

## B7-3. 입력 격리 원칙 재확인 `[기존 유지]`

- `[기존]` "P3의 입력은 `seeds/`·`plant/`·`personas/`·시나리오 정의뿐이다. 이전 실행의 `ledger/cards.jsonl`·`artifacts/*`를 P3·P4의 입력이나 few-shot 예시로 되먹이지 않는다."
- `[신규 제안]` 확장 후에도 이 원칙을 유지하기 위한 명시적 허용 목록:
  - P3 허용 입력 = `seeds/`, `plant/**`(P1·P1.5 산출물 — **사람이 작성한 기준정보이므로 생성물이 아님**), `personas/`, `prototypes/`(P2.5 — 사람이 작성), `manuals/`(P1.5 — 사람이 작성한 가상 매뉴얼).
  - P3.5 허용 입력 = P3의 같은 실행 산출물(같은 사건 내 앞 단계)만. **다른 사건의 결과·재발을 few-shot으로 쓰지 않는다.**
  - P4 허용 입력 = P3·P3.5 원장의 **역참조**만. 원장 내용 재작성 금지(기존 규칙 유지).
  - 금지: 이전 실행의 `ledger/`·`artifacts/`·`revisions/`를 어느 단계의 입력이나 few-shot으로도 쓰지 않는다.
- `[신규 제안]` 검사 QC-ISO-01: 각 단계의 실행 로그에 열린 파일 경로를 기록하고, 허용 목록 외 경로가 열렸으면 실행 실패로 처리한다.
- `[기존]` "다수의 합성 답변이 같은 내용을 말한다는 사실을 정확성의 증거로 인정하지 않는다" — B10의 어떤 지표도 "여러 생성 결과의 일치율"을 정확성 지표로 쓰지 않는다. judge는 4항목 점수만 내고, 일치율은 `distinct-2`·중복 검사(다양성 관리)에만 쓴다.

---

# B8. 자동 품질검사 기준 (확장)

`[기존]` 게이트 순서 **스키마 → 규칙 → 중복 → judge → 사람** 과 합격 기준(스키마·참조무결성 100 %, 물리 모순 0, 안전 위반 0 + T5 100 % 사람 검수, judge 4항목 평균 ≥ 4.0 & 안전 5점, 사람 검수 봉인셋 100 %·T5 100 %·나머지 20 % 층화, 검수자 일치 ≥ 0.8, 5-gram Jaccard ≥ 0.8 폐기, distinct-2 ≥ 0.6, D 사건 불확실성 표현 95 %)를 **전부 보존**한다. 아래는 규칙 단계에 추가하는 신규 검사다.

| 검사 ID | 검사 내용 | 판정 | 위반 시 처리 | 구현 난이도 | 담당 |
| --- | --- | --- | --- | --- | --- |
| QC-REF-01 | 모든 FK가 대상 엔티티에 존재 | 100 % | `rejected_rule` 폐기 | 하 | 유현준 |
| QC-REF-02 | `component` 문자열이 Component 사전에 존재 | 100 % | 수정 큐(오타 가능) | 하 | 유현준 |
| QC-REF-03 | `seed_ids`가 `seeds.yaml`에 존재 | 100 % | `rejected_rule` | 하 | 전혜민 |
| QC-REF-04 | `Event.equipment`(유형)와 `primary_equipment_id`의 유형이 일치 | 100 % | 수정 큐 | 하 | 유현준 |
| QC-REF-05 | `scope_level`에 맞는 대상 ID만 채워짐 | 100 % | 수정 큐 | 하 | 유현준 |
| QC-ID-03 | ID 형식 정규식(끝 고정) 통과, 중복 ID 0 | 100 % | 실행 실패(전체 중단) | 하 | 유현준 |
| QC-REL-01 | `from_kind`/`to_kind`에 맞는 테이블에 ID 존재, 자기참조 금지 | 100 % | `rejected_rule` | 하 | 유현준 |
| QC-REL-02 | `traversed_relation_ids`가 실제 그래프 경로를 이룸(연결성) | 100 % | 수정 큐 | 중 | 유현준 |
| QC-REL-03 | 사건 시각에 `valid_from ≤ occurred_at < valid_to` | 100 % | `rejected_rule` | 하 | 유현준 |
| QC-REL-04 | 관계 그래프에 방향 사이클 없음(`material_flow`·`drive`·`*_supply` 기준) | 사이클 0 | 실행 실패 | 중 | 유현준 |
| QC-CAUSE-01 | `cause_candidate` 링크에 지지 관측 1건 이상 + 그 관측이 비정상 판정 | 100 % | `affected` 또는 `checked_no_finding`으로 강등 | 중 | 최재영 |
| QC-CAUSE-02 | `causality=co_occurrence` 관계로 `cause_candidate` 부여 금지 | 위반 0 | `common_cause_candidate`로 강등 | 하 | 최재영 |
| QC-CAUSE-03 | 원인 관측 시각과 결과 관측 시각 차이가 `lag_seconds`의 0.5~20배 | 위반 0 | 수정 큐 | 중 | 최재영 |
| QC-CAUSE-04 | `cause_confidence=determined`인데 `true_cause`를 지지하는 관측이 없음 → 금지 | 위반 0 | `undetermined`로 강등 | 중 | 전혜민 |
| QC-TIME-01 | B1-0의 시간 순서 부등식 전부 만족 | 100 % | `rejected_rule` | 하 | 유현준 |
| QC-TIME-02 | 사건 내 관측 시각 중복 없음(≥1분 간격), 관측 3건 이상 | 100 % | 수정 큐 | 하 | 유현준 |
| QC-TIME-03 | `shift_code`·`shift_date`가 `captured_at`에서 규칙대로 계산됨 | 100 % | 자동 재계산 | 하 | 유현준 |
| QC-LEAK-01 | 같은 `prototype_id`의 사건이 두 개 이상 분할에 걸쳐 있지 않음 | 위반 0 | 실행 실패(봉인 차단) | 중 | 전혜민 |
| QC-LEAK-02 | 카드·산출물·인계·개정의 `split`이 사건에서 정확히 상속됨 | 100 % | 자동 재배정 | 하 | 유현준 |
| QC-LEAK-03 | `sealed` 사건의 카드가 `kb` 인덱스에 없음 | 위반 0 | 실행 실패 | 하 | 허재원 |
| QC-LEAK-04 | 프롬프트 화이트리스트 ∩ (post_action ∪ ground_truth) = ∅ | 공집합 | 단위 테스트 실패 | 하 | 유현준 |
| QC-LEAK-05 | 카나리 토큰이 검색 결과·프롬프트·응답 로그에 없음 | 0건 | 지표 실패 + 원인 추적 | 중 | 최재영 |
| QC-LEAK-06 | 반환 레코드 최대 타임스탬프 ≤ `as_of` | 위반 0 | 테스트 실패 | 중 | 유현준 |
| QC-LEAK-07 | 정답지 파일이 `kb` 경로·Jetson 복사 대상에 없음 | 위반 0 | 배포 차단 | 하 | 허재원 |
| QC-CTX-01 | 정지 모드에서 `line_speed` null 또는 0 | 위반 0 | `rejected_rule` | 하 | 최재영 |
| QC-CTX-02 | `isolated_loto` 장비에 운전 중 측정값(회전·전류>0) 없음 | 위반 0 | `rejected_rule` | 하 | 최재영 |
| QC-CTX-03 | `segment_states`가 물류 순서와 모순 없음(상류 `starved`인데 하류 `blocked` 동시 금지 등) | 위반 0 | 수정 큐 | 중 | 전혜민 |
| QC-CTX-04 | 활성 알람의 `equipment_id`가 그 알람 코드를 가진 장비인지 | 100 % | `rejected_rule` | 하 | 유현준 |
| QC-PH-01~08 | B3-3 물리 모순 8규칙 | 위반 0 | `rejected_rule` | 중 | 최재영 |
| QC-ACT-01 | `ActionExecuted.action_candidate_id`가 null이면 `deviation_reason` 필수 | 100 % | 수정 큐 | 하 | 최재영 |
| QC-ACT-02 | 모든 `Outcome`이 정확히 하나의 `ActionExecuted`를 가리킴 | 100 % | `rejected_rule` | 하 | 유현준 |
| QC-ACT-03 | `immediate_result=resolved`인데 `post_measurements`가 여전히 비정상이면 금지 | 위반 0 | 수정 큐 | 중 | 최재영 |
| QC-ACT-04 | `requires_approval=true`인데 `approval_status=not_required` 금지 | 위반 0 | `rejected_rule` | 하 | 유현준 |
| QC-ACT-05 | `safety_flag=true` 행동이 승인 없이 `approved` 표기되지 않음 | 위반 0 | `rejected_safety` | 하 | 허재원 |
| QC-REC-01 | `no_recurrence`는 `checked_at ≥ recorded_at + window` 만족 시에만 | 위반 0 | `observing`으로 강등 | 하 | 유현준 |
| QC-REC-02 | `recurred`면 `recurred_event_id` 존재 + 같은 `prototype_id` | 100 % | `rejected_rule` | 하 | 유현준 |
| QC-REC-03 | 성공 집계 스크립트가 `observing`·`unconfirmed`를 제외함(단위 테스트) | 통과 | 테스트 실패 | 하 | 최재영 |
| QC-MAN-01 | 카드·행동 후보의 `manual_refs`·`basis_section_ids`가 존재하는 절이며 그 시점 발행 버전 | 100 % | 수정 큐 | 중 | 전혜민 |
| QC-MAN-02 | `doc_kind=manufacturer_original`에 대한 개정 제안 0건 | 위반 0 | `rejected_rule` | 하 | 전혜민 |
| QC-REV-01 | `is_editable=false` 문서 개정 차단 | 위반 0 | `rejected_rule` | 하 | 유현준 |
| QC-REV-02 | `base_version`·`base_section_sha256`이 현재 값과 일치 | 100 % | 개정 상태 `needs_revision` | 중 | 유현준 |
| QC-REV-03 | `basis_event_ids` 2건 이상 + 1건 이상 `result_status=confirmed` | 100 % | 개정 후보 생성 취소 | 중 | 전혜민 |
| QC-REV-04 | 개정 근거 사건이 실제로 그 절과 연관(장비·구간 교집합 ≠ ∅) | 100 % | 수정 큐 | 중 | 전혜민 |
| QC-PUB-01 | 승인(`decision=approved`) 없는 `PublishRecord` 0건 | 위반 0 | 실행 실패 | 하 | 유현준 |
| QC-PUB-02 | `rollback` 발행은 `rollback_of_publish_id`가 존재하고 그 버전이 실재 | 100 % | `rejected_rule` | 하 | 유현준 |
| QC-PUB-03 | `searchable_after_publish=false`인 개정이 검색 인덱스에 없음 | 위반 0 | 배포 차단 | 하 | 허재원 |
| QC-ISO-01 | 단계별 열린 파일 경로가 허용 목록 내 | 100 % | 실행 실패 | 중 | 최재영 |
| QC-BAL-01 | B4의 12유형 최소 건수 충족, 커버리지 매트릭스 빈칸 0 | 100 % | 추가 생성 | 하 | 전혜민 |
| QC-BAL-02 | `case_type × relation_type` 매트릭스에서 3개 필수 시나리오 행 빈칸 0 | 100 % | 추가 생성 | 중 | 전혜민 |

**처리 방침 `[신규 제안]`**: `rejected_rule` = 폐기(원장 보존, 기존 원칙). **수정 큐** = 폐기하지 않고 `qc/review_queue.csv`에 올려 사람이 1건씩 고친다. 구조적으로 불가능한 조합(참조·시간·안전)은 폐기, 서술·정합 문제는 수정 큐로 보낸다. `[기존]` "앞 단계 탈락은 뒤 단계로 보내지 않는다" 원칙 유지 — 수정 큐 항목은 수정 후 스키마 단계부터 재진입한다.

---

# B9. 누수 방지 체크리스트 (확장)

`[기존]` 보존 항목: 사건 단위 분할 / 같은 템플릿 파생물 그룹 분할 / `sealed` 카드는 KB 미포함·`cards_expected` 정답지 전용 / 2주차 말 sha256 봉인 + Git 태그 `data-v1.0-sealed` / 채점 시 해시 재검증 / 생성 ≠ judge ≠ 온디바이스 추론 계열 / 형식 SFT 학습 데이터는 `split=kb`에서만 추출.

## B9-1. 원형 사건(prototype) 단위 그룹 분할 `[기존 수정안]`

`[기존]` "동일 원문·설비·사건 템플릿에서 파생된 데이터는 하나의 그룹으로 분할한다"는 원칙은 이미 있으나 **그룹 키가 데이터에 없다**. 그룹 키를 명시적 엔티티로 만들자는 제안이다.

**원형 ID 설계**
- `EventPrototype`(`PT-xxxx`)를 P2.5에서 **사람이** 카탈로그로 작성한다(LLM 생성 금지 — 그룹 키가 비결정적이면 누수 검사가 무의미).
- 원형 동일성 판정 키 `[신규 제안]` = `(case_type, root_equipment_type, sorted(relation_path_types), primary_symptom_class)`. 이 4요소가 같으면 **같은 원형으로 합친다**. 예: "GR 베어링 이상 → drive → RT 이송 불균일"과 "GR 감속기 이상 → drive → RT 이송 불균일"은 같은 원형(PT-0003)이다.
- 분할은 **원형 단위로 먼저 배정**(`EventPrototype.assigned_split`)하고, 사건은 그 값을 상속한다. 기존 "분할은 Event에서 결정"은 "분할은 원형에서 결정하고 Event가 상속"으로 한 단계 위로 올린다.
- 재발 체인(`is_recurrence_of`)은 정의상 같은 원형이므로 자동으로 같은 분할에 들어간다.

**검사 스크립트 의사코드** `[신규 제안]`

```python
def check_prototype_split_leakage(events, prototypes, cards, artifacts, handovers, revisions):
    errors = []
    # 1) 원형 단위 분할 유일성
    by_proto = defaultdict(set)
    for e in events:
        by_proto[e.prototype_id].add(e.split)
    for pid, splits in by_proto.items():
        if len(splits) > 1:
            errors.append(("QC-LEAK-01", pid, sorted(splits)))
    # 2) 원형 배정과 사건 상속 일치
    for e in events:
        if e.split != prototypes[e.prototype_id].assigned_split:
            errors.append(("QC-LEAK-01b", e.event_id))
    # 3) 하위 산출물 상속 (카드·산출물·인계·개정)
    split_of_event = {e.event_id: e.split for e in events}
    for rec in chain(cards, artifacts, handovers, revisions):
        parents = {split_of_event[eid] for eid in rec.event_ids if eid in split_of_event}
        if len(parents) > 1:                      # 여러 분할의 사건을 동시에 참조
            errors.append(("QC-LEAK-02a", rec.id, sorted(parents)))
        elif parents and rec.split not in parents:
            errors.append(("QC-LEAK-02b", rec.id, rec.split, sorted(parents)))
    # 4) sealed 카드가 kb 인덱스에 없음
    kb_ids = load_kb_index_ids()
    for c in cards:
        if c.split == "sealed" and c.card_id in kb_ids:
            errors.append(("QC-LEAK-03", c.card_id))
    # 5) 텍스트 근접 누수: sealed 사건 서술과 kb 레코드의 5-gram Jaccard
    for se in (e for e in events if e.split == "sealed"):
        for kb in (r for r in chain(cards, artifacts) if r.split == "kb"):
            if jaccard_5gram(norm(se.symptom_text), norm(kb.text)) >= 0.8:
                errors.append(("QC-LEAK-08", se.event_id, kb.id))
    return errors
```

- `[신규 제안]` QC-LEAK-08(텍스트 근접 누수)은 기존 중복 검사(같은 분할 내 중복 폐기)와 **목적이 다르다**. 분할을 건너뛴 근접 중복은 폐기가 아니라 **sealed 쪽 문항을 다시 쓰는** 것으로 처리한다(kb를 지우면 지식베이스가 빈다).

## B9-2. 관계·설비 사전·매뉴얼의 분할 귀속 `[신규 제안]`

| 데이터 | 분할 귀속 | 근거 (왜 누수가 아닌가) |
| --- | --- | --- |
| 설비 사전(`plant/**`), 관계(`relations.yaml`) | **kb 공용** (분할 없음) | 이들은 **문제의 전제 조건**이지 정답이 아니다. 실제 현장에서도 작업자는 라인 구조와 배관 계통도를 알고 있는 상태에서 판단한다. 시험에서 "주기율표를 보고 푸는" 것과 같다. 정답(`true_cause`)은 사건에만 있으므로, 구조를 안다고 정답이 유도되지 않는다. |
| 매뉴얼(`MD-`/`MS-`) | **kb 공용** (발행 버전만) | 위와 같은 이유. 단 **조건**: sealed 사건의 `true_cause`를 그대로 서술하는 절을 만들지 않는다(예: "RT-03 이송 불균일은 GR-01 베어링 손상 때문이다"). 검사 QC-LEAK-09 `[신규 제안]`: 매뉴얼 절 본문과 sealed 사건 `true_cause`의 5-gram Jaccard ≥ 0.5면 절을 다시 쓴다. |
| 페르소나(`personas/`) | **kb 공용** | 해석 층이며 정답이 아니다. |
| 원형 카탈로그(`prototypes/`) | **분할 사전 배정표 자체** | `assigned_split`은 정답의 일부다. **Jetson·검색 계층에 복사하지 않는다.** 검사 QC-LEAK-07에 포함. |
| 개정 후보(`RV-`)·승인·발행 | **사건에서 상속** + `visibility=post_action` | sealed 사건의 개정 후보는 정답에 준한다. `published` 상태의 발행본만 `as_of` 이후 검색 가능. |
| 인계 기록(`HO-`) | 사건에서 상속 | `expected_open_items`는 ground_truth. |

`[신규 제안]` 위 "kb 공용" 판단의 **한계 명시**: 관계 그래프가 정답을 좁혀 주는 것은 사실이다(그것이 이 프로젝트의 가설이다). 따라서 기준선 비교에 **관계 탐색을 끈 기준선**을 추가해야 관계의 효과와 누수를 구별할 수 있다(B10-4 기준선 (2b)).

## B9-3. 봉인 절차 단계별 체크리스트 `[기존 확장]`

| # | 시점 | 누가 | 무엇을 | 기록 위치 | 재검증 방법 |
| --- | --- | --- | --- | --- | --- |
| 1 | 2주차 목(10/9) | 전혜민 | 봉인 후보 목록 확정(사건·문항·정답지). 미검수 잔량 0 확인 | `qc/report.json` | 검수 완료율 100 % 스크린샷 |
| 2 | 10/9 | 유현준 | QC-LEAK-01~09 전부 통과 확인 | `qc/violations.jsonl`(빈 파일) | 스크립트 재실행 |
| 3 | 10/10 | 최재영 | 카나리 토큰 삽입·grep 검사 통과 | `qc/canary_report.json` | 재실행 |
| 4 | 10/11 | 전혜민 | `eval/sealed_items.jsonl` 동결. 이후 **열람 금지** 선언 | `DATASET_CARD.md` 봉인 절 | — |
| 5 | **10/12** | 유현준 | `sealed.jsonl`·`eval/sealed_items.jsonl`·`splits/prototype_split.json` **각각의 sha256** + 3개를 묶은 루트 해시 계산 | `manifest.json` | `sha256sum -c manifest.sha256` |
| 6 | 10/12 | 유현준 | Git 태그 `data-v1.0-sealed` 생성(주석에 루트 해시 포함) | Git | `git tag -v` / `git show` |
| 7 | 10/12 | 허재원 | Jetson 복사 대상에서 sealed·정답지·원형 분할표 제외 확인 | 배포 스크립트 로그 | 파일 목록 diff |
| 8 | 10/12 | 유현준 | Aiven `dataset_version`에 `manifest_sha256`·`sealed_at`·`sealed_by` 적재 | MySQL | SELECT 결과 캡처 |
| 9 | 3주차 채점 직전(10/13~) | 전혜민 | 봉인 해시 재검증 → 불일치면 채점 중단·원인 기록 | `eval/seal_verify.log` | `sha256sum -c` |
| 10 | 채점 후 | 전혜민 | 봉인셋 변경 금지 확인(전문가1 D-35 메모: 봉인 이후 평가셋 변경 금지) | `decision-log` | Git diff = 0 |

`[신규 제안]` 봉인 대상에 **`splits/prototype_split.json`을 반드시 포함**한다. 이 파일이 봉인되지 않으면 "분할을 나중에 바꿔서 점수를 올렸다"는 의심을 반박할 수 없다. `[신규 제안]` 봉인 해시는 3개 파일 각각 + 루트 해시 2단으로 두어, 한 파일만 손상돼도 어느 파일인지 특정할 수 있게 한다.

---

# B10. 평가 지표와 합격 기준

## B10-1. 목표치 고정 절차 (사용자 요구: "합격 수치는 개발셋 측정 후 봉인 평가 전에 고정") `[신규 제안]`

| 단계 | 시점 | 누가 | 내용 | 산출물 |
| --- | --- | --- | --- | --- |
| **사전 등록** | 1주차 말(~10/5) | 전혜민·유현준 | 측정할 지표 **목록·계산식·측정 대상·기각 규칙**을 먼저 확정하고 해시 봉인. **목표 수치는 비워 둔다.** | `eval/metric_registry.v0.yaml` + sha256 |
| 개발셋 측정 | 2주차(10/6~10/11) | 최재영 | 개발셋 18건으로 기준선 (0)(1)(2)(2b) 측정. 결과를 그대로 기록 | `eval/dev_baseline.json` |
| **목표치 고정** | **10/12 (봉인 당일, 봉인 직전)** | 팀 4인 합의 | 개발셋 결과를 근거로 각 지표의 합격선 결정. 근거 문장 1줄 필수 | `eval/metric_registry.v1.yaml` + sha256 + Git 태그 `eval-targets-v1.0` |
| 봉인 | 10/12 | 유현준 | 평가셋 + 목표치 레지스트리를 **함께** 봉인 | `manifest.json` |
| 채점 | 3주차(10/13~) | 전혜민·최재영 | 목표치 레지스트리 v1.0만 사용 | `eval_result` |
| 변경 시 | 3주차 이후 | — | **목표치 변경 금지.** 불가피하면 v2.0을 새로 만들고 v1.0 결과를 **함께** 보고한다 | `decision-log` |

**사후 조작이 아님을 보이는 장치** `[신규 제안]`
1. **지표 정의와 목표 수치의 분리 봉인** — 정의는 개발셋 측정 **전에**(v0), 수치는 측정 후 봉인 **전에**(v1). 정의를 나중에 바꾸는 방식의 조작이 불가능해진다.
2. **Git 태그 2개**(`eval-targets-v0`, `eval-targets-v1`)와 두 커밋 시각이 개발셋 측정 커밋 시각을 앞뒤로 감싸는지 확인할 수 있다.
3. **목표치 결정 근거 1줄 필수** — 예 "개발셋 Recall@5 = 0.72 관측, 봉인셋은 난도가 같으므로 0.70을 합격선으로 둔다".
4. **변경 이력** — `metric_registry`는 append-only. 이전 버전 삭제 금지. 발표 시 v0→v1 diff를 그대로 보여준다.
5. `[기존]` 미결 #6의 기존 목표치(Recall@5 ≥ 0.8 등)는 **삭제하지 않고 "기존 설계 목표(미승인)" 열에 남긴다.** 새 목표치가 기존보다 낮으면 그 사실과 이유를 함께 보고한다.

## B10-2. 통합 지표표

`[기존]` 4.9의 10개 지표 + 사용자 요구 14개 지표를 하나로 합쳤다. 목표치는 전부 `[잠정 제안 — 개발셋 측정 후 확정]`.

| # | 지표 | 정의(계산식) | 측정 대상 데이터 | 기존 목표치(#6, 미결) | 신규 제안 목표치 | 상태 | 측정 시점 | 담당 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M-01 | Recall@5 | 기대 카드 중 상위 5에 포함된 사건 비율 = `|{사건: cards_expected ∩ top5 ≠ ∅}| / |사건|` | 봉인 질의 28문항 | ≥ 0.8 | ≥ 0.70 `[잠정]` (42문항에서 ±12 pp) | 기존 | 3주차 | 최재영 |
| M-02 | 근거 충실도 | 답변 문장 중 인용 카드·절 내용과 일치하는 문장 비율(정답지 대조) | 봉인 질의 | ≥ 0.9 | ≥ 0.85 `[잠정]` | 기존 | 3주차 | 전혜민 |
| M-03 | 조건 불일치 오적용률 | `applied_conditions`가 컨텍스트와 불일치하는데 인용한 건수 / 전체 인용 건수 | 봉인 질의 + `condition_mismatch` 5건 | ≤ 5 % | **≤ 10 %** `[잠정]` (42문항의 통계적 한계, B5-3) | **기존 수정안** | 3주차 | 전혜민 |
| M-04 | 안전 금기 누락 | T5 또는 `safety_flag=true` 카드가 기대되는 사건에서 미노출 건수 | 봉인 안전 서브셋 15 | 0건 | 0건 (**95 % 상한 18 %로 함께 보고**) | 기존 | 3주차 | 허재원 |
| M-05 | 근거 없는 위험 조치·무권한 실행 | 근거 ID 없는 행동 권고 또는 읽기 전용 위반 건수 | 봉인 전체 42 | 0건 | 0건 | 기존 | 3주차 | 허재원 |
| M-06 | 지식 없음 처리율 | 카드 없는 질의에 "해당 지식 없음" 응답 비율 | `normal` 7 + 결손 질의 | ≥ 0.95 | ≥ 0.90 `[잠정]` | 기존 | 3주차 | 최재영 |
| M-07 | 인계 누락률 / 오연결률 | 누락 = `1 − |추출 항목 ∩ expected_open_items| / |expected|` / 오연결 = 잘못 연결한 항목 수 / 전체 연결 수 | 봉인 인계 14문항 | 규칙 Baseline 대비 누락 감소·오연결 비증가 | 동일(방향 기준 유지) | 기존 | 3주차 | 전혜민 |
| M-08 | p95 지연 / 조회 지연 | 신규 요청 1건 p95 / 카드 검색 p95 (플랜 B) | 런타임 로그 | 15초 / 2초 | 동일 | 기존 | 3주차 | 허재원 |
| M-09 | 발열 상태 처리량 | 25 W 연속 20건 처리 시 건당 지연·온도 | Jetson 실측 | 측정·보고(목표 미설정) | 동일 | 기존 | 3주차 | 허재원 |
| M-10 | 오프라인·복구 | 네트워크 차단 실행률, 재시작·재동기화 성공률, 감사 로그 완전성 | 런타임 시험 | 측정·보고 | ≥ 0.95 `[잠정]` | 기존 확장 | 3주차 | 허재원 |
| M-11 | 관련 공정·장비 범위 식별 정확도 | `EventEquipmentLink`(role≠excluded) 집합에 대한 Jaccard = `|예측 ∩ 정답| / |예측 ∪ 정답|`. 구간 단위와 장비 단위를 각각 보고 | 봉인 질의 28 (`upstream_cause`·`downstream_block`·`common_utility` 필수 포함) | — (신규) | ≥ 0.65 `[잠정]` | **신규** | 3주차 | 최재영 |
| M-12 | 인용 정확도 | 응답이 인용한 ID 중 실존·유효·해당 시점 발행 버전인 비율 | 봉인 전체 42 | — | ≥ 0.98 `[잠정]` (ID 검증은 코드가 하므로 높게) | **신규** | 3주차 | 유현준 |
| M-13 | 조건 불일치 제외율 | 제외해야 할 유사 사례 중 실제로 제외하고 **제외 이유를 밝힌** 비율 | `condition_mismatch` 5건 + 봉인 내 유사 쌍 | — | ≥ 0.80 `[잠정]` | **신규** | 3주차 | 전혜민 |
| M-14 | 근거 부족 보류율 | 근거 부족 사건에서 원인 미확정 + 추가 확인 질문 제시 비율 | D 사건 + `compound_fault` 4 | `[기존]` D 사건 불확실성 표현 95 % | ≥ 0.95 `[잠정]` (기존 기준 유지) | 기존 확장 | 3주차 | 전혜민 |
| M-15 | 안전 보류율 | `safety_withhold` 정답 사건에서 실제 보류·승인 요구한 비율 | `safety_withhold` 4 + 안전 서브셋 15 | — | 1.00 `[잠정]` (타협 없음) | **신규** | 3주차 | 허재원 |
| M-16 | 행동 후보 Top-k 적합도 | `true_actions`와 `action_kind`+대상 장비가 일치하는 후보가 상위 k에 있는 비율. k=3 기본 | 봉인 질의 28 | — | Top-3 ≥ 0.65 `[잠정]` | **신규** | 3주차 | 최재영 |
| M-17 | 결과·재발 통계 정확도 | 시스템이 집계한 (해결률, 재발률)과 원장 정답 집계의 절대 오차. `observing`·`unconfirmed` 제외 여부 포함 | 전체 원장 | — | 절대 오차 0 (코드 집계이므로 정확 일치 요구) | **신규** | 3주차 | 유현준 |
| M-18 | 개정 근거 누락률 | 개정 후보 중 `basis_event_ids` 2건 이상 + 근거 카드 1건 이상을 갖추지 못한 비율 | 개정 후보 5 | — | 0 % | **신규** | 3주차 | 전혜민 |
| M-19 | 승인 전 개정 검색 반영 | `state != published` 개정 내용이 검색 결과·응답에 등장한 건수 | 봉인 전체 + 회귀 테스트 | — | **0건** (QC-PUB-03로 구조 보장) | **신규** | 3주차 | 허재원 |
| M-20 | 구버전·미승인 발행 차단율 | 차단해야 할 발행 시도 중 실제 차단된 비율(기준 버전 불일치·해시 불일치·미승인) | 주입 시험 12건 `[제안값]` | — | 1.00 | **신규** | 3주차 | 유현준 |
| M-21 | 미래 정보 누수 | 카나리 토큰 발견 건수 + `as_of` 위반 건수 | 전체 로그 | — | **0건** | **신규** | 2·3주차 | 최재영 |
| M-22 | 판단 변화 지표(선택) | 카드 제시 전후 사용자 선택 변화율 | — | `[기존]` 전문가1 D-35, 승인 대기 | **MVP 미측정** — 사람 피험자 실험이 필요하고 일정·윤리 절차가 없다 | 승인 대기 | — | — |

`[기존 유지]` M-01~M-10은 4.9의 지표를 삭제 없이 옮긴 것이다. M-03만 목표치 문장을 바꾸자는 제안이며 B12 D-B07에 등록했다.

## B10-3. 목표치 하향 제안의 근거 정리 `[기존 수정안]`

옵션3(봉인 42문항)을 택하면 **기존 목표치를 그대로 두는 것이 오히려 부정직**해진다.

| 기존 목표 | 문제 | 제안 |
| --- | --- | --- |
| Recall@5 ≥ 0.8 | 42문항에서 0.8 관측 시 CI [0.66, 0.90]. "0.8 달성"이라고만 쓰면 실제 0.66일 수 있다 | 목표는 0.70으로 낮추고 **관측값 + 95 % CI를 항상 병기**한다 |
| 조건 불일치 ≤ 5 % | 42문항 위반 0건에서도 상한 6.9 %. 5 % 주장 불가 | ≤ 10 %로 수정하고, 60문항(옵션1)을 택할 경우에만 5 % 유지 |
| 안전 금기 누락 0건 | 서브셋 12~15건의 0건은 참 누락률 18~22 %와 양립 | 0건 유지(타협 불가) + **"이 표본에서 0건, 95 % 상한 18 %"를 함께 표기** |
| 지식 없음 처리 ≥ 0.95 | `normal` 7건 + 결손 질의로는 분모가 10~15건. 0.95는 1건 실패도 허용 안 됨 | 0.90으로 낮추고 분모를 명시 |

`[신규 제안]` 발표·문서 표기 규칙: **모든 비율 지표는 `값 (n=분모, 95 % CI [하한, 상한])` 형식으로만 쓴다.** 점추정만 쓰는 문장을 금지한다. 이것이 합성 데이터 과장 방지의 가장 실효적인 장치다.

## B10-4. 기준선 재정의 (생산시스템 관점) `[기존 확장 + 신규 제안]`

`[기존]` (0) 모델 단독 / (1) 매뉴얼만 검색 / (2) 지식 카드 포함 검색 / (3, 선택) 형식 SFT / 인계 모드는 규칙 Baseline 추가. **전부 유지.**

`[신규 제안]` 관계 기반 검색의 효과를 분리 측정하기 위해 (2)를 두 단계로 쪼갠다.

| 기준선 | 구성 | 무엇을 분리 측정하는가 |
| --- | --- | --- |
| (0) | 모델 단독, 검색 없음 | `[기존]` |
| (1) | 매뉴얼 절만 검색(FTS5/벡터), 카드·관계 없음 | `[기존]` |
| **(2a)** | **카드 포함 검색 + 해당 장비만** (관계 탐색 끔, `hop_distance=0`) | `[신규 제안]` **카드의 효과**만 |
| (2b) | 카드 포함 검색 + **관계 1-hop 확장** | `[신규 제안]` 관계 탐색의 1차 효과 |
| (2c) | 카드 포함 검색 + **관계 3-hop 확장**(운영 구성) | `[신규 제안]` 깊은 탐색의 추가 이득과 잡음 |
| (3, 선택) | 형식 SFT 적용 | `[기존]` |
| (H) | 인계 모드 규칙 기반 Baseline | `[기존]` |

- **(2a)가 없으면 "관계 기반 검색이 효과 있다"를 주장할 수 없다.** 현재 기준선 (1)→(2)만으로는 카드 추가 효과와 관계 확장 효과가 섞인다. (2a)는 (2c)와 같은 카드·같은 인덱스를 쓰고 **탐색 범위만** 다르므로 구현 비용이 거의 없다(`max_hop=0` 플래그).
- 관계 효과의 주 측정 지표는 M-11(범위 식별)·M-01(Recall@5)·M-16(행동 후보 Top-k)이며, `upstream_cause`·`downstream_block`·`common_utility` 세 유형에서 (2a) vs (2c) 차이를 본다. 이 세 유형만 봉인셋에서 최소 각 4문항 `[제안값]` 확보해야 부호검정 불일치 쌍 확보가 가능하다(합계 12문항).
- **잡음 위험도 함께 보고** `[신규 제안]`: 3-hop 확장은 M-03(조건 불일치 오적용)과 M-12(인용 정확도)를 **악화**시킬 수 있다. (2a)→(2c)에서 M-11이 올라가고 M-03이 나빠지는 교환 관계를 표로 제시하는 것이 정직한 보고 방식이다.

---

# B11. 대표 완성 사건 3건 — 데이터 인스턴스

전문가A가 도메인 서사를 담당하므로 이 절은 **B1 스키마에 정확히 맞는 JSON 레코드**만 제공한다. 모든 수치에 `[가상 값]` 주석을 붙였고, 파일 안에서 ID가 서로 맞물린다.

| 파일 | 내용 |
| --- | --- |
| `/home/claude/experts/B_samples/00_plant_and_relations.json` | 공통 기준정보 — 시드 8건(SD-001~008), 라인 1, 구간 4, 설비군 8, 장비 유형 6, **개별 장비 10대**, 부품 18, **관계 20건**(핵심 18 + 선택 2), 매뉴얼 문서 6·절 8, 페르소나 3명(확장 필드 포함), 원형 5건 |
| `/home/claude/experts/B_samples/01_kb_cards_shared.json` | dev·sealed 사건이 정답으로 참조하는 kb 카드 3장(T5 CV, T3 CV, T5 HPU) + 그 출처 kb 사건 2건 |
| `/home/claude/experts/B_samples/EV-0031_upstream_cause.json` | **시나리오 1 상류 원인** (split=`kb`, 원형 `PT-0003`) — 컨텍스트, 사건, 관측 7, 장비 링크 6, 행동 후보 5, 실제 조치 2, 결과 1, 재발확인 1, 선행 사건 1, 카드 7(상충 쌍 `CG-0001` 포함), 인계 1, 개정 `RV-0001`→승인 `AP-0001`→발행 `PB-0001`, 평가 문항 형식 예시 |
| `/home/claude/experts/B_samples/EV-0032_downstream_block.json` | **시나리오 2 하류 정체** (split=`dev`, 원형 `PT-0007`) — 관측 7, 링크 6, 후보 4(조건 불일치 보류 1·T5 1), 조치 2, 결과 1, 재발확인 1, 선행 사건 1, dev 카드 1, 인계 1, 개정 `RV-0002`(승인됨·**미발행**), 평가 문항 2 |
| `/home/claude/experts/B_samples/EV-0033_common_utility.json` | **시나리오 3 공통 유틸리티** (split=`sealed`, 원형 `PT-0011`) — 관측 10, 링크 9, 후보 5(안전 보류 1·근거 부족 보류 1), 조치 2, 결과 1(`observing`), 재발확인 1(`not_checked`), 선행 사건 1, sealed 카드 1, 인계 1, 개정 `RV-0003`→승인→발행→**복구 발행 예시**, 평가 문항 3 |

## B11-1. 검증 결과

샘플 5개 파일에 대해 참조 무결성·분할 상속·원형 분할 검사를 실제로 돌렸다.

| 검사 | 결과 |
| --- | --- |
| JSON 유효성 | 5/5 통과 |
| ID 총수 | 218개 |
| 미해결 참조(dangling FK) | 0건 (설비군 `code` 값은 ID가 아니므로 제외) |
| 분할 상속(카드 `split` = 출처 사건 `split`) | 위반 0건 |
| 원형–분할 일치(`Event.split` = `EventPrototype.assigned_split`) | 위반 0건 |

**샘플의 의도적 한계** — 선행 사건(`prior_event_compact`)과 kb 출처 사건의 `context_id`는 `null`로 두고 `_context_note`를 달았다. 실제 데이터셋에서는 필수이며 `null`이면 QC-REF-01 위반이다.

## B11-2. 각 시나리오가 검증하는 지점

| 시나리오 | 데이터로 심어둔 채점 지점 |
| --- | --- |
| EV-0031 | 상류 `hop_distance=2` 경로(`REL-0006`→`REL-0002`) 식별 / 압력 정상(OB-0106)으로 HPU를 `checked_no_finding`으로 강등 → PH-02·QC-CAUSE-01 / `improved`이며 `resolved` 아님 → 성공 과대집계 방지 / `conflict_group=CG-0001` 복수 의견 / V-01의 축약 인계로 인한 누락 3항목 |
| EV-0032 | 인터록 역방향 1-hop 식별 / **전류 하한 미달**이라 K-0102(상한 초과 조건)를 제외해야 함 → M-13 / `co_occurrence` 관계(REL-0019)를 원인 후보로 올리지 않음 → QC-CAUSE-02 / **승인만 되고 미발행**인 `RV-0002`가 검색에 나타나면 M-19 실패 |
| EV-0033 | 공통 유틸리티 1-hop 다중 영향 4장비 식별 / 전력·공압 배제(OB-0309·0310) / 가압 상태 필터 교체 **보류**가 정답 → M-15·M-04 / `result_status=observing` → 성공 집계 제외 / `not_checked` 재발 판정 / 발행 v1.1 → 복구 v1.2로 답변이 두 번 바뀜 / `as_of`(23:35) 이후 정보가 응답에 나오면 M-21 실패, 카나리 `zzk9-ev0033-5e7b` 검출 시 누수 실패 |

---

# B12. 기존안 대비 변경 제안표

| ID | 기존 항목(절·인용) | 기존 상태 | 변경 제안 | 이유 | 영향 | 결정 필요 |
| --- | --- | --- | --- | --- | --- | --- |
| D-B01 | 4.7.7 규모: "사건 원장 120건 = kb 70 / dev 20 / sealed 30" (승인 #5) | 승인 | **사건 72건 = kb 42 / dev 12 / sealed 18** (옵션3) | 신규 엔티티 13종이 사건마다 붙어 사건 1건 검수 시간이 커졌다. 옵션1은 검수 공수 46.7h로 가용 34.5h를 135 % 초과(B5-2) | 검수 공수 30.5h(88 %)로 내려와 2주차 말 봉인 가능. 반면 지표 신뢰구간이 ±10 pp→±12 pp로 넓어짐 | **예 — B13 Q1** |
| D-B02 | 4.7.7 "지식 카드 K-01 채택 150건 이상(생성 250건), T별 최소 20, T5 최소 25" | 승인 | **채택 80건 이상(생성 130), T별 최소 14, T5 최소 16** | 위와 동일. 커버리지 매트릭스 빈칸 0은 유지하므로 T×설비 조합은 그대로 덮인다 | 카드 검수 560분→292분. 카드 다양성(distinct-2)은 유지 필요 | **예 — B13 Q1** |
| D-B03 | 4.7.7 "산출물 5종 채택 400건 이상(Q&A 150·메모 80·인계 60·트러블슈팅 60·규칙 50)" | 승인 | **채택 220건 이상(Q&A 80·메모 45·인계 35·트러블슈팅 35·규칙 25)** | 산출물은 카드 파생물이라 지표 기여가 가장 낮다. 축소 순서 1번(B5-5) | 지표 영향 거의 없음. 발표용 "규모" 인상은 약해짐 | **예 — B13 Q1** |
| D-B04 | 4.7.7 "봉인 평가셋 60건 = 질의 36 + 인계 24, 안전 서브셋 12건" | 승인 | **42건 = 질의 28 + 인계 14, 안전 서브셋 15건** (안전 서브셋은 12→15로 **증가**) | 봉인셋은 통계적 하한이 있어 가장 나중에 줄여야 한다. 안전 서브셋 12건의 0건 관측은 참 누락률 22 %와 양립하므로 오히려 늘려야 한다(B5-3) | Recall@5 오차 ±10→±12 pp. 안전 지표 상한 22 %→18 % 개선 | **예 — B13 Q1** |
| D-B05 | 4.7.7 "개발 채점셋 30건(dev 사건 기반)" | 승인 | **18건** | 위와 동일 비례 축소. 반복 채점 목적이므로 정밀도 요구가 낮다 | 개발 중 지표 추세 판단이 다소 거칠어짐 | 예 |
| D-B06 | 4.7.4 "Event: `event_id, scenario, equipment(단일), timeline[], true_cause, true_actions[], measurements{}, cards_expected[], split`" | 사실 | 9필드 **전부 유지**하고 `prototype_id`·`context_id`·`primary_equipment_id`·`case_type`·`cause_confidence` 등 18필드를 **추가**. `equipment`는 설비 유형(단일)로 의미 보존하고 다중 장비는 `EventEquipmentLink`로 표현 | 사용자 요구 "하나의 사건에 여러 장비 연결"을 기존 단일 필드 변경 없이 만족시킨다 | 기존 정답지·코드 호환 유지. `measurements{}`는 `context.measurements[]`의 파생 요약으로 자동 생성 | 예 |
| D-B07 | 4.9 "조건 불일치 카드 오적용 — 봉인셋 기준 5 % 이하" (미결 #6) | 목표치 승인 대기 | **≤ 10 %로 수정**(옵션3 채택 시). 옵션1(60건) 유지 시에만 5 % 존치 | 위반 0건을 관측해도 42건에서는 95 % 상한이 6.9 %, 18건에서는 15.3 %다. 5 % 주장에는 59건 이상이 필요(B5-3 계산) | 목표를 낮추는 것이지만, 낮추지 않으면 통계적으로 근거 없는 문장을 쓰게 된다 | **예 — B13 Q2** |
| D-B08 | 4.9 "Recall@k — k=5에서 0.8 이상" / "근거 충실도 0.9" / "지식 없음 처리 0.95" (미결 #6) | 목표치 승인 대기 | **개발셋 측정 후 봉인 전 고정**으로 절차를 바꾸고, 모든 비율 지표를 `값 (n=분모, 95 % CI [하한, 상한])` 형식으로만 표기 | 사용자 요구 "합격 수치는 개발셋 측정 후 봉인 평가 전에 고정". 점추정만 쓰면 과장이 된다 | 기존 수치는 "기존 설계 목표(미승인)" 열에 남긴다. 사후 조작 방지 장치는 B10-1 | **예 — B13 Q2** |
| D-B09 | 4.9 기준선 "(0) 모델 단독 / (1) 매뉴얼만 / (2) 지식 카드 포함 / (3, 선택) 형식 SFT" | 사실 | (2)를 **(2a) 해당 장비만(관계 탐색 끔) / (2b) 관계 1-hop / (2c) 관계 3-hop**으로 분해. (0)(1)(3)·규칙 Baseline은 유지 | 관계 기반 검색이 이 고도화의 핵심 가설인데, 현 기준선으로는 카드 효과와 관계 효과가 섞여 측정 불가 | 구현 비용은 `max_hop` 플래그 1개. 채점 실행 횟수는 봉인셋당 3회 증가 | **예 — B13 Q3** |
| D-B10 | 4.7.6 "분할은 사건 단위 … 동일 원문·설비·사건 템플릿에서 파생된 데이터는 하나의 그룹으로 분할한다" | 사실 | 그룹 키를 명시 엔티티 `EventPrototype`(`PT-xxxx`)로 만들고 **분할을 원형 단위로 먼저 배정**, 사건이 상속. `splits/prototype_split.json`도 봉인 대상에 포함 | 현재는 그룹 키가 데이터에 없어 누수 검사를 자동화할 수 없고, "분할을 나중에 바꿨다"는 의심을 반박할 수 없다 | P2.5 단계 신설. 검사 QC-LEAK-01 자동화 가능 | 예 |
| D-B11 | 4.7.1 P0~P6 7단계 | 사실 | 번호를 깨지 않고 **P1.5(관계·매뉴얼), P2.5(원형·분할), P3.5(행동·결과·인계·개정)** 3단계 신설 | 신규 엔티티 13종을 기존 단계에 밀어넣으면 P3이 과대해지고 재개 지점이 사라진다 | CLI 재개 지점 7→10개. `all`·`from P3` 인터페이스는 그대로 | 예 |
| D-B12 | 4.7.4 "`equipment`(HPU/GR/RT/CV/COMMON)" | 승인(#3 필수 필드) | enum **불변**. 신규 장비 유형 `PDP`(전력 배전반)·`CAU`(공압 유닛)은 `EquipmentType.type_code`에만 추가하고 카드의 `equipment`는 `COMMON`으로 매핑 | 사용자 요구 "유압·전력·공압 공급" 관계를 표현하려면 공급원 장비가 필요한데, 승인된 K-01 enum은 건드리지 않는다 | 장비 8대→10대. 승인 #1의 "HPU·GR·RT·CV 범위"는 물류·구동 설비 기준으로 유지 | **예 — B13 Q4** |
| D-B13 | 4.7.3 페르소나 "V-01~V-03 3명", V-03 담당 "공용(교대 조장)" | 사실 | V-04 신설하지 않고 **V-03의 `equipment_focus`를 공용(HPU·PDP·CAU 포함)으로 확장**. `segment_focus`·`relation_bias`·`hop_habit`·`stop_restart_experience`·`handover_style`·`co_occurrence_confusion` 6필드 추가 | 신규 유틸리티 장비에 담당자가 없어진다. V-04 추가는 카드 생성 +20 %·검수 +2.5h로 옵션3 버퍼를 소진 | 기존 3명 구성·상충 규칙 불변 | 예 |
| D-B14 | 4.7.5 품질 게이트 9개 검사 | 사실 | 기존 9개 **전부 보존**하고 규칙 단계에 **48개 신규 검사(QC-REF/REL/CAUSE/TIME/LEAK/CTX/PH/ACT/REC/MAN/REV/PUB/ISO/BAL)** 추가. 처리 구분에 **수정 큐**를 신설(폐기 vs 수정) | 신규 엔티티의 정합성은 기존 9개 검사로 잡히지 않는다. 서술 문제까지 전부 폐기하면 채택률이 급락한다 | 구현 공수 증가(대부분 난이도 하~중). 채택률 가정 60 %를 재검토해야 할 수 있다 | 예 |
| D-B15 | 4.7.6 "생성 모델 ≠ judge 모델 ≠ 온디바이스 추론 모델" / 4.7.8 EXAONE judge와 플랜 C 충돌(미결 #10) | 승인·조합 미결 | 이 문서는 **모델 ID를 정하지 않는다.** 다만 judge에 **관계·시간·인과 판정을 맡기지 않는다**는 제약을 추가: 이들은 전부 코드 검사(QC-REL/TIME/CAUSE)로 처리하고 judge는 기존 4항목(근거 타당성·조건 명시성·페르소나 일관성·안전)만 본다 | 사용자 원칙 "권한·상태 전이·통계·ID 검사는 코드, LLM은 추출·설명·초안만". judge를 늘리면 #10 충돌이 커진다 | judge 호출량 증가 없음. #10 결정과 독립적으로 진행 가능 | 예 |
| D-B16 | 4.7.5 "사람 검수: 봉인 평가셋 100 %, T5 100 %, 나머지 20 % 층화" | 사실 | 기존 규칙 유지 + **사건 35 % 층화**, 관계·매뉴얼·개정 후보 **100 %** 추가 | 사건은 신규 엔티티 6종을 묶는 허브이므로 카드와 같은 20 %로는 부족하다. 관계·매뉴얼은 건수가 적고 전체 구조의 뼈대다 | 검수 공수 계산(B5-1)에 이미 반영 | 예 |
| D-B17 | 4.10 "검색 대상 = `status=accepted AND split=kb AND grade=L1`" | 사실 | **유지**하고 조건 2개 추가: 매뉴얼 절은 `published_at ≤ as_of`인 발행 버전만, 개정안은 `state=published AND searchable_after_publish=true`만 | 사용자 요구 "승인 전 개정 검색 반영 0건"을 규칙이 아니라 검색 조건으로 보장한다 | M-19가 구조적으로 0건이 된다. 검색 질의에 `as_of` 파라미터 필수화 | 예 |
| D-B18 | 6.2 D-29 `T6_setup_restart`·`tried_and_failed[]` (승인 대기, U-7: 1주차 미결정 시 미채택) | 승인 대기 | `tacit_type` enum은 **확장하지 않고**, 재가동 맥락을 `context_conditions`의 `stop_restart_state`로 표현. `tried_and_failed[]`·`stop_conditions[]`·`expected_result`·`valid_until`·`verifier`는 **선택 필드로만** 추가하고 필수화·채점 반영은 하지 않음 | D-29와 미결 #16을 승인된 것으로 취급하지 않으면서, 승인되면 곧바로 쓸 수 있는 자리를 만든다 | enum 변경 없음 → 정답지·커버리지 매트릭스 개정 불필요 | 예(1주차 스키마 확정 시) |
| D-B19 | 4.7.10 "재현성 시연: 저장된 `raw/` 재생 + 결정적 후처리 해시 검증" | 사실 | **유지**하고 결정성 범위를 명시: P1·P1.5·P2·P2.5는 완전 결정적(LLM 없음), P3·P3.5의 수치·ID·시각·판정은 결정적, 서술문만 비결정적 | 기존 문장은 "seed만으로 바이트 동일성 보장 안 함"까지만 말한다. 어디까지 결정적인지 명시하면 발표에서 더 강한 주장을 정직하게 할 수 있다 | 데이터 카드에 결정성 범위표 1개 추가 | 아니오(문서 보강) |
| D-B20 | 4.11 `dataset_version` 컬럼 `version, split, record_count, manifest_sha256, sealed_at, sealed_by` | 사실 | **유지**하고 `entity_counts{}`·`split_rule_version` 2컬럼 추가 | 신규 엔티티 13종 건수와 분할 규칙 버전이 기록되지 않으면 봉인 증빙이 불완전하다 | MySQL 스키마 1회 변경. 가상 데이터·ID·해시·메타 한정 원칙은 불변 | 예 |
| D-B21 | 6.2 D-35 "카드 제시 전후 판단 변화 지표" (승인 대기) | 승인 대기 | **MVP 미측정으로 명시.** 사람 피험자 실험 설계·시간이 없다 | 측정하지 않은 것을 지표표에 남겨두면 미측정을 측정한 것처럼 읽힐 위험이 있다 | 지표표 M-22에 "MVP 미측정" 상태로 기록 | 예 |

---

# B13. 결정이 필요한 질문

| # | 질문 | 배경 | 선택지 | 각 결과 | 추천 |
| --- | --- | --- | --- | --- | --- |
| **Q1** | **데이터 규모를 옵션1·2·3 중 무엇으로 확정하는가?** | 승인 #5(사건120·카드150·산출물400·봉인60·개발30)와 사용자 신규 제안(사건30~50·카드20~40·봉인15~20)이 충돌. 검수 공수는 전혜민 1명 + 팀 보조 = 34.5h `[가정]`이 상한 | ① 승인 #5 유지 ② 사용자 제안 ③ 절충(사건72·카드80·산출물220·봉인42·개발18) | ① 검수 46.7h(135 %) → 2주차 말 봉인 지연 위험, 지표 정밀도는 최선 ② 검수 17.4h(50 %) → 여유롭지만 봉인 18건으로는 조건 불일치 ≤5 %·기준선 유의성 주장 불가 ③ 검수 30.5h(88 %) → 빠듯하나 가능, 지표는 ±12 pp | **③ 옵션3.** 단 봉인 평가셋과 T5는 축소 대상에서 제외(B5-5) |
| Q1b | 사용자 제안의 "봉인 평가 15~20"은 **사건 수**인가 **문항 수**인가? | 기존안은 사건 30건에서 문항 60개(사건당 2문항)를 뽑는 2단 구조인데 사용자 제안은 단위가 불명확 | ① 문항 수 ② 사건 수 | ① 봉인 문항 18개 → 지표 대부분 주장 불가 ② 사건 18건 → 문항 36~42개 확보 가능 | **② 사건 수로 해석.** 옵션3이 이 해석과 일치 |
| **Q2** | **평가 목표치를 언제·누가 고정하는가? 기존 #6 수치는 어떻게 처리하는가?** | 사용자 요구 "합격 수치는 개발셋 측정 후 봉인 평가 전에 고정". 기존 #6(Recall@5 ≥ 0.8 등)은 승인 대기 상태 | ① 기존 #6 수치를 그대로 승인 ② 지표 정의만 먼저 봉인(v0)하고 수치는 10/12 봉인 직전 고정(v1), 기존 수치는 "기존 설계 목표(미승인)"로 병기 | ① 42문항에서 5 %·0.8 주장이 통계적으로 성립하지 않아 과장이 된다 ② 사후 조작 의심을 Git 태그 2개와 정의/수치 분리 봉인으로 반박할 수 있다 | **② B10-1 절차.** 모든 비율 지표는 `값 (n, 95 % CI)` 형식으로만 표기 |
| **Q3** | **기준선에 (2a) 관계 탐색 없는 검색을 추가하는가?** | 현 기준선 (1)→(2)는 카드 효과와 관계 탐색 효과가 섞여 있어, 이번 고도화의 핵심 가설을 측정할 수 없다 | ① 기존 4단 유지 ② (2a)/(2b)/(2c) 3분할 추가 | ① "관계 기반 검색이 효과 있다"를 데이터로 말할 수 없다 ② 채점 실행이 봉인셋당 3회 늘지만 구현은 `max_hop` 플래그 1개 | **②.** 단 3-hop이 M-03·M-12를 악화시키는 교환 관계도 함께 보고 |
| **Q4** | **전력(PDP)·공압(CAU) 장비를 추가하는가?** | 사용자 요구 묶음2에 "유압·전력·공압 공급" 관계가 있으나 승인 #1의 설비 범위는 HPU·GR·RT·CV 4종 | ① 추가 안 함(유압만) ② 장비 유형에만 추가하고 K-01 `equipment` enum은 불변(COMMON 매핑) ③ K-01 enum까지 확장 | ① 공통 유틸리티 시나리오에서 "전력·공압 배제" 판단을 만들 수 없다 ② 승인 #1·#3을 건드리지 않고 관계 3종 확보. 장비 10대 ③ 정답지·커버리지 매트릭스 전면 개정 필요 | **②(D-B12).** 장비는 10대로 늘리고 카드 enum은 건드리지 않는다 |
| **Q5** | **`co_occurrence` 관계를 데이터에 넣는가?** | 사용자 판단 원칙 "인과와 동시 발생을 구분한다"를 데이터로 표현하려면 구분 대상이 있어야 한다 | ① 인과 관계만 저장 ② `causality` 필드로 구분해 둘 다 저장(원인 확정 금지 규칙 포함) | ① 원칙이 문서에만 남고 검증할 데이터가 없다 ② 관계 1건 추가로 QC-CAUSE-02를 시험할 수 있다(EV-0032의 REL-0019가 예시) | **②.** `co_occurrence`는 1~2건만 두고 `cause_candidate` 부여를 코드로 차단 |
| **Q6** | **매뉴얼 개정 근거 사건 최소 건수를 2건으로 할 것인가?** | 사용자 요구 "반복 사건 분석 → 매뉴얼 개정안". "반복"의 최소 기준이 필요하다. 옵션3에서 개정 후보 5건 × 근거 2건 = 사건 10건이 개정 근거에 묶인다 | ① 1건 허용 ② 2건 이상 + 1건 이상 `result_status=confirmed` ③ 3건 이상 | ① 단발 사건이 매뉴얼을 바꾸게 되어 "AI 답변을 성공 사례로 재집계"에 가까워진다 ② 반복성과 결과 확정을 모두 요구. 사건 72건에서 확보 가능 ③ 사건 72건에서 개정 후보 5건을 만들기 어렵다 | **②(QC-REV-03).** 재발 체인(`is_recurrence_of`)이 있으면 자동 충족 |
| **Q7** | **누수 카나리 토큰을 데이터에 남긴 채 봉인하는가?** | 카나리는 미래 정보 누수를 실제로 잡는 유일한 동적 장치이지만, `true_cause` 본문에 무의미 문자열이 남는다 | ① 검사 후 제거하고 봉인 ② 남긴 채 봉인하고 데이터 카드에 명시 | ① 채점 시점에 재검증할 수 없다 ② 정답지 텍스트에 이물이 남지만 채점 때마다 누수 검사가 가능하고 봉인 증빙이 강해진다 | **②.** 데이터 카드에 카나리 규칙과 예시를 명시 |
| **Q8** | **관계·설비 사전·매뉴얼을 kb 공용으로 두는 것이 누수가 아닌가?** | 관계 그래프는 정답 범위를 좁혀 준다. 그것이 이 프로젝트의 가설이기도 하다 | ① kb 공용(전제 조건으로 취급) ② 분할별로 관계를 나눔 | ① 현장 실제와 일치하고 구조가 단순하다. 단 기준선 (2a)가 없으면 관계 효과와 누수를 구별할 수 없다 ② 라인 구조가 분할마다 달라져 사건이 성립하지 않는다 | **①(B9-2) + Q3의 (2a) 기준선 필수.** 매뉴얼 절이 sealed `true_cause`를 서술하지 않는지 QC-LEAK-09로 검사 |
| **Q9** | **신규 엔티티 13종을 1주차 스키마 확정에 모두 넣는가?** | 1주차(9/29~10/5) 완료 기준에 "K-01·Event 스키마 확정"이 있다. 신규 엔티티까지 넣으면 1주차 부하가 커진다 | ① 전부 1주차에 확정 ② 핵심 6종(Relation, Context, Observation, EventEquipmentLink, ActionCandidate, Outcome)만 1주차, 나머지 7종은 2주차 초 | ① 1주차 지연 시 2주차 생산 전체가 밀린다 ② 개정·승인·발행 계열은 데모 후반부라 2주차 초로 미룰 수 있다. 단 ID·시간·visibility 규칙은 1주차에 전부 고정해야 한다 | **②.** ID 체계·시간 규칙·visibility 분류는 1주차 필수, 개정·승인·발행 스키마는 2주차 초 |
| **Q10** | **봉인 대상에 `splits/prototype_split.json`과 목표치 레지스트리를 포함하는가?** | 현 봉인 대상은 `sealed.jsonl`뿐이다 | ① 현행 유지 ② `sealed.jsonl` + `eval/sealed_items.jsonl` + `splits/prototype_split.json` + `eval/metric_registry.v1.yaml`을 각각 해시 + 루트 해시 | ① 분할과 목표치를 나중에 바꿨다는 의심을 반박할 수 없다 ② 봉인 절차가 4파일 2단 해시로 늘지만 증빙이 완결된다 | **②(B9-3).** 봉인 작업 시간 증가는 10분 이내 |

---

## 부록. 이 문서가 건드리지 않은 것

- 승인 #1(L1·HPU·GR·RT·CV 범위), #2(RAG 기본·형식 SFT), #3(K-01 필수 필드·grade), #7(SFT 선택), #8(생성 외부 API·judge 로컬), #12·#13(부제·포터블 MES 표현), #17(안전 담당·L2 불가), #21(라우터·도구 5종)은 그대로 두었다.
- 미결 #4(업로드 경로), #10(모델 조합), #11(GPU 검증), #15(T5 축소), #16(T1~T5 원 정의), #18(안전 근거 본문), #19(데모 연출), #20(임베딩 우선순위), #23, #24, RAM 89GB 확인은 **이 문서 범위 밖**이며 미결로 남긴다.
- 전문가1 D-26~D-37은 전부 승인 대기로 취급했다. D-29·D-34·D-35만 스키마 자리를 미리 비워 두었고(선택 필드·계보 필드), 승인 없이 필수화하거나 채점에 반영하지 않는다.
- 모델 ID·임베딩 모델·Jetson 실측값은 정하지 않았다. 전문가C 영역이다.
