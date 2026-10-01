# 관측 표현 구체화 후 카드 검색 회귀 검증

CI 실패 보고에서 도출한 작업이다. 관측 기준을 구체화해도 펌프 소음 질의가 기존 징후 카드 K-1004를 찾는 동작을 유지한다.

## 원인과 수정

K-1004의 symptom에서 펌프라는 설비 주어가 빠져 검색 관련도가 낮아졌다. 합성어 베인펌프만으로는 기존 두 글자 접두 토큰 비교에서 펌프와 일치하지 않았다. symptom에 `펌프 운전 중`을 복원하고 정상 소음 기록·요구값·현장 기준 미확인 시 미판정이라는 구체화 내용은 유지했다.

cards.json, out/HPU.json, 대응표 JSON/Markdown의 인용을 동기화하고 build_kb.py로 통합 목록을 다시 생성했다. 카드 ID·개수·조건·승인 상태·출처는 변경하지 않았다. 검색 가중치나 CI 평가 기준도 변경하지 않았다. 회귀 테스트는 dev 질문이나 정답을 복사하지 않고 짧은 설비·증상 질의 `펌프 소음`을 사용한다.

## RED / GREEN 증거

2026-09-30에 Python 3.12.10, `PYTHONPATH=.test-deps`로 실행한 결과다.

| 보장 | 실제 명령 | 결과 |
| --- | --- | --- |
| 수정 전 펌프 소음 검색 회귀 재현 | `python -m pytest tests/test_kb_cards.py -k pump_noise -q` | RED: 검색 결과가 []여서 1 failed, 3 deselected. 체크포인트 `4c1e459`. |
| 같은 검색이 K-1004를 1위로 반환 | `python -m pytest tests/test_kb_cards.py tests/test_card_loader.py tests/test_mes_card_adapter.py -q` | GREEN: 26 passed. |
| 기존 프로젝트 동작 유지 | `python -m coverage run --data-file=artifacts/numeric-card-routing.coverage --source=shiftlink.rag -m pytest tests -q` | 549 passed in 26.42s. |
| 검색 모듈 커버리지 | `python -m coverage report --data-file=artifacts/numeric-card-routing.coverage --fail-under=80` | 92% 전체, retrieval.py 94%. |
| CI 점수 기준 충족 | `python eval/qa/route_score.py` | dev 20/30, t4 7/20, sanity 29/30. |

main 카드 목록으로 같은 평가를 실행하면 dev 20/30, t4 7/20, sanity 28/30이다. 수정 전 PR은 dev 19/30, t4 7/20, sanity 29/30이었다. 이번 수정은 Q-001의 회귀를 해소했으며 기존 T4 미일치의 개선을 주장하지 않는다. qa_test.json 등 최종 평가 데이터는 읽지 않았다.

전체 검증은 저장소의 tests 경로를 명시했다. 최초 무제한 수집은 로컬 tmp/artifacts의 별도 테스트·다른 ABI 의존성까지 수집해 중단됐다. tests 한정 실행에서 누락된 PyYAML을 .test-deps에 보완한 후 위 결과를 얻었다. 이는 CI 설정 변경이 아니다.

카드 원본에서 K-1004 symptom만 변경됐으며 출력·두 대응표의 인용 일치를 별도로 검사했다. 실제 설비 적용성은 사람 검수 대상이다. 작업 폴더 접근 중단으로 지연된 커밋·PR 반영을 2026-10-01에 재개했다.
