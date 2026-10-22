# 시각화 담당 인계

검증일: 2026-10-22 (Asia/Seoul). 역할: 발표용 지식 그래프 시각화. 쓰기 범위: `docs/demo/kg/viz/`.

## 기준과 입력

- 기준 SHA: `5167376b5ded1e33725394f2b65cb6977c121dec`
- 시작 시 확인한 브랜치: `codex/kg-viz`
- 계약 버전: `kg-demo-v1`
- 문서 확인 순서: project-structure.md → 루트 AGENTS.md(경로상 하위 지침 없음) → schema.md → distributed-work-plan.md.
- 사용자 메시지의 승인·독립 구현 지시가 작업 파일에 남아 있는 승인 대기 문구보다 우선한다.
- 시작 전부터 무관한 수정·미추적 파일이 있었다. 이를 초기화하지 않고 담당 폴더만 작성했다.

**최종 Git 상태 주의:** 시작 시 브랜치·HEAD는 요청 기준과 일치했다. 최종 확인 중 같은 브랜치의 HEAD가 `6295f1454c777244a5f14d9ee0e4ee455f63f311`로 바뀐 것을 발견했다. 해당 커밋은 작성자 `hyunjun`, 제목 `feat: pass 20 tests and freeze causal notification policy comparison`, 변경 파일 `scripts/mes_timestral_notifications.py`다. 이 시각화 담당은 Git 변경 명령을 실행하지 않았고 임의로 되돌리지 않았다. 사용자에게 보고했으며 기준 SHA 위에서의 최종 인수 여부는 통합 담당자가 확인해야 한다. 시각화 파일은 최종 확인 시 미추적 상태이고 스테이징된 변경은 없었다.

| 입력 | 바이트 SHA-256 |
|---|---|
| 작업 파일 `docs/demo/kg/schema.md` | `90afb3ca2590a6b6eccaa4a0bc9bcb991471d5534096fa03e87281399475b651` |
| 기준 SHA의 `schema.md` (git show 바이트) | `ad460fc639146d17d448457a5c0a7908bf4aaca92f4098860456401fe0b81613` |
| `docs/data/knowledge_cards/kb/kb_cards.json` | `05cfc4e79a3087e3544fc01e6b830268b542f55ae3be31bd6ad7601fc1d6dd3a` |
| `docs/data/reference/00_plant_and_relations.json` | `aee891c5e5e2270e815080f22b153e9b64e9128951d2262240c1f41cdc5e1708` |
| `viz/mock_graph.json` | `3f8dbedfcb8f7e2953d14637eecc7f85bffebeeaa71fda55b4047dad88bb2066` |

작업 시작부터 schema.md 작업 파일과 기준 커밋의 바이트가 달랐다. 기존 차이는 승인·실행 상태 설명과 공백 등이며 노드·관계·JSON 계약 정의는 같다. 읽은 작업 파일과 커밋판의 해시를 구분해 기록했다. 공통 문서는 수정하지 않았다. 통합 담당자는 다른 담당자의 계약 해시와 이 차이를 대조해야 한다.

## 만든 파일

| 파일 | 목적 |
|---|---|
| `index.html` | CSS/JavaScript를 포함하는 의존성 없는 탐색 화면 |
| `mock_graph.json` | 계약 형식의 가짜 그래프, 12개 노드·14개 관계 |
| `demo_questions.md` | 화면에서 확인할 질문·시연 순서·오류 재현·발표 범위 |
| `HANDOFF.md` | 기준·해시·검증·통합 확인 사항 |
| `verify.cjs` | Node 표준 API와 설치된 Chrome CDP를 이용한 브라우저 회귀 검사 |
| `.qa/browser-results.txt` | 실제 브라우저 검증 결과 |
| `.qa/*.png` | desktop/mobile/missing-file/actual-file 확인 이미지 |

mock은 원본을 복사한 자료가 아니다. MOCK 식별자·매뉴얼·관측·설명은 모두 가짜이며 실제 작업 절차를 제공하지 않는다.

## 실행 방법

저장소 루트 PowerShell:

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory docs/demo/kg
```

- 기본: `http://127.0.0.1:8765/viz/` → `../build/graph.json`
- 가짜 데이터: `http://127.0.0.1:8765/viz/?mock=1` → `mock_graph.json`, “가짜 데이터” 표시
- mock 화면 자가 점검: `http://127.0.0.1:8765/viz/?mock=1&selftest=1`
- `?mock=0`과 인자 없음은 실제 파일. `?selftest=1`만으로 mock을 선택하지 않는다.
- `file://`로 직접 열지 않고 HTTP로 제공한다. 로드 실패 시 다른 데이터로 전환하지 않는다.

