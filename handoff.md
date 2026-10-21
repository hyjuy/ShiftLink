# ShiftLink 작업 인계

갱신: 2026-10-21 (Asia/Seoul). 작업 폴더: `D:\obsd\Projects\ShiftLink`.

## 후속 Git 동기화 요청

사용자는 원격·로컬이 뒤처지지 않도록 동기화하고 **PDA는 원격 main과 일치**시키라고 추가 지시했다.
`origin/main` (`4c50d6c`) 병합은 `6c5676f`로 완료했고, PDA 화면과 `shiftlink/pda/`는 원격과 차이가 없다.
기존 PDA 로컬 수정은 백업하고 재적용하지 않았다. MES 서버 로컬 수정은 충돌 없는 3-way로 복원했으며 다른 미커밋 작업은 남겨 두었다.
병합 후 관련 Python 검사 **249개 통과**. 삭제된 `tries`를 요구하던 구형 PDA 테스트는 활성 상태 격리를 더 넓게 검사하도록 갱신했다.
복구 참조·검증·최종 동기화 확인 명령은 `docs/testing/git-sync-20261021.md`에 있다. 새 대화에서는 먼저 `git status --short --branch`와 해당 문서의 동기화 명령으로 현재 원격 반영 상태를 확인한다.
미커밋 작업은 커밋 기준 동기화와 구분하며, 사용자 요청 없이 일괄 커밋하거나 정기 자동 동기화를 만들지 않는다.

## 후속 실행 결과 — 2026-10-21 17:05 KST

- 사용자 요청에 따라 현재 작업 트리에서 관련 12개 Python 테스트 파일을 다시 실행했다. **184 passed in 149.07s**. 실제 Chrome·HTTP·NumPy 랭커 검사를 포함하며, 모델 응답은 결정적 픽스처다. 아래의 183 passed/89%는 이전 실행 기록이고 이번에는 커버리지를 다시 측정하지 않았다.
- PDA JavaScript 문법과 Node 회귀 8개 명령, 검수 JavaScript 문법을 재확인했다. 모두 통과했다. 재생성된 1280/390 화면 이미지도 직접 확인했다.
- `scripts/check_knowledge_publication.py`는 작업 트리·스테이징 Python 검사 포함 `ok=true`였다.
- 실제 `tests/publication_live.py`를 로컬 Ollama 대상으로 실행했지만 **1 failed in 10.58s**. 첫 `/api/embed` 요청에서 `ConnectionRefusedError: [WinError 10061]` / `urllib.error.URLError`가 발생했다. 실제 벡터·게시·검색·judge·답변 성공 증거는 없다.
- 외부 연결을 추가로 분리해서 확인했다. Tailscale ping은 `jetson-06 (100.115.59.4)`에 성공했고, Jetson MES `http://100.115.59.4:8000/api/config`도 응답했다. 따라서 장비 전체가 연결 불가인 상태로 단정하지 않는다.
- Ollama는 `127.0.0.1:11434`, `100.115.59.4:11434`, Tailscale가 확인한 LAN `192.168.10.166:11434` 모두 외부에서 연결 실패했다. SSH `jetson@100.115.59.4`는 `Permission denied (publickey,password).`로 내부 모델·서비스 설정을 확인하지 못했다. localhost에만 바인딩된 것인지, 서비스가 중지된 것인지는 미확인이다.
- 재개에는 접근 가능한 Ollama 주소 또는 인증된 Jetson SSH 연결 정보가 필요하다. 사용자에게 주소/SSH 별칭만 요청했다. 비밀번호·개인키는 요청하지 않았다. 장비 서비스 재시작·모델 설치·배포·운영 DB 변경은 수행하지 않았다.
- 증거: `artifacts/knowledge-publication-live-20261021/regression.xml`, `regression.log`, `live-local.xml`, `live-local.log`. 자세한 명령과 반증 기록은 `docs/harness/knowledge-publication-adoption-20261021.md`의 후속 실행 절을 참고한다.
- 기본 샌드박스 pytest는 Temp 폴더 `PermissionError: [WinError 5]`로 중단했고, 승인된 샌드박스 밖 실행에서 위 결과를 얻었다. 제품 코드 수정은 필요하지 않았다. 기존 사용자 변경·스테이징 상태를 유지했다.

