# 지식 그래프 시연: 3대 PC · 3개 작업 브랜치 운영 계획

작성일: 2026-10-21 (Asia/Seoul)
상태: **2026-10-21 스키마와 세 문서의 기준 브랜치 생성·커밋·push를 사용자 승인받은 공유용 운영 계획. 분담 구현·통합은 아직 수행 전이다.**
데이터 계약: [schema.md](schema.md)
적용 스킬: `dispatching-parallel-agents` — 독립된 작업 범위, 각자에게 필요한 문맥만 전달, 결과를 한 곳에서 통합.

## 1. 운영 원칙

**공통 기준 커밋 1개에서 세 브랜치를 만들고, 각자 한 폴더만 수정한다. 통합은 한 사람이 별도 브랜치에서 수행한다.**

브랜치만 나누고 같은 파일을 편집하면 충돌한다. 파일 작성자를 분리하고 계약·입력 데이터를 동결해야 한다. Git이 자동 병합에 성공해도 스키마·의미·안전 제약이 맞는지는 별도로 검증한다.

2026-10-21 사용자는 schema.md를 승인하고 총괄에게 이 운영 계획·schema.md·필수 구조 문서만 담은 공통 기준 브랜치의 생성·커밋·push를 명시적으로 허용했다. 이 승인은 기준 준비 범위에 적용한다. 이후 역할별 AI의 커밋·push·PR·배포 금지는 유지하며, 각 사람은 검토한 자기 결과의 Git 작업을 직접 수행하거나 별도로 지시한다.

## 2. 확정된 공유 범위와 공통 출발점

공유 기준 브랜치는 `codex/kg-base`다. 기준 커밋 **B는 아래 세 문서를 처음 추가한 커밋의 전체 SHA**이며, 총괄의 완료 전달문에서 받아 세 PC에 똑같이 사용한다. SHA 자체를 그 커밋 안에 적으면 다시 SHA가 바뀌므로 이 문서에는 자기 커밋 SHA를 넣지 않는다.

| 항목 | 확정 내용 |
|---|---|
| 새 커밋의 부모 | 이미 원격에 있는 `000b9102a10914ca694852aa0ff92285e3cc2056` |
| 준비 당시 로컬 HEAD | `be832068cd29371eb63eab66d827c97ef321ee3f`; 미공유 16개 커밋은 이번 기준에 포함하지 않음 |
| 추가 파일 1 | `docs/demo/kg/schema.md` — 승인된 데이터 계약 |
| 추가 파일 2 | `docs/demo/kg/distributed-work-plan.md` — 이 운영 계획 |
| 추가 파일 3 | `docs/design/project-structure.md` — 필수 구조 문서 |
| 코드·입력 데이터 | 부모 커밋 그대로; 다른 로컬 변경·미추적 자료는 제외 |
| 루트 AGENTS.md | Git 추적 대상이 아닌 로컬 지침. 각 사람에게 별도 전달 |
| 원본 줄바꿈 | 기존 .gitattributes의 LF 정책 유지 |

준비는 별도 깨끗한 worktree에서 세 경로만 정확히 추가해 수행한다. 각 담당 폴더의 빈 파일·README·graph.json은 미리 만들지 않는다. 기존 작업 폴더의 브랜치·staging과 무관 변경은 보존한다.

공통 기준에는 구조 문서·schema.md·이 계획·두 입력 JSON·필수 검사 스크립트가 존재한다. 구조 문서는 로컬 작업 트리 분석에서 출발했으므로 미공유 구현·자료의 설명이 일부 있으며, 해당 경로는 문서의 안내에 따라 구분한다. 그것을 이유로 다른 로컬 작업을 가져오지 않는다.

각 PC는 B 체크아웃 후 다음 원본 해시와 계약 해시를 비교한다.

| 파일 | SHA-256 |
|---|---|
| `docs/data/knowledge_cards/kb/kb_cards.json` | `05cfc4e79a3087e3544fc01e6b830268b542f55ae3be31bd6ad7601fc1d6dd3a` |
| `docs/data/reference/00_plant_and_relations.json` | `aee891c5e5e2270e815080f22b153e9b64e9128951d2262240c1f41cdc5e1708` |
| `docs/demo/kg/schema.md` | `ad460fc639146d17d448457a5c0a7908bf4aaca92f4098860456401fe0b81613` |

