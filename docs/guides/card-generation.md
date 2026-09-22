# 근거 연결·검증·초안 저장 파이프라인

2026-09-22 구현. 진입점은 [`shiftlink/data/generation.py`](../../shiftlink/data/generation.py)이며 기존 `python -m shiftlink.data all`은 계속 계획 출력 전용이다. 카드 스키마와 생성 프롬프트를 재사용하며 의존성은 추가하지 않았다.

## 처리 흐름

1. 운영자가 작성한 요청·출처 등록부·그룹 배정표를 읽는다. 요청의 알 수 없는 필드, 미배정 그룹, sealed 그룹을 거부한다. 신규 그룹은 계보 검토 후 기존 분할 계약에 따라 배정표에 먼저 등록한다.
2. 선택한 출처가 `approved_for_draft`이고 선택한 절의 검토 기록이 완전한지 확인한다. 발췌문 UTF-8 SHA-256을 검토된 해시와 비교한다. 사건 원문은 요청과 같은 그룹이어야 한다.
3. 검토된 발췌문·허용 주장·제외 범위·스키마를 생성기에 전달한다. 다른 사건 파일, 정답지, 전체 출처 등록부는 전달하지 않는다.
4. 생성 결과의 JSON, 카드 스키마, 필드별 근거 연결, 원문 참조 ID, 알 수 없는 필드, 관리 필드 침범을 검사한다.
5. 통과한 카드를 SQLite `drafts`에 `status=draft`, `grade=L0`로 저장한다. 실패는 `generation_runs`의 `needs_review`로 저장한다. 카드 ID/버전이 같으면 덮어쓰지 않는다. 카드와 실행 기록 저장은 한 트랜잭션이다.

현재 [등록부](../../seeds/source_registry.json)의 실제 자료는 모두 `pending_review`다. 이번 구현에서 출처를 자동 승인하거나 실제 카드를 생성하지 않았다. 출처 확인·분할 규칙은 [데이터 계약](../data/policies/source-and-split-contract.md)을 따른다.

## 검토된 절 등록

검토자가 원문 판본과 해당 절을 확인한 뒤 출처의 `review_status`를 `approved_for_draft`로 변경하고 `approved_scope`에 아래 형식의 항목을 추가한다. 한 문서의 일부 절만 승인할 수 있다. 나머지 출처 정보는 유지한다. 아래 값은 형식 예시이며 실제 승인 기록이 아니다.

```json
{
  "scope_id": "section-7-reviewed",
  "locator": "section 7, printed page 33",
  "document_version": "검토한 실제 판본",
  "text_sha256": "검토한 발췌문 UTF-8 바이트의 64자리 소문자 SHA-256",
  "allowed_claims": ["이 발췌문으로 뒷받침할 수 있는 주장"],
  "exclusions": ["이 자료로 확정할 수 없는 적용 범위"],
  "reviewed_by": "실제 검토자 식별자",
  "reviewed_at": "2026-09-22T09:00:00+09:00",
  "use_scope": "검토한 이용 범위",
  "kind": "background",
  "group_id": null,
  "reference_ids": []
}
```

`kind=case`인 경우 `group_id`를 필수로 맞추고 원문에 실제 존재하는 `EV-0001`, `AR-0001` 형태의 참조만 `reference_ids`에 등록한다. `background`에는 사건 그룹·참조를 넣지 않는다. 생성된 K 카드의 재투입은 거부한다. 별칭 대신 등록부의 기준 `source_id`를 사용한다.

해시는 `hashlib.sha256(text.encode("utf-8")).hexdigest()`로 계산한다. 줄바꿈·공백을 포함해 요청의 `text`와 정확히 일치해야 한다. PDF 파일 전체 해시와 발췌문 해시는 다르다. 검토자가 선택한 원문 범위를 텍스트로 준비하는 단계이며 PDF 자동 추출·의미 검증은 포함하지 않는다.

## 생성 요청

요청 파일에는 다음 필드만 넣는다. confidence는 모델이 만들지 않고 근거를 기록한 요청자가 제공한다. 생성 시각·스키마·프롬프트 버전·출처 연결·split·grade·status는 실행기가 정한다.

```json
{
  "card_id": "K-9001",
  "version": "1.1-draft-001",
  "group_id": "PT-0003",
  "persona_id": "작성자 식별자",
  "model_version": "실제로 호출하는 모델 및 버전",
  "confidence": 0.4,
  "confidence_basis": "이 값을 부여한 검토 근거; 예시값을 그대로 사용하지 않음",
  "excerpts": [
    {
      "evidence_id": "E1",
      "source_id": "SD-002",
      "scope_id": "section-7-reviewed",
      "text": "해시 검토를 마친 실제 발췌문"
    }
  ]
}
```

