# C3 비상 복귀 자료와 Pi JS 단독 교체 사전 검증

2026-10-22 KST, 배포 후보 main `75823786b44befc2b6fb75b531d6344a08bd82c0`에 대한 사전 검사 기록이다. 이 단계에서는 장비 파일 수정이나 서비스 정지·재시작을 하지 않았다. 후속 배포와 장비 검증은 [최종 결과](jetson-main-deployment-result-20261022.md)에 별도로 기록했다.

## C3 비상 복귀 자료

`/home/jetson/rag2_tmp/c5_install/rollback.sh`는 사용자 설명대로 **C5 장애 시 C3로 돌아가는 비상 절차**다. SHA-256은 `59eb7a5575ee8f1617529461e1a67580f50fbd06f8af1f7e6798b07160a665b1`이고 `bash -n` 종료 코드 0이다. 내용과 문법만 검사했으며 실행하지 않았다.

스크립트는 구버전 rag2·query를 복원하고 mes_block.py·rag/embedding.py를 제거하며 이전 색인을 복사한다. zz-c5.conf 제거, ck176 unload와 ck106 요청, MES 재시작도 포함한다. 이 동작은 C3 전환 목적에 맞는다. 이번 main 배포를 취소하면서 C5를 유지하려면 [새 백업을 사용하는 절차](jetson-main-deployment-preparation-20261022.md)를 따라야 한다.

`/home/jetson/shiftlink/app/backup-20261022-c5/`에는 rag2 Python 7개, query.py, 색인 2개, 이전 pda.js 등 일반 파일 11개가 있다. 백업 색인은 3,951행 × 768차원으로 현재 C5의 3,950행 색인과 다르다. 이번 배포 13개 경로 중 query.py만 포함하며 내용도 배포 직전 C5와 다르다. server·storage·전체 웹·DB·설정이 없어 현재 C5 전체 백업으로 사용할 수 없다. main 게시 모듈 적용 이후 C3 실제 복귀의 전체 호환성은 시험하지 않았다.

## Pi 기존 HTML과 main JS 조합

Pi에서 GET으로 읽은 기존 HTML/JS를 로컬에서 고정 main JS와 비교했다.

| 파일 | SHA-256 |
|---|---|
| 기존 Pi pda.html | `450ab200d0abdec571475ba1e65bafb3ed11c982ffe3ba8d4468a6c52a622033` |
| 기존 Pi pda.js | `2fe6e7d82ef96b8a5485e66d67987099944e3b222c1482998467f0f623b2e2b4` |
| main pda.js | `057ea5b52f1835fc025a6d571ea89107e602458b581300f3de1d5f8f1f79a2f6` |

JS 차이는 `document.dispatchEvent(new Event('shiftlink:knowledge-dashboard'));` 한 줄이었다. 두 HTML의 DOM ID 집합은 같으며 Pi HTML은 별도 화살표 CSS를 갖고 main의 knowledge.css/js 참조는 포함하지 않는다. 기존 HTML을 유지한 조합에서 해당 자산 요청이 새로 발생하지 않음을 확인했다. Pi 서버의 모든 자산 제공 능력을 일반화한 결론은 아니다.

Node 검사 **6개**(pda_sensor_display, pda_network_boot, unity_pda_link, pda_symptom_rank, mes_query_pda, pda_chat), JS 문법, 게시 무결성 검사가 통과했다.

실제 Chrome에서 **기존/main JS × 1280/390px의 4개 조합**을 검사했고 각 조합의 8개 검사 묶음이 통과했다. 기동·홈, 대시보드 이벤트, RT-02 센서 값/단위/시각, 질의당 요청 1회와 MES 접두사, 인용·안전 바 키보드 펼침, 폴링 실패/복구와 질의 당시 근거 보존, 설비 전환 초기화, JS 오류·예상 밖 요청 부재를 확인했다.

이 브라우저 검사는 GET 응답을 재생하고 질의·인용·안전 카드는 **로컬 픽스처**를 사용했다. 운영 POST·카메라·업로드가 나가지 않도록 요청을 가로챘다. 실제 모델 품질·얼굴 인증·Pi 물리 카메라·터치 검증이 아니다. 초기 테스트 코드의 함수 범위·선택자·펼침 처리 오류는 테스트에서 수정 후 재실행했고 앱을 고치거나 기대값을 완화하지 않았다.

사전 검사 전후 Jetson 서비스 시작 시각·C5 설정·색인·코드와 Pi HTML/JS가 유지됐다. 이후 실제 배포에서는 Pi JS만 바꾸고 HTTP 해시와 실제 Pi 주소의 Chrome 표시를 확인했다. 기존 키오스크 세션 재로드와 물리 입력은 여전히 미검증이다. 장비 파일 사본·화면·임시 검증 코드는 이 문서 PR에서 제외한다.
