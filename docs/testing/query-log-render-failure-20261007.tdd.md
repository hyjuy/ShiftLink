# 질의 로그 렌더링 실패 보호

사용자가 지적한 경로를 재현했다: 답은 생성됐지만 로그용 `render_response` 또는 `AgentResponse.model_validate` 예외가 `MesService.query`의 반환을 중단한다. 별도 계획 파일 없이 이 두 실패를 테스트로 옮겼다.

| 보장 | 검증 | 결과 |
|---|---|---|
| 렌더러 예외에도 원래 답·안전 공지·인용 ID를 반환하고 로그에 보존, 렌더 전문만 null | `tests/test_mes_query.py::test_log_render_failure_returns_answer_and_preserves_safety[render_response]` | PASS |
| 로그용 모델 검증 예외에도 동일하게 답변 반환 | 같은 테스트의 `AgentResponse.model_validate` 조건 | PASS |
| 정상 안전 우선 렌더링, 검토 대기·지식 없음 처리 및 기존 서버·예열·통신·PDA 계약 유지 | 관련 회귀 대상 423개 | PASS |

- RED `988aa8b`: 새 테스트 2개가 `RuntimeError: log rendering failed`로 실패했다.
- GREEN `fdeeb7e`: 렌더링 및 그 모델 검증만 try로 감싸고 실패 시 `rendered_response=None`; 질의 생성과 저장 오류 처리는 변경하지 않았다. 동일 재현 테스트를 포함한 질의·서버·예열 검사 31개가 통과했다.
- 기존 MES·통신·PDA·응답 렌더러 대상 최종 423개 통과. 분기 포함 `shiftlink/mes/server.py` 커버리지 83%. 프로젝트 전체 커버리지가 아니다.

```powershell
$env:PYTHONPATH = '.;D:/obsd/Projects/ShiftLink/.test-deps'
uv run --offline --python 3.12 --no-project python -B -X utf8 -m pytest tests/test_mes_query.py -k log_render_failure -q -p no:cacheprovider --tb=short
$logRenderTests = (Get-ChildItem tests -Filter 'test_mes_*.py').FullName
uv run --offline --python 3.12 --no-project python -B -X utf8 -m coverage run --branch --source=shiftlink.mes.server --data-file=tmp/query-log-render.coverage -m pytest @logRenderTests tests/test_communication_integration.py tests/test_pda_app.py tests/test_retrieval_response.py -q -p no:cacheprovider --tb=short
uv run --offline --python 3.12 --no-project python -B -X utf8 -m coverage report --data-file=tmp/query-log-render.coverage -m
```

[Jetson 배포와 실제 query_log 행 검증](h1-g2-policy-20261007.tdd.md). 실제 모델 질의는 HTTP 200, 안전 공지 → 답변 → 참고 카드 순서를 Jetson 저장 행에서 확인했다. 렌더 실패는 로컬 예외 주입으로 검증했으며 운영 서버에 실패를 주입하지 않았다. 로그 행 크기 증가에 대한 스키마·업로더 변경은 하지 않았다.