불일치하면 원본을 고쳐 맞추지 말고 기준 커밋·줄바꿈 설정부터 확인한다. 기준 브랜치가 나중에 움직이더라도 이번 회차에는 배포된 B를 사용한다.

## 3. 브랜치와 파일 소유권

아래 브랜치명은 제안이다. 이미 사용 중이면 준비 담당자가 공통 접미사를 정해 한 번에 공지한다.

| 역할 | 작업 브랜치 | 유일한 쓰기 범위 | 결과 |
|---|---|---|---|
| 사람 1 / 변환 AI | `codex/kg-build` | `docs/demo/kg/build/**` | build_graph.py, graph.json, validation.json, HANDOFF.md |
| 사람 2 / 증상 AI | `codex/kg-symptoms` | `docs/demo/kg/symptoms/**` | symptom_concepts.json, review.md, HANDOFF.md |
| 사람 3 / 시각화 AI | `codex/kg-viz` | `docs/demo/kg/viz/**` | index.html, mock_graph.json, demo_questions.md, HANDOFF.md |
| 준비·통합 담당자 | `codex/kg-base` → `codex/kg-integration` | kg/ 바로 아래 공통 문서; 통합 시 빌더 실행에 의한 build 산출물 갱신 | 공통 기준, 최종 README.md, 최종 그래프·검증 결과 |

통합 담당자는 세 사람 중 한 명이 겸해도 된다. 전용 통합 작업 폴더를 사용한다.

모든 작업 브랜치에서 schema.md와 이 계획, 원본 JSON, naming registry, 프로젝트 구조 문서, 루트 README, .gitignore, .gitattributes, 의존성 파일, CI는 **읽기 전용**이다. 새 공통 helper·공용 테스트·공유 진행상황 파일도 만들지 않는다. 보조 스크립트·검증 결과·임시 입력은 자기 폴더 아래에만 둔다.

다른 폴더의 문제가 보이면 자신의 HANDOFF.md에 남기고 담당자에게 전달한다. 다른 사람의 파일을 대신 수정하지 않는다. 각자 작업 중 다른 작업 브랜치를 merge/cherry-pick하지 않는다.

## 4. 각 PC의 시작 절차

각 사람은 저장소의 독립된 clone을 사용하면 충분하다. 기존 작업을 계속해야 하는 PC만 별도 worktree를 사용한다. 하나의 공유·동기화 폴더에서 세 명이 작업하지 않는다.

아래는 **B를 받은 뒤 사람이 실행하는 예시**다. `origin`은 팀이 사용하는 원격 이름으로 확인한 뒤 사용한다. 기존 브랜치가 있으면 `-C`로 덮어쓰지 않는다.

```powershell
git status --short
git fetch origin
$KgBase = '여기에_공유받은_전체_커밋_SHA'
# 깨끗한 전용 작업 폴더에서 역할에 맞는 명령 하나만 실행한다.
git switch -c codex/kg-build $KgBase
# 사람 2: git switch -c codex/kg-symptoms $KgBase
# 사람 3: git switch -c codex/kg-viz $KgBase
git rev-parse HEAD
git status --short
```

