# ShiftLink 지식 그래프 통합 결과

검증일: 2026-10-22 (Asia/Seoul). 계약: `kg-demo-v1`.

세 담당자의 지정 커밋만 깨끗한 별도 작업트리에 `git cherry-pick --no-commit`으로 적용하고, 실제 증상 매핑을 넣어 그래프를 재생성했다. 기존 작업트리의 변경은 보존한다. 새 커밋·push·PR·배포는 하지 않는다.

## 기준과 인수 이력

| 항목 | 값 |
|---|---|
| 작업트리 | `C:/Users/hyjuy/.codex/worktrees/kg-integration/ShiftLink` |
| 통합 브랜치 | `codex/kg-integration` |
| 기준 B / 현재 HEAD | `5167376b5ded1e33725394f2b65cb6977c121dec` |
| 변환 인수 커밋 | `6df10055ca37d87f6db266a4a74021ab28ddebd8` |
| 증상 인수 커밋 | `704c7b6c3ee96289822e30312a5a0c91e527e5d5` |
| 시각화 인수 커밋 | `87438a9b5c964934470305e22eae6285664911e8` |

각 인수 커밋 자체는 자기 소유 폴더만 추가한다. 증상 커밋의 상속 이력에는 main/CI/아키텍처 변경이, 시각화 커밋의 상속 이력에는 별도 연구 변경이 있어 전체 브랜치를 병합하지 않았다. 세 커밋 자체의 변경분만 적용했으며 그 상속 변경은 포함하지 않는다. 시각화 원격 브랜치는 현재 없지만 지정 SHA를 origin에서 직접 fetch하는 데 성공하여 원격 공유 객체임을 확인했다. 변환·증상은 원격 브랜치 끝이 지정 SHA와 일치했다. 세 SHA 모두 B를 조상으로 가진다.

최종 통합 내용은 전부 미커밋이다. HEAD는 B에 머물러 있으므로 이 HEAD SHA만 다른 PC에 전달하면 산출물이 전달되지 않는다. 공유 커밋·push는 사용자가 결정한다. 원래 담당자 HANDOFF는 당시 실행 기록으로 보존하며, 아래 결과와 `integration_validation.json`이 이번 통합 검증 기록이다.

## 실행

이 작업트리의 저장소 루트에서 PowerShell로 실행한다. Python 표준 라이브러리로 변환·데이터 검증하며, 화면은 추가 패키지나 CDN 없이 동작한다.

```powershell
Set-Location 'C:/Users/hyjuy/.codex/worktrees/kg-integration/ShiftLink'
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONDONTWRITEBYTECODE='1'
python docs/demo/kg/symptoms/check_symptoms.py
python docs/demo/kg/build/build_graph.py --self-test
python docs/demo/kg/build/build_graph.py
python scripts/check_knowledge_publication.py
node docs/demo/kg/viz/verify.cjs
```

브라우저 자동 검증에는 Node 24와 설치된 Chrome을 사용했다. Chrome 기본 경로는 `C:/Program Files/Google/Chrome/Application/chrome.exe`; 필요하면 `KG_CHROME`으로 지정한다. 검증기가 자기 실행용 로컬 HTTP 서버와 임시 Chrome 프로필을 만들고 종료·정리한다. 해당 실행은 Chrome headless이며 실제 모바일 기기 검증은 아니다.

화면을 계속 열어 두려면 별도 터미널에서 아래 서버를 실행한다. 기존 8765 서버와 작업 폴더가 섞이지 않도록 8766을 예시로 사용한다. 포트가 사용 중이면 다른 포트를 선택한다.

```powershell
python -m http.server 8766 --bind 127.0.0.1 --directory 'C:/Users/hyjuy/.codex/worktrees/kg-integration/ShiftLink/docs/demo/kg'
```

주소: <http://127.0.0.1:8766/viz/>. 기본 데이터는 `../build/graph.json`이며 `?mock=1` 없이 확인한다. 로컬 서버는 Ctrl+C로 종료한다. 기존에 열어 둔 8765 화면은 다른 작업트리의 그래프일 수 있다.

## 실제 집계

| 노드 타입 | 수 | 관계 타입 | 수 |
|---|---:|---|---:|
| EquipmentType | 83 | PART_OF | 76 |
| Symptom | 18 | DESCRIBES_SYMPTOM | 20 |
| CardVersion | 86 | ABOUT | 172 |
| DocumentVersion | 92 | CITES | 156 |
| Asset | 10 | INSTANCE_OF | 10 |
| AssetPart | 0 | INSTALLED_ON | 0 |
| 합계 | 289 | 합계 | 434 |