등록부·배정표는 신뢰할 수 있는 운영자 입력이다. 모델 출력으로 이를 갱신하지 않는다. 검토자 신원 인증, 역할 권한, 원문 자체의 진위·유사 사건 중복 판정은 이 모듈이 대신하지 않는다. 정답이나 사후 정보가 발췌문에 포함되지 않도록 검토 단계에서 확인한다.

## 호출 방법

프로젝트 루트에서 실행한다. 생성기는 UTF-8 프롬프트를 표준입력으로 받고 JSON 하나를 표준출력으로 반환하는 실행 파일/스크립트면 된다. 진행 로그는 표준오류로 출력해야 한다. `--generator-command` 이후의 인자는 모두 생성기에 전달되므로 마지막에 배치한다. shell 없이 실행하며 기본 제한 시간은 120초다.

```powershell
python -m shiftlink.data.generation --request artifacts/request.json --generator-command python path/to/your_generator.py
```

기존 Python 모델 호출을 연결할 때는 함수를 직접 전달한다.

```python
from shiftlink.data.generation import generate_draft

result = generate_draft(
    request, registry=registry, policy=split_policy,
    generate=my_generator,  # (prompt: str) -> JSON str
    database="artifacts/generation/drafts.sqlite3",
)
```

이미 생성한 응답을 같은 검사·저장 경로로 가져올 수도 있다. 이 경우 `model_version`에는 원래 응답을 만든 모델 버전을 기록한다.

```powershell
python -m shiftlink.data.generation --request artifacts/request.json --candidate artifacts/candidate.json
```

종료 코드: `0` 초안 저장, `1` 보완 대기 기록, `2` 입력 파일 읽기/JSON 해석/저장 실패. 코드 2는 보완 대기 기록조차 저장되지 않았을 수 있다. DB 접근 오류는 라이브러리 호출에서는 예외로 전달한다. 생성기 오류는 자격증명 등이 포함될 수 있는 원문 오류 메시지 대신 예외 종류만 기록한다.

## 생성기 응답과 근거 연결

응답은 `{"card": {...}, "evidence": {...}}`다. `card`에는 관리 필드 `card_id`, `version`, `grade`, `status`, `split`, `confidence`, `provenance`, `safety_review`를 넣지 않는다. schema의 나머지 내용 필드를 작성한다. 사람이 승인한 안전 검토 기록도 생성 모델이 만들 수 없다.

`component`, `title`, `symptom`, `know_how`, `rationale`, `conditions`, `exclusions`, `safety_basis`, `type_payload`, `generalization_evidence`, `conflict_group` 아래의 값이 있는 모든 말단 필드를 JSON Pointer로 연결한다. 목록은 0부터 인덱스를 사용한다. null과 빈 목록은 연결 대상이 아니다. 예:

```json
{
  "/know_how": ["E1"],
  "/conditions/0/signal": ["E1"],
  "/conditions/0/op": ["E1"],
  "/conditions/0/value": ["E1"],
  "/type_payload/steps/0/action": ["E1", "E2"]
}
```

이 예는 evidence 일부를 설명한 것이며 완전한 카드 응답은 아니다. 실제 필드 누락, 존재하지 않는 경로, 없는 evidence_id, 중복 연결은 보완 대기로 간다. 사건·실패 참조는 해당 경로에 연결한 발췌문의 검토 범위에도 등록되어 있어야 한다.

카드에는 사용한 출처의 ID·위치·판본을 `provenance.sources`로 기록한다. 더 상세한 필드별 연결, 검토된 발췌문, 요청자의 confidence 근거, 프롬프트·후보 응답, 요청/등록부/분할/프롬프트/출력 해시는 실행 감사 기록에 남긴다. 생성 전 차단된 입력은 본문 대신 해시와 오류를 기록한다.

## 초안·보완 대기 조회

기본 DB는 git에서 제외되는 `artifacts/generation/drafts.sqlite3`다. 저장된 JSON은 `KnowledgeCard.model_validate_json()`으로 다시 읽을 수 있다.

```sql
SELECT card_id, version, card_json FROM drafts;
SELECT run_id, stage, errors_json, audit_json
FROM generation_runs WHERE status = 'needs_review';
```

재시도는 새 실행 기록을 만든다. 동일 카드의 새 버전은 요청자가 명시해야 한다. 초안은 기존 검색기의 `accepted/kb/L1` 조건을 통과하지 않으므로 자동 KB 반영이 일어나지 않는다.

근거 연결 검사는 **참조의 존재·범위·완전성**을 확인한다. 인용된 문장이 주장을 실제로 뒷받침하는지, 작업 지시가 적절한지, 숫자가 실제 설비에 맞는지는 사람이 검토해야 한다. 성공 결과도 `human_review_required=true`다. 실제 모델 품질·처리량·대용량 병렬 성능은 별도 측정 대상이며, 이 구현의 테스트는 모의 생성기를 사용한다.
