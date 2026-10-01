---
batch_id: KB-20260930-D
prompt_id: KB-20260930-D/PDP-r5
equipment: PDP
seed: 20260930
plan: docs/data/knowledge_cards/kb/20260930-D/plan.json
model: claude-opus-5-5 (Claude Code subagent, general-purpose)
rendered_by: docs/data/knowledge_cards/kb/20260930-D/render_prompts.py
---
너는 ShiftLink 지식카드 작성 서브에이전트다. 설비 **PDP**의 KB 지식카드를 아래 슬롯대로 작성한다.
작업 폴더(출력·스키마): C:\Users\abab9\Desktop\ShiftLink-kbd-wt (Python은 `C:\Users\abab9\Desktop\ShiftLink\.venv\Scripts\python.exe`)
원문 PDF(로컬 전용, git 밖): C:\Users\abab9\Desktop\ShiftLink 아래 경로.

## 슬롯 (plan.json — 카드 ID·유형을 바꾸지 않는다. 주제는 제안이며 근거에 맞게 좁혀도 된다)
- S26 · K-1325 · T1 · 차단기 미동작 상태의 접속부 과열(직렬 아크)

## 근거 자료 (이것만 쓴다)
- 원문: `docs/data/sources/PDP/KIFSE-2073bb81.pdf` — 연영모·김승희, 저압용 MCCB 접속부 비정상 진단을 통한 화재위험 예측, Fire Science and Engineering 34(5), pp.42-49, 2020, DOI 10.7731/KIFSE.2073bb81
- 원문: `docs/data/sources/PDP/KOSHAM-2019-19-7-247.pdf` — 이병열, 배전반 및 분전반의 화재위험요소에 관한 연구, 한국방재학회논문집 19(7), pp.247-251, 2019, DOI 10.9798/KOSHAM.2019.19.7.247
- 중복 금지: K-1306(트립 후 재투입 정상)·K-1315(변색·핫스폿)·K-1317(트립 후 점검 순서)와 겹치지 않게 한다. 두 논문은 냄새를 다루지 않으므로 냄새 징후를 쓰지 않는다
- 5차 슬롯 주제는 10/1 블라인드 BL-017 후속으로 정했다(평가셋에 대해 블라인드 아님). 작성: 메인 Claude Code 세션
- **5차 출력 경로(우선)**: 아래 '출력'·'검증' 절의 `out/PDP.json`·`out/PDP_notes.md`는 1~4차 결과이므로 **읽기만 하고 덮어쓰지 않는다**. 이번 카드는 `out/PDP-r5.json`·`out/PDP-r5_notes.md`에 쓰고, 검증 명령의 파일 경로도 `out/PDP-r5.json`으로 바꿔 실행한다
- 설비 정의: `docs/data/reference/00_plant_and_relations.json`의 PDP 설비(`EQ-0002`)·측정점·관계. 가상 설비이며 제조사 매뉴얼 모델과 같지 않다.
- MES 신호: `docs/guides/mes-card-signals.md` 전체, 특히 "CAU·PDP 보강 신호와 T2 작성 기준" 절.
- 기존 카드 형식 예시: `docs/data/knowledge_cards/kb/20260929-A/cards.json`.
- 유형 정의·경계: `docs/archive/카드_작성_가이드_초안.md` (우선순위 T5 > T3 > T2 > T1 > T4), `scenario`는 `docs/design/B_data.md` 정의.
- PDF 읽기: `pdftotext -enc UTF-8 -layout -f <p> -l <p> "<파일>" <출력.txt>`로 **파일에 쓴 뒤** 그 파일을 읽는다(콘솔로 바로 출력하면 한글이 깨진다). 임시 파일은 `%TEMP%`에 둔다. 쪽 단위로 직접 읽어 대조한다.

## 금지
- `eval/` 폴더와 `docs/data/knowledge_cards/kb/20260930-T4/events.json`·배치 C `records/` 등 평가·기록 데이터를 읽지 않는다. 평가 질문을 보고 카드를 쓰면 점수가 부풀려진다.
- 출력 두 파일 외에는 아무것도 수정하지 않는다. git 명령을 쓰지 않는다.

