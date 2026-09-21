# 검증 문서 안내

[전체 문서 목차](../README.md)

기능별 테스트 근거, 평가 데이터 형식, 개발용 샘플을 정리한다. 아래 보고서는 작성 시점의 결과다. 실행 명령·환경·제약은 각 문서에서 확인한다.

## 모의 MES

| 문서 | 확인 범위 |
| --- | --- |
| [mock-mes.tdd.md](mock-mes.tdd.md) | 모의 MES 통합 검증 |
| [mock-mes-modularization.tdd.md](mock-mes-modularization.tdd.md) | 모듈화 독립 통합 검증 |
| [mock-mes-recovery.tdd.md](mock-mes-recovery.tdd.md) | 이상상황 조치·복귀 검증 |
| [mes-operator.tdd.md](mes-operator.tdd.md) | 설비 관계·선택 근거 화면 검증 |
| [mes-flow-overview.tdd.md](mes-flow-overview.tdd.md) | MES 전체도·연결선 개선 검증 |

관련 가이드: [MES 실행](../guides/mock-mes-usage.md), [공통 계약](../design/mock-mes-contract.md), [화면 설계](../design/mes-operator-design.md).

## 데이터·에이전트 파이프라인

| 문서 | 확인 범위 |
| --- | --- |
| [data-cli.tdd.md](data-cli.tdd.md) | 데이터 CLI 검증 |
| [pipeline-schema-v0.9.tdd.md](pipeline-schema-v0.9.tdd.md) | 스키마 v0.9 검증 |
| [router-fixed-pipeline.tdd.md](router-fixed-pipeline.tdd.md) | 라우터·고정 파이프라인 검증 |

관련 설계: [데이터·평가 파이프라인](../design/B_data.md), [시스템·검증 설계](../design/C_system.md).

## 평가 형식·샘플

- [정답지_형식_초안.md](정답지_형식_초안.md): 정답 데이터 형식 명세 초안.
- [dev_sample_memos.jsonl](dev_sample_memos.jsonl): 개발용 메모 샘플.

실제 정답 데이터의 보관·분할 규칙은 정답지 형식 문서를 따른다.

## 실측·작업 기록

- [Jetson PRE-01~04 실측](../reports/Jetson_실측_PRE01-04.md)
- [허재원 Day2 작업 결과](../reports/허재원_Day2작업결과.md)
