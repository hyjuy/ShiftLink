# 지식 그래프 변환 담당 인계

- 역할: 발표용 `kg-demo-v1` 변환. 작성일: 2026-10-21.
- 시작·종료 확인 브랜치: `codex/kg-build`.
- 기준 및 확인 HEAD: `5167376b5ded1e33725394f2b65cb6977c121dec`.
- 쓰기 범위: `docs/demo/kg/build/`만. 커밋·push·PR·배포·브랜치 변경 없음.
- 사용자 메시지의 승인 완료 지시를 적용했다. 문서의 과거 승인 대기 문구를 이유로 구현을 보류하지 않았다.

## 계약·입력 해시

SHA-256은 실제 읽은 파일 바이트 기준이다. 줄바꿈 변환 없이 확인했다.

| 파일 | SHA-256 |
|---|---|
| 로컬 `docs/demo/kg/schema.md` | `90afb3ca2590a6b6eccaa4a0bc9bcb991471d5534096fa03e87281399475b651` |
| 기준 커밋의 `docs/demo/kg/schema.md` | `ad460fc639146d17d448457a5c0a7908bf4aaca92f4098860456401fe0b81613` |
| 로컬 `docs/demo/kg/distributed-work-plan.md` | `5e8210a91658d008f75269b429a98a34331f1cc1f73a47a387adc5dab8ed2ed3` |
| 기준 커밋의 `docs/demo/kg/distributed-work-plan.md` | `6f6276350e143e7d1160f450e4dd7409bbebc9036d2d1a4adf2e794c477c5383` |
| `docs/data/knowledge_cards/kb/kb_cards.json` | `05cfc4e79a3087e3544fc01e6b830268b542f55ae3be31bd6ad7601fc1d6dd3a` |
| `docs/data/reference/00_plant_and_relations.json` | `aee891c5e5e2270e815080f22b153e9b64e9128951d2262240c1f41cdc5e1708` |

증상 입력 `docs/demo/kg/symptoms/symptom_concepts.json`은 없었다. 실제 산출물은 `symptoms_loaded: false`이며 증상 노드·관계가 0개다. 매핑 파일이 생기면 인자 없이 재실행하여 적용한다. 존재하는 파일이 잘못된 JSON, `null`, 중복 키, 불완전·부정확한 매핑이면 실패한다.

작업 시작 전부터 공통 문서 3개와 여러 프로젝트 파일에 로컬 변경이 있었다. schema.md의 기준 커밋 대비 차이는 승인 상태·운영 설명이며 노드·관계·ID·교환 파일 계약은 동일했다. 공통 문서는 수정하지 않았다. `validation.json.contract_sha256`은 위 로컬 계약 해시다. 통합 담당자는 이 값이 기준 커밋의 계약 해시와 다름을 확인해야 하며, 기준 문서로 실행하면 보고서의 계약 해시는 그 실행 입력을 반영한다.

## 만든 파일

| 파일 | 목적 |
|---|---|
| `build_graph.py` | 표준 라이브러리 변환기, 엄격한 입력·그래프 검증, assert 자가 점검 35개 |
| `graph.json` | 계약의 `nodes`, `edges`만 포함하는 UTF-8/LF 그래프 |
| `validation.json` | 6종별 집계, 보류 인용 원문, 검수 대상, 해시 불변·결정성·자가 점검 결과 |
| `HANDOFF.md` | 실행 조건, 검증 결과와 인계 주의점 |

원본 카드 객체는 CardVersion.props에 모든 필드를 그대로 복사한다. 합성 자산 10개는 마스터의 equipment_type_id FK로 유형을 연결한다. mes_equipment_id로 사건 관계를 추정하지 않는다. AssetPart·INSTALLED_ON은 생성하지 않는다.

판본 없는 출처는 DocumentVersion·CITES로 만들지 않는다. 원본 CardVersion.props.provenance.sources와 validation.json.unversioned_sources의 source 객체에 손실 없이 남긴다. reason은 `document_version_missing`이다. 카드 판본·마스터 판본을 문서 판본으로 대입하지 않는다. 판본이 있는 인용은 카드/문서 쌍별로 locator 원문을 첫 출현 순으로 중복 제거하고 원본 항목 수를 기록한다.

## 실행 명령과 결과

저장소 루트에서 실행했으며 모두 종료 코드 0이었다.

```powershell
python docs/demo/kg/build/build_graph.py --self-test
python docs/demo/kg/build/build_graph.py
python -B scripts/check_knowledge_publication.py
git diff --name-status 5167376b5ded1e33725394f2b65cb6977c121dec...HEAD
git diff --cached --name-status
git diff --check -- docs/demo/kg/build
git diff --cached --check
```