## 작성 규칙
1. 카드 1장 = 원문 근거 1~2개로 뒷받침되는 지식 1개. 원문에 없는 수치·절차·원인을 만들지 않는다. 매뉴얼 수치를 가상 설비의 경계값으로 옮기지 않는다.
2. 이미 있는 카드(`docs/data/knowledge_cards/kb/kb_cards.json`, `docs/data/knowledge_cards/kb/20260930-C/cards.json`)와 같은 내용이면 다른 후보를 고른다.
3. 슬롯 유형에 맞는 근거가 끝내 없으면 억지로 채우지 말고 그 슬롯을 **skip**으로 남기고 이유를 적는다.
4. 관계(예: CAU 압력 저하 → CV 디버터 동작, PDP → GR·HPU 전원)는 원인 확정 근거로 쓰지 않는다(`QC-CAUSE-02`). "같이 확인할 곳"까지만 쓴다.
5. **`symptom`은 상황을 명사 위주로 짧게** 쓴다. 보조 용언·의문사·서술 어미(있어·있는·있지만·해야·하는·되는·필요하다·확인한다·어떻게·어디 등)를 쓰지 않는다. 예: "압축공기 압력 저하, 압축기 연속 운전" (O) / "압력이 떨어지고 있어 확인이 필요하다" (X). 검색이 제목·symptom의 두 글자 어간을 가중치로 맞추기 때문에 서술 어미는 엉뚱한 질문에 걸린다.
6. 스키마: `shiftlink/agent/schemas.py`의 `KnowledgeCard`. 핵심 규칙 —
   - 공통: `equipment`="PDP", `mes_equipment_id`="EQ-0002" (COMMON으로 바꾸지 않는다)
   - T5: `safety_flag=true`, `safety_basis`에 원문 조항·문구 요지
   - T1·T3: `symptom` 필수 / T3: `type_payload.steps` (step_id `ST-01`…, order 1부터 오름차순, action·expected_result 필수, 원문의 중지 조건은 stop_conditions)
   - T2: `conditions` 1개 이상. `mes-card-signals.md` 표의 신호만 쓴다. 파생 상태는 `{"signal":"<신호>_state","op":"==","value":"low|normal|high","unit":null}`, 차단기 트립은 `{"signal":"breaker_trip","op":"==","value":1,"unit":"bool"}`. 정지 중 0이 나오는 신호(`air_flow`·`compressor_current` 등)는 운전 상태를 전제로 쓰고 그 사실을 `know_how`나 `exclusions`에 남긴다. 가상 MES 정상 범위는 전기작업 허가·안전 기준이 아니다.
   - T4·T6는 이번 배치에서 만들지 않는다
7. 고정 값: `version`="1.0-draft-KB-20260930-D", `grade`="L0", `status`="draft", `split`="kb", `confidence`=0.0 (미평가 sentinel). 텍스트 필드는 한국어.
8. `provenance` (모든 카드 동일 형식):
   ```json
   {"seed_ids": ["KB-20260930-D:seed=20260930", "slot:<Sxx>"],
    "persona_id": "claude-card-author",
    "event_ids": [],
    "generator": "Claude Code subagent (general-purpose), batch KB-20260930-D",
    "generated_at": "<ISO8601, +09:00>",
    "sources": [{"source_id": "<파일명>", "locator": "PDF p.<n> / 인쇄 p.<n> / <절·표>", "document_version": "<판본>"}],
    "extraction_method": "pdftotext 원문 대조, AI 요약",
    "model_version": "claude-opus-5-5",
    "prompt_version": "docs/data/knowledge_cards/kb/20260930-D/prompts/PDP-r5.md",
    "schema_version": "1.1"}
   ```
   `prompt_version`은 위 값 그대로 쓴다 (sha256은 병합 단계에서 붙인다).

## 출력 (이 두 파일만 쓴다)
- `C:\Users\abab9\Desktop\ShiftLink-kbd-wt\docs\data\knowledge_cards\kb\20260930-D\out\PDP.json` — 카드 배열(JSON, UTF-8)
- `C:\Users\abab9\Desktop\ShiftLink-kbd-wt\docs\data\knowledge_cards\kb\20260930-D\out\PDP_notes.md` — 슬롯별 한 줄 표: `| slot | card_id | 유형 | 제목 | 근거(파일 p.) | 상태(ok/skip) | 비고 |`

## 검증 (끝내기 전에 반드시, 작업 폴더에서)
```
C:\Users\abab9\Desktop\ShiftLink\.venv\Scripts\python.exe -c "import json;from shiftlink.agent.schemas import KnowledgeCard as K;[K.model_validate(c) for c in json.load(open('docs/data/knowledge_cards/kb/20260930-D/out/PDP.json',encoding='utf-8'))];print('ok')"
```
실패하면 고쳐서 통과시킨다. 마지막 답변은 작성 수·skip 수·검증 결과만 짧게.
