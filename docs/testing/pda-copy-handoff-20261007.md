# PDA 문구 및 인계 화면 개선 인수인계

2026-10-07 PDA 검토 의견 10건을 화면과 수정 의견 문서에 반영했다. 사용자 요청으로 라즈베리파이 화면과 Jetson 근거 상세 API를 배포했으며, 이번 변경과 검증 결과를 PR에 함께 정리한다.

## 사용자 요청과 작업 상태

- 10월 6일에는 수정 의견 6건만 문서로 기록했다. 당시 시도한 코드 수정은 모두 되돌렸다.
- 해당 문서 커밋은 `1873e00`이며 GitHub `codex/pda-ui-review-20261006` 브랜치에 push했다.
- 10월 7일에는 사용자가 문서뿐 아니라 PDA 화면도 수정하도록 명시했다. 추가 의견 9건과 `최근 설비` 표현 개선 1건을 구현했다.
- PR 브랜치는 `codex/pda-copy-handover-20261007`이며, 생성 시 최신 `origin/main`과 같은 커밋 `b04c13e`에서 시작했다. 이번 작업 파일 7개만 포함한다.

## 반영 내용

1. 스캔 안내를 `설비를 스캔하면 인식된 설비가 자동으로 선택됩니다.`로 변경했다.
2. 설비명 아래의 카메라 확정·직접 선택 표시는 제거했다. 질의에 필요한 source와 scan_id는 유지한다.
3. 직접 선택 화면의 `상자의 색 띠와 이름표를 보고 고르세요.`를 삭제했다.
4. 설비 위치를 Unity 가상 공장의 구역 및 X·Y·Z 좌표로 표시한다. 현재 MES route와 `FactoryRig.Layout`의 계산을 따른다.
5. 돌아가기 버튼을 `설비 스캔으로 돌아가기`로 변경했다.
6. 인계 확인에서 open은 `조치 필요`, needs_recheck는 `재확인 필요`로 표시하고 의미를 설명한다. done·closed·withdrawn은 미완료 목록에서 제외한다. 근거는 펼쳐서 카드 본문·조치·결과·측정값을 확인할 수 있다.
7. 인계 작성의 영어 항목을 `작업 상황 및 측정 기록`, `받는 사람`, `전달 시점`, `전달 방법`, `인계 확인 방법`으로 변경했다. 작업 상황은 textarea로 수정할 수 있고 저장 시 value를 전송한다. `MES 기록 불러오기` 버튼을 추가했다.
8. 안전 카드와 상단 안내를 황색 주의 표시로 변경했다. 안전 본문·멈춤 조건·상단 고정은 유지하고, 카드 누락·설비 불일치는 오류 색상으로 구분한다.
9. 수동 측정값 안내를 `MES에서 가져오지 못한 측정값은 직접 입력해 주세요. 같은 항목을 입력하면 질의에는 직접 입력한 값이 사용됩니다.`로 변경했다.
10. `최근 설비`를 `최근 선택한 설비`로 변경했다.

## 이번 작업 파일

- `shiftlink/mes/web/pda.html`: 화면 문구, 입력 필드, 버튼, 안전 표시 색상.
- `shiftlink/mes/web/pda.js`: Unity 위치 계산, 인계 상태 설명, 근거 펼치기, MES 기록 가져오기, 수정한 작업 상황 저장.
- `shiftlink/mes/server.py`: `/api/kb/cards` 응답에 인계에서 참조하는 `basis_records` 추가. 기존 검색 카드 필터는 유지한다.
- `tests/test_pda_mes_alignment.py`: 근거 응답 및 노출 범위 검증 추가.
- `tests/pda_handover_copy.cjs`: 위치 계산, 상태 문구, 측정 품질·설비 필터, 최근 이벤트 5건 검증. 이번 작업에서 추가한 테스트다.
- `docs/testing/pda-ui-review-20261006.md`: 10월 7일 의견 10건 추가.
- `docs/testing/pda-copy-handoff-20261007.md`: 이 인수인계 문서.

## 검증 결과

- `node --check shiftlink/mes/web/pda.js`: 통과.
- `node tests/pda_handover_copy.cjs`: 통과.
- `node tests/unity_pda_link.cjs`: 통과.
- 번들 Node로 `tests/mes_query_pda.cjs`: 통과. 시스템 Node v20에서는 기존 테스트의 navigator 참조가 실패하므로 번들 Node를 사용했다.
- 기존 `test_pda_mes_alignment.py` 함수 4개와 `test_pda_handover.py` 테스트 1개를 번들 Python의 unittest로 실행: 5개 통과. 시스템 Python에는 pydantic이 없고, 시스템·번들 Python 모두 pytest가 없어 추가 설치 없이 실행했다.
- 실제 로컬 MES 서버와 headless Chrome에서 모바일 화면의 안내, Unity 위치, 근거 펼치기, 작업 상황 수정, MES 기록 추가, 인계 저장, 안전 색상과 브라우저 오류 부재를 확인했다. 가로 화면 캡처도 생성했다.
- 변경 파일의 `git diff --check`: 통과.
- `graphify update .`: 완료. SQL parser 미설치 경고가 있었으나 해당 작업은 SQL을 변경하지 않았다.

