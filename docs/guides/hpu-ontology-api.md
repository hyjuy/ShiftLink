# HPU 온톨로지 설명 API (4단계)

기준: 2026-10-24 로컬 구현. 운영 장비 배포와 PDA 화면 연결은 수행하지 않았다.
기존 질의·검색·답변에는 필드나 호출을 추가하지 않는다.

## 설정과 접근

MES 서버 프로세스에 아래 환경 변수를 명시한다. 기본 off이며 shadow 모드도 HTTP 조회를 열지 않는다.

```powershell
$env:SHIFTLINK_HPU_ONTOLOGY='explain'
$env:SHIFTLINK_HPU_ONTOLOGY_DB='D:\approved\copy.sqlite3'
$env:SHIFTLINK_HPU_ONTOLOGY_CATALOG='D:\approved\catalog.json'
$env:SHIFTLINK_HPU_ONTOLOGY_MANIFEST='D:\approved\manifest.json'
```

파일은 서버 관리자가 승인한 DB 복사본과 해당 자료의 카탈로그·manifest다.
HTTP 요청으로 경로를 지정할 수 없고, 현재 서비스 DB·현재 카탈로그로 자동 대체하지 않는다.
manifest의 `source_namespace`와 `config_catalog_hashes`는
[shadow 안내](hpu-ontology-shadow.md)의 계약을 따른다. 과거 구성과 카탈로그 결합을 확인하지 못하면
현재 해시를 임의로 채우지 않는다. 결합 미확인 사유가 응답에 남는다.

기존 `/api/admin/login`으로 발급한 관리자 Bearer 토큰을 사용한다.
작업자 역할은 이 원문 포함 API를 사용할 수 없다. 사건 ID만으로 조회할 수 없다.
토큰 만료·로그아웃 후에는 기존 계정 인증에 따라 차단된다.

```text
GET /api/incidents/<incident_id>/ontology?limit=100&offset=0
Authorization: Bearer <관리자 토큰>
```

승인 복사본에 있는 사건을 조회하므로 현재 운영 사건 목록과 일치한다고 가정하지 않는다.
`off`로 전환하면 새 라우트만 비활성화된다. CLI shadow는 기존 `--mode shadow`로 별도 실행한다.

## 응답과 페이징

응답에는 `schema_version`, `equipment_type`, `snapshot_hash`, `scope`, `nodes`, `edges`,
`unresolved`, `truncated`, `summary`, `page`가 있다.
`scope`는 출처 namespace와 사건 ID이며 HPU만 투영한다.
자산·관측·사건·조치·결과와 원본 참조, 누락·상충 사유를 기존 projector 그대로 반환한다.
작업자 이름 필드는 `worker_ref`로 참조하지만 관찰·조치 원문에는 개인정보가 있을 수 있으므로
응답을 공개 자료로 취급하지 않는다. HTTP 응답은 기존 서버의 `Cache-Control: no-store`를 사용한다.

`limit`은 1~100(기본 100), `offset`은 0~2000(기본 0)이다.
세 배열 각각에 같은 offset/limit를 적용한다. 따라서 한 페이지의 관계가 다른 페이지의 노드를
참조할 수 있으며 전체 그래프는 페이지를 합쳐 복원한다.
`page.totals`는 배열별 개수, `next_offset`은 다음 offset 또는 null이다.
두 번째 페이지부터 첫 응답의 `snapshot_hash`를 반드시 함께 보낸다.

```text
GET /api/incidents/<incident_id>/ontology?limit=100&offset=100&snapshot_hash=<첫 응답 해시>
```

요청마다 복사본을 읽어 투영하며 서버에 페이지 캐시를 저장하지 않는다.
해시가 달라지면 409로 거절하므로 첫 페이지부터 다시 조회한다.
`asset_id`는 선택적인 사건 내 자산 소속 확인 조건이며 개별 자산 필터가 아니다.
단일 사건에 속한 여러 HPU 자산은 같은 그래프에 포함될 수 있다.

원본 조회 상한은 일지·질의 각 30건, projector 상한은 노드 1000개·관계 2000개다.
상한 초과는 `truncated: true`로 표시한다. 페이지를 모두 받아도 원본 상한 초과분이 복원되지는 않는다.
미확인 관계를 추측 연결하지 않으며 `summary.unresolved_by_reason`와 `unresolved`에서 확인한다.

| HTTP 상태 | 의미 |
|---|---|
| 200 | 연결 결과 또는 미확인·부분 연결·잘림을 포함한 정상 진단 |
| 400 | 잘못된/중복/알 수 없는 인자, 후속 페이지의 해시 누락 |
| 401 | 관리자 인증 없음·만료·다른 역할 |
| 404 | 모드 비활성, 사건 없음, 자산 소속 조건 불일치 |
| 409 | 요청 해시와 재조회 결과 불일치 |
| 503 | 출처 설정·파일·투영 오류. 내부 경로나 예외 원문은 반환하지 않음 |

승인 복사본 읽기와 투영만 수행하며 업무 DB 쓰기·검색·모델·게시 호출은 없다.
API 요청 자체의 CPU/IO 비용은 있으므로 운영 부하·실제 장비 성능은 별도 검증 대상이다.
검증 기록은 [4단계 테스트](../testing/hpu-ontology-api-20261024.tdd.md)를 참고한다.
