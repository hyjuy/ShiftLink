# 모의 MES 로컬 실행

저장소 루트에서 `python -m shiftlink.mes` 실행 후 http://127.0.0.1:8000/ 에 접속한다.
표준 라이브러리만으로 서버를 실행할 수 있다. 기본 데이터베이스는 `data/mock-mes.sqlite3`이며 Git 제외 경로다.
서버 재시작과 새 실행은 기존 런 기록을 보존한다. 같은 DB를 여러 서버에서 동시에 열어 운전하지 않는다.

모든 수치와 조치는 합성이며 실제 설비의 운전·정비 절차를 의미하지 않는다.
기준정보의 10대 설비 구성은 시연 가정이다. 기존 미결 사항은 승인 처리하지 않는다.

## 시연

1. 실시간 화면에서 시작을 누르고 소재 위치와 센서 추이를 확인한다.
2. 구동부 이상, 출측 정체, 유압 공급 이상 중 하나를 선택한다.
3. 원인 설비 고장과 영향 설비 대기, 활성 알람 및 이벤트 순서를 비교한다.
4. 복구 진행을 누르고 복구 대기 후 정상 상태로 돌아오는지 확인한다.
5. 기록에서 실행을 선택해 재생하거나 시간 위치를 이동한다. 실시간 제어는 재생과 구분된다.
6. 해당 실행의 JSONL 또는 CSV를 내려받는다.

## 관측 데이터

`MesStorage`와 `ObserverAdapter.observations(run_id, as_of=시각)`으로 해당 시점까지의 스냅샷과 이벤트를 읽는다.
일반 조회와 내보내기는 평가용 `GroundTruth` 테이블을 포함하지 않는다.
기존 Event 변환이나 검수된 지식카드 생성은 구현하지 않았다. 지원 시나리오 S1/S2/S3와 운전 `scenario_id`는 별개다.

## 검증 명령

테스트 의존성이 설치된 환경: `python -m pytest -q`.
이 작업에서 프로젝트 로컬에 설치한 의존성을 쓸 때는 PowerShell에서 `$env:PYTHONPATH = '.test-deps'`를 먼저 설정한다.
커버리지: `python -m coverage run --source=shiftlink.mes -m pytest -q` 후 `python -m coverage report -m`.
JavaScript 행동 검증은 `tests/test_mes_web.py`에 기록된 명령을 사용한다.

세부 시연 가정은 `mock-mes-domain.md`, API는 `mock-mes-contract.md`, 실제 검증 결과는 `testing/mock-mes.tdd.md`를 참고한다.