재검증용 런타임:

```text
Node: /Users/hyemin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
Python: /Users/hyemin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
```

브라우저 검증 스크립트는 `/tmp/check-pda-copy.cjs`, 캡처는 `/tmp/pda-safety-copy-20261007.png`와 `/tmp/pda-safety-copy-wide-20261007.png`에 있다. 임시 파일은 영구 테스트 자산이 아니다. 검증용 8877 서버는 종료했다가 사용자 미리보기 요청으로 다시 실행했다.

## 실제 기기 배포 상태

- 사용자 요청으로 `pi@raspberrypi.tail0a6af3.ts.net` (`100.72.187.104`)에 접속해 `/home/pi/shiftlink/app/shiftlink/mes/web/pda.html`과 `pda.js`를 배포했다.
- 기존 파일은 `/home/pi/shiftlink/backups/pda-copy-20261007/`에 백업했다.
- 두 파일의 SHA-256이 로컬 수정본과 일치하고, 기기의 `http://127.0.0.1:8080/pda.html` 및 `/static/pda.js` 응답이 배포 파일과 일치함을 확인했다.
- 기존 실행 인수와 데스크톱 환경을 유지해 PDA 앱을 재시작했다. Python 서버와 Chromium 키오스크 프로세스 실행, 수정된 문구 및 JavaScript HTTP 200을 확인했다. 물리 화면을 직접 확인한 것은 아니다.
- 사용자가 Jetson 접속 정보를 제공한 뒤 `/home/jetson/shiftlink/app/shiftlink/mes/server.py`의 `kb_cards()` 변경을 배포했다. Jetson에 별도로 적용된 답변 로그 예외 처리는 보존했다. 기존 서버 파일은 `/home/jetson/shiftlink/backups/pda-copy-20261007/server.py`에 백업했다.
- `shiftlink-mes` 서비스 재시작 후 active 상태, Jetson `/api/state` 및 `/api/kb/cards` 응답을 확인했다. 근거 ID `AC-0101`, `AX-0102`, `K-0101`, `K-0104`, `OC-0101` 5건과 작업 상세·측정 결과 필드를 검증했다.
- 파이의 API 요청이 한 차례 시간 초과됐으나 이후 Jetson 직접 요청과 PDA 프록시 요청 모두 성공했다. PDA 프록시에서 동일 근거 5건을 확인하고 키오스크를 다시 시작해 새 API를 불러오도록 했다. 실제 AI 답변 생성 및 사용자의 물리 화면 확인은 별도다.

## 제한과 다음 확인 사항

- MES 기록 가져오기는 현재 상태와 선택 설비의 최근 이벤트 5건을 기존 입력에 추가한다. 전체 과거 로그 조회는 구현하지 않았다. 반복해서 누르면 같은 기록이 추가될 수 있다.
- 전송 확인이 안 된 인계는 기존 payload로 재전송하는 기존 계약을 유지한다. 해당 상태에서는 MES 기록 추가 버튼을 비활성화한다. 기존 내용 변경 후 재전송은 기존 검증에 따라 거절된다.
- 인계 상태는 원본 기록의 값을 설명해서 표시한다. 상태 자동 전환 규칙은 추가하지 않았으며 MES 정상화로 자동 완료 처리하지 않는다.
- Unity 위치 계산은 JS에 동일하게 구현했다. C# `FactoryRig.Layout` 배치 규칙이 바뀌면 함께 갱신해야 한다. 실제 Unity 실행 화면과 물리 PDA에서는 추가 확인이 필요하다.
- 근거 상세는 기존 샘플 인계의 참조 자료를 연결했다. 검색 가능한 카드 원문을 우선하고, 없는 원문은 담당자 확인 안내를 표시한다.
- 검증 서버는 판정 모델에 연결하지 못해 질의가 503인 상태였다. 이번 검증에서 실제 LLM 답변 생성은 확인하지 않았다.
- 사용자 요청에 따라 이번 작업 파일만 선택해 커밋·push하고 PR을 생성한다. 현재 작업 트리의 `docs/data/knowledge_cards/kb/kb_cards.json`, `.agents/`, 별도 planning 문서 변경은 이번 작업에서 만들지 않았으므로 포함하거나 되돌리지 않는다.
