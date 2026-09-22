# ShiftLink 문서 안내

문서는 아래처럼 목적별로 관리한다. 최신 구현 기준과 과거 제안·검증 기록을 구분해서 읽는다.

## 폴더 구성

| 폴더 | 담는 내용 |
|---|---|
| [planning/](planning/) | 개발 일정, 통합 계획, 변경 사항, 결정 질문·미결 사항 |
| [design/](design/) | 도메인·데이터·시스템 설계, 스키마·MES 계약 |
| [guides/](guides/) | 현재 기능의 실행·구성·복구·카드 생성 방법 |
| [data/](data/README.md) | 기준정보, 카드 묶음, 복합 시나리오, 단일 Event, 관리 규칙 |
| [sources/](sources/README.md) | 외부 매뉴얼·안전 근거와 출처 검토 기록 |
| [testing/](testing/README.md) | 테스트 방법·검증 기록·평가 형식·테스트 자료 |
| [reports/](reports/) | 작업 결과, 검수 결과, 비교·실측 보고서 |
| [collaboration/](collaboration/README.md) | 브랜치 전략, 공유 이름 등록 규칙 |
| [templates/](templates/) | 에이전트·개발자에게 전달할 작업 지시 템플릿 |
| [archive/](archive/README.md) | 이전 버전 가이드, 과거 전달 절차·Git bundle |

## 목적별 시작점

| 하려는 일 | 먼저 읽을 문서 |
|---|---|
| 현재 개발 일정 확인 | [9/21~10/2 개발계획](planning/개발계획_20260921-1002_회의결정반영.md) |
| 통합 계획 확인 | [고도화 v1.1 통합본](<planning/최종 통합본(고도화 v1.1)(codex).md>) |
| 결정·미결 사항 확인 | [확정·미결 목록](planning/04_확정_미결_목록.md), [결정 질문](planning/03_결정질문.md), [제약 대장](planning/constraint_register.md) |
| T1~T6 카드 작성 | [현재 작성 가이드 v1.1](../seeds/카드_작성_가이드_초안.md), [구현 계약](design/D26-29_계약_v1.0.md) |
| 카드 생성 실행 | [생성 가이드](guides/card-generation.md) |
| 실제 사건 기반 Event 확인 | [공개 사건 목록](data/events/public_incidents/README.md) |
| 데이터 분류·사용 기준 확인 | [데이터 안내](data/README.md), [출처·분할 계약](data/policies/source-and-split-contract.md) |
| 모의 MES 실행 | [실행 가이드](guides/mock-mes-usage.md) |
| 장비 구성 변경 | [구성 가이드](guides/mock-mes-configuration-guide.md) |
| 이상상황 조치·복귀 | [복구 가이드](guides/mock-mes-recovery.md) |
| 검증 결과 확인 | [검증 문서 목차](testing/README.md) |
| 공동 개발 시작 | [협업 안내](collaboration/README.md) |

## 설계와 작업 지시

- 기초 설계: [도메인](design/A_domain.md), [데이터](design/B_data.md), [시스템](design/C_system.md). 제안·미결 여부는 각 문서의 상태를 따른다.
- MES 설계: [도메인](design/mock-mes-domain.md), [계약](design/mock-mes-contract.md), [구조](design/mock-mes-modularization.md), [작업자 화면](design/mes-operator-design.md).
- 개발 지시: [초기 개발 템플릿](templates/mock-mes-development-template.md), [고도화 템플릿](templates/mock-mes-claude-upgrade-template.md).
- 결과 보고: [하니스 검증](reports/D26-29_하니스_검증_20260921.md), [Jetson 실측](reports/Jetson_실측_PRE01-04.md), [매뉴얼 검수](reports/매뉴얼_절_검수시트_20260921.md).

## 관리 기준과 이동 기록

- `docs/data`는 작성·검토용 자료다. 저장소 루트의 `data/`는 모의 MES 실행 DB이므로 별도로 관리한다.
- 현재 카드 작성 기준은 `seeds/카드_작성_가이드_초안.md` 한 곳을 따른다. v0.9 문서는 archive에 보관한다.
- 과거 보고서의 검증 결과는 당시 기록이며 현재 상태의 재검증을 뜻하지 않는다.
- 기존 JSON·PDF·bundle 내용은 폴더 정리 과정에서 변경하지 않았다. 이동한 Markdown의 상대 링크와 활성 경로 참조는 갱신했다.
- 과거 보고서 및 `splits/inventory.json`의 당시 경로·해시는 소급 수정하지 않았다. 아래 표와 [데이터 이동표](data/README.md#이전-경로-대응)로 현재 위치를 찾는다.

| 이전 위치 | 현재 위치 |
|---|---|
| `docs/manual/` | `docs/sources/manual/` |
| `docs/safety_sources_18/` | `docs/sources/safety/` |
| `docs/naming-registry/` | `docs/collaboration/naming-registry/` |
| `docs/guides/branching.md` | `docs/collaboration/branching.md` |
| `docs/guides/카드_작성_가이드_초안.md` | `docs/archive/카드_작성_가이드_초안.md` |

새 문서는 해당 목적의 폴더에 추가한다. 사용 방법은 guides, 테스트 근거는 testing, 완료된 작업 보고는 reports에 둔다. 문서 이동 시 참조 링크·코드 경로·출처 등록부도 확인한다.
