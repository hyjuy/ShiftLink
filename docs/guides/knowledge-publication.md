# 근무일지 지식카드의 검수와 검색 반영

## 사용 흐름

1. PDA에서 설비를 선택하고 질문한다. `no_applicable_card`는 적용 가능한 지식을 찾지 못한 상태다. 판정 모델 장애·답변 보류는 이 상태와 다르다.
2. 실제 시도한 조치와 결과를 근무일지에 기록한다. 질문에서 시작한 기록은 `query_id`를 보존한다. 작업자가 기록한 정상 운전 결과와 저장 시점 MES 센서값은 별개의 근거다.
3. 후보 생성 결과와 부족한 항목을 확인한다. 후보가 만들어져도 검색에는 사용되지 않는다.
4. MES `/knowledge-candidates.html`에 관리자로 로그인한다. 원본·원인·조치 결과를 확인한 뒤 **검토 승인**을 누른다. 부족하면 보완 요청 또는 반려한다.
5. 적용 조건·제외 조건·안전·조치 근거를 확인하고 검수 의견을 작성해 **검수 통과**를 누른다. 미구조화 기록이나 임시 결과가 있는 후보는 먼저 근무일지 근거를 보완한다. 현재 화면은 후보를 직접 편집하는 편집기가 아니다.
6. **임베딩 대기 → 임베딩 처리 중 → 검색 반영 완료** 상태를 확인한다. 실패하면 오류와 다음 시도 시각이 표시된다. 사용자가 의견을 작성 중이지 않을 때 선택한 후보 상태를 자동 갱신한다.
7. 같은 설비·자산에서 후속 질문을 하면 게시된 지식을 검색 후보로 사용한다. 질문과 조건에 맞지 않거나 judge가 거절하면 답변에는 채택하지 않는다.

검수 후 보완 요청·반려·다시 검토 승인을 처리하면 기존 산출물은 **재검토로 검색 제외**가 된다. 진행 중이던 임베딩 결과도 다시 게시하지 못한다.

## 저장과 실행

- 기존 MES 실행 진입점 `python -m shiftlink.mes`를 사용한다. 게시 작업자는 이 서버 안의 별도 스레드에서 실행된다. 별도 배포·서비스 재시작 API를 추가하지 않았다.
- 원본 후보는 `draft/L0/dev`를 유지한다. 검수된 `accepted/L1/kb` 사본과 입력 텍스트·해시·검수자는 `card_drafts.review_flags.publication`에 저장한다.
- SQLite `knowledge_publications`에 검수 리비전·카드·청크·벡터·manifest를 원자적으로 저장한다. 기존 정적 KB JSON과 `data/rag2` 파일은 덮어쓰지 않는다.
- S30h는 정적 인덱스와 일치하는 모델·prefix·차원의 게시 데이터를 질의용 뷰에 합쳐 벡터 검색한다. 기존 FixedPipeline은 임베딩이 완료된 카드만 기존 카드 검색 방식에 합친다. 이 모드의 검색 순위는 기존처럼 어휘 기반이다.
- 모델은 현재 S30h C와 같은 `embeddinggemma:300m`다. `OLLAMA_HOST`의 `/api/embed`를 사용하며 문서 prefix와 query prefix를 공유한다. CPU 옵션을 사용한다. 모델 이름만 바꿔 기존 벡터를 재사용하지 않는다.
- 네트워크 호출 중 MES 잠금을 유지하지 않는다. 실패 시 최대 300초 간격으로 재시도하고, 중단된 작업은 180초 lease가 끝난 뒤 복구한다.
- 질의마다 새 게시 상태를 읽으므로 검색 반영을 위해 서버를 다시 띄울 필요가 없다. 정적 KB 파일을 별도 변경하는 기존 수동 시연 스크립트와는 다른 경로다.

## 검증 명령

프로젝트 Python 환경과 저장소 루트에서 실행한다.

```powershell
python scripts/check_knowledge_publication.py
python -m pytest tests/test_knowledge_publication.py tests/test_publication_worker.py tests/test_publication_s30h.py tests/test_candidate_management.py tests/test_embedding_contract.py tests/test_publication_harness.py -q
python -m pytest tests/test_publication_browser.py -q
```

브라우저 테스트에는 Python Playwright와 Chrome이 필요하다. CI에서는 `SHIFTLINK_BROWSER_CHANNEL`을 빈 문자열로 지정하고 Playwright Chromium을 사용한다. 기본 테스트는 실제 모델 대신 명시적인 결정적 응답을 사용한다.

실제 Ollama가 준비됐을 때만 아래 검사를 별도로 실행한다. 모델을 다운로드하거나 외부 서비스를 재시작하지 않으며 임시 DB·인덱스를 사용한다.

```powershell
$env:SHIFTLINK_LIVE_EMBED_HOST = 'http://127.0.0.1:11434'
python -m pytest tests/publication_live.py -q -s
```

이 검사는 실제 문서 임베딩·DB 게시·실제 query 임베딩·S30h 검색 후보 조회까지 확인한다. 최종 judge·답변 품질이나 실장비 안전성을 검증하는 검사는 아니다.
