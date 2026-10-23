# v14c PR 체크아웃 검증

원본 작업 트리와 산출물을 보존하고 `origin/main`의 `93fcad62`에서 `codex/causal-v14c-cooling` 브랜치를 만들었다. 기본 브랜치에 없는 v8~v13 의존 코드·계약·회귀·보고서만 `13ceffae`의 Git 내용에서 복원하고, v14 관련 7개 커밋을 순서대로 옮겼다. 기존 PDA/MES 서비스·배포 파일·다른 진행 중 작업은 포함하지 않았다.

정적 import 목록만으로는 `importlib`이 읽는 `mes_timestral_notifications.py`를 놓쳐 첫 테스트 수집이 실패했다. 원본 파일을 그대로 추가한 뒤 아래 검사를 다시 실행했다.

```powershell
python -m unittest tests.test_mes_causal_v14c tests.test_mes_causal_v14 tests.test_mes_causal_v13 tests.test_mes_causal_v12 tests.test_mes_causal_v11 tests.test_mes_causal_v10b tests.test_mes_causal_v10 tests.test_mes_causal_v9 tests.test_mes_causal_benchmark tests.test_mes_causal_train tests.test_mes_causal_contract_edges tests.test_mes_timestral_tail_guarded -q
```

결과: **130 tests / 50.381초 / OK**. 기존 로컬 Python3.13.15·NumPy2.2.6 연구 환경으로 실행했다. 새 변경 Python51개 구문 컴파일, Git diff 공백 검사, v14/v14c 핵심·실행기 원본 Git blob 동일성, 공개 평가 사본6개 SHA256 검사가 통과했다.

고정 후보를 다시 학습·보정하지 않았고 미사용 평가를 재생성하지 않았다. PR의 `docs/research/evidence/mes-causal-v14c-20261023/`는 보존된 최종 요약을 복사한 것이다. 전체 원자료·이전 단계 캐시·절대 경로 기반 lock이 없으므로 새 체크아웃에서 전체 성능 평가 CLI를 그대로 재실행할 수는 없다. 전체 프로젝트 테스트 및 GitHub CI 결과는 별도로 확인해야 한다. Pi/Jetson 실행·배포·운영 통지 연결은 수행하지 않았다.