검증 명령:

```powershell
node docs/demo/kg/viz/verify.cjs
python -B scripts/check_knowledge_publication.py
git diff --check -- docs/demo/kg/viz/
```

화면은 브라우저만으로 실행한다. 검증 보조 스크립트에는 전역 `fetch`, `WebSocket`, `AbortSignal.timeout`을 제공하는 Node와 설치된 Chrome이 필요하다. 이번 환경은 Node `v24.19.0`이다. Chrome 기본 경로는 `C:/Program Files/Google/Chrome/Application/chrome.exe`이며 다른 경로라면 `$env:KG_CHROME='Chrome 실행 파일 경로'`로 설정한다. 새 패키지를 설치하지 않는다.

검증기는 임시 로컬 HTTP 서버 두 개로 mock과 실제 404를 각각 확인한다. build 파일은 옮기거나 수정하지 않는다. 결과와 임시 Chrome 프로필은 .qa/에 생성하며 해당 실행이 만든 프로필만 정리한다. 샌드박스에서 Chrome 디버깅 연결이 되지 않아 승인된 샌드박스 밖 실행으로 검증했다. 연결된 브라우저 도구와 agent-browser CLI는 이 환경에 없었다.

## 검증 결과

| 확인 | 결과·범위 |
|---|---|
| 구현 전 RED | Node VM에서 runSelfChecks 실행 시 미구현 validateGraph의 ReferenceError 확인 |
| assert 자가 점검 | 누락 관계 끝점·중복 ID·안전/null 카드 증상 연결 거부, HTML 문자열과 데이터 경로 선택 확인 |
| mock 브라우저 | Chrome headless에서 12개 노드/14개 관계, 가짜 표시, 필터·선택·이웃·원문·인용 locator PASS |
| 키보드 | Chrome Input ArrowDown 실제 이벤트로 네이티브 목록 선택과 상세 갱신 PASS |
| 데이터 HTML | img/onerror 모양 문자열을 텍스트로 보존, img 요소·스크립트 실행 없음 PASS |
| 보류 표시 | 안전 카드·null 증상·판본 미지정 인용 PASS |
| 오류 | 실제 HTTP 404, 오류·실행 안내·재시도, mock 자동 대체 요청 없음 PASS |
| 반응형 | 1440×1000/390×844, 페이지 가로 넘침 없음, 그래프 안에서 가로 스크롤하여 글자 크기 유지 |
| 실제 파일 연결 | 기존 graph.json 읽기 전용 연결, 271개 노드/414개 관계·증상 0 확인 |
| 게시 무결성 | `ok: true`, `errors: []`, `staged_python_checked: true` |
| UI 기계 검사 | impeccable detector 결과 `[]` |
| /67 수정 회귀 | 실제 모드+selftest, Asset 없는 그래프, 빈 그래프의 배너, null 인용의 조기 거부, 증상 연결 있음/없음 표시 PASS |
| 최종 브라우저 검사 수 | `.qa/browser-results.txt`에 PASS 30개, 브라우저 Runtime 예외 0개 |
| 범위 보존 | 시작 전에 있던 폴더 밖 수정·미추적 파일 159개의 바이트 해시가 모두 동일. 계약·두 원본 해시도 동일 |

실제 파일의 집계는 확인 시점의 읽기 전용 연결 결과이며 증상 후보 통합 완료가 아니다. “실제 파일”은 경로 구분이고 현장 실측 데이터라는 뜻이 아니다. 원본 전 필드 일치·마스터 FK·인용 정합성·의미 정확성·사람 검수 완료는 UI assert만으로 증명하지 않는다. 변환 담당자의 validation.json을 따로 확인한다. Chrome 외 브라우저와 스크린리더는 검증하지 않았다. 테스트 프레임워크를 추가하거나 커버리지 비율을 측정하지 않았다.

디자인 마감 검토의 기존 두 지적(선택 상태 문구 불일치, 모바일 SVG 글자 축소)은 수정·재캡처 후 `disposition: ship` 판정을 받았다. 이 판정은 해당 두 수정의 확인 범위다. 일반적인 디자인 인터뷰·별도 PRODUCT/DESIGN 산출물 대신 사용자가 지정한 구현 범위와 이 인계 문서에 결정 사항을 기록했다.

