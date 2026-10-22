# Jetson 지식카드 변경을 최신 main에 통합한 기록

점검일: 2026-10-22. 기준 main: `cf8b3fe9e4ef41b518a399150d7cb8c1eb6c31a9`.
작업 브랜치: `codex/jetson-knowledge-sync`.

## 통합 범위

Jetson 배포 파일을 읽기 전용으로 확보한 뒤 별도 작업트리에서 추가 기능을 이식했다.
사용자 결정은 **최신 main 유지 + Jetson 추가 기능 이식**이다. 주 작업 폴더의 변경과 staging은 건드리지 않았다.

- `storage.py`: 기준 KB 카드의 SQLite 목록 저장·동기화. 유효한 accepted/kb/L1 카드만 받아들이고 후보 심사로 이 목록을 승격하지 않는다.
- `server.py`: `/api/knowledge-cards` 목록·상태 집계, 새 정적 자산, 기존 Jetson의 `SHIFTLINK_SERVE_PDA` 스위치.
- `pda.html`: 안전 카드 접기 스타일과 새 모듈 링크.
- `pda.js`: 기존 지식 현황 렌더 뒤 이벤트 한 개를 발행한다. 기존 근무일지·주간 집계·손실 상세·센서·질의 처리를 유지한다.
- `knowledge.css/js`: 카드 검색·상태 필터·원문/출처·근무일지 연결·오류 안내. 기존 대시보드 집계를 유지하며 목록 진입부를 덧붙인다. 390px/1280px 화면에서 공통 버튼 폭 및 flex 축소 충돌을 보정했다.

Jetson의 오래된 파일에는 최신 main의 게시 관리자·작업자, 검수 artifact, 질의 snapshot·최종 publication ticket 확인이 빠져 있었다. 이 삭제는 이식하지 않았다.
`query.py`의 C5 스위치는 main에 이미 있어 파일을 변경하지 않았다. main과의 diff는 0이다.
검토 승인, 검수 통과, 임베딩 대기, 검색 반영 완료, 재검토로 검색 제외를 구분한다.
정적 기준 KB 수와 게시된 현장 후보 수를 섞어 표시하지 않는다.

## 검증

- 새 저장/API 검사 4개: 최초 구현 전 실패를 확인한 뒤 통과. 영속성·중복/부적격 거절·현재 KB 필터·검수/게시/재검토 상태·원문 보존·PDA 제공 스위치를 검사했다.
- 관련 Python 단위/HTTP/S30h/게시 작업자 회귀 118개 통과. 새 실제 Chrome 검사의 초기 대기 조건을 보이지 않는 화면의 렌더 이전 값에서 대시보드 값으로 수정한 뒤 해당 검사도 통과했다. 총 119개의 서로 다른 검사가 통과했다.
- 새 실제 Chrome 검사는 로컬 MES HTTP와 fixture 임베딩을 사용한다. 목록 86건, 검색, 상태 전이, 원문/locator, Enter 진입, 기존 대시보드와 센서 영역, API 503 시 이전 목록 제거, 390px/1280px 제목 및 목록/상세 겹침 방지를 확인했다.
- 기존 게시 Chrome 검사는 질문→근무일지→검토→검수→게시 흐름을 실행했다. 출력 경로만 `docs/demo/kg/.jetson-sync-qa/`로 바꾼 검증용 복사본으로 실행했다.
- Node: `pda_sensor_display`, `pda_network_boot`, `unity_pda_link`, `pda_symptom_rank`, `mes_query_pda`, `pda_chat` 모두 통과. `pda.js`, `knowledge.js` 문법 통과.
- `python scripts/check_knowledge_publication.py` 통과. staging 후 재실행하여 staged Python 문법 검사까지 통과했다.
- 추가 `pda_dashboard_layout.cjs` 검사는 `375 reportSelect: logo x`에서 실패했다. 최신 main 원본 HTML/JS를 같은 HTTP fixture로 제공해도 동일하게 실패함을 확인했다. 기존 모바일 로고 정렬 실패를 이번 범위에서 고치거나 통과로 기록하지 않았다.
- 실제 모델 생성 결과와 fixture 결과를 구분한다. 이 PR 코드를 Jetson에 배포해 실행한 검증은 아니다.

검증 임시 파일·스크린샷·다운로드 원본은 커밋에서 제외한다.

## 배포 시 확인할 사항 — 이번에는 실행하지 않음

1. PR 병합 후 **같은 병합 리비전의 `server.py`와 `query.py`를 함께 배포**한다. 현재 Jetson의 query.py는 C5 스위치가 들어간 이전판이므로 그대로 두면 최신 게시 snapshot/ticket 계약을 놓친다.
2. `storage.py`, 새 웹 파일 및 main의 publication 관련 의존 모듈도 같은 리비전으로 맞춘다. 두 파일만 복사해서 모든 의존성이 충족된다고 가정하지 않는다.
3. 기존 DB·서비스 설정·배포 파일을 보존하고 실제 상태/질의/게시 경로를 배포 절차에서 확인한다. 모델·정적 KB·인덱스를 재생성하지 않는다.
4. Pi의 `shiftlink/pda/__main__.py`는 현재 `pda.html`과 `pda.js`만 정적 제공한다. 따라서 **Pi 로컬 서버에서는 새 knowledge 자산과 관리자 검토 페이지가 아직 제공되지 않는다**. 이번 Jetson 파일 통합에서는 보호 지침에 따라 Pi 서버를 수정하지 않았다. Pi 화면까지 배포하려면 별도 정적 경로 지원·검증이 필요하다.

장비 서비스 재시작·배포·main 병합은 수행하지 않았다. Jetson 확인 종료 시 MES 서비스는 PID `34795`, 시작 시각 `2026-10-22 12:57:34 KST`, active 상태를 유지했다. server/storage/query 파일 해시도 읽기 전용 확보 당시와 같았다.

## 확보한 Jetson 원본 SHA-256

배포 폴더에는 Git 이력이 없어 배포 SHA를 추정하지 않고 파일 해시를 남긴다.

| 파일 | SHA-256 |
|---|---|
| `server.py` | `0828238f62a9758f1aecb433be0a5733ee1476d5c3a7730244f6617a0d945551` |
| `storage.py` | `d7712dbb65540be91ce9fa0baf991945c6a8d5fd2dacee8fdcd9328186ab12bc` |
| `query.py` | `cf2f5049c8d8a59cc11e157573f7e3ce67f8f4ae0075d3f437a89b35911ef114` |
| `pda.html` | `051a6a7c17b1784d10cce624557851b20d727cf6ed738916509dcc9aadf643c3` |
| `pda.js` | `64779ff6b0b16ca6300faee2ec3dff80e29101ac82bda2b47fac923a068db22c` |
| `knowledge.css` | `1767843201f712d62fa9733f17e44741c26f013f7aefb6e6a049037e7f0ef25d` |
| `knowledge.js` | `67495c9e0c47197d8b742458ff07d753c94cb40545c6c9c232b9b4373dde4a61` |
