# 카드 생성 파이프라인 검증 기록

검증일: 2026-09-22. 요청: 근거 연결·검증·초안 저장이 가능한 생성 파이프라인 구현.

구현은 [generation.py](../../shiftlink/data/generation.py), 실행 계약은 [사용 가이드](../guides/card-generation.md), 검증 코드는 [test_generation.py](../../tests/test_generation.py)에 있다. 요청을 승인된 원문 범위로 제한하고 생성 결과를 초안 또는 보완 대기로 저장하는 흐름을 검증했다.

최초 테스트 실행은 새 모듈이 없는 상태에서 `ModuleNotFoundError: No module named 'shiftlink.data.generation'`로 실패했다. 구현 후 최초 실행의 임시 폴더 접근 오류는 권한을 허용받아 재실행했으며 20개가 통과했다. 이후 경계·CLI·트랜잭션 검증을 추가했고, 최종 실행은 작업 폴더 내부의 새 임시 디렉터리를 사용했다.

최종 실행 명령(PowerShell):

```powershell
$env:PYTHONPATH = (Resolve-Path '.test-deps').Path
$env:COVERAGE_FILE = 'artifacts/generation-tests.coverage'
python -m coverage run --source=shiftlink.data.generation -m pytest tests/test_generation.py tests/test_schemas.py tests/test_retrieval_response.py tests/test_data_cli.py --basetemp=artifacts/generation-test-run-20260922-2 -q --tb=short
python -m coverage report -m
```

결과: **130 passed in 4.37s**. 생성 파이프라인 자체 테스트 38개, 기존 스키마·검색/응답·계획 CLI 회귀 테스트 92개. 새 모듈 문장 커버리지 **97% (248 statements, 8 missed)**.

| 보장 | 검증 |
|---|---|
| 검토된 발췌문 → 카드 생성 → 근거 연결 → SQLite 저장 → 스키마 재로드 | Python 함수 통합 테스트 |
| UTF-8 stdin/stdout 생성기 호출 및 기존 후보 응답 가져오기 | 실제 자식 프로세스를 실행한 CLI 테스트 |
| pending 출처·변조된 본문·sealed·미배정 그룹·사건 그룹 불일치·금지 입력 차단 | 모델 호출 횟수가 0인지 확인 |
| 없는 출처 연결·누락/중복 연결·잘못된 경로·스키마 위반·미등록 참조·임의 승인·알 수 없는 필드 거부 | 초안 0건, needs_review 기록 확인 |
| T3 단계·실패 기록·동일 그룹 EV/AR 참조 저장 | 승인된 합성 테스트 원문을 이용한 성공 경로 |
| 같은 ID/버전의 중복·동시 요청에 덮어쓰기 없음 | 초안 1건, 실행 기록 2건 확인 |
| 감사 기록 저장 실패 시 초안도 롤백 | SQLite 실패 트리거로 트랜잭션 확인 |
| 생성기 예외에서 민감한 원문 오류 메시지 비노출 | 예외 종류만 반환되는지 확인 |
| draft/L0의 자동 KB 채택 방지 | 기존 검색기에 넣어도 로드되지 않는지 확인 |
| dev 분할 유지 | 저장된 카드의 split 확인 |

추가로 `python -m shiftlink.data.generation --help`와 `git diff --check`를 확인했다. 운영 원문 승인·실제 모델 생성·전체 저장소 테스트·대용량 부하 측정은 수행하지 않았다. 근거 문장과 주장의 의미적 일치, 원문 진위, 승인자 권한, 유사 사건 누출 여부는 사람 검토와 별도 운영 통제가 필요하다. 현재 실제 출처 등록부의 승인 상태는 변경하지 않았다.
