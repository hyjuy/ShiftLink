# 운영 질의에 연결한 온톨로지·지식 그래프

기준일: 2026-10-24. 기준: 원격 main `99c334d`와 2026-10-24 확인한 Jetson 온톨로지 5파일의 로컬 통합본. Jetson 재배포·재시작·실제 모델 품질 측정은 이 구현과 구분한다.

## 사용자 흐름과 구현 위치

작업자가 설비를 선택해 `/api/query`로 질문하면, 기존 게시 관리자가 해당 설비·자산·관측 조건에서 검색 가능한 카드만 질의별 뷰에 합친다. S30h가 벡터 검색으로 씨앗 카드를 찾고, 그 카드의 하위 분류 또는 문서 판본을 공유하는 이웃 카드를 그래프에서 두 단계로 탐색한다. 이웃은 최대 2개이며 기존 청크·토큰 예산과 judge의 근거 판정을 통과해야 답변에 사용된다.

- `shiftlink/rag/knowledge_graph.py`: 도메인 스키마, 질의별 그래프, 두 단계 관계 탐색, 후보 순위 보완.
- `shiftlink/rag2/s30h.py:evidence`: 벡터 순위와 그래프 후보를 결합하고 기존 근거 예산 적용.
- `shiftlink/rag2/s30h.py:run`: 기존 근거 판정·보류·인용 검증 유지. 추적 정보 기록.
- `shiftlink/mes/query.py:build_query_pipeline`: S30h에서 기본 활성화. `SHIFTLINK_KNOWLEDGE_GRAPH=0`으로 벡터 검색만 사용하여 비교할 수 있다. FixedPipeline의 어휘 검색 경로는 이번 통합 대상이 아니다.

서비스 응답과 저장되는 질의 추적의 `s30h_trace.knowledge_graph`에 스키마 버전, 노드·관계별 수, 실제 선택된 그래프 후보 청크, 씨앗·이웃 카드 ID, 연결 노드와 방향을 가진 관계, 인용 관계별 원문 위치가 기록된다. 이 정보는 검색 후보가 된 이유이며 최종 답변의 정답성·안전성 보증이 아니다.

## 온톨로지 관점의 도메인 스키마

스키마 버전: `shiftlink-retrieval-graph-v1`. 별도 그래프 DB나 OWL 추론기 없이 타입과 허용 관계를 코드로 정의한 인메모리 그래프다. 독립 발표 시연인 `docs/demo/kg`의 생성물·고정 해시에 의존하지 않는다.

| 노드 | 의미와 식별 기준 |
|---|---|
| EquipmentType, level=equipment | 카드 설비 유형. COMMON은 공통 분류 |
| EquipmentType, level=classification | 설비 유형 안의 원본 component 분류. 실제 부품 장착을 뜻하지 않음 |
| CardVersion | 원본 card_id와 version의 조합 |
| DocumentVersion | 원본 source_id와 document_version의 조합 |

| 관계 | 시작 타입 | 끝 타입 | 의미 |
|---|---|---|---|
| ABOUT | CardVersion | EquipmentType(classification) | 카드의 정확한 하위 분류 |
| PART_OF | EquipmentType(classification) | EquipmentType(equipment) | 분류의 상위 유형 |
| CITES | CardVersion | DocumentVersion | 판본과 원문 위치가 명시된 인용 |

노드 ID는 원본 문자열을 JSON 배열로 직렬화하므로 구분자·공백·한글·수치를 임의로 정규화하지 않는다. 관계 생성 시 도메인·범위를 검증한다. `PART_OF` 상위 유형을 통과하여 같은 설비의 모든 카드를 이웃으로 취급하지 않는다. 증상·원인·조치나 부품 장착 관계는 추론하여 만들지 않는다.

## 검색 알고리즘과 경계

