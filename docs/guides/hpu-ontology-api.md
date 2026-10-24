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

## 5단계: 실제 인용 게시 카드 연결

관리자 인증·explain 모드·승인 복사본 설정은 그대로 사용한다.
`query_id`를 추가하면 해당 질의가 실제 인용한 검수 카드의 판본만 사건 설명에 연결한다.
파라미터를 생략하면 기존 4단계 그래프다. 자동 검색·판정·답변에는 이 연결을 사용하지 않는다.

```text
GET /api/incidents/<원본 사건 ID>/ontology?query_id=<저장된 질의 ID>
```

질의 이후 만든 승인 복사본이 필요하다. 복사본과 현재 서비스의 질의 payload·저장 시각,
출처 사건·자산·일지 원문이 일치해야 한다. 동일 ID만으로 서로 다른 데이터셋을 결합하지 않는다.
현재 서비스의 게시 상태를 검사하므로 복사본에 게시본이 남아 있어도 현재 반려 상태면 연결하지 않는다.
질의의 현재 사건과 카드가 유래한 사건은 다를 수 있으며, 대상은 카드의 명시적인 원본 사건이다.

새 질의 로그는 기존 최종 ticket 검증 잠금 안에서 실제 인용된 항목만 `publication_ticket`
내부 메타데이터로 함께 저장한다. 항목은 카드 ID·검수 리비전·내용 해시·설비 ID·자산 ID다.
응답에는 이 필드를 추가하지 않고 기존 로그를 수정하거나 과거 ticket을 추정해 채우지 않는다.
ticket이 없는 과거 인용은 `citation_revision_unverified`로 보류한다.

응답은 `CardVersion` 노드와 `DERIVED_FROM_INCIDENT` 관계를 추가한다.
카드 원문을 복제하지 않고 카드 ID·판본·검수 리비전·해시와 인용 질의 참조만 제공한다.
`publication_overlay`에는 확장 스키마 `shiftlink-hpu-publication-v1`, 질의 ID, 연결 카드 ID가 있다.
기존 노드·관계·원문은 유지한다. 전체 결과의 `snapshot_hash`와 요약은 확장 결과로 다시 계산한다.
페이지를 넘길 때 `query_id`와 `snapshot_hash`를 함께 유지한다.

게시 리비전·모델·prefix·청크·벡터·원문은 검색 경로와 동일한 순수 검증 함수를 재사용한다.
설명 API는 인덱스를 수리하거나 게시 상태를 쓰지 않는다. 연결 생성 후 같은 MES 잠금에서
ticket과 게시 행을 다시 확인하며 도중 반려·자산 변경 시 연결을 제거한다.

| 미확인 사유 | 의미 |
|---|---|
| `query_source_mismatch` | 승인 복사본과 서비스의 질의 내용·저장 시각 불일치 |
| `publication_not_current` | 반려·게시 보류·리비전/해시 변경·자산 교체 |
| `citation_revision_unverified` | 당시 실제 인용 ticket 없음 또는 현재 검수 판본과 불일치 |
| `publication_integrity_mismatch` | 게시 원문·청크·벡터·모델·manifest 검증 실패 |
| `publication_origin_mismatch` | 원본 사건·자산·일지 참조 또는 투영 원본 해시 불일치/상한으로 출처 제외 |
| `citation_snapshot_missing` | 인용 ID에 해당하는 저장 카드 스냅샷 없음 |
| `publication_changed` | 설명 생성 후 최종 ticket/게시 행 재확인 실패 |

질의가 어느 한쪽 DB에 없으면 404, 출처 조회 오류는 내부 정보를 숨긴 503이다.
관계 상한은 기존 노드 1000개·관계 2000개를 유지하고 인용 스냅샷은 최대 30개를 검사한다.
상한 초과는 `truncated`로 표시한다. API의 잠금·CPU 비용은 운영 성능 보장과 별개다.
[5단계 검증 기록](../testing/hpu-publication-links-20261024.tdd.md)을 참고한다.