## 사용자 요청

PDA 질문에서 적용 지식 없음 확인 → 조치 시도 → 근무일지 → 지식카드 후보 → 심사 → 검수 → 스키마 구조화 → 임베딩 → RAG 검색 풀 반영까지 구현. `crash-out`과 `harness-engineering` 사용. 컨텍스트가 50% 미만이면 이 파일을 남기고 새 대화로 인계.

이번 세션에는 잔여 컨텍스트 비율 조회나 새 대화 생성 도구가 없다. 새 창을 열었다고 주장하지 않았다. 새 대화에서는 **“handoff.md와 docs/design/project-structure.md를 읽고 이어서 진행해 줘”**라고 시작하면 된다.

## 현재 결과

전체 흐름의 코드와 MES 검수 화면을 구현했다. 결정적 모델 픽스처·실제 HTTP·실제 Chrome·실제 NumPy 검색 랭커로 전체 경로를 검증했다. **실제 Ollama 모델과 Jetson 배포까지 검증한 것은 아니다.**

- 전체 계획: `docs/planning/knowledge-publication-20261021.plan.md`
- 사용법·모드 차이·검증 명령: `docs/guides/knowledge-publication.md`
- 하니스 채택·반증 결과·수치: `docs/harness/knowledge-publication-adoption-20261021.md`
- 실패 기억: `docs/failures/knowledge-publication-integrity.md`
- 파일 범위 지침: `.github/instructions/knowledge-publication.instructions.md`
- 검사 명령: `python scripts/check_knowledge_publication.py`
- CI gate: `.github/workflows/knowledge-publication.yml` (GitHub 실행 결과는 아직 없음)

## 구현 경계

- 기존 `/api/admin/card-drafts/{id}/review`의 `approve`와 `quality_pass`를 구분. 실제 관리자·사유·리비전 감사 이력.
- 원본 근무일지와 draft/L0/dev 카드를 보존. 별도 accepted/L1/kb 사본·입력·해시·원본 사건 자산을 publication에 저장.
- 미구조화·placeholder·스키마 오류·미심사 변경은 검수/게시 차단.
- `mes/publication.py`의 PublicationManager가 Ollama 임베딩을 잠금 밖에서 실행. lease·attempt ID·재시도·늦은 응답 폐기.
- SQLite `knowledge_publications`에 카드·청크·벡터·manifest를 원자적으로 저장. 정적 KB JSON이나 `data/rag2`를 덮어쓰지 않음.
- S30h는 같은 모델/prefix/차원의 delta 벡터를 질의용 뷰에 합친다. FixedPipeline은 임베딩 완료된 카드를 기존 어휘 기반 검색에 합친다.
- 원본 설비·자산·검증된 조건에만 적용. shared pipeline/index는 변형하지 않음. 질의 최종 저장 잠금 안에서 publication ticket을 재검사.
- 재심사·반려 시 검색 제외. 인덱스 손상/불일치는 실패로 표시하고 격리·재처리. judge 거절은 여전히 답변 보류.
- MES 후보 화면에 검수 통과·임베딩 상태·구조화 미리보기·자동 상태 갱신. 긴 JSON은 별도 스크롤.
- PDA 센서·통신·질의 evidence 코드는 수정하지 않음.

## 검증 증거

최종 관련 회귀 **183 passed in 101.84s**:

```powershell
.venv/Scripts/python.exe -m coverage run --branch --data-file=artifacts/knowledge-publication-20261021/.coverage --include=*/mes/publication.py,*/mes/candidate_review.py,*/rag/embedding.py -m pytest tests/test_knowledge_publication.py tests/test_publication_worker.py tests/test_publication_s30h.py tests/test_publication_browser.py tests/test_candidate_management.py tests/test_embedding_contract.py tests/test_publication_harness.py tests/test_work_report_capture.py tests/test_work_report_reuse_harness.py tests/test_s30h.py tests/test_mes_query.py tests/test_mes_storage.py -q --tb=short
```

핵심 모듈 branch 포함 커버리지 **89%** (candidate_review 94%, publication 87%, embedding 94%). 기존 대형 서버·저장소 전체 커버리지가 아님. `coverage report --fail-under=80` 통과.