## /67 개발 검토와 종합

사용자의 `/67` 지시에 따라 같은 과제를 여섯 독립 전략으로 검토한 뒤 일곱 번째 판정자가 비교했다. 동시 실행 한도로 세 시도씩 나눴다. 여섯 시도는 공동 파일을 수정하지 않았으며 구현 제안·코드 확인·메모리 입력 교란 결과를 반환했다. 판정 점수는 전략 제안 간 상대 평가이고 제품 성능 수치가 아니다. 판정자는 전달받은 여섯 결과를 평가했으며 별도 실행 검증은 하지 않았다.

| 순위 | 전략 | 정확성 | 완결성 | 설계 판단 | 평균 | 판정 |
|---|---|---:|---:|---:|---:|---|
| 1 | Adversarial | 10 | 9 | 10 | 9.67 | 재현 가능한 null 출처 렌더 예외의 최소 방어 |
| 공동 2 | First principles | 9 | 9 | 9 | 9.00 | 연결의 존재와 검수 상태를 분리 |
| 공동 2 | Maximalist | 9 | 10 | 8 | 9.00 | 검증 주장 범위·인계 환경을 명확히 구분 |
| 공동 2 | Minimalist | 9 | 8 | 10 | 9.00 | 확장 없이 요구를 만족하는 작은 구조 |
| 공동 5 | Prior art | 9 | 8 | 9 | 8.67 | 네이티브 조작·locator 중심 탐색 |
| 공동 5 | Wildcard | 9 | 8 | 9 | 8.67 | 근거 우선 시연과 배너의 사실성 |

승자의 입력 경계 방어를 골격으로 삼고 다음 장점을 채택했다.

- Minimalist: 단일 HTML·네이티브 목록·직접 이웃 SVG를 유지. 전체 그래프 배치·새 라이브러리는 추가하지 않음.
- Maximalist: UI assert를 원본 보존·마스터 FK·의미 검수 증거로 확대하지 않는 인계.
- First principles: `증상 연결 후보 · 검수 전`과 `증상 후보 연결 없음` 구분.
- Prior art: 인용 locator를 직접 표시하고 문서 이웃에서 인용 카드로 역탐색.
- Adversarial: provenance.sources의 null 등 객체 아닌 항목을 선택 전에 거부, 실패 재현 assert 추가.
- Wildcard: Asset이 있을 때만 “합성 장비 포함” 배너, 근거 → 검수 상태 → 현장 자산 증명 여부의 짧은 시연 순서.

여러 시도가 찾은 실제 모드 `?selftest=1`의 mock 전용 점검 호출 오류도 수정했다. 자동 화면 점검은 mock 모드에서만 실행한다. 위 모든 변경은 Chrome 회귀 검사로 재확인했다.

## 실제 그래프 통합 후 확인할 사항

1. 공통 계약과 원본 해시를 대조하고 변환 담당자가 공식 생성·validation.json 검증을 수행한다.
2. 증상 후보 통합 후 비안전·비null 카드에만 DESCRIBES_SYMPTOM이 생기고 노드·관계 모두 “검수 전”으로 표시되는지 확인한다. 안전/null 연결은 0개여야 한다.
3. 실제 카드의 ABOUT 분류, 문서 판본, 모든 locator, 원본 인용 수, 판본 미지정 출처와 props를 원문과 대조한다.
4. 합성 Asset 10개·AssetPart 0개·실제 현장 자산 미확인을 확인한다. mes_equipment_id를 자산 사건 관계로 추론하지 않는다.
5. COMMON은 공통 적용 분류이며 PART_OF는 실제 부품 장착 증거가 아님을 확인한다.
6. 기본 모드·명시 mock·파일 누락·재시도·필터 밖 이웃·키보드를 통합 데이터로 재검증한다.

구현·검증 단계에서는 커밋·push·PR·배포·브랜치 변경을 실행하지 않았다. 이후 사용자가 인계용 커밋을 명시적으로 요청하여 이 폴더의 산출물만 커밋한다. 커밋 SHA는 자기 참조를 피하기 위해 최종 전달 메시지에서 보고한다. push·PR·배포·브랜치 변경은 승인 범위에 포함하지 않는다. 현재 브랜치에는 다른 작업의 커밋도 있으므로 통합 담당자는 이 시각화 커밋만 cherry-pick하여 인수한다. build·원본 데이터·공통 문서·다른 담당자 폴더는 수정하지 않는다.
