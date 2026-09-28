# T4 COMMON 후속 버전·비교 실험 사전 설계 인계 · 2026-09-26

작업 공간: `D:\obsd\Projects\ShiftLink`. 이전 [장비별 인계](t4-equipment-synthetic-handoff-20260926.md)를 이어받은 별도 후속 버전이다. 진입점은 [통합 보고서](../data/knowledge_cards/drafts/20260926-t4-followup/README.md)다. 원본 카드·대본·검토·파일럿은 수정하지 않았다. 커밋·푸시는 하지 않았다.

## 후속 카드

M07/M08/M13/M16/M18만 ID를 유지한 버전 `synthetic-followup-7f44e65733f0`으로 개정했다. [카드 전문](../data/knowledge_cards/drafts/20260926-t4-followup/cards.md), [변경 전후](../data/knowledge_cards/drafts/20260926-t4-followup/changes.json), [계보](../data/knowledge_cards/drafts/20260926-t4-followup/lineage.json)를 함께 읽는다. COMMON25+장비20=45개 논리 카드이며 개수 목표·상한은 없다. 모두 개발 초안이고 후속5개는 T4 / COMMON / draft / L0 / dev다.

수신 확인, 정보 해결, 현장 확인, 작업·운전·재가동 승인을 분리했다. 새 증빙은 기존 공백과 나눠 원문·대상·판본·유효성의 대조 대상으로 연결한다. 명시적 무응답은 답변 대기, 기록 미첨부는 회신 여부 확인 대기다. 현재 인계자의 현황 인수와 원래 의뢰 대상의 회신을 서로 대신하지 않는다.

[최종 내용 검토](../data/knowledge_cards/drafts/20260926-t4-followup/review-content.json)는 비작성자 pass다. 초기 revise와 경계 대조 수정 전 파일을 보존했다. [검증](../data/knowledge_cards/drafts/20260926-t4-followup/validation.json)은 스키마5/5·필드 누락/공백거부50/50·dev 차단5/5·draft/L0 제외5/5·원본67파일 불변·대본5개 동일을 확인한다. 경계 대조9개는 저자 작성 예시이며 역할 실행 결과가 아니다.

## 사전 설계와 실행 경계

[프로토콜](../data/knowledge_cards/drafts/20260926-t4-followup/experiment/protocol.md), [장비·카드·실패 요인·계보](../data/knowledge_cards/drafts/20260926-t4-followup/experiment/coverage-and-lineage.json), [평가 기준](../data/knowledge_cards/drafts/20260926-t4-followup/experiment/evaluation-only/rubric.md)을 먼저 읽는다. 실제 실행 전에는 [동결 기록](../data/knowledge_cards/drafts/20260926-t4-followup/freeze.json)의 해시와 독립 설계 검토를 다시 확인한다.

[최종 독립 설계 검토](../data/knowledge_cards/drafts/20260926-t4-followup/experiment/review-design.json)는 pass이며 입력을 실행 전에 동결했다. 초기 revise·수정 snapshot7개·내용 지적4건과 로그 보완을 보존했다. 최종 사실69/미확인27개, 역할packet/template/원자료30개 불변, 카탈로그 참조21개를 검증했다. 하위 저자 문서의 대기 표시는 작성시점 기록이며 최종상태는 동결 파일을 따른다.

- HPU/GR/RT/CV/PDP/CAU 6개 개발 사건 × 3조건 × 3반복 =54쌍, 기본108역할 호출 계획. 서로 독립인54개 사건이 아니다.
- 카드 없음/일반5항목/선택카드 **know_how 원문만**. 선택은 K-0037/K-0033/K-0048/K-0028/K-0042/K-0026이다. 카드 전문·전체20개·이번 COMMON5개 효과로 확대하지 않는다.
- 원자료6개, 송신packet18개, 수신template6개와 평가원장 분리. 미래 실제 송신문을 넣기 전의 수신template를 실입력이라고 부르지 않는다.
- 역할별 `fork_turns=none`, 자기packet1회 읽기 외 도구금지, 송신1편+수신1편. OS 보안격리가 아니다.
- 각1800 Unicode자 요청, 역할당600초, 인프라실패 한정1회재시도. 토큰/비용/모델스냅샷 등 비노출 설정은 unavailable. 고정 순환 순서와 정보노출 시 중단 규칙을 준수한다.
- 고정 원장 기준 종단 보존과 실제 수신입력 기준 충실도를 분리한다. 입력 밖 명칭의 부정형 전제는 엄격/대안 기준을 사전 지정한다. 신규 요청·수신확인 요청·자발 되짚기·기존정보 재질문을 따로 센다.

이번 작업에서 새 역할 실험은 **미실행**이다. 실행 원문·판정·차이·개선 효과도 없다. 기존 파일럿의 카드 추가효과 미입증과 HPU 명칭 경계0~1을 유지한다. [기존 경험 비교·장비카드 미수정 결정](../data/knowledge_cards/drafts/20260926-t4-followup/experience-decisions.md)을 읽고 실행 뒤 실제 성공/실패 근거가 있을 때만 수정한다. 원상황 재실행은 회귀 확인이며, 수정에 쓰지 않은 별도 사건 구조의 새 상황 평가는 다시 사전 설계·검토·동결한다.

## 정보 접근 편차

최초 설계 에이전트가 원본 카탈로그 전체 출력에서 sealed 지정 프로토타입 요약 메타데이터1건을 우발적으로 보았다. 산출물 없이 중단하고 `fork_turns=none`의 새 작성자로 교체했다. 최종 작성자는 equipment_types/equipment/relations만 담은 투영본을 사용했다. [접근 편차 전문](../data/knowledge_cards/drafts/20260926-t4-followup/access-deviation.md)을 보존한다. 작업 전체가 sealed 메타데이터 비열람을 완벽히 충족했다고 주장하지 않는다. 기존 sealed/holdout 사건을 열거나 이후 실험 재료로 사용하지 않는다.

## 재검증·다음 작업

```powershell
python -X utf8 docs/data/knowledge_cards/drafts/20260926-t4-followup/verify.py
python -X utf8 docs/data/knowledge_cards/drafts/20260926-t4-followup/experiment/verify-design.py
```

첫 명령은 현재 폴더의 validation.json만 갱신하고 원본과 동결 입력의 해시를 검사한다. 두 번째는 설계 정적 검사이며 역할을 실행하지 않는다. 기존 build.py/pilot.py를 다시 실행해 과거 자료를 덮어쓰지 않는다. 새 실행·누락·부적격·재시도·입출력해시는 별도 execution 폴더에 남기고 동결본은 그대로 유지한다. 계획 변경이 필요하면 새 버전에서 변경 이유와 재검토를 남긴다.

운영 DB·등록부·split 정책·KB 채택은 계속 범위 밖이다. 연구의 내부 정합성, 합성 역할 결과, 일반화, 사람/현장 효과를 각각 분리해 보고한다.
