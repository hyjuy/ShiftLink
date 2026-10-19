# 근무일지 고장 기록의 사건 연결

2026-10-16 기준. 기존 근무일지 API에서 개별 `고장·정비` 기록에 사건을 생성하거나 명시한 사건을 이어 붙인다. 사건은 일지 원본과 해결 근거를 나중에 카드 후보로 연결하기 위한 기준이며, 사건 생성 자체가 해결 확인이나 카드 승격을 뜻하지 않는다.

[후속 구현인 근무일지 후보 연결과 하네스](work-report-reuse-harness-20261016.md)에서 현재 동작과 실행 방법을 확인할 수 있다.

## 구현 범위

- `POST /api/work-reports`와 근무일지 본문을 받는 `POST /api/handover`가 같은 저장 경로를 사용한다.
- `고장·정비` 기록마다 `INC-` UUID를 생성한다. `candidate=false`여도 고장 사건은 보존한다.
- 기록에 `incident_id`를 명시하면 기존 사건에 연결한다. 같은 설비라는 이유만으로 자동 병합하지 않는다.
- 대상 설비 집합과 실제 `asset_id`가 모두 일치해야 이어 붙인다. 다른 설비나 교체된 자산의 연결은 거절한다.
- 일지 원문과 사건·기록 연결을 하나의 SQLite 트랜잭션으로 저장한다. 오류가 나면 모두 취소한다.
- 동일 `handover_id`와 동일 본문 재전송은 같은 사건 ID를 반환한다. 다른 본문 재전송은 기존 409 충돌 처리를 유지한다.
- 기존 DB에는 새 테이블만 추가한다. 과거 일지에 사건을 소급 생성하지 않는다.
- `candidate`, 원인 확실성, 조치와 결과는 일지 원본 그대로 보존한다. MES가 검증한 해결로 바꾸지 않는다.

## API 계약

새 사건을 만들 때는 기존 근무일지 요청을 그대로 전송한다. 응답에 다음과 같은 연결 목록이 추가된다. `record_index`는 `work_report.records`의 0부터 시작하는 위치다.

```json
{
  "handover_id": "HO-EXAMPLE",
  "duplicate": false,
  "incidents": [{"record_index": 0, "incident_id": "INC-..."}]
}
```

기존 사건을 이어 쓰려면 해당 `고장·정비` 기록에 `incident_id`를 추가한다. 일지 전체의 최상위 필드가 아니다. 기존 기록을 수정하는 대신 새로운 `handover_id`로 후속 일지를 저장한다.

| 경로 | 반환 내용 |
| --- | --- |
| `GET /api/incidents?limit=30` | 최신 사건과 연결된 일지 기록, 최대 100건 |
| `GET /api/incidents/{incident_id}` | 대상 설비·자산, 생성 당시 설정 ID, 원본 일지 기록 이력 |
| `GET /api/work-reports` | 기존 일지 목록과 각 일지의 `incidents` 연결 |
| `GET /api/work-reports/{handover_id}` | 기존 상세와 `incidents` 연결 |

PDA 프록시는 기존 `/api/*` 전달 기능으로 새 조회 경로를 전달한다. 일지 원본 업로드 본문은 유지하며, 서버가 생성한 사건 연결은 현재 로컬 SQLite에 저장한다. 중앙 DB 사건 동기화는 후속 작업이다.

## 변경 파일

- [storage.py](../../shiftlink/mes/storage.py): 사건·기록 연결 테이블, 원자적 저장 및 조회.
- [server.py](../../shiftlink/mes/server.py): 기존 저장 API 연결, 사건 목록·상세 API.
- [work_reports.py](../../shiftlink/mes/work_reports.py): 선택적 사건 ID와 고장 유형 검증.
- [test_work_report_api.py](../../tests/test_work_report_api.py): HTTP 저장·조회, 프록시, 동시 재전송, 구버전 DB 및 오류 검증.

## 검증 근거

브랜치: `feat/work-report-incidents-20261015`.

- RED: 사건 연결 기능 부재로 신규 7개 테스트 실패, 기존 5개 통과. 체크포인트 `45f4f19`.
- GREEN: 초기 회귀 검사 75개 통과. 대상은 근무일지 API, MES 저장, 현장 카드 초안, 승격, 인계 HTTP 테스트다.
- 보강 검사: 동시 재전송과 구버전 DB 이관 검사를 추가한 뒤, 근무일지 API 14개 모두 통과. 구버전 DB 테스트의 임시 연결 미종료로 생긴 Windows 정리 오류를 고쳤다.
- 커버리지: 위 회귀 검사와 보강 검사를 합쳐 새로 추가한 실행문 52개 모두 실행됨. 전체 프로젝트 커버리지나 분기 커버리지 수치가 아니다.
- 기존 일지 업로드 본문 보존 및 Raspberry Pi 프록시를 통한 사건 상세 조회 통과.

테스트 실행에는 기존 `.test-deps`를 `PYTHONPATH`에 지정하고 `PYTHONDONTWRITEBYTECODE=1`을 사용한다.

```powershell
python -m pytest -p no:cacheprovider tests/test_work_report_api.py tests/test_mes_storage.py tests/test_field_draft.py tests/test_field_card_promote.py tests/test_mes_handover_http.py -q
```

## 다음 구현 순서

1. 사건과 질의 ID·검색 결과를 연결해 ‘적용 가능한 카드 없음’을 구분한다. 시스템 오류는 카드 없음과 분리한다.
2. 해결 일지의 후보 표시와 실제 해결 근거를 기존 카드 초안 생성 기능에 연결한다. 부족한 정보는 검토 항목으로 표시하고 MES 복구 근거를 지어내지 않는다.
3. PDA에서 사건 ID 표시·기존 사건 선택·이어가기를 제공한다.
4. 검토·승인·배포 후 새 질의에 카드가 검색되는 전체 흐름을 검증한다.

현재 변경은 첫 단계의 서버 저장 기반이다. 실제 카드 초안 생성 연결, 검토 화면, 검색 반영 및 장비 배포는 아직 포함하지 않는다. 기존에 수정 중인 PDA HTML·JavaScript는 이번 작업에서 변경하거나 커밋하지 않는다.
