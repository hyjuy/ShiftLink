# HPU 온톨로지 shadow 실행

3단계는 **승인된 오프라인 DB 복사본을 읽는 별도 진단 실행기**다.
기존 MES/PDA 서버와 `/api/query`, 검색·judge·답변·게시·업무 DB 저장에는 연결하지 않는다.
서비스 설정에 환경 변수만 추가해도 질의별 진단이 자동 실행되지는 않는다.
4단계의 인증된 별도 조회는 [설명 API 안내](hpu-ontology-api.md)를 따른다.
shadow 실행 자체는 서버의 질의 경로에 연결하지 않는다.

구현: `shiftlink/mes/ontology_shadow.py:run_shadow`,
CLI: `shiftlink/mes/hpu_ontology.py:main`.
기존 공통 `read_incident_bundle`/`project_incident`를 그대로 사용한다.

## 준비 자료

- 승인된 SQLite 복사본과 조회할 기존 `incident_id`.
- 해당 자료에 대응하는 보존 catalog JSON.
- 아래 형태의 출처 manifest JSON. 값은 예시이며 실제 자료 묶음의 확인 결과로 작성한다.

```json
{
  "source_namespace": "approved-dataset-id",
  "config_catalog_hashes": {
    "recorded-config-id": "canonical-catalog-sha256"
  }
}
```

hash는 공통 `content_hash(catalog)`의 canonical JSON SHA-256이다.
`config_catalog_hashes`는 자료 묶음 담당자가 확인한 config와 catalog의 대응이다.
현재 catalog 해시를 모든 과거 config에 자동 대입하지 않는다. 대응을 확인하지 못하면
이 필드를 생략하거나 빈 객체로 두고 `unverified_catalog_binding` 진단을 확인한다.
namespace를 DB 절대 경로나 복사할 때마다 달라지는 임의 값으로 만들지 않는다.

## 실행

저장소 루트의 프로젝트 Python 환경에서 실행한다. 다음은 파일 경로·사건 ID를 바꿔 쓰는 형식 예시다.

```powershell
# 기본 off: 입력 파일을 읽거나 출력 파일을 만들지 않는다.
python -m shiftlink.mes.hpu_ontology

# 별도 shadow 진단. output은 아직 없는 파일이어야 한다.
python -m shiftlink.mes.hpu_ontology --mode shadow --db approved-copy.sqlite3 --incident-id INC-existing-id --catalog preserved-catalog.json --manifest source-manifest.json --output hpu-shadow-result.json
```

`--mode`가 없으면 `SHIFTLINK_HPU_ONTOLOGY`를 사용하고 환경 변수도 없으면 `off`다.
명시적 `--mode off`가 환경 변수보다 우선한다. 현재 지원 값은 `off`, `shadow`이며
`explain`은 미구현이다. 기존 지식 그래프 환경 변수의 의미를 변경하지 않는다.

`--max-records`는 기본 30이고 1..100이다. 사건에 속한 일지·질의를 각각 제한한다.
공통 projector의 노드 1000개·관계 2000개 상한도 유지한다. 생략 범위가 있으면 `truncated=true`다.

`--output`을 생략하면 콘솔 요약만 얻는다. 원문 출처·관계·미확인 항목을 상세히 보려면
새 출력 파일을 지정한다. 부모 폴더는 미리 존재해야 하며 기존 파일은 원본 DB·catalog·manifest를
포함해 덮어쓰지 않는다. 전체 artifact에는 원문 업무 내용이 포함되므로 승인된 로컬 검토 범위에서 다룬다.

## 결과 읽기

콘솔 JSON은 graph를 제외한 요약이고, 출력 파일은 같은 요약과 전체 graph를 함께 가진다.

| 필드 | 의미 |
|---|---|
| `mode`, `status` | off/disabled, shadow/completed 또는 shadow/error |
| `summary.projection_state` | 아래 연결 상태 구분. 작업 안전성·모델 품질 판정이 아님 |
| `summary.node_counts`, `edge_counts` | 타입/관계별 수 |
| `summary.unresolved_count`, `unresolved_by_reason` | 미확인 수·사유별 집계 |
| `summary.snapshot_hash` | 기존 projector의 내용 식별 해시. 같은 입력이면 동일 |
| `summary.truncated` | 자료/그래프 상한 때문에 전체를 확인하지 못했는지 |
| `timings_ms.read`, `project` | 이번 로컬 실행의 읽기·변환 시간. 기기 성능 보장 수치가 아님 |
| `graph.nodes`, `edges` | 출처·내용 해시·주장 종류를 포함한 연결 결과. 파일/Python 결과에만 포함 |
| `graph.unresolved` | 원본 ID/필드 위치·reason·binding_status. 구체적 누락·충돌 확인 위치 |

상태는 다음과 같이 해석한다.

- `connected`: 노드가 있고 보고된 미확인/잘림이 없다. 모든 업무 사실이 검증됐다는 뜻은 아니다.
- `partial`: 연결된 노드와 미확인 사유가 함께 있다.
- `unresolved`: 노드 없이 미확인 사유만 있다.
- `empty`: 선택 범위에 노드·미확인 사유가 없다. 전체 DB에 HPU 이력이 없다는 결론으로 확대하지 않는다.
- `truncated`: 입력 또는 그래프가 잘렸다. 반환된 노드 수만으로 전체 커버리지를 판단하지 않는다.

`unverified_catalog_binding`은 과거 config의 출처 대응이 부족한 경우다.
`query_context_conflict`, `measurement_asset_conflict`, `measurement_unit_conflict`,
`session_binding_unresolved` 등은 1~2단계의 기존 사유를 그대로 보존한다.
shadow는 이 사유를 감추거나 현재 자산·단위·시각으로 보완하지 않는다.

## 실패와 종료 코드

- 종료 0: disabled 또는 진단 completed. 미확인 항목이 있어도 진단 실행 자체는 완료될 수 있다.
- 종료 1: 입력 읽기/manifest, DB 읽기, 투영, 출력 실패.
- 종료 2: CLI 인자 누락·잘못된 인자.

오류 결과는 `error.stage`(configuration/input/read/project/write)와 예외 **종류**만 제공한다.
예외 메시지·접속 문자열을 출력하지 않는다. 이전 그래프를 성공 결과처럼 반환하지 않는다.
쓰기 실패 시 artifact가 완성됐다고 간주하지 말고 새 경로로 재실행한다.
기존 출력 파일 때문에 실패했다면 그 파일은 과거 실행 결과다. 현재 명령의 종료 코드와 status를 확인한다.
이 실행기는 업무 DB 상태나 기존 질의의 성공/실패를 변경하지 않는다.

[설계](../design/hpu-ontology-extension.md),
[TDD·회귀 근거](../testing/hpu-ontology-shadow-20261024.tdd.md).