PDA 검증 명령 모두 통과: `node --check shiftlink/mes/web/pda.js`, `node tests/pda_sensor_display.cjs`, `node tests/pda_network_boot.cjs`, `node tests/unity_pda_link.cjs`, `node tests/pda_symptom_rank.cjs`, `node tests/mes_query_pda.cjs`, `node tests/pda_report_auto_candidates.cjs`, `node tests/pda_report_save_success.cjs`.

검수 JavaScript 문법, drift checker, working/index Python syntax, `git diff --check` 통과. Chrome 1280/390 화면과 후속 질문·재심사 제외를 검증. 아래 최종 이미지를 직접 확인했다:

- `artifacts/knowledge-publication-20261021/review-1280.png`
- `artifacts/knowledge-publication-20261021/review-390.png`
- `artifacts/knowledge-publication-20261021/coverage.json`

## 남은 외부 검증

로컬 `127.0.0.1:11434`와 문서의 Jetson `100.115.59.4:11434` 모두 연결 실패. Jetson은 require_escalated curl로도 연결 불가. 모델을 설치하거나 장비 서비스를 재시작하지 않았다.

실제 Ollama가 준비되면 별도로 실행:

```powershell
$env:SHIFTLINK_LIVE_EMBED_HOST = 'http://127.0.0.1:11434'
.venv/Scripts/python.exe -m pytest tests/publication_live.py -q -s
```

이 opt-in 검사는 실제 임베딩→임시 DB 게시→실제 query 임베딩→S30h dense 검색까지다. 실제 judge/답변 품질·실장비 안전 검증은 별도다. 기본 테스트 성공을 실모델 성공으로 표현하면 안 된다.

## Git·안전 지침

브랜치 `fix/pda-workspace-restore-pr317`. 사용자·다른 작업의 미커밋 변경이 많다. 전체 git add/reset/stash 금지.

특히 기존 변경: `.github/workflows/ci.yml`, `.gitignore`, `server.py`, `storage.py`, `pda.js`, 계정·랜덤 MES·Unity·연구 파일 등. `AGENTS.md`는 로컬 ignored 파일. `docs/design/project-structure.md`는 다른 작업이 만든 미추적 파일이며 이번 publication 경로만 덧붙였다. 이 두 파일을 강제로 추가하거나 문서 전체를 임의로 커밋하지 않는다.

주요 체크포인트:

- `d0028e3`, `24345cd`: 별도 검수/구조화 RED/GREEN.
- `2818790`, `b4182db`: 작업자/검색 뷰 RED/GREEN. 단, b4182db의 스테이징 코드 배치 오류는 아래에서 수정됨.
- `b60b3d8`, `98fdfb4`: 인덱스/화면 RED/GREEN, 스테이징 배치 수정.
- `a7f694a`, `4647560`: 손상/미심사 변경 RED/GREEN 및 하니스.
- 최종 문서·화면 미세 조정 커밋은 `git log -1`로 확인.

중요한 실패: 필터링한 zero-context patch를 부분 스테이징해 코드가 다른 위치에 들어간 적이 있다. 작업 트리 테스트만으로 발견할 수 없었고 커밋 대조에서 발견·수정했다. **그 방식은 재사용 금지.** 현재 checker는 staged blob도 AST 검사하며, 검사 자체를 고장 주입 테스트로 확인한다. `tmp/stage_publication_hunks.py`는 문맥이 있는 전체 섹션을 비교·AST 검증하는 방식으로 교체했으나 임시 보조일 뿐이다.

## 환경과 후속 대화

`.venv/Scripts/python.exe`: Python 3.13, pytest 8.3.3, NumPy·Python Playwright·coverage 7.16.2. Chrome 사용 가능. Node Playwright와 agent-browser CLI는 없어 Python Playwright로 검증했다. 샌드박스 기본 Temp 접근이 차단되어 pytest/coverage는 require_escalated로 실행했다.

적용 스킬: ponytail, tdd-workflow, systematic-debugging, crash-out, harness-engineering, impeccable. 자동 새 대화 생성은 지원 도구가 없어 수행하지 못했다. 새로운 요구가 없다면 외부 모델 연결 복구 후의 실모델 검증이 다음 단계다.
