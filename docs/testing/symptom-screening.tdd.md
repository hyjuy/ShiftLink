# 증상 조합 가상 시나리오 검증

일자: 2026-09-30. [논문 조사 및 적용 수치](../research/mes-symptom-screening.md).

## 변경과 판정 범위

15개 증상 조합을 설비별 22개 시나리오로 추가했다. 정상 대조 신호를 포함한 복수 센서 관측으로 원인 후보·추가 확인·출처·해석 한계를 제공한다. 판정 함수는 시나리오 ID·주입 원인·알람 정답을 읽지 않는다. 상태 API와 운영 화면에 연결했다. 기존 승인 카드에는 자동 연결하지 않고 신호 대응표의 `unlinked`에 등록했다.

## TDD 결과

| 단계 | 확인 | 커밋 |
| --- | --- | --- |
| 최초 RED | 미구현 시나리오·함수 때문에 25 failed | `64e6c26` |
| 기본 GREEN | 누락 테스트의 tuple fixture 수정 후 25 passed | `098a8c0` |
| 알람 전환 RED | warning → critical 전환 시 warning 잔류 재현 | `affc804` |
| 알람 전환 GREEN | 양방향 severity 갱신, 25 passed | `1c959ee` |
| 연속성 RED | 중간 paused, 같은 시각, 역순 시각, 재개 후 이전 창 사용 — 4 failed | `a8f12f1` |
| 연속성 GREEN | 유효 수집 상태·엄격한 시각 증가·pause 창 초기화, 29 passed | `e6925d4` |

작은 검증: `python -m pytest -q tests/test_mes_symptom_screening.py --tb=short` — **29 passed**. 원인 라벨 제거, 품질·단위·누락·NaN·Boolean·오래된 관측, 정상 복귀, 중복 프레임, 일시정지·재개, PDP 차단 전후와 Node 화면 표시를 검사했다.

전체 검증: Python 3.10, 기존 프로젝트 의존성으로 다음을 실행했다.

```text
coverage run --source=shiftlink.mes.symptoms,shiftlink.mes.engine,shiftlink.mes.configuration,shiftlink.mes.contracts,shiftlink.mes.scenarios.priority -m pytest -q tests --basetemp=artifacts/symptom-screening-full-01 --tb=short
coverage report --fail-under=80 -m
```

결과: **529 passed in 39.32s**. 변경 모듈 합계 **96%**: symptoms 96%, engine 96%, configuration 94%, contracts 100%, priority 96%. 전체 프로젝트 커버리지나 원격 CI 실행 결과가 아니다. 측정 파일은 `artifacts/symptom-screening.coverage`다. coverage C tracer 미설치로 Python tracer를 사용했다.

## 독립 검토

서브에이전트가 논문 근거·가상 수치 분리, 정답 라벨 미사용, 누락·품질 차단, RT 직접 검증 부재를 검토했다. 알람 등급 갱신과 관측 시간·상태 연속성 문제 2건을 실제 실행으로 발견했고 위 RED/GREEN으로 수정했다. 별도 연구 에이전트가 HPU·CAU 3개 논문의 출처·숫자·접근 제한 표시를 대조해 오류가 없음을 확인했다.

최종 독립 재검토에서 증상 테스트 29개를 다시 실행해 통과했고, 연구 문서의 22개 시나리오 수치·단위가 실제 구성과 모두 일치함을 확인했다. GR·CV·PDP 적용 한계를 포함해 추가 필수 수정은 발견하지 못했다.

실설비 고장 판별 성능을 검증한 결과는 아니다. 가상 수치·3회 관측 설정이며 실제 센서 위치, 부하·수요, 파형, 정격 및 보호 이력이 확보되기 전에는 후보로만 사용한다.
