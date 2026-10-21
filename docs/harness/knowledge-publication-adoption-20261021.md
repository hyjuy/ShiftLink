# 지식카드 게시 하니스 적용 기록

기준일: 2026-10-21. 대상은 질문·근무일지·심사·검수·임베딩·검색 반영 경로다.
`crash-out`과 `harness-engineering`을 적용했다. Python/SQLite/정적 JavaScript 구조와 기존 실행 방식을 유지했다.

## 적용 표면

| 표면 | 파일과 목적 |
| --- | --- |
| 지침 | `.github/instructions/knowledge-publication.instructions.md`: 검수/게시 경계, 원문·자산 보존, 잠금·버전·판정 게이트 |
| 실패 기억 | `docs/failures/knowledge-publication-integrity.md`: 실제 발견한 실패와 실행 가능한 Detection 참조 |
| drift 검사 | `scripts/check_knowledge_publication.py`: 모델·화면 상태·회귀 참조·작업 트리 및 스테이징 코드 문법 |
| 행동 검사 | `tests/test_knowledge_publication.py`, `test_publication_worker.py`, `test_publication_s30h.py`, `test_embedding_contract.py` |
| 실제 화면 | `tests/test_publication_browser.py`: 실제 Chrome·MES HTTP, 명시적 임베딩 픽스처 |
| 검사 자체의 반증 | `tests/test_publication_harness.py`: 모델/화면/참조 변경과 스테이징만 깨진 경우를 주입 |
| CI | `.github/workflows/knowledge-publication.yml`: 독립 gate, 커버리지 80%, Chromium 화면 검사. 기존 수정 중인 CI는 보존 |
| 실제 모델 후속 검사 | `tests/publication_live.py`: 명시적으로 실행하는 Ollama→게시→dense 검색 검사 |

## 반증 결과

| 주장 | 판정과 증거 |
| --- | --- |
| 스키마가 유효하면 검수 통과시켜도 된다 | **BUSTED**. 임시 절차도 스키마를 통과했다. 미구조화/placeholder를 차단하는 회귀 추가 |
| 카드 해시만 맞으면 검색 데이터도 같은 버전이다 | **BUSTED**. 모델·prefix·청크·입력·원본 리비전을 별도 검사하고 불일치를 격리 |
| 임베딩이 끝나면 검색 가능으로 바꿔도 된다 | **BUSTED**. 중간 반려·재심사를 다시 검사하며 카드/벡터/상태를 한 트랜잭션으로 게시 |
| 작업 트리 테스트가 통과하면 커밋도 실행 가능하다 | **BUSTED**. 부분 zero-context 스테이징 배치 오류를 발견했다. 커밋 수정과 index AST gate·고장 주입 테스트 추가 |
| 새 카드가 S30h에 실제 검색되고 judge 거절도 유지된다 | **SURVIVED**. 실제 NumPy 랭커·기존 judge 게이트 테스트와 HTTP/브라우저 후속 질의로 확인. 모델 응답은 픽스처 |
| 실제 Ollama 모델과 배포 장비까지 검증됐다 | **미검증**. 로컬과 기록된 Jetson 주소 모두 연결 실패. 실물 모델 검사 명령을 따로 제공 |

## 명령과 결과

- 작업자/검수/관리자 회귀: 31 passed.
- S30h/실제 Chrome 1차: 8 passed. 화면 폭 1280/390, 수평 넘침 없음, JavaScript 오류 없음. 이미지 직접 확인.
- 손상 index/미심사 변경/HTTP 계약 추가 검사: 19 passed.
- 하니스 정상 및 고장 주입: 5 passed.
- 최종 관련 회귀: **183 passed in 101.84s**. 아래 12개 파일을 coverage로 함께 실행했다.
- `python -m coverage run --branch --data-file=artifacts/knowledge-publication-20261021/.coverage --include=*/mes/publication.py,*/mes/candidate_review.py,*/rag/embedding.py -m pytest tests/test_knowledge_publication.py tests/test_publication_worker.py tests/test_publication_s30h.py tests/test_publication_browser.py tests/test_candidate_management.py tests/test_embedding_contract.py tests/test_publication_harness.py tests/test_work_report_capture.py tests/test_work_report_reuse_harness.py tests/test_s30h.py tests/test_mes_query.py tests/test_mes_storage.py -q --tb=short`: 통과.
- `python -m coverage report --data-file=artifacts/knowledge-publication-20261021/.coverage --show-missing --fail-under=80`: **전체 89%** (candidate_review 94%, publication 87%, embedding 94%). 기존 대형 서버·저장소 전체 커버리지를 뜻하지 않는다.
- `python -m coverage json --data-file=artifacts/knowledge-publication-20261021/.coverage -o artifacts/knowledge-publication-20261021/coverage.json`: 생성 완료.
- `python scripts/check_knowledge_publication.py`: `ok=true`, 스테이징 Python 검사 포함.
- `node --check shiftlink/mes/web/pda.js`, `node tests/pda_sensor_display.cjs`, `node tests/pda_network_boot.cjs`, `node tests/unity_pda_link.cjs`, `node tests/pda_symptom_rank.cjs`, `node tests/mes_query_pda.cjs`, `node tests/pda_report_auto_candidates.cjs`, `node tests/pda_report_save_success.cjs`: 모두 통과.
- `node --check shiftlink/mes/web/candidate-review.js`: 통과.
- Impeccable detector: `/static/*.css` URL을 파일 경로로 해석하지 못해 경고. 실제 연결된 CSS·브라우저 화면을 기준으로 확인했다.
- 실행 모델 목록 확인: `curl.exe --max-time 8 --silent --show-error http://100.115.59.4:11434/api/tags` 연결 실패. 로컬 `127.0.0.1:11434`도 연결 실패.
- CI workflow는 로컬과 동등한 gate를 정의했으나 GitHub에서 실행한 결과는 아직 없다.
- `git diff --check`: 통과. 검증 결과 이미지 두 장을 직접 확인했다. 최종 UI는 긴 구조화 JSON을 별도 스크롤로 표시하며 화면 폭을 넘지 않는다.

## 운영상 해석과 효과 측정

검수 상태와 게시 상태를 혼동하는 버그, 늦은 임베딩 결과의 재게시, 모델/인덱스 drift, 다른 자산의 기록 혼입을 반복 주입해 탐지 여부를 측정한다.
CI 성공은 결정적인 회귀 기준이다. 실장비·실제 모델 성능이나 사실 정확도의 인증으로 사용하지 않는다.
전체 흐름의 구현과 실제 모델 측정은 구분하고, 모델 준비 후 `tests/publication_live.py` 결과를 이 문서에 추가한다.