1. 기존 설비·공통 폴더 필터 안에서 벡터 순위를 계산한다.
2. 상위 8개 청크 중 그래프에 일치하는 카드 최대 3개를 씨앗으로 정한다.
3. 카드→하위 분류←카드 또는 카드→문서 판본←카드 경로를 찾는다. 원문 판본과 locator가 없는 출처는 CITES 연결을 만들지 않는다.
4. 같은 질의 뷰의 유효 카드 청크만 벡터 순서대로 최대 2개 보완한다. 청크에 판본이 명시돼 있으면 일치해야 하며, 판본 없는 기존 정적 청크는 현재 카드의 know_how 전체가 포함된 경우에만 그래프 연결에 사용한다. 검증된 게시 카드 청크의 판본은 질의용 사본에 명시한다. 씨앗으로 이미 선택된 카드는 추가하지 않는다. 벡터 top30 밖의 청크도 같은 필터 안에서 관계로 찾을 수 있다.
5. 기존 top30 후보 수·최대 8청크·토큰 예산·이벤트 제한을 유지한다. 실제 근거 예산에서 제외된 그래프 후보는 trace paths에서도 제외한다.
6. 모든 채택 후보를 기존 judge가 판정한다. 근거 부족·모델 장애·인용 검증 실패의 응답 보류 동작은 유지한다. 관계 경로를 근거 텍스트로 만들어 답변 프롬프트에 넣지 않는다.

accepted/L1/kb 카드만 그래프에 들어간다. 이 기존 KB 상태가 전문가 안전 검수 완료를 뜻하지는 않는다. 다른 설비 유형, 다른 설치 위치에 한정된 카드, 빈 분류·판본, 중복 card_id의 모호한 판본은 제외한다. 현장 카드는 기존 `PublicationManager.snapshot`의 검수·내용 해시·임베딩 모델·자산·관측 조건·리비전 검증을 통과한 뷰에서만 받는다. 질의 종료 시 publication ticket 재검사는 그대로 유지한다. 정적 KB·인덱스와 공유 파이프라인을 수정하지 않는다.

## 확인과 남은 검증

테스트: `python -m pytest tests/test_knowledge_graph_runtime.py tests/test_s30h.py tests/test_publication_s30h.py tests/test_publication_worker.py -q`.
게시 무결성: `python scripts/check_knowledge_publication.py`.

새 테스트는 관계와 판본 구분, 그래프 후보 확장, judge 거절·최종 인용, 검색 예산, 질의 간 격리, 검수 게시 전후·반려 후의 검색 변화를 검증한다. 실제 원문 카드로 구성한 로컬 그래프와 결정적 모델 픽스처 테스트는 실제 Ollama 추론·검색 품질 평가와 다르다. 기존 S30h의 10/16 성능 수치를 새 그래프 경로의 측정값으로 재사용하지 않는다. 벡터 검색만 사용한 기준과 새 경로의 응답·인용·거절·지연 비교 및 Jetson 배포 후 확인은 별도 수행해야 한다.


## 게시 카드의 설명 그래프 연결과 이력 보존

`mes/publication.py:PublicationManager.snapshot`은 검증된 게시 카드 청크의 질의용 사본에 카드 판본을 부착한다. `mes/query.py:query_service`는 같은 snapshot의 publication ticket에 포함된 ID만 `rag/graph_explain.py:GraphSnapshot.add_publications`로 전달한다. 설명 그래프는 질의별 메모리 사본에만 현장 카드를 연결하며 정적 graph.json, 카드 원문, 임베딩 인덱스를 쓰지 않는다. 판본 없는 근무일지 출처는 임의 판본을 만들지 않고 보류 인용으로 남긴다.

검색 그래프는 답변 전 후보를 보완하고, 설명 그래프는 최종 인용 후 관계를 설명한다. 둘은 동일한 게시 자산/판본 가시성 경계를 지키며, 그래프 연결만으로 judge를 우회하지 않는다. 반려·교체·검수 취소 시 다음 질의에서 제외하고 기존 저장 답변은 보존한다.

`rag2/field_history.py`는 main 원본을 유지한다. 과거 원문 응답과 현재·미래 요청의 원 질문/MES 모델 전달을 각각 검사하며, 37분을 137분으로 선택하는 부분문자열 회귀도 검사한다. Pi PDA·Jetson 센서 엔진·AI 모델/분석 설정은 변경하지 않는다. Pi가 PDA를 제공하고 Jetson은 MES를 실행하며, Jetson의 구형 PDA/UI 사본은 통합 대상이 아니다.

통합 검사: `python -m pytest tests/test_knowledge_graph_runtime.py tests/test_publication_ontology_integration.py tests/test_field_history_integration.py -q -s`. 모델·임베딩 fixture와 임시 SQLite/인덱스만 사용한다. 검증 결과 및 TDD 근거는 `docs/testing/ontology-main-integration-20261024.tdd.md`에 기록한다. 이 문서의 로컬 통합은 운영 배포 완료를 뜻하지 않는다.
