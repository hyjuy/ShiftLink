# main 7582378 Jetson·Pi 배포 결과

2026-10-22 KST에 승인된 배포와 아래 범위의 검증을 완료했다. 적용 소스는 병합 main `75823786b44befc2b6fb75b531d6344a08bd82c0`이다. 최종 운영 상태 확인 시각은 **14:26:08 KST**이며 이후 상태를 보장하는 기록은 아니다.

이 문서는 배포 당시 로컬 검증 기록을 요약한다. 문서 PR에는 DB·압축 백업·장비 응답 사본·스크린샷·임시 검증 스크립트·JSON 결과를 포함하지 않는다. 장비에서 다시 검증하거나 배포한 결과가 아니다.

## 적용 범위

Jetson의 `/home/jetson/shiftlink/app/` 아래에서 다음 13개를 같은 리비전으로 함께 적용했다. MES와 업로더가 모두 정지한 상태에서 교체하고, 전체 적용을 확인한 뒤 MES를 시작했다. 파일별 원자 교체이며 13개 전체를 단일 원자 연산으로 교체한 것은 아니다.

| 상대 경로 | 적용 |
|---|---|
| `shiftlink/mes/candidate_review.py` | 교체 |
| `shiftlink/mes/publication.py` | 신규 |
| `shiftlink/mes/query.py` | 교체 |
| `shiftlink/mes/server.py` | 교체 |
| `shiftlink/mes/storage.py` | 교체 |
| `shiftlink/rag/embedding.py` | 동일 내용 재설치 |
| `shiftlink/mes/web/candidate-review.css` | 교체 |
| `shiftlink/mes/web/candidate-review.js` | 교체 |
| `shiftlink/mes/web/knowledge-candidates.html` | 교체 |
| `shiftlink/mes/web/knowledge.css` | 교체 |
| `shiftlink/mes/web/knowledge.js` | 교체 |
| `shiftlink/mes/web/pda.html` | 교체 |
| `shiftlink/mes/web/pda.js` | 교체 |

교체 대상 외 의존 파일 49개는 비교만 했다. 적용 후 62개 소스 해시가 고정 main과 일치했다. 배포 묶음 SHA-256은 `183558f43b382a18af33be851e1b5b9493dbe1723ba0037ca4980eaa35d9c82a`이다. 별도 KG explain 브랜치의 코드를 이 배포에 섞지 않았다.

Pi는 `/home/pi/shiftlink/app/shiftlink/mes/web/pda.js`만 교체했다. 기존 HTML·PDA 서버·autostart 설정과 실행 프로세스를 유지했으며 서비스를 재시작하지 않았다. HTTP가 새 JS를 제공하는 것을 확인했다. 기존 물리 키오스크 세션을 강제 새로고침하지 않았으므로 해당 화면은 다음 새로고침부터 새 JS를 읽는다.

| Pi 파일 | 배포 후 SHA-256 |
|---|---|
| pda.js | `057ea5b52f1835fc025a6d571ea89107e602458b581300f3de1d5f8f1f79a2f6` |
| 보존한 pda.html | `450ab200d0abdec571475ba1e65bafb3ed11c982ffe3ba8d4468a6c52a622033` |

## 새 백업과 보호 대상

- Jetson: `/home/jetson/shiftlink/backups/20261022-140849-main-7582378/`.
- Pi: `/home/pi/shiftlink/backups/20261022-140849-main-7582378/`.
- Jetson `code-before.tar`: 기존 코드 12개와 메타데이터. 신규 publication.py의 사전 부재도 기록했다.
- Jetson `settings-before.tar`: MES·업로더 unit, MES drop-in 4개, 계정 및 업로더 환경 파일 등 8개를 보호 백업했다. 내용은 공유하지 않는다.
- `database-before.sqlite3`: 두 서비스의 정지와 MainPID=0을 확인한 뒤 읽기 전용 연결과 SQLite backup API로 생성했다. 크기 **2,487,664,640 bytes**, SHA-256 **`8df21eb10b38aeaaf86ed4cd4493008e13add763a78d370a060bf30872241247`**.
- 백업의 21개 테이블 행 수와 주요 내용 해시가 원본과 일치했다. `integrity_check=ok`, 외래키 위반 0건. 백업·검사에 243.71초가 걸렸다.
- 별도 복구 사본의 초기 바이트 동일성을 확인한 뒤 사본만 이행·게시 검증에 사용했다. 보존 백업 해시는 끝까지 유지됐다.
- Pi는 기존 JS·HTML·서버 파일과 autostart 설정을 별도로 백업했다.