시작 직후 HEAD가 B이고 작업 트리가 깨끗해야 한다. 이후 구조 문서, 로컬 지침, schema.md, 이 운영 계획을 읽고 입력 해시를 확인한다. 출력 파일의 인코딩은 UTF-8, 줄바꿈은 LF를 사용한다. 기존 Git 줄바꿈 정책을 바꾸지 않는다.

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONDONTWRITEBYTECODE='1'
Get-FileHash -Algorithm SHA256 docs/data/knowledge_cards/kb/kb_cards.json
Get-FileHash -Algorithm SHA256 docs/data/reference/00_plant_and_relations.json
Get-FileHash -Algorithm SHA256 docs/demo/kg/schema.md
```

## 5. 서로 기다리지 않는 개발 방식

### 변환 담당

매핑 파일이 없는 상태로 변환·검증을 완성한다. 매핑이 있으면 계약 경로에서 읽도록 구현하고, 잘못된 매핑은 오류로 처리한다. 필요하면 **build/ 안의 작은 테스트 입력**으로 매핑 경로를 자가 점검한다. symptoms/에 가짜 매핑 파일을 만들지 않는다.

최초 graph.json·validation.json은 증상 미입력 결과여도 된다. HANDOFF.md에 이를 명시한다. 입력 데이터의 안전 제약과 판본 누락 처리까지 구현하며 다른 담당자의 결과를 받으려고 브랜치를 섞지 않는다.

### 증상 담당

자기 폴더의 매핑·검수 문서만 만든다. 검증에 필요한 코드는 자기 폴더에 둔다. 변환 담당의 graph.json을 직접 편집하거나 재생성하지 않는다. schema.md에 고정된 원본 카드 집합, 안전·null 보류 규칙을 검증한다.

### 시각화 담당

viz/mock_graph.json만으로 개발한다. 실제 데이터를 읽는 상대 경로 `../build/graph.json`을 처음부터 구현하므로 통합 시 경로를 고치는 작업이 없어야 한다. 가짜 데이터는 `?mock=1`에서만 선택한다. 실제 파일이 없으면 안내와 오류를 표시한다.

실제 그래프를 테스트하려고 build/graph.json을 복사·수정하지 않는다. 자신의 폴더 안에서 계약에 맞는 다양한 가짜 데이터로 선택·필터·오류·검수 표시를 검증한다.

## 6. 담당자에게 전달할 프롬프트

각 PC의 새 AI 대화에는 **이 공통 프롬프트 + 해당 담당 프롬프트 + 확정 B + 로컬 AGENTS 지침**을 함께 전달한다. 이전 총괄 대화의 맥락을 알고 있다고 가정하지 않는다. 계약은 승인 완료이며, 아래 프롬프트는 B를 받은 담당자가 사용할 수 있다.

### 공통 프롬프트

```text
ShiftLink 발표용 지식 그래프 시연의 분담 작업을 수행한다.
공통 기준 커밋 B: [담당자가 확정 SHA를 기입]
배정 브랜치와 쓰기 허용 폴더: [아래 역할에서 기입]

먼저 docs/design/project-structure.md와 적용되는 AGENTS.md를 읽어라.
그다음 docs/demo/kg/schema.md와 distributed-work-plan.md를 읽어라.
schema.md가 노드·관계·파일 형식의 유일한 계약이다.
kg-demo-v1은 사용자 승인 완료다. 계약 승인을 다시 기다리지 않고 배정 폴더에서 구현한다.
전체 저장소를 읽지 말고 필요한 입력과 코드만 확인하라.
기존 파일과 다른 담당자 폴더는 읽기만 하며, 자기 폴더에만 새 산출물을 만든다.
원본 카드·마스터를 수정하거나 생성기를 실행하지 않는다.
안전 카드의 증상 연결은 자동 확정하지 않으며 schema.md의 보류 규칙을 지킨다.
발표 문구에서 구현 범위를 부풀리거나 성능 향상을 주장하지 않는다.
로직 파일마다 assert 기반 자가 점검을 남기고 테스트 프레임워크를 추가하지 않는다.
다른 담당자의 완료를 기다리거나 해당 브랜치를 병합하지 않는다.
계약 변경이 필요하면 자기 HANDOFF.md에 변경 요청을 적고 총괄에게 알린다.
커밋·push·PR·배포·Git 브랜치 변경은 실행하지 않는다.
검증 후 자기 폴더의 HANDOFF.md에 변경 파일, 실행 결과, 한계, 입력 해시를 남긴다.
```

### 사람 1에게 추가

```text
너는 변환 담당이다.
브랜치: codex/kg-build
쓰기 허용: docs/demo/kg/build/ 만.

표준 라이브러리 Python으로 build_graph.py, graph.json, validation.json을 만든다.
KB와 합성 마스터를 읽고 schema.md의 ID·속성·관계·검증을 구현한다.
symptoms/symptom_concepts.json이 없으면 증상 없이 성공한다.
있으면 읽어 적용하며 유효하지 않은 파일은 조용히 무시하지 않는다.
테스트용 매핑이 필요하면 build/ 안에만 두고 자가 점검에서 사용한다.
안전·null 증상 연결, 누락 참조, 잘못된 도메인/범위를 거부하는 검사를 포함한다.
원본 해시 불변과 결정적 재생성을 확인한다.
최종 보고에서 증상 입력 유무를 명확히 표시한다.
```

### 사람 2에게 추가

```text
너는 증상 담당이다.
브랜치: codex/kg-symptoms
쓰기 허용: docs/demo/kg/symptoms/ 만.

