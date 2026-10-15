# PDA 사건 연결과 지식카드 승격 현재 단계 검증

2026-10-15. [수용 계획](reusability-pda-card-flow-20261015.plan.md)의 구현 착수 전 기준선이다. 기존 조치 세션·초안 생성·수동 승격 기능을 활용하고, 사건 참조를 기존 저장 경로에 추가하는 방식으로 개발 범위를 좁힌다.

## 1 실행 결과

| 검사 | 결과 | 확인 범위 |
| --- | --- | --- |
| 기존 Python 검사 7개 파일 | 93 passed in 15.69s | 조치 단계·전후 관측·인계 원자성·초안 병합·수동 승격·질의·KB 로딩·판정기 장애 |
| tests/pda_resolution.cjs | PASS | 조치 입력·세션 payload·초안 안내·조치 칩 순서 |
| tests/mes_query_pda.cjs | PASS | 현재 PDA 질의 payload와 서버 응답 계약 |
| tests/pda_handover_copy.cjs | PASS | 인계용 MES 정보 선택과 중복 복사 방지 |
| 추가 진단 | 실행 관찰 6개와 소스 확인 1개 | 사건 ID 미지원·세션 조회/DB 재조회·반복 start·새 질문의 피드백 초기화 |

실행 명령:

~~~powershell
$env:PYTHONPATH = (Resolve-Path '.test-deps').Path
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m pytest -p no:cacheprovider tests/test_field_draft.py tests/test_field_card_promote.py tests/test_mes_query.py tests/test_mes_storage.py tests/test_mes_handover_http.py tests/test_card_loader.py tests/test_judge_unavailable.py -q

node tests/pda_resolution.cjs
node tests/mes_query_pda.cjs
node tests/pda_handover_copy.cjs

$env:PYTHONPATH = (Resolve-Path '.').Path + [System.IO.Path]::PathSeparator + (Resolve-Path '.test-deps').Path
python artifacts/reusability_baseline_probe.py
~~~

기본 Python의 pytest 누락은 기존 .test-deps를 사용해 해결했다. 새 패키지를 설치하지 않았다. 추가 진단 스크립트는 프로젝트 루트를 PYTHONPATH에 포함해 실행했다.

## 2 활용 가능한 현재 기반

- 서버 조치 세션을 session_id로 조회하고 완료 단계와 근거를 복원할 수 있다.
- 임시 SQLite를 닫고 다시 열어도 저장한 조치 단계가 유지된다.
- 인계·초안·세션 저장의 원자성과 재전송 중복 방지 검사가 통과했다.
- failed 기록의 신규 초안 미생성과 적합한 기존 초안의 반대 근거 병합 검사가 통과했다.
- 검수 대기 초안의 검색 제외, 수동 승격 및 KB 원복 검사가 통과했다.
- 판정기 장애 차단과 기존 질의 계약 검사가 통과했다.

## 3 직접 확인한 미구현 경계

| 경계 | 관찰 | 필요한 변경 |
| --- | --- | --- |
| 질의 HTTP 본문 계약 | query_service에 incident_id를 추가하면 ValueError가 발생한다. 오류는 query body must contain question and optional equipment_id, scan_id, k다. 이 관찰은 실제 HTTP 전송이 아닌 동일 서비스 입력 검증의 직접 호출이다. | 서버 요청 계약에 선택적 사건 참조 추가 |
| 내부 파이프라인 계약 | QueryRequest에 incident_id를 넣으면 extra_forbidden이다. | 첫 서버 연결에서는 incident_id를 모델 입력으로 전달하지 않고 서버 메타데이터로 관리 |
| 사건 저장 | 새 임시 DB에 incidents 테이블이 없다. | 사건의 대상 설비·자산·구성·상태와 기록 참조를 저장 |
| 조치 시작과 이어가기 | 같은 설비에서 resolution_start를 두 번 호출하면 서로 다른 세션이 생성된다. 기존 ID 조회는 가능하다. | 사건의 기존 세션을 명시적으로 선택·조회 |
| 질문 간 카드 피드백 | sendChat의 S.tries 초기화가 소스에 있다. 실제 브라우저 조작 재현은 이번에 수행하지 않았다. | PDA가 사건별 서버 이력을 조회하고 새 질문에서 해당 이력을 유지 |