- `symptoms_loaded: true`. 비안전·증상 문자열 카드 28장 중 18장에 후보 연결 20개가 있다. 나머지 10장은 연결 보류다.
- 스키마 위반 0건, 고아 노드 0개(`[]`). 원본 86장 전 필드와 값이 일치한다.
- 안전 카드 56장의 증상 연결 0개. `symptom=null` 13장의 증상 연결 0개. 두 집합은 11장이 겹치며 합집합은 58장이다.
- 인용 원본 222건 중 판본 있는 180건을 CITES 156개로 집약했다. 판본 없는 42건은 원문과 함께 보류 목록에 남겼다. 문서 판본을 임의로 만들지 않았다.
- Asset 10개는 합성 기본 구성 스냅샷이다. 실제 현장 자산을 확인한 것이 아니며 AssetPart는 생성하지 않았다.

## 검증 근거

- [변환 검증 보고서](build/validation.json): 타입·ID·양끝·도메인/범위·관계 속성·카드 원문·마스터 FK·인용 보존, assert 자가 점검 35개.
- [통합 검증 보고서](integration_validation.json): 원본 카드 전체 값, 매핑과 관계의 정확한 대응, 인용 locator·집약 수·판본 누락 원문, 입력 해시, 동일 입력 재생성 결과를 별도로 대조.
- 증상 검증기의 정상/안전/null/잘못된 개념/누락/빈 검수 사유 거부 검사를 실행했다. 증상 생성기의 build와 assert 자가 점검도 출력 파일을 쓰지 않고 실행해, 제출 매핑·검수 문서와 같음을 확인했다.
- 그래프와 validation.json을 다시 생성한 뒤 두 파일 모두 바이트 동일함을 확인했다.
- 게시 무결성 검사는 `ok: true`, `errors: []`, `staged_python_checked: true`였다.
- [Chrome 검증 로그](viz/.qa/browser-results.txt): 기본 검증 30개와 통합 실제 데이터 검증 10개, 총 PASS 40개. 실제 그래프 로드·필터·후보 표시·이웃 버튼·인용 locator·안전/null 차단·판본 미지정 보류·합성 표시·키보드를 확인했다. 브라우저 Runtime 예외는 0개다.
- [통합 그래프 화면](viz/.qa/actual-file.png). mock 화면·모바일 크기·404 안내도 `.qa/`에 기록했다. missing-file/empty/assetless/null-source는 검사 입력이며 통합 그래프를 덮어쓰지 않는다.
- 기본 브라우저 검증 재실행은 로그를 기본 30개 결과로 갱신한다. 40개 기록은 이번 통합 시 실제 그래프를 대상으로 추가한 메모리 내 검사 10개를 포함한다. 담당자의 verify.cjs 파일은 수정하지 않았다.
- 전체 프로젝트 pytest·실제 LLM·PDA/Jetson 기기·운영 서버는 이번 범위에서 검증하지 않았다.

## 계약과 원본 해시

| 입력 | SHA-256 |
|---|---|
| schema.md | `ad460fc639146d17d448457a5c0a7908bf4aaca92f4098860456401fe0b81613` |
| KB | `05cfc4e79a3087e3544fc01e6b830268b542f55ae3be31bd6ad7601fc1d6dd3a` |
| 합성 장비 마스터 | `aee891c5e5e2270e815080f22b153e9b64e9128951d2262240c1f41cdc5e1708` |
| 증상 매핑 | `c1765e5f82efa3dc11e7c84f663b7a33385a1719ed0c2758535e4074e3b76556` |

변환·시각화 HANDOFF에 적힌 당시 로컬 계약 해시 `90afb3ca2590a6b6eccaa4a0bc9bcb991471d5534096fa03e87281399475b651`는 기준 커밋의 계약 해시와 다르다. 당시 차이는 승인·실행 상태·공백 관련 문서 차이였다. 이번에는 승인된 기준 커밋의 schema.md를 수정하지 않고 사용했으며 위의 기준 해시를 검증했다. 과거 HANDOFF의 해시나 집계를 현재 결과로 간주하지 않는다.

## 검수 대상과 한계 (AI 검토 결과는 아래 참조)

- [증상 검수 목록](symptoms/review.md)과 [매핑의 needs_review](symptoms/symptom_concepts.json)에 86장 모두의 후보·보류 사유가 있다. 그래프 후보 18개 및 관계 20개는 모두 `needs_review`다. 카드의 accepted 상태가 새 증상 매핑의 검수 완료를 뜻하지 않는다.
- 안전 카드 56장을 우선 검수한다. 안전 카드 중 문자열 증상이 있는 45장의 후보는 review.md에만 있고 그래프에는 연결하지 않았다.
- 복합 개념(K-1004, K-1011), K-1323의 독립 후보 3개 분리, K-1301의 출력 저하 표현, 개념 병합 2건, 인계·절차 카드 보류 판단과 정의의 임계값을 사람이 확인해야 한다.
- null 증상 13장은 제목·조치로 증상을 새로 추정하지 않는다. 판본 누락 인용 42건의 문서 판본도 추가 확인이 필요하다.
- 유형/하위 분류 PART_OF는 실제 부품 장착 관계가 아니다. 합성 자산은 현재 운영 MES 설치 상태나 교체 이력의 증거가 아니다.
- 이번 결과는 그래프 데이터 통합과 탐색 화면 검증이다. PDA 답변·검색 경로 연결, 원인·조치 모델링, 정식 OWL/RDF 추론, 검색·답변 성능 평가는 별도 작업이다.

