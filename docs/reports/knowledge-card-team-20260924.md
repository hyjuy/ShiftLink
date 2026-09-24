# 원문 기반 지식카드 생성팀 결과

현재 기본 보관 위치는 사용자 승인에 따라 [docs/data/knowledge_cards/drafts/20260924](../data/knowledge_cards/drafts/20260924/README.md)다. 아래 artifacts 링크는 생성·검토 당시 작업 기록으로 유지한다. 보관 승인으로 카드 상태를 승격하지 않았으며 3건은 draft/L0다.

2026-09-24. 사용자 요청에 따라 원문 선별 → 생성 → 독립 검토 → 분석 순서로 서브에이전트 팀을 운영했다. **실제 KnowledgeCard JSON 3건을 생성했으며 모두 draft/L0 검토용 초안이다.** M-101-2012 문헌 내용을 요약한 카드로, 현장 경험을 새로 수집한 결과나 안전 작업 승인으로 해석하지 않는다.

## 생성 카드

| ID | 유형 | 내용 | 원문 위치 |
|---|---|---|---|
| K-0301 | T5 | 컨베이어 정지스위치 주변 장애물 금지 | SD-005, PDF p.7 / 인쇄 p.5 / §4.3(3) |
| K-0302 | T6 | 비상·사고 정지 후 재기동 전 원인·보수상황 확인 | SD-005, PDF p.7 / 인쇄 p.5 / §4.3(7) |
| K-0303 | T5 | 컨베이어 올라가기 금지와 원문 예외 | SD-005, PDF p.8 / 인쇄 p.6 / §4.3(11) |

[카드 읽기](../../artifacts/knowledge-card-team-20260924/cards.md) · [카드 JSON](../../artifacts/knowledge-card-team-20260924/cards.json) · [필드별 근거 지도](../../artifacts/knowledge-card-team-20260924/evidence-map.json)

## 팀과 작업 순서

1. `source_editor`: 로컬 KOSHA·SKF·NSK PDF 관련 페이지를 추출·렌더링 대조하고 원문 해시, 계보, 후보와 제외 범위를 작성했다. 생성 중 요청된 재기동 전제와 올라가기 예외를 원문 전체 조항으로 보강했다.
2. `card_author`: 근거 패킷에서 3건을 생성했다. 본문 사실과 유형·독자·분할 등 제작 메타데이터의 근거를 구분했다. 프로젝트 Qwen/Ollama를 호출한 결과가 아니라 Codex 서브에이전트(GPT-6 계열)가 작성한 결과다.
3. `card_reviewer`: 원문과 완성 카드를 독립 대조했다. K-0302 문구의 일본어 혼입을 수정 요청해 한국어 정정 후 검수했다. 3건의 내용 검토는 통과, 운영 채택은 보류로 구분했다.
4. `card_analyst`: 검수된 배치의 유형·출처 편중, 충족 범위, 보완 우선순위를 분석했다. 메인은 최종 파일·해시 및 기존 계약으로 형식과 격리 조건을 확인했다.

[원문 검토](../../artifacts/knowledge-card-team-20260924/source-review.md) · [작성 판단](../../artifacts/knowledge-card-team-20260924/author-notes.md) · [독립 검수](../../artifacts/knowledge-card-team-20260924/review.md) · [결과 분석](../../artifacts/knowledge-card-team-20260924/analysis.md)

## 보류·제외

- SKF 감속기 사례: 단일 설계개선 사례로, 조건에 따라 달라지는 재사용 요령이 부족하여 T2로 강제 분류하지 않았다. 개발용(dev) 계보를 유지한다.
- NSK 냉간압연 베어링 사례: 현재 GR/RT 설비 분류와 대응하는 근거가 부족하다. 개발용(dev) 계보를 유지한다.
- KOSHA 정비 중 정지·작동방지: 기존 K-0108과 상당 중복하여 새 카드를 만들지 않았다.
- 유압 자료: 기존 sealed 계보 메타데이터를 확인하고 이번 원문 열람·생성에서 제외했다.

## 검증과 사용 범위

프로젝트 고정 버전 Pydantic 2.9.2로 3건을 검증했다. 알 수 없는 필드, 카드 ID 충돌(공유 KB와 20260923 초안 대상), 전체 유효 말단 필드의 근거 연결, 원문 파일 SHA-256, 분할 해시, 런타임 검색기에서 초안 제외를 확인했다. 기존 카드 스키마 테스트도 **23 passed**다. 재현 명령과 상세 결과는 [검증 스크립트](../../artifacts/knowledge-card-team-20260924/validate.py), [validation.json](../../artifacts/knowledge-card-team-20260924/validation.json)에 있다.

```powershell
$env:PYTHONPATH = (Resolve-Path '.test-deps').Path + ';' + (Get-Location).Path
python artifacts/knowledge-card-team-20260924/validate.py
python -m pytest tests/test_schemas.py -q -p no:cacheprovider
```

3건은 같은 문헌 계보 1개에 속한다. `split=kb`는 기존 해시 규칙의 미등록 제안값이며 KB 편입 승인이 아니다. `confidence=0.0`은 미평가 표시이며 정확도나 신뢰도 측정값이 아니다. 평가 사건·실패 경험·임계값·복구 성공을 창작하지 않았다.

SD-005는 `pending_review`, 승인 범위는 비어 있는 상태를 유지했다. 승인된 출처를 요구하는 공식 생성·DB 저장 파이프라인은 실행하지 않았으며, 검토용 파일을 작성했다. 출처 이용 범위, 현행 문서와 현장 적용성, 사람 안전 검토, 전체 자료의 의미 중복·계보 검토는 남아 있다. 구조 검증 및 AI 내용 검토를 사람의 승인으로 표시하지 않았다.

출처 등록부·정식 배정표·운영 KB 파일은 작업 전후 해시가 같다. 제품 코드는 이 작업에서 변경하지 않았다. 산출물 디렉터리 `artifacts/knowledge-card-team-20260924/`는 기존 Git 제외 정책을 따르는 로컬 결과물이므로 공유 시 별도 보관이 필요하다.

## 후속 요청: 기존 페르소나 적용

`seeds/personas_v0.1.yaml`의 기존 V-01 박 반장(HPU·GR), V-02 김 기장(RT·CV), V-03 이 주임(교대 인계)을 별도 서브에이전트가 적용해 카드 3건씩 총 9건을 검토했다. 모두 합성 설정이며 실제 작업자의 발언·승인으로 표시하지 않았다.

세 검토 모두 문헌 사실 본문 유지를 제안했다. 이에 역할별 표현, 오해 방지 메모, 원문 밖 확인 질문을 [페르소나별 카드 설명](../../artifacts/knowledge-card-team-20260924/persona-review/cards-by-persona.md)에 반영했다. 카드 JSON·원문·기존 검수 이력은 유지하고 제작자 필드를 페르소나 ID로 바꾸지 않았다. 독립 카드 수는 계속 3건이며 유형 변경·운영 승격은 없다. [적용·검증 기록](../../artifacts/knowledge-card-team-20260924/persona-review/application.json)에서 페르소나와 검토 대상의 파일 해시 및 3×3 대응을 확인할 수 있다.
