# 배치 C — 상위 출처·분할 계약 반영

반영일 2026-09-30. 카드 19장의 출처와 일반화 근거를 수정했다.
원본 생성 프롬프트, 카드 ID, 기존 운영 KB 41장, 기존 승인·그룹 배정은 유지했다.
이 반영은 등록·보완 대기·오사용 차단이며 사람 승인이나 계약 준수 완료 선언이 아니다.

## 카드와 출처에 반영한 내용

- PDF 7개를 M-C-001~007, 인용 사건/기록 45개를 SC-C-EV/AR 기준 ID로 출처 등록부에 추가했다.
- 카드 provenance.sources는 기준 ID를 사용한다. 기존 파일명·EV/AR·쪽·절은 locator와 등록부 aliases에 보존했다.
- 원문 PDF 7개의 실제 파일 SHA256, 사용 페이지 25개 범위의 텍스트 SHA256, KB 관측 항목 45개의 SHA256을 기록했다. 원문 텍스트 자체는 등록부에 복제하지 않았다.
- approved_scope는 모두 빈 상태이고 review_status는 pending_review다. 검토 후보의 해시가 있다는 사실을 사용 승인으로 취급하지 않는다.
- 카드 provenance.index_version은 policy_manifest.json의 실제 UTF-8 파일 바이트 SHA256을 고정한다.
- T6 9장의 confidence_basis·generalization_scope에 단일 합성 계보, 독립 현장 반복 미입증, 출처 승인 보완 대기를 명시했다.

## 사건 계보와 분할

동일 설비·재가동 유형의 생성 템플릿, 복합 사건에서 연결된 재가동 단계,
ID·숫자를 정규화한 기록 중복을 연결해 보수적인 계보 후보 7개를 기록했다.
기존 사건 번호 중 최소 ID를 그룹 이름으로 정한 뒤 계약의 SHA256 규칙을 계산했다.
원하는 분할이 나올 때까지 ID를 바꾸지 않았다.

| 후보 그룹 | 사건 수 | 해시 bucket | 검토 후 배정 후보 |
|---|---:|---:|---|
| KB-20260930-C:EV-0401 | 5 | 6 | kb |
| KB-20260930-C:EV-0403 | 2 | 5 | kb |
| KB-20260930-C:EV-0405 | 3 | 6 | kb |
| KB-20260930-C:EV-0407 | 2 | 10 | sealed |
| KB-20260930-C:EV-0409 | 3 | 2 | kb |
| KB-20260930-C:EV-0411 | 2 | 8 | dev |
| KB-20260930-C:EV-0413 | 3 | 3 | kb |

위 표는 분할 정책의 pending_groups로 관리하는 후보이며 활성 assignments가 아니다.
현재 카드 split=kb와 원장의 KB15/dev5는 최초 생성의 역사적 라벨로 남긴다.
후보의 lineage_review_status는 pending_review, assignment_active는 false다.
사람이 계보를 확인한 뒤 실제 기록·카드의 split을 확정한 그룹 배정과 일치시켜야 한다.
sealed 후보도 이미 생성·검토에 사용한 합성 자료이므로 새로운 독립 최종 평가로 사용하지 않는다.

## 評価資料の隔離

EV-0416~0420과 대응 AR-0431~0440은 KB와 같은 템플릿에서 파생됐다.
원래 내용은 records/quarantined_dev_events.json과 quarantined_dev_artifacts.json에 보관하고,
records/dev_events.json·dev_artifacts.json의 활성 입력은 비웠다.
event_plan 전체 20건의 evaluation_eligible은 false이며 policy_manifest의 independent_dev_event_ids도 비어 있다.
events.json과 artifacts.json은 감사용 원장이며 독립 평가 입력으로 이용하지 않는다.
프로젝트의 기존 평가 자료와 기존 sealed 자료는 변경하지 않았다.

## 승인·KB 편입 검사

policy_gate.py는 등록부의 승인 범위·판본·텍스트 해시, 사건의 계보 참조,
카드의 지지 사건으로 계산한 그룹, 실제 활성 배정과 split, 독립 반복 근거를 확인한다.
등록됐어도 승인이 없는 19장은 모두 보완 대기다.

```powershell
# CI와 같은 Python 3.10 / Pydantic 2.9.2 검증 환경
python verify.py             # 구조·참조·격리 검증
python verify.py --kb-ready  # 현재 종료 코드 1: 승인·계보·반복 근거 미해결
```

merge.py는 미해결 항목이 있는 accepted 카드를 파일에 쓰기 전에 거부한다.
verify.py도 직접 accepted로 변경한 카드를 거부하고, 격리 dev의 재투입을 감지한다.
공식 생성 preflight도 pending 출처와 미등록 활성 그룹을 거부한다.
상위 build_kb.py는 변경하지 않았고 C는 운영 KB에 포함되지 않는다.

## 추적 기록

- align_policy.py: 한 번만 실행하는 등록·격리 처리. 기존 변경 이력이 있으면 재실행하지 않는다.
- policy_alignment_changes.json: 원본 19장, 갱신한 카드, 이전 등록부·분할 정책 해시, manifest 핀 보정 이력.
- policy_manifest.json: 출처 ID 대응표, 후보 7개, 카드별 보완 항목, 평가 제외 ID.
- policy-alignment-review.md: 독립 에이전트 재검증.

남은 항목은 출처 사용 범위의 실제 승인, 계보와 그룹 배정 확정, T6의 독립 반복 근거다.
다른 ID를 만들거나 중복 문장을 바꿔 써서 근거가 늘어난 것으로 취급하지 않는다.

## 확인 결과

전체 기존 테스트는 445 passed in 12.02s였다. 배치 구조·참조·격리 검증도 통과했다.
독립 서브에이전트가 출처 등록, 해시, 계보 후보, 승인 차단 동작을 재검증했다.
`--kb-ready`가 종료 코드 1을 반환하는 것은 현재 승인 미완료 상태를 정확히 반영한 결과다.

## 10/2 정책 게이트 통과 (최재영 승인)

`verify.py --kb-ready` 결과: **READY, 막힌 카드 0** (이전 19장).

| 항목 | 처리 |
|---|---|
| 출처 승인 52개 | 매뉴얼 7개는 검토 후보 발췌 25개를 그대로 `approved_scope`(background)로 승인. 합성 기록·사건 45개는 `case`로 승인(로컬 스냅샷 해시 기준) |
| 계보 그룹 7개 | 모두 `kb`로 확정해 `assignments`에 옮김. EV-0407(해시 후보 sealed)·EV-0411(dev)도 이미 카드 생성·검토에 쓴 합성 자료라 kb로 두고 독립 평가에 쓰지 않음 |
| T6 독립 반복 근거 9장 | 실제 공개 사례 5장: K-1213·K-1216(맞음), K-1212·K-1215·K-1219(부분, 범위 표시). 출처 `RC-T6-001~007`에 URL·위치·요약만 등록(원문 미보관). 미확보 4장(K-1211·1214·1217·1218)은 프로젝트 수준 예외 |
| 기록 | `t6_independent_evidence-20261002.json` (요청 원문 포함), `policy_gate.py`가 이 파일을 읽음 |

카드 본문·제목·증상·근거 목록은 바꾸지 않았다. 검색 점수와 `kb_cards.json`은 그대로다.
이 승인은 프로젝트 수준이며, 원문 이용 범위의 법적 검토나 현장 숙련자 평가를 한 것은 아니다.
