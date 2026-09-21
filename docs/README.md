# ShiftLink 문서 안내

자료 유형별로 폴더를 나누었다. 파일명은 유지하고, 이동한 파일을 참조하는 문서 링크와 실행 코드·테스트의 경로를 갱신했다.

## 폴더 구성

| 폴더 | 자료 유형 |
| --- | --- |
| [planning/](planning/) | 개발계획, 고도화 초안, 변경표, 결정 질문, 제약 대장 |
| [design/](design/) | 도메인·데이터·시스템·MES 설계와 계약 |
| [guides/](guides/) | 실행·구성·복구·카드 작성 가이드, 브랜치 전략 |
| [templates/](templates/) | 개발 작업 지시 템플릿 |
| [reports/](reports/) | 검수·비교·평가·실측·작업 결과 보고서 |
| [data/](data/) | 공통 기준정보와 JSON 샘플 |
| [testing/](testing/) | 테스트 검증 기록, 평가 형식, 개발용 테스트 샘플 |
| [manual/](manual/) | 산업 매뉴얼과 다운로드 기록 |
| [safety_sources_18/](safety_sources_18/) | 안전 근거 조사 자료 |
| [naming-registry/](naming-registry/) | 공유 이름 등록 규칙과 레지스트리 |
| [archive/](archive/) | 과거 초안 전달용 Git bundle과 당시 업로드 절차 |

## 목적별 시작점

| 하려는 일 | 먼저 읽을 문서 |
| --- | --- |
| 프로젝트 계획 파악 | [개발계획 v2](planning/개발계획_v2_260911.md) → [고도화 초안](planning/01_고도화_초안.md) |
| 승인·미결 사항 확인 | [확정·미결 목록](planning/04_확정_미결_목록.md) → [결정 질문](planning/03_결정질문.md) |
| 모의 MES 실행 | [실행 가이드](guides/mock-mes-usage.md) |
| 장비 구성 변경 | [구성 가이드](guides/mock-mes-configuration-guide.md) |
| 데이터·지식 카드 작성 | [데이터 설계](design/B_data.md) → [카드 작성 가이드 초안](guides/카드_작성_가이드_초안.md) |
| 검증 근거 확인 | [검증 문서 목차](testing/README.md) |
| 공동 개발 시작 | [브랜치 전략](guides/branching.md) → [네이밍 규칙](naming-registry/README.md) |

## 계획·의사결정

- [개발계획_v2_260911.md](planning/개발계획_v2_260911.md): 개발계획과 일정.
- [01_고도화_초안.md](planning/01_고도화_초안.md): 검토용 v0.1, 미승인 고도화 제안.
- [02_변경표.md](planning/02_변경표.md): 기존안 대비 변경과 충돌.
- [03_결정질문.md](planning/03_결정질문.md): 결정이 필요한 질문과 답변 기록 양식.
- [04_확정_미결_목록.md](planning/04_확정_미결_목록.md): 기존 승인 사항과 미결 사항.
- [05_검수결과.md](reports/05_검수결과.md): 초안 정합성 검수 및 반영 기록.
- [constraint_register.md](planning/constraint_register.md): MES 기능 제약 대장.

초안의 제안과 기존 승인 사항은 각 문서의 상태 표기를 기준으로 구분한다. 검수·측정·테스트 기록은 해당 시점의 결과이며, 현재 상태의 재검증을 의미하지 않는다.

## 도메인·데이터·시스템 설계

- [A_domain.md](design/A_domain.md): 생산시스템·암묵지·지식경영 검토.
- [B_data.md](design/B_data.md): 합성 데이터·평가 파이프라인 고도화안.
- [C_system.md](design/C_system.md): 온디바이스 시스템·구현·검증 설계.
- [설비_사전_항목_목록_v0.1.md](design/설비_사전_항목_목록_v0.1.md): 설비 사전 항목.
- [카드_작성_가이드_초안.md](guides/카드_작성_가이드_초안.md): 지식 카드 작성 규칙 초안.
- [N-7_생성API_비교.md](reports/N-7_생성API_비교.md): 생성 API 비교 자료.

### 기준정보·샘플 데이터

