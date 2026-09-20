# 설비 관계·선택 근거 화면 검증

## 사용자 여정 및 RED

사건 발견 → 설비 또는 관계 선택 → 가정 부품과 관측 근거 구분 → 다음 조치 확인 → 정상 복귀 및 인계 맥락 보존.

`python -m unittest tests.test_mes_operator -v`를 먼저 실행하여 `operator.js`와 화면 설명/검색/필터가 없는 2개 실패를 확인했다. RED 체크포인트는 `2b23d12`다.

전문가 피드백 후 안정화의 ‘복구 관찰’, 기준 없는 신호 판정, 비활성 선행 설비 등 회귀 검증을 추가했다. 안정화가 ‘영향 대기’로 표시되는 실패를 재현한 후 수정했다. 유압유 과열의 부품 기대값은 실제 시나리오 정의에 맞춰 `cooling`으로 정정했다.

## GREEN

PowerShell에서 `PYTHONPATH=.test-deps`를 설정하고 실행:

```text
python -m coverage run --source=shiftlink.mes -m pytest -q tests/test_mes_recovery.py tests/test_mes_recovery_web.py tests/test_mes_engine.py tests/test_mes_configuration.py tests/test_mes_integration.py tests/test_mes_http.py tests/test_mes_server.py tests/test_mes_storage.py tests/test_mes_contracts.py tests/test_mes_web.py tests/test_mes_ui_layout.py tests/test_mes_operator.py
python -m coverage report -m
```

**97 passed, MES Python 92% coverage**. Windows 임시 SQLite 폴더 접근이 샌드박스에서 거부되어, 승인된 동일 명령을 권한 제한 밖에서 재실행해 통과했다. Python coverage는 JavaScript coverage가 아니다.

| 보장 | 검증 |
| --- | --- |
| 유압 영향 4대, 구동 영향 2대, CV-02 물류 분기 보존 | 실제 서비스 스냅샷 기반 Node assertions |
| 부품 가정·현재값·구성 범위·누락·기준 없음 구분 | test_mes_operator.py |
| 과열 2종·누유·제품 보류 및 안정화·완료 | test_mes_operator.py, test_mes_recovery.py |
| 비활성 선행 설비를 원인으로 선택하지 않음 | test_mes_operator.py |
| 관계 출발/도착/종류의 고유 선택 및 근거 | test_mes_operator.py |
| 같은 공급원의 다른 목적지 관계 포커스 보존 | mes_operator_dom.cjs |
| 갱신 때 열린 details와 summary 포커스 보존 | mes_operator_dom.cjs |
| 최초 연결 실패 뒤 재시도 | test_mes_web.py |
| 기존 제어·품질 보류·저장·재생·내보내기 | 기존 MES 회귀 테스트 |

추가 확인: `node --check shiftlink/mes/web/app.js`, `git diff --check`. 로컬 서버 `http://127.0.0.1:8011`에서 `/`, `/static/operator.js`, `/static/app.js`, `/static/style.css`, `/api/state`가 모두 HTTP 200으로 응답하고 설비 10개가 반환됨을 확인했다.

## 한계와 독립 평가

DOM 계약 테스트는 제한된 테스트 객체를 사용하므로 실제 브라우저 동작 검증을 대체하지 않는다. 연결된 브라우저가 없어 클릭 E2E·화면 캡처·실제 표시 대비·터치 검증은 수행하지 못했다. UI 91점, 설비 92점은 정적 준비도다. 지표별 점수, 수정 경과, 별도 실측 성능은 [설계 및 평가 기록](../mes-operator-design.md)에 있다.

기존 작업 트리의 관련 화면 변경을 보존·통합했으며, 매뉴얼 원본 등 무관 파일은 수정하지 않았다.

## 사용자 피드백: 장비 애니메이션 복원

텍스트 노드보다 이전 장비 애니메이션이 한눈에 이해된다는 피드백을 반영했다. 기존 SVG 그림을 재사용하여 롤러·기어·벨트·공급 계통을 표시하고 코일 위치는 별도로 갱신한다. 관계·부품·근거·복귀 패널은 유지한다.

- RED `2b61531`: 장비 그림과 회전 요소 누락을 테스트로 재현했다.
- GREEN: `PYTHONPATH=.test-deps`에서 `python -m pytest -q tests/test_mes_operator.py tests/test_mes_web.py tests/test_mes_ui_layout.py tests/test_mes_recovery_web.py` → **13 passed**.
- 같은 설비 안 코일 위치만 변할 때 장비 SVG를 재생성하지 않는 렌더 계약을 검증했다. 기존 가동/대기/고장/일시정지/움직임 끄기 판정 테스트도 통과했다.
- `node --check`로 app.js/operator.js 구문을 확인했고, 실행 중 로컬 서버가 장비 그림이 포함된 최신 정적 파일을 HTTP 200으로 제공함을 확인했다.
- 이전 97개 회귀 및 성능 수치는 애니메이션 복원 전 리비전의 결과다. 이번 변경은 위 13개 관련 테스트로 검증했다. 실제 브라우저의 애니메이션·FPS·배치 검증은 여전히 미수행이다.
