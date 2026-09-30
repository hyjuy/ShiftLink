# 배치 C 검증 기록 — 2026-09-30

## 상위 계약 반영 후 재검증

기준 출처 52개·계보 후보 7개·카드 provenance 수정·중복 dev 격리 후,
Python 3.10.21/Pydantic 2.9.2에서 전체 제품 테스트를 다시 실행했다.
`python3.10.exe -m pytest -q tests --basetemp=artifacts/batch-c-policy-pytest-01 --tb=short`:
**445 passed in 12.02s**.
기본 배치 검증은 PASS, `verify.py --kb-ready`는 승인·계보·독립 근거 미완료로 의도한 종료 코드 1이다.
accepted 병합·직접 상태 변경·dev 재활성화·불완전 승인·계보 변조 차단은 독립 에이전트가 재현했다.
현재 평가용 dev 입력은 0건이며 최초 dev5는 격리 보관한다.
아래 기존 실행 기록은 보완 전 시점의 결과다. 현재 상태는 policy-alignment-review.md를 따른다.

## 환경과 CI 기준

현재 main의 `.github/workflows/ci.yml`을 GitHub에서 직접 확인했다.
CI는 ubuntu-latest, Python 3.10, `pip install -r requirements.txt`,
`python -m pytest -q`, `python eval/qa/route_score.py`를 실행한다.
점수 하한은 dev_route_acc 20, sanity_route_acc 28이다.
현재 로컬 브랜치는 mes/develop, HEAD f0e20fa이며 CI 파일은 이 브랜치에 없다.

로컬 검증은 기존 Python 3.10.21, pydantic 2.9.2, pydantic-core 2.23.4,
pytest 8.3.3을 사용했다. Python 3.10용 core와 exceptiongroup·tomli·PyYAML은
기존 로컬 uv 캐시에서 읽었으며 프로젝트 고정 의존성은 바꾸지 않았다.
기본 Python 3.14 및 기존 `.test-deps`의 cp312 core 조합은 스키마 import가 실패했다.
Pydantic 업그레이드 설치는 진행하지 않았다.

## 실행 결과

| 검증 | 결과 |
|---|---|
| plan.py 재실행 바이트 동일성 | PASS, SHA256 `455b0dd01b6d2273e341a6a2a478d9230a09fcc21067b435fed919ae61ab91ea` |
| merge.py → verify.py | T2 10장·T6 9장, 고유 ID·슬롯·스키마·draft/L0 통과 |
| 원장 계약 | 사건 20건(KB15/dev5), 기록 40건, 인계 5요소·MES 신호 통과 |
| 근거 연결 | T6별 KB 사건 2건 이상, 평가용 인용 0, 시도별 원본 일치 |
| 출처·생성 추적 | 출처 존재·locator·원본 프롬프트 SHA256 통과 |
| 기존 프로젝트 전체 테스트 | **445 passed in 31.23s** |
| route_score | dev 18/30, t4 5/20, sanity 26/30 |
| 기존 의존성·통합 KB 파일 | git diff 없음 |

전체 테스트 실제 명령:

```powershell
# Python 3.10 및 해당 바이너리·패키지 캐시를 PYTHONPATH로 지정한 뒤
python3.10.exe -m pytest -q --ignore=tmp --basetemp=tmp/batch-c-pytest-20260930-01 --tb=short
```

첫 테스트 시도에서는 누락된 yaml, Python 3.10의 exceptiongroup/tomli,
임시 의존성 폴더의 테스트 수집, 기본 OS 임시폴더 접근권한 때문에 실행이 막혔다.
기존 캐시 패키지 및 저장소 내부 전용 임시폴더를 사용해 해결했다.
실제 제품 테스트는 제외하지 않았다. `tmp`의 패키지 공급자 자체 테스트만 수집에서 제외했다.

## 판정과 한계

카드 생성·독립 수정·재검토 및 배치 계약 검증은 완료했다. 사람 승인은 미정이다.
현재 브랜치 검색 점수는 main CI의 20/28 하한에 미달하므로 CI 전체 통과로 보고하지 않는다.
C는 draft라 통합 accepted KB에 들어가지 않았고 기존 KB 파일도 바뀌지 않았다.
따라서 이 실행은 C의 검색 효과를 평가한 결과가 아니다.
사람 검수 후 승인된 카드만 통합하고, 평가 라벨과 검색 성능을 재검증해야 한다.
평가 스크립트 실행은 생성·수정이 끝난 뒤 시행했으며 결과로 카드 내용을 변경하지 않았다.
원문 모델 적용성·합성 템플릿 반복·독립 검토자의 원장 접근 편차는 review_round2.md에 기록했다.