- `--self-test`: assert 35개 통과. 정상/미입력 매핑, 안전·null 카드의 매핑 및 관계 차단, 잘못된 끝점·도메인/범위·관계 속성, 중복 노드/관계/매핑/JSON 키, 고아 노드, 필드 손실·관계 누락·인용 수 손실, 미정의/미참조 개념, 검수 목록 누락/중복/빈 사유, 여러 카드 판본, 마스터 FK, ID 이스케이프, 결정성 등을 검사한다.
- 기본 빌드: 성공. 스키마 오류 0, 고아 노드 0, 안전 카드 증상 연결 0, null 카드 증상 연결 0.
- 게시 무결성 검사: `ok: true`, `errors: []`, `staged_python_checked: true`.
- 기준 SHA...HEAD 차이 및 staged 변경 없음. build/ 범위와 staged 공백 검사 통과. 기존 범위 밖 변경은 정리하거나 되돌리지 않았다.
- `python -B -`에 전달한 표준 라이브러리 인라인 통합 검증도 통과했다. `tempfile.TemporaryDirectory(dir=build/)` 안에 원본 복사본과 86장 전체를 포함하는 시험 매핑을 만들고 모듈의 입력·출력 루트를 그 임시 폴더로 지정했다. 실제 다른 담당자 폴더에는 쓰지 않았고 임시 입력은 검사 후 제거됐다.
- 통합 검증에서 유효한 후보 1개는 노드 272개·관계 415개를 생성했다. 안전 카드 연결, 파손 JSON, 최상위 null, 중복 JSON 키 4가지 오류는 모두 거부됐으며 두 성공 산출물의 바이트가 각각 유지됐다.
- 같은 스크립트를 build/ 작업 디렉터리에서 `python -B <저장소 절대경로>/docs/demo/kg/build/build_graph.py`로 별도 재실행했다. 저장소 위치를 스크립트 경로에서 계산하므로 실행 디렉터리와 무관하게 성공했다. graph.json과 validation.json 모두 첫 실행과 바이트·해시가 같았다.
- `ast.parse` 문법 검사, 모든 산출물의 UTF-8/LF, 기본 빌드 실행 전후 원본·계약 해시 불변을 확인했다. Python 바이트코드·새 의존성·테스트 프레임워크는 추가하지 않았다.
- 작업 전부터 변경·미추적이던 범위 밖 파일 109개의 SHA-256이 모두 같고, 추가 범위 밖 변경 및 staging 변경이 없음을 별도 비교했다.

| 노드 타입 | 실제 수 | 관계 타입 | 실제 수 |
|---|---:|---|---:|
| EquipmentType | 83 | PART_OF | 76 |
| Symptom | 0 | ABOUT | 172 |
| CardVersion | 86 | DESCRIBES_SYMPTOM | 0 |
| DocumentVersion | 92 | CITES | 156 |
| Asset | 10 | INSTANCE_OF | 10 |
| AssetPart | 0 | INSTALLED_ON | 0 |
| 합계 | 271 | 합계 | 414 |

인용 원본 222건 = 판본 포함 180건 + 판본 누락 보류 42건. 180건은 CITES 156개로 집약됐다. 검수 대상은 전체 86장, 안전 56장, symptom=null 13장이며 두 차단 집합의 합집합은 58장이다. 매핑 미입력 상태에서도 검수 대상을 원본에서 계산했다.

| 산출물 | 재실행 동일 SHA-256 |
|---|---|
| `graph.json` | `c4001cd608e72cd45ed37def653f5b6789d4b52e29eaca7d15cbb9d42c7075c5` |
| `validation.json` | `492e7b4c822897c9f71aa608d30e698415c791c29b217367b7ecccc3b05f0611` |

## 미해결 사항과 인계 조건

- 변환 기능의 확인된 미해결 오류는 없다. 계약 변경 요청도 없다.
- 공통 계약의 로컬/기준 커밋 해시 차이는 작업 전 상태에서 이어진 인계 주의점이다. 허용 쓰기 범위 밖이므로 문서를 고쳐 맞추지 않았다.
- 실제 증상 매핑은 아직 입력되지 않았다. 통합 담당자가 매핑을 인수한 뒤 빌더를 재실행해야 한다. 안전 56장·null 13장의 연결 차단은 매핑 검증과 그래프 검증에서 각각 강제한다.
- 증상 의미의 사람 검수 및 판본 없는 인용 42건의 판본 확인은 남아 있다. schema 오류 0을 그 검수 완료로 해석하지 않는다.
- 자산은 합성 기본 구성 스냅샷이다. 실제 현장 자산·설치 이력, UI 통합 검증, 운영 검색·GraphRAG·추론·성능 평가는 이 인계에 포함되지 않는다.