발표 문장:

> 온톨로지 스키마를 설계하고 카드를 그 스키마에 맞춰 그래프로 구성했습니다. 증상 연결은 사람 검수 전이며, 증상-원인-조치 모델링과 GraphRAG는 다음 단계입니다.

## 원래 작업트리 보존 확인

원래 작업트리 `C:/Users/hyjuy/.codex/worktrees/63e5/ShiftLink`의 변경·미추적 파일 169개를 실행 전후 대조했다. 파일 내용 합산 해시, Git 상태, staging 해시, HEAD와 detached 상태가 모두 같았다. 대조 값은 integration_validation.json에 기록했다.

이번 실행의 미리보기 서버: <http://127.0.0.1:8766/viz/>. HTTP 응답의 graph.json 바이트가 이 통합 작업트리의 산출물과 같음을 확인했다.

## 기존 통합 결과 재인수·재검증 (2026-10-22)

사용자 후속 지시에 따라 소유권 기준은 `git diff --name-only --no-renames "${KgSha}^" $KgSha`다. 변환 4개·증상 5개·시각화 10개 파일이며 소유 폴더 밖 변경은 모두 0개다. B 이후 상속된 다른 변경을 이유로 새 SHA를 요청했던 판단은 철회했다. 이 작업트리의 기존 적용 결과를 재인수했으며 중복 cherry-pick·merge를 하지 않았다.

[재검증 보고서](recheck-validation.json)는 기존 그래프·validation 및 기존 KG 파일 23개가 재실행 전후 동일했음을 기록한다. 두 번의 빌더 실행도 바이트 동일했다. 이후 이 README를 보완하고 AI 검토 문서를 추가했으며 담당자 소유 파일은 변경하지 않았다. [최종 보존·인수 확인](acceptance-validation.json)에 단일 커밋 차이, 담당자 파일 대조, 데이터 재검증과 미커밋 목록을 기록한다.

최신 Chrome 검증은 **PASS 42개**, Runtime 예외 0개다. 실제 그래프 키보드 탐색과 합성 자산/AssetPart 검사를 추가했다. 기존 40개 기록은 보존했다. [최신 로그](.recheck-20261022/browser-results.txt)와 [실제 화면](.recheck-20261022/actual-file.png)을 참조한다. 담당자 verify.cjs를 수정하지 않고 통합 검증기를 별도 경로에 보관했다.

```powershell
node docs/demo/kg/.recheck-20261022/browser.cjs
```

`/67` 원문 충실성 검토는 [6개 전략·심판 결과](ai-review-67.md), [86장 대장](ai-review-cards.json), [담당자 수정 요청](revision-requests.md)에 기록했다. AI 검토는 완료했지만 확인된 문구 오류의 담당자 수정과 누락 판본·현장 근거 확인은 남아 있다. 승인된 데이터 계약과 `needs_review` 상태는 유지한다.

현재 통합 브랜치 HEAD는 여전히 B이고 staging은 비어 있다. 산출물은 모두 미추적·미커밋이다. 별도 조사 clone `D:/obsd/Projects/ShiftLink-kg-integration-20261022`에는 앞선 전체 병합 지시로 만든 변환 단독 merge `76e0531fbd9bf8d970e02cde1265d96860170095`가 남아 있다. 이 커밋은 본 통합 작업트리의 HEAD가 아니며 여기로 가져오지 않았다. 그 clone의 이전 인수 거절 기록은 후속 단일 커밋 기준으로 대체되었다. 두 저장소를 초기화하거나 삭제하지 않았다.

최종 생성물의 추가 커밋·push·PR·main 병합·배포를 수행하지 않았다. 기존 integration_validation.json 및 기존 미리보기 서버 기록은 당시 실행 기록이며, 최신 검증은 위 재검증 파일을 따른다.

보존 확인 주의: 주 작업폴더 `D:/obsd/Projects/ShiftLink`는 비교 기준 HEAD `479303f02aaf70eb12e1510d3897793b633859c0`에서 최종 확인 시 `94bf56748295c65cca54a0bac46cd410e94b7b5f`로 이동해 있었다. 이번 통합에서 이 저장소에 커밋하지 않았으며 이동을 되돌리지 않았다. 기록된 파일 내용·브랜치·staging은 그대로다. 통합 작업트리의 HEAD B는 변하지 않았다.