C5 drop-in과 나머지 영구 설정, 입력 JSON, `data/rag2` 색인, 모델 digest를 보존했다. 색인은 3,950행 × 768차원이며 교체하거나 재생성하지 않았다. C3 비상 복귀 스크립트도 실행하지 않았다.

## 서비스와 실제 질의

| 대상 | 배포 당시 확인 결과 |
|---|---|
| MES | 14:23:30 KST 시작, active, 자동 재시작 0회, 종료 상태 0 |
| 업로더 | 14:25:27 KST 재개, active, 자동 재시작 0회, 종료 상태 0 |
| 임시 제어 | 검증 중 업로더의 동시 시작을 막은 작업 전용 `/run` drop-in 제거 완료 |
| 답변 모델 | 11434의 `ollama ps`에서 `exaone-rag-mes-ck176:latest` 확인 |
| judge 모델 | 11436의 `ollama ps`에서 `exaone-sft-judge:latest` 확인 |

Ollama 서비스는 재시작하지 않았고 모델 선택·파일·digest를 바꾸지 않았다. 새 MES 프로세스의 C5 환경 항목도 확인했다.

RT-02(`EQ-0007`)에 **“클램프 압력 지금 어때요?”**를 실제 요청했다. HTTP 200, 8.81초였으며 답변이 **`현재 MES(RT-02):`**로 시작했다. 센서 근거의 설비 ID·값·단위가 유지됐고 당시 클램프 압력 105.479 bar를 정상 범위 95–115 bar와 연결해 설명했다. 응답 원문이나 요청 식별자 사본은 이 문서에 싣지 않는다.

이 답변의 카드 인용은 비어 있었다. 실제 필드는 `no_knowledge=false`, `knowledge_status=unknown`이었으므로 카드 기반 답변 성공으로 해석하지 않는다. 실제 Pi 주소를 연 Chrome에서 센서 GET을 확인하고, 위 실제 응답을 로컬에서 재생해 답변·센서 근거·인용 필드의 표시를 검증했다. 브라우저의 추가 POST를 가로채 중복 질의 기록을 만들지 않았다.

## 검증 결과

| 검증 | 실제 결과와 범위 |
|---|---|
| 장비 DB 사본 | Python 3.10.12 + 실제 배포 코드로 18개 검사 통과. 복원·이행·원문 보존·게시·재검토·무결성 확인 |
| 실제 게시 검색 | 사본에 실제 embeddinggemma:300m의 768차원 벡터 저장. 운영 색인 3,950행을 읽기 전용으로 사용하고 게시 2행을 합친 3,952행 뷰에서 검색 결과 8개 내 게시 카드 확인 |
| 게시 경계 | 검토 승인만으로 검색 불가, 검수 후 임베딩 대기, 재검토 시 검색 제외와 ticket 무효화 확인 |
| 운영 데이터 보존 | 주요 14개 테이블의 원래 행 해시 보존. 새 실행·질의 기록은 정상 추가로 구분 |
| 운영 후보 | 검토 대기 3건·검토 승인 1건 유지. 게시 테이블 0행, 검증용 기록 0행. 기존 카드 86개 유지 |
| 운영 HTTP | 상태·설정·카드 목록·웹 해시·Pi 프록시·RT-02 계약 등 13개 검사 통과 |
| 실제 Chrome | Pi 센서·답변 표시, Jetson 게시 관리 로그인 화면 확인. 미처리 JS 오류 0, 비인증 관리자 API 401 |
| 업로더 | handover pending 0 / uploaded 4 / conflict 0 / simulation 10; query pending 0 / uploaded 485 / conflict 0 |

게시 양성 검증은 격리 DB 사본에서 수행했다. 운영 후보를 임의 승인하거나 검증용 후보를 운영 DB에 추가하지 않았다. 게시 후 최종 judge·답변 생성까지 통과했다는 의미는 아니다. 업로더 수치는 마지막 점검 시점 값이다.

## 미확인 항목과 관련 기록

Pi 물리 카메라·터치·기존 키오스크 세션 재로드, 운영 관리자 로그인 후 실제 후보 게시, 게시 카드의 최종 judge·답변 생성, 운영 DB 복원과 C3 비상 복귀 실행은 검증하지 않았다. 합성 MES 센서의 성공을 현장 안전 검증으로 해석하지 않는다.

- [온라인 DB 백업·사본 검증](jetson-db-copy-validation-20261022.md): 배포 전 로컬 검증과 장비 검증의 차이.
- [C3 비상 복귀·Pi 사전 검증](jetson-c5-pi-preflight-20261022.md): 기존 롤백 자료의 용도와 HTML 호환성.
- [백업·롤백 절차](jetson-main-deployment-preparation-20261022.md): 이번 새 백업의 구성과 복구 시 주의할 데이터 경계.