| 파일 | 용도 |
| --- | --- |
| [00_plant_and_relations.json](data/00_plant_and_relations.json) | 공통 기준정보와 설비 관계. 실행 코드·테스트에서 경로 참조 |
| [01_kb_cards_shared.json](data/01_kb_cards_shared.json) | 공용 KB 카드 |
| [EV-0031_upstream_cause.json](data/EV-0031_upstream_cause.json) | 상류 원인 사건 샘플 (`kb`) |
| [EV-0032_downstream_block.json](data/EV-0032_downstream_block.json) | 하류 정체 사건 샘플 (`dev`) |
| [EV-0033_common_utility.json](data/EV-0033_common_utility.json) | 공통 유틸리티 사건 샘플 (`sealed`) |

데이터의 분할·사용 범위는 원본의 `split` 및 데이터 설계를 따른다. `sealed` 파일을 개발용 데이터로 재사용하지 않는다.

## 모의 MES

| 구분 | 문서 |
| --- | --- |
| 실행·사용 | [로컬 실행](guides/mock-mes-usage.md) |
| 구성 변경 | [장비 교체·추가·수정](guides/mock-mes-configuration-guide.md) |
| 도메인 | [산업 도메인 모델](design/mock-mes-domain.md) |
| 인터페이스 | [공통 계약](design/mock-mes-contract.md) |
| 구조 | [모듈화·구성 적용 설계](design/mock-mes-modularization.md) |
| 조치·복귀 | [이상상황 조치·복귀와 부품 내구도](guides/mock-mes-recovery.md) |
| 화면 설계 | [설비 흐름·현장 확인 화면](design/mes-operator-design.md) |
| 화면 검토 | [설비 시각화 독립 평가](reports/mes-visualization-review.md) |
| 개발 지시 템플릿 | [초기 개발](templates/mock-mes-development-template.md), [고도화](templates/mock-mes-claude-upgrade-template.md) |

구현 검증 기록은 [검증 문서 목차](testing/README.md)의 모의 MES 항목에서 확인한다.

## 검증·실측·작업 기록

- [testing/README.md](testing/README.md): 기능별 검증 기록과 평가 자료 목차.
- [Jetson_실측_PRE01-04.md](reports/Jetson_실측_PRE01-04.md): PRE-01~04 측정 기록. PRE-04는 문서에 재측정 필요로 표시되어 있다.
- [허재원_Day2작업결과.md](reports/허재원_Day2작업결과.md): Day2 환경 구성·모델 실행 결과.

## 참고 자료·협업·전달

- [manual/README.md](manual/README.md): 산업 매뉴얼 출처와 활용 메모.
  - [다운로드 기록](manual/download-status.md)
  - [Siemens G120 매뉴얼 PDF](manual/siemens-G120-CU240BE2-LH11-0112-en.pdf)
- [safety_sources_18/README.md](safety_sources_18/README.md): 안전 근거 조사 목차와 출처별 기록.
- [branching.md](guides/branching.md): 브랜치 전략.
- [naming-registry/README.md](naming-registry/README.md): 공유 이름 등록 규칙.
- [naming-registry/registry.md](naming-registry/registry.md): 이름 레지스트리.
- [업로드_방법.md](archive/업로드_방법.md): 2026-09-17 작성된 초안 전달 절차. 당시 환경·경로를 전제로 한 기록.
- [shiftlink-plan-draft.bundle](archive/shiftlink-plan-draft.bundle): 초안 전달용 Git bundle. 사용 방법은 업로드 문서 참고.

## 문서 추가·관리

- 새 문서는 위 분류에 맞는 폴더에 저장하고, 이 목차의 해당 주제에 링크를 추가한다. 루트에는 이 안내 문서만 둔다.
- 검증 기록·평가 형식은 `testing/`, 산업 매뉴얼은 `manual/`, 안전 출처 조사 기록은 `safety_sources_18/`, 공유 이름은 `naming-registry/`에서 관리한다.
- 초안·승인·미결·측정 결과는 본문에 구분해서 기록한다.
- 기존 파일을 이동하거나 이름을 바꿀 때는 문서 링크뿐 아니라 코드·테스트의 경로 참조도 함께 확인한다.