세션이 복원된다는 것은 사건이 자동 연결된다는 뜻이 아니다. 새 세션 생성과 기존 세션 이어가기는 구분한다.

## 4 권장하는 다음 차례의 최소 변경 범위

| 파일 | 변경할 내용 |
| --- | --- |
| shiftlink/mes/storage.py | 사건 저장과 조회, 기존 질의·세션·인계와의 참조. 이전 DB를 보존하는 추가 방식의 이전 |
| shiftlink/mes/server.py | 사건 생성·조회 API, 세션·인계의 사건 대상 검증, 원자적 저장과 재전송 보장 유지 |
| shiftlink/mes/query.py | 선택적 incident_id 수용·검증과 응답/기록 연결. 기존 호출과 모델 입력 형식 유지 |
| tests/test_mes_incidents.py 제안 | 사건 생성·조회, 대상 불일치, 세션 연결, 재시작·기존 DB 이전 검사 |
| 기존 질의·조치·저장 검사 | 사건 참조 유무 모두에서 기존 동작·중복 방지·원자성 유지 확인 |

파이프라인에 사건 ID를 새로 노출해야 하는 요구가 생기기 전에는 agent/router.py와 SFT 모델을 변경하지 않는다. 이전 시도 맥락을 답변 판단에 반영하는 작업은 후속 적용성 단계에서 별도 계약으로 다룬다.

## 5 다음 차례 이후의 변경 범위

| 차례 | 제품 파일 | 완료할 결과 |
| --- | --- | --- |
| PDA 사건 이어가기 | shiftlink/mes/web/pda.js, pda.html | 새 사건/이어가기, 기존 세션·피드백 복원 |
| 기록 저장 안내 | pda.js, pda.html과 필요한 응답 필드 | 저장 전/완료·MES 결과·초안 처리·전송 대기 구분 |
| 검수·승격 고도화 | field_draft.py, storage.py, server.py, 수동 승격 도구와 필요한 검수 화면 | 사건별 근거 집계, 검토·배포 이력 |
| 다음 사건의 지식 활용 | retrieval.py, card_adapter.py, pipeline.py | 조건·실패·호환성에 따른 적용 사유 추적 |

이 범위는 개발 단위 제안이다. 구체적 API·필드·파일 수는 해당 차례의 실패 재현 테스트를 만들며 확정한다. 센서·영상·장비 서비스와 카드 데이터의 전면 교체는 필요하지 않다.

## 6 보존할 보장과 검증 한계

- 기존 호출에서 incident_id가 없어도 동작해야 한다.
- 사건의 설비·자산이 맞지 않으면 이전 근거를 섞지 않고 거절한다.
- 사건 연결을 추가해도 질의 당시 evidence, 센서 품질·단위·시각 검증과 안전 차단을 유지한다.
- 같은 사건의 여러 기록을 서로 독립적인 해결 사례로 집계하지 않는 검사는 승격 고도화 차례에 추가한다.
- 이번 테스트는 로컬의 임시 DB·모의 엔진·테스트용 파이프라인으로 실행했다. 실제 PDA 터치, Jetson SFT 응답 품질, 지속 운전과 지연 p50/p95는 측정하지 않았다.
- 15.69s는 93개 테스트 전체 실행 시간이며 제품의 답변 지연이 아니다.
- 추가 진단 전후 제품 파일 8개의 SHA-256이 일치했다. 이번 차례에는 제품 구현과 배포를 변경하지 않았다.

추가 진단: [스크립트](../../artifacts/reusability_baseline_probe.py), [결과 JSON](../../artifacts/reusability-baseline-probe-20261015.json).
