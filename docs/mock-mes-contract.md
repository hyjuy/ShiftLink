# 모의 MES 공통 계약

모든 값은 합성 데이터이며 실제 설비 제어·물리 검증·MES 연동을 뜻하지 않는다.

## 상태 모델

- 런타임 `scenario_id`: `normal`, `drive_fault`, `downstream_block`, `hydraulic_fault`
- 지원 목적 `support_scenario`: 기존 `S1`, `S2`, `S3` 값과 분리한다.
- `Snapshot`의 식별자는 `(run_id, sequence)`이며 `simulated_at`은 런의 시작 시각과 tick으로 계산한다.
- `operating_state`와 `fault_level`은 독립이다. 예를 들어 하류 정체로 멈춘 정상 설비는 `waiting` / `normal`이다.
- `GroundTruth`는 평가 전용으로 저장하며 일반 API·관측 어댑터·내보내기에 노출하지 않는다.

## 로컬 HTTP API

조회·제어 응답은 JSON이며 `is_synthetic: true`를 포함한다. 내보내기는 JSONL 또는 CSV다.
`/api/state`는 Snapshot 필드와 현재 배속 `speed`를 반환한다. `/api/events`는 `run_id`와 `events`를 반환한다.
한 sequence에 여러 이벤트가 존재한다. 이벤트를 sequence 하나로 중복 제거하지 않는다.
서로 다른 응답의 run_id가 다르면 클라이언트는 이전 실행의 커서를 폐기하고 다시 조회한다.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/catalog` | 기준정보와 설비 ID |
| GET | `/api/state` | 현재 snapshot |
| GET | `/api/events?after_sequence=N` | N 이후 runtime events |
| GET | `/api/runs` | 저장된 런 목록 |
| GET | `/api/runs/{run_id}/replay?sequence=N` | 저장 snapshot 재생 |
| POST | `/api/control` | `start`, `pause`, `resume`, `reset`, `speed`, `scenario`, `recover` |
| GET | `/api/export?format=jsonl|csv` | 관측 기록 내보내기 |
| GET | `/api/config` | 활성 구성(route·layout·시나리오 포함) |
| GET | `/api/configs/{config_id}` | 저장된 구성(과거 런 재생용) |
| POST | `/api/config/validate` | 초안 검증: `{draft}` → `{valid, errors, diff}` |
| POST | `/api/config/apply` | 구성 적용: `{base_config_id, draft, reason, actor}` — 가동 중/기준 불일치는 409 |

잘못된 명령·시나리오·형식은 400, 없는 런·기록은 404, 서버 오류는 500을 반환한다. 기본 바인딩은 `127.0.0.1`이다.

재생 응답은 `snapshots`, `events` 배열과 `config_id`, `config_preserved`를 포함한다. `config_preserved=false`는 업그레이드 이전 런으로 당시 구성이 미보존임을 뜻한다. `sequence=N`은 N보다 큰 기록을 뜻한다. 전체 재생은 -1을 사용한다.
`/api/state`는 활성 `config_id`를 포함한다. 구성 적용은 안전한 런 경계에서만 수행되며(가동 중 hot swap 없음), 성공 시 이전 런을 보존하고 새 구성의 새 런을 만든다. 되돌리기는 이전 구성을 참조하는 새 런이다. 상세는 `docs/mock-mes-modularization.md` 참고.
내보내기에 `run_id`를 지정하면 해당 기록을 사용한다. 생략하면 현재 실행을 사용한다.
기록 재생 중에는 실시간 상태를 화면에 병합하지 않는다. 가상시각은 연결 상태 판단에 사용하지 않는다.