원본 카드와 schema.md를 근거로 symptom_concepts.json, review.md를 만든다.
86개 카드에 대한 연결 또는 보류 이유를 빠짐없이 기록한다.
safety_flag=true인 56장과 symptom=null인 13장은 계약대로 연결을 보류한다.
비안전 후보도 검수 전으로 표시하고 의미가 다른 증상을 병합하지 않는다.
원인·조치·정비 시점을 증상으로 억지 변환하지 않는다.
검증 스크립트가 필요하면 symptoms/에만 만들고 assert 자가 점검을 넣는다.
build/graph.json을 만들거나 수정하지 않는다.
```

### 사람 3에게 추가

```text
너는 시각화 담당이다.
브랜치: codex/kg-viz
쓰기 허용: docs/demo/kg/viz/ 만.

index.html, mock_graph.json, demo_questions.md를 만든다.
schema.md의 형식을 따르는 작은 가짜 그래프로 독립 개발한다.
기본 데이터는 ../build/graph.json, ?mock=1에서만 mock_graph.json을 쓴다.
실제 데이터 로드 실패를 가짜 데이터로 숨기지 않는다.
필터·노드 선택·이웃 관계·원문 속성·인용 위치를 확인할 수 있게 한다.
합성 장비와 검수 전 증상 상태를 구분하고 키보드 탐색을 지원한다.
서버 경로·새 의존성·다른 담당자 폴더를 변경하지 않는다.
화면 로직의 assert 자가 점검과 실제 브라우저에서 확인한 항목을 남긴다.
```

## 7. 제출 전 확인과 인계 형식

각 사람이 자신의 작업 폴더에서 아래 네 범주를 모두 확인한다. 커밋 diff만 보면 미커밋 변경이나 미추적 파일을 놓칠 수 있다.

```powershell
git diff --name-status "$KgBase...HEAD"
git diff --name-status
git diff --cached --name-status
git ls-files --others --exclude-standard
git diff --check
git diff --cached --check
```

첫 세 변경 목록과 새 미추적 산출물은 모두 자기 허용 폴더 안에 있어야 한다. 전달된 로컬 AGENTS.md처럼 작업 전에 존재하던 지침은 baseline과 구분한다. 원본·계약·공용 파일 변경이 있으면 제출하지 말고 원인을 확인한다. 무관 파일을 자동 삭제·되돌리거나 전체를 stage하지 않는다.

HANDOFF.md는 각자 자기 폴더에 만들고 다음을 기록한다.

- 역할, B, 계약 버전과 schema.md 해시, 입력 원본 해시.
- 만든 파일 목록과 각 파일의 목적.
- 실행한 명령, 성공/실패 결과, 자가 점검 범위.
- 실제 브라우저 확인 여부 또는 증상 입력 유무처럼 결과 해석에 필요한 조건.
- 미해결 사항, 사람 검수 대상, 계약 변경 요청이 있으면 그 내용.

사람이 자기 폴더만 검토·커밋·공유한 뒤 **최종 커밋 SHA S1/S2/S3**를 총괄에게 전달한다. 최종 SHA를 그 커밋 자체의 HANDOFF.md에 넣으려 하면 SHA가 바뀌므로, 최종 SHA는 전달 메시지에서 보고한다.

이때 브랜치명을 가리키는 “최신 결과” 대신 정확한 SHA를 사용한다. 총괄이 인수한 SHA 이후에는 해당 인계본을 고정하고 수정이 생기면 새 SHA로 다시 알린다.

## 8. 통합 순서와 산출물 작성자 전환

통합은 별도 깨끗한 작업 폴더의 `codex/kg-integration`에서 B로 시작한다. 통합 담당자 한 명만 수행한다. 아래는 순서이며 지금 실행한 작업이 아니다.

1. S1/S2/S3가 모두 B를 조상으로 갖는지 확인한다. 각 `git diff --name-status B...S<n>`가 해당 담당 폴더 안에만 있는지 검사한다.
2. 공통 계약·입력 해시가 세 인계본에서 같은지 비교한다. 누락, 계약 변경, 무관 파일 변경이 있으면 해당 인계본을 담당자에게 돌려보낸다.
3. 검토한 **S1 변환 → S2 증상 → S3 시각화** 순으로 병합한다. 다른 작업 브랜치 전체 이력을 섞지 않는다. 같은 B에 폴더도 분리되어 있으므로 정상 인계라면 파일 충돌이 없어야 한다.
4. 세 소스가 모두 들어온 다음에만 빌더를 실행한다. 증상을 반영한 graph.json과 validation.json을 재생성한다.
5. 스키마 위반, 고아 노드, 타입별 집계, 안전 카드 연결 0개, 보류 항목, 원본 불변, 그래프 재생성 동일성을 확인한다.
6. 실제 그래프를 연결한 화면에서 필터·선택·인용·검수 표시·로드 오류를 확인한다. 저장소의 게시 무결성 검사도 실행한다.
7. 통합 담당자만 kg/README.md에 최종 실행 방법·실제 집계·한계·발표 문장을 작성한다. 사람이 최종 diff를 확인한 뒤 커밋·공유 여부를 결정한다.

병합 명령 예시의 S1/S2/S3는 전달받은 SHA다. 사람의 Git 권한 결정 후 실행한다.

```powershell
git switch -c codex/kg-integration $KgBase
git merge --no-ff $KgBuildSha
git merge --no-ff $KgSymptomsSha
git merge --no-ff $KgVizSha
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONDONTWRITEBYTECODE='1'
python docs/demo/kg/build/build_graph.py
python scripts/check_knowledge_publication.py
```

**생성 파일 충돌 방지:** 개발 중에는 변환 담당자가 graph.json·validation.json의 유일한 작성자다. S1 인수 후 통합 기간에는 통합 담당자의 빌더 실행이 유일한 생성 경로다. JSON을 수작업으로 합치거나 증상·시각화 담당자가 별도 생성본을 커밋하지 않는다. 빌더 코드 수정은 계속 변환 담당자가 맡는다.

## 9. 계약 변경·수정 요청·충돌 발생 시

| 상황 | 처리 |
|---|---|
| 필드·ID·관계 의미 변경 필요 | 작업자가 schema.md를 고치지 않고 자기 HANDOFF.md에 제안. 총괄이 영향·승인 확인 후 새 계약과 기준 커밋을 배포 |
| 단순 구현 버그 | 기존 계약 유지. 담당자가 자기 폴더에서 수정하고 검증한 새 SHA 제출 |
| 통합 이후 추가 수정 | 이전 오래된 작업 브랜치에 통합본을 섞지 말고, 합의한 최신 통합 커밋에서 `codex/kg-build-fix-01` 같은 새 수정 브랜치 시작 |
| 생성 JSON 충돌 | 병합을 진행하지 말고 두 작성자가 생긴 원인을 확인. 허용 소스 변경을 다시 정리한 뒤 통합본에서 빌더로 재생성 |
| schema.md·README·공용 파일 충돌 | 소유권 위반 또는 기준점 불일치. 자동으로 ours/theirs를 선택하지 않고 해당 담당자에게 반환 |
| 원본 KB가 다른 작업에서 갱신됨 | 시연은 B의 입력으로 계속 작업. 새 KB 반영은 별도 동결·전체 재검증 회차로 취급 |
| 프로젝트 전체 검사에 기존 실패 존재 | 시연 변경의 실패와 분리해 기록. 관련 없는 코드·테스트를 고치지 않음 |

계약 변경으로 B가 바뀌면 세 사람이 임의로 각자 다른 방식의 rebase/merge를 하지 않는다. 총괄이 새 공통 기준을 공지하고, 각 담당자는 그 기준의 새 브랜치에 검토된 자기 폴더 변경만 옮겨 재검증한다. 공유 브랜치 강제 push는 하지 않는다.

## 10. 이 계획의 완료 조건과 이번 확인

실행 단계 완료 조건은 세 인계 SHA·공통 해시 일치, 소유권 위반 0개, 통합 검증 통과, 실제 화면 확인, 사람 검수 목록과 최종 README 기록이다. 파일 충돌이 없다는 사실만으로 완료하지 않는다.

최초 계획 작성에서는 로컬 상태와 입력 해시를 확인했다. 이번 공유 기준 준비에서는 이미 공유된 부모 커밋과 세 문서만의 차이를 검사하며, 최종 B와 push 결과는 총괄의 완료 전달문에 기록한다. 다른 PC의 환경과 세 구현 결과는 아직 검증하지 않았다.

총괄과 각 담당자는 이 문서를 기반으로 분담하되, 데이터 의미는 schema.md만 따른다. README와 최종 생성 그래프는 통합 단계에서 한 번 정리한다.
