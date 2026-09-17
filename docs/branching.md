# 브랜치 전략 (GitHub Flow)

## 브랜치
- `main` : 항상 동작하는 상태. 직접 push 금지, PR만 허용.
- `feat/pipeline-*` : 유현준 (라우터/스키마/통합)
- `feat/rag-*` : 최재영 (검색/추출/합성데이터)
- `feat/edge-*` : 허재원 (Jetson/추론/저장)
- `feat/eval-*` : 전혜민 (검수/평가/시나리오)
- `fix/*`, `chore/*` : 동일 규칙

## PR 규칙
- 리뷰 없이 PR을 바로 merge할 수 있다 (리뷰어 필수 규칙 제거).
- squash merge로 `main` 히스토리 선형 유지.

## 태그
- 주차 통합 체크포인트: `v0.1-week1`, `v0.2-week2`(MVP E2E), `v0.3-week3`(평가 완료), `v1.0-week4`(최종 동결)
- 데이터 봉인은 별도 네임스페이스: `data-v1.0-sealed` (코드 태그와 분리, 4.7.6 원칙)

## 충돌 예방
- K-01/Event 스키마, 도구 인터페이스는 `src/pipeline/`에서 작게 자주 머지 → 나머지가 그 위에서 작업.
- 대용량 합성데이터(`ledger/`, `artifacts/`, `splits/`, `raw/`)는 git에 올리지 않음 (`.gitignore`). 코드와 `manifest.json`(해시)만 커밋.
