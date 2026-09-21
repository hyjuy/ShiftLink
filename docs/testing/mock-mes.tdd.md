# Mock MES integration TDD evidence

Source: `docs/templates/mock-mes-development-template.md`. This integration suite was derived from its normal-operation, incident, recovery, replay/export, deterministic restart, and observation-isolation guarantees.

| Guarantee | Test | Type | Result |
| --- | --- | --- | --- |
| Normal operation, each of the three incidents, and recovery distinguish a self fault from an affected normal waiting device. | `test_normal_all_incidents_and_recovery_are_consistent` | integration | PASS |
| Identical run inputs produce the same terminal snapshot and events after a new engine is constructed. | `test_fixed_run_inputs_reproduce_after_engine_restart` | integration | PASS |
| Multiple state/API reads do not advance the shared engine; only a tick does. | `test_service_state_reads_do_not_advance_the_shared_engine` | integration | PASS |
| Stored snapshots/events replay and their JSONL/CSV exports have matching public record counts. | `test_persisted_replay_and_exports_match_public_runtime_history` | integration | PASS |
| Observer `as_of` output excludes later runtime records; observer and exports exclude evaluation-only ground truth. | `test_observer_and_exports_exclude_ground_truth_and_future_records` | integration | PASS |

## Evidence

- RED: `python -m unittest tests.test_mes_integration` initially ran four tests with one intended failure: persisted replay lacked `alarm_raised`. `set_scenario()` emitted the transition at a previously persisted sequence, so the storage primary key could not accept the corresponding snapshot again.
- GREEN: after the simulation owner deferred control/transition events to the next tick, `python -m unittest tests.test_mes_integration -v` ran five tests successfully.
- Broader MES check: `python -m unittest tests.test_mes_contracts tests.test_mes_engine tests.test_mes_storage tests.test_mes_server tests.test_mes_web tests.test_mes_integration -v` ran 25 tests successfully.
- Browser check: a local `python -m shiftlink.mes` run was opened at `http://127.0.0.1:8000`. The dashboard showed the synthetic-data notice, normal start, a hydraulic-supply fault with one alarm and affected waiting equipment, recovery, resumed normal running, and the event history. The browser check also exposed and led to fixes for the SQLite worker-thread write and the event-feed cursor.
- Initial pass had no installed pytest/coverage. The collaborative development pass below installs test-only dependencies locally and supersedes this limitation.

## 산업·UI·UX 협업 개발 검증 (2026-09-20)

- 산업: 실제 기준정보 소재 경로, 정지 설비 이동 금지, 설비당 코일 1개, 입출 수량 보존, 공급·구동 영향, 일시정지 중 고장 알람 유지.
- UI: 모바일 레이아웃, 소재 주경로와 보조설비 구분, 접을 수 있는 관계 목록, 차트·재생·내보내기 제어.
- UX: 같은 tick 다중 이벤트 유지, 새 run 커서 초기화, 오래된 run 응답 거부, 초기 조회 실패 재시도, 가상시각과 연결상태 분리. Node 실행 기반 행동 테스트 포함.
- 서버: 실제 HTTP 요청으로 제어/기록/내보내기/오류 응답 검증. SQLite 파일을 닫고 다시 연 서비스에서 이전 기록 동일성 검증.
- 최종 명령: PowerShell `$env:PYTHONPATH = '.test-deps'` 후 `python -m coverage run --source=shiftlink.mes -m pytest -q` → **75 passed**.
- `python -m coverage report -m` → **Python MES 91%** (589 statements, 54 missed). JavaScript 커버리지 비율은 포함하지 않는다.
- 실제 브라우저: 3개 코일 표시, 유압 이상 고장/대기/압력/알람/같은 tick 이벤트, 센서 SVG 추이, 복구 명령, 기록 재생 및 실시간 제어 비활성화, 새 실행 이벤트 초기화 확인.
- 390px viewport에서 문서 clientWidth=375 / scrollWidth=375로 가로 넘침 없음. 임시 viewport 설정은 복원했다.
- 최신 서버에서도 구동부 이상(GR-01 고장, RT-01/02 대기), 출측 정체(CV-01 고장, RT-03 대기), 고장 중 일시정지 시 알람 1개 유지까지 브라우저로 확인했다.
- 초기 병렬 작업 중 실행은 작성 중 UI 및 Windows 임시 폴더 권한으로 실패했다. 작성 완료 후 정상 권한 실행에서 전체 통과했다.
- 한계: 단순화한 가상 모델이며 관계 지연·압연 물리·실제 PLC를 검증하지 않는다. 화면의 기록은 전체 런을 한 번에 읽으므로 장기 운영 규모에 맞춘 페이지 처리는 미구현이다. 스크린리더 및 두 브라우저 실제 동시 부하 실험은 수행하지 않았다.
- 커밋·푸시·PR은 생성하지 않았다.
