# 데이터 분류와 사용 안내

이 폴더에는 기준정보, 카드 묶음, 복합 시나리오, 단일 Event와 관리 규칙이 있다. 모든 JSON이 Event는 아니다.

| 폴더 | 내용 | 시작 파일 |
|---|---|---|
| `reference/` | 합성 라인·설비·부품·관계·페르소나 등 공통 기준정보 | [00_plant_and_relations.json](reference/00_plant_and_relations.json) |
| `knowledge_cards/` | 합성 공용 KB 카드와 출처 사건 묶음; 파일 전체가 단일 KnowledgeCard는 아님 | [01_kb_cards_shared.json](knowledge_cards/01_kb_cards_shared.json) |
| `scenarios/` | 사건·관측·카드·정답 등 복합 합성 시나리오; 파일 전체가 단일 Event는 아님 | [EV-0031](scenarios/EV-0031_upstream_cause.json) (`kb`), [EV-0032](scenarios/EV-0032_downstream_block.json) (`dev`), [EV-0033](scenarios/EV-0033_common_utility.json) (`sealed`) |
| `events/` | 냉간코일 공장 내 오류·고장과 조치·결과 사건; 현재 적격 실제 사건 0건 | [범위·작성 기준](events/README.md) |
| `policies/` | 출처·계보·분할·평가 데이터 관리 규칙 | [원문·출처·평가 분할 계약](policies/source-and-split-contract.md) |

## 사용 기준

- 실제 사건 검증은 오류·수행 조치·결과가 확인된 냉간코일 공장 내 사례를 확보한 후 시작한다. 기존 EV-0101~0105는 [안전 참고자료](../sources/safety/public_incidents/README.md)로 분리했으며 조치 정답 자료로 사용하지 않는다.
- 합성 기준정보의 수치는 실제 설비 값이 아니다. 공개 사건 초안도 현장 검수·KB 채택 완료 데이터가 아니다.
- `sealed` 시나리오는 개발·카드 생성·튜닝 입력으로 사용하지 않는다.
- 2026-09-22 폴더 정리에서 JSON 내용과 파일명은 유지했다. 시나리오 내부의 파일명 참조는 위 표의 위치를 따른다.

## 이전 경로 대응

모든 경로는 저장소 루트 기준이다. 과거 보고서와 `splits/inventory.json`은 당시 기록이므로 소급 수정하지 않았다. 이전 해시 기록을 확인할 때 아래 경로로 연결한다. 정책 문서는 이동 후 상대 링크를 수정했으므로 과거 해시와 달라질 수 있다.

| 이전 경로 | 현재 경로 |
|---|---|
| `docs/data/00_plant_and_relations.json` | `docs/data/reference/00_plant_and_relations.json` |
| `docs/data/01_kb_cards_shared.json` | `docs/data/knowledge_cards/01_kb_cards_shared.json` |
| `docs/data/EV-0031_upstream_cause.json` | `docs/data/scenarios/EV-0031_upstream_cause.json` |
| `docs/data/EV-0032_downstream_block.json` | `docs/data/scenarios/EV-0032_downstream_block.json` |
| `docs/data/EV-0033_common_utility.json` | `docs/data/scenarios/EV-0033_common_utility.json` |
| `docs/data/source-and-split-contract.md` | `docs/data/policies/source-and-split-contract.md` |
| `docs/data/public_incidents/`, `docs/data/events/public_incidents/` | `docs/sources/safety/public_incidents/` (안전 참고자료로 재분류) |
