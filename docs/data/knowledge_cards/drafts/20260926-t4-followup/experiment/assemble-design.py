"""Author: /root/experiment_design_fresh. Evaluation-side design assembly only.

Does not invoke role agents, write to prior batches, or freeze/review the design.
Run once; refuses to overwrite outputs. Standard library only.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent.parent / "20260926-t4-equipment" / "cards.json"
cards = {c["card_id"]: c for c in json.loads(SOURCE.read_text(encoding="utf-8-sig"))}

def write(name, value):
    p = HERE / name
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8", newline="\n") as f:
        f.write(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + "\n")

def digest(data):
    return hashlib.sha256(data).hexdigest()

# These assertions and design labels are evaluator-only, never role input.
CASES = [
    dict(id="F-HPU", family="HPU", card="K-0037", equipment=["HPU-01", "RT-02", "RT-03", "CV-01"],
         mechanism="시각이 어긋난 공급/수요 관측과 일부 수치 회신; 항목명이 없는 RT-03 회신",
         related_pilot="P-HPU의 공급/수요 구분 및 대상명 경계에서 착안; 독립 holdout 아님",
         memos=[
             "계측 종이: HPU-01 / hpu_pressure / 151 bar / 10:14",
             "RT-02 쪽 문자 옮김: 10:09 rt_clamp_press 105 bar",
             "CV-01 종이 조각: cv_belt_tension 421 … 뒤쪽 찢김. 단위, 시간 부분 안 보임.",
             "10:17 RT-03 채팅: '인계문 봄'",
             "10:18 RT-02 채팅: '105 수치 받음. 시간은 어느 건?'",
         ],
         facts=[
             (0, "HPU-01 hpu_pressure의 기록값은 151이다."),
             (0, "HPU-01 hpu_pressure의 원문 단위는 bar다."),
             (0, "HPU-01 hpu_pressure의 기록시각은 10:14다."),
             (1, "RT-02 rt_clamp_press의 기록값은 105다."),
             (1, "RT-02 rt_clamp_press의 원문 단위는 bar다."),
             (1, "RT-02 rt_clamp_press의 기록시각은 10:09다."),
             (2, "CV-01 cv_belt_tension의 읽히는 기록값은 421이다."),
             (3, "RT-03의 회신 원문은 인계문을 봤다는 범위다."),
             (3, "RT-03 회신시각은 10:17이다."),
             (4, "RT-02는 105라는 수치를 받았다고 회신했다."),
             (4, "RT-02는 해당 수치의 시각을 질문했다."),
             (4, "RT-02 회신시각은 10:18이다."),
         ], unknowns=[
             (2, "CV-01 종이 조각에 적힌 단위는 읽을 수 없다."),
             (2, "CV-01 종이 조각의 관측시각은 읽을 수 없다."),
             (3, "RT-03의 실제 측정 항목명은 제공되지 않았다."),
             (3, "RT-03의 실제 관측값은 제공되지 않았다."),
             (3, "RT-03이 구체 내용을 정확히 인수했는지는 회신만으로 확정할 수 없다."),
             (4, "RT-02의 시각 관련 질문은 현재 자료에서 해결되지 않았다."),
         ]),
    dict(id="F-GR", family="GR", card="K-0033", equipment=["GR-01", "GR-02"],
         mechanism="동명 태그의 인스턴스 결측·출처시각 충돌과 무응답/기록미첨부 구별",
         related_pilot="P-GR 보고서의 기록미첨부 경계에서 착안; 이번 동명태그 메모는 새 작성",
         memos=[
             "GR-01 화면 옮겨 적음: gr_vib_rms 2.1 mm_s / 화면 머리 11:03",
             "수첩: 위 GR-01 2.1 찍은 시간 11:08이라고 씀. 화면 머리 시간과 안 맞음.",
             "GR-02 쪽: gr_vib_rms 2.7 mm_s / 11:05",
             "따로 떨어진 줄: gr_vib_rms 2.4 mm_s 11:06. 장비 머리글 없음.",
             "11:12 통화기록: 정비 연락 담당에게 전화, 응답 없음.",
             "교대 취합 담당 답장 캡처 첨부를 빼먹었다는 메모. 캡처 본문은 없음.",
         ], facts=[
             (0, "GR-01 gr_vib_rms의 기록값은 2.1이다."),
             (0, "GR-01 gr_vib_rms의 원문 단위는 mm_s다."),
             (0, "GR-01 화면 머리의 시각은 11:03이다."),
             (1, "GR-01 수첩의 촬영시각 주장은 11:08이다."),
             (2, "GR-02 gr_vib_rms의 기록값은 2.7이다."),
             (2, "GR-02 gr_vib_rms의 원문 단위는 mm_s다."),
             (2, "GR-02 기록시각은 11:05다."),
             (3, "장비 머리글이 없는 gr_vib_rms의 값은 2.4다."),
             (3, "장비 머리글이 없는 gr_vib_rms의 단위는 mm_s다."),
             (3, "장비 머리글이 없는 gr_vib_rms의 시각은 11:06이다."),
             (4, "정비 연락 담당에게 건 전화는 무응답으로 기록됐다."),
             (4, "정비 연락 담당에게 전화한 기록시각은 11:12다."),
             (5, "교대 취합 담당 답장 캡처는 첨부에서 빠졌다."),
         ], unknowns=[
             (1, "11:03과 11:08 중 확정할 관측시각은 미해결이다."),
             (3, "2.4 mm_s 기록의 GR 인스턴스는 미확인이다."),
             (5, "교대 취합 담당의 실제 답장 내용은 미확인이다."),
             (5, "캡처 미첨부만으로 교대 취합 담당의 실제 무응답을 확정할 수 없다."),
         ]),
    dict(id="F-RT", family="RT", card="K-0048", equipment=["RT-01", "RT-02"],
         mechanism="소재 식별 일부 판독과 뒤늦게 도착한 사진의 촬영시각 결측",
         related_pilot="P-RT의 위치/방향 관측과 다른 소재 이동 경계 사건; 같은 인계 연구의 개발 계보",
         memos=[
             "12:04 RT-01 끝에서 B-72 나가는 거 봤음 — 운전 메모",
             "RT-02 12:06: B-7? 지나감. 마지막 글자 안 읽힘 — 다른 작업자 메모",
             "12:10 단체방에 사진 파일 도착. 파일명 B72.jpg라고 적혀 있음. 사진 본문은 이 묶음에 없음.",
             "취합 담당 12:11 '사진 파일 도착한 건 받았음'",
         ], facts=[
             (0, "RT-01 송출 관측의 소재 표기는 B-72다."),
             (0, "RT-01 송출 관측시각은 12:04다."),
             (1, "RT-02 통과 관측의 판독 표기는 B-7?다."),
             (1, "RT-02 통과 관측시각은 12:06이다."),
             (2, "사진 파일의 도착시각은 12:10이다."),
             (2, "사진 파일명은 B72.jpg라고 기록됐다."),
             (2, "사진 본문은 제공된 묶음에 없다."),
             (3, "취합 담당 회신은 사진 파일 도착의 수신 범위다."),
             (3, "취합 담당의 회신시각은 12:11이다."),
         ], unknowns=[
             (1, "RT-02에서 본 소재의 마지막 글자는 미확인이다."),
             (1, "양쪽 관측이 동일 소재인지 확정되지 않았다."),
             (2, "사진 촬영시각은 제공되지 않았다."),
             (2, "사진 내용이 이동 완료를 확인하는지는 미확인이다."),
         ]),
    dict(id="F-CV", family="CV", card="K-0028", equipment=["CV-01", "CV-02"],
         mechanism="대기율의 수정 주장에 시각이 없고 육안 개수·신호 발췌가 서로 다른 범위",
         related_pilot="P-CV의 대기율/신호 구별과 연관; 새로운 값만의 치환으로 독립 일반화 주장하지 않음",
         memos=[
             "CV-01 13:20 cv_queue_len 64 pct — 화면 필사",
             "쪽지 덧붙임: 'CV-01 아까 64 아니고 46 pct였던 것 같음' / 작성자, 시간 안 적힘",
             "13:22 CV-01 끝단 눈으로 본 건 적재물 3개 — 순회",
             "CV-02: cv_queue_len 29 pct. 이 줄에는 시간 없음.",
             "신호 캡처는 파일이 안 열려 이번 묶음에 빠짐.",
             "13:25 CV-01 담당 답: '화면 64 pct라는 보고 받음'. CV-02 담당에게 보낸 메시지는 13:27까지 응답 없었음.",
         ], facts=[
             (0, "CV-01 화면 필사값은 64다."),
             (0, "CV-01 화면 필사 단위는 pct다."),
             (0, "CV-01 화면 필사시각은 13:20이다."),
             (1, "출처 불명 쪽지는 CV-01 값이 46 pct였던 것 같다는 수정 주장을 담는다."),
             (2, "CV-01 끝단 육안 기록의 적재물은 3개다."),
             (2, "CV-01 끝단 육안 관측시각은 13:22다."),
             (3, "CV-02 cv_queue_len의 기록값은 29다."),
             (3, "CV-02 cv_queue_len의 원문 단위는 pct다."),
             (4, "신호 캡처가 제공 묶음에서 빠졌다."),
             (5, "CV-01 담당은 화면 64 pct라는 보고를 받았다고 회신했다."),
             (5, "CV-01 담당 회신시각은 13:25다."),
             (5, "CV-02 담당의 응답은 없었다고 기록됐다."),
             (5, "CV-02 담당 무응답 기록의 확인 시한은 13:27이다."),
         ], unknowns=[
             (1, "64와 46 중 실제 값을 확정할 근거는 미해결이다."),
             (1, "46 pct 수정 주장의 작성자는 미확인이다."),
             (1, "46 pct 수정 주장의 관측시각은 미확인이다."),
             (3, "CV-02 29 pct의 관측시각은 미확인이다."),
             (4, "실제 신호 상태는 자료에서 확인할 수 없다."),
         ]),
    dict(id="F-PDP", family="PDP", card="K-0042", equipment=["PDP-01"],
         mechanism="표시 전압 비율과 타인의 절대전압 환산 메모 충돌; 외부 관찰·접수 범위",
         related_pilot="기존 네 장비 파일럿에는 PDP가 없었음; K-0042의 방법을 보고 만든 개발 상황",
         memos=[
             "PDP-01 14:02 표시: bus_voltage 98 pct",
             "동료 쪽지: '그러면 392 V겠네'라고 계산해 둠. 기준으로 쓴 전압 숫자는 안 붙어 있음.",
             "순회 14:05: 외함 밖 표시만 봄. 안쪽 기록은 못 받았음.",
             "전기 기록 접수 14:08 답장: '표시값 보고 접수'.",
         ], facts=[
             (0, "PDP-01 bus_voltage의 표시값은 98이다."),
             (0, "PDP-01 bus_voltage의 원문 단위는 pct다."),
             (0, "PDP-01 bus_voltage의 기록시각은 14:02다."),
             (1, "392 V는 동료 쪽지의 환산 주장이다."),
             (2, "순회 관찰 범위는 외함 밖 표시다."),
             (2, "순회 기록시각은 14:05다."),
             (2, "안쪽 기록은 전달받지 못했다."),
             (3, "전기 기록 접수 답장은 표시값 보고의 접수 범위다."),
             (3, "전기 기록 접수 답장시각은 14:08이다."),
         ], unknowns=[
             (1, "환산에 필요한 기준 전압은 제공되지 않았다."),
             (1, "392 V를 실제 절대 전압으로 확정할 수 없다."),
             (2, "내부 전원 상태는 제공 자료에서 미확인이다."),
         ]),
    dict(id="F-CAU", family="CAU", card="K-0026", equipment=["CAU-01", "CV-01"],
         mechanism="공급원 표시와 시간·대상 범위가 어긋난 디버터 육안 기록; 해결과 재전송의 구별",
         related_pilot="기존 네 장비 파일럿에는 CAU가 없었음; K-0026의 방법을 보고 만든 개발 상황",
         memos=[
             "CAU-01 air_pressure 612 kPa / 15:01 화면 필사",
             "CV-01 디버터 쪽 메모: '오전에 한 번 움직이는 건 봤다'. 시각 숫자 없음.",
             "15:06 디버터 사진 보내려다 전송 실패. 사진 내용 없음.",
             "15:09 CV-01 쪽 답: '사진은 안 왔고 오전에 봤다는 말은 받음'",
             "15:12 전송함: 사진 재전송 완료 표시. 읽음 표시는 아직 없음.",
         ], facts=[
             (0, "CAU-01 air_pressure의 기록값은 612다."),
             (0, "CAU-01 air_pressure의 원문 단위는 kPa다."),
             (0, "CAU-01 air_pressure의 기록시각은 15:01이다."),
             (1, "CV-01 디버터 육안 메모는 오전에 한 번 움직임을 봤다는 범위다."),
             (2, "최초 사진 전송은 실패로 기록됐다."),
             (2, "최초 사진 전송 시각은 15:06이다."),
             (2, "사진 내용은 제공되지 않았다."),
             (3, "CV-01 쪽은 오전 관측이라는 말을 받았다고 회신했다."),
             (3, "CV-01 쪽 회신은 사진이 오지 않았다는 내용이다."),
             (3, "CV-01 쪽의 회신시각은 15:09다."),
             (4, "전송함에는 사진 재전송 완료 표시가 있다."),
             (4, "사진 재전송 완료 표시의 시각은 15:12다."),
             (4, "재전송 사진의 읽음 표시는 아직 없다고 기록됐다."),
         ], unknowns=[
             (1, "디버터 육안 관측의 정확한 시각은 미확인이다."),
             (1, "오전 육안 기록과 15:01 공급압 관측의 시간 대응은 미확인이다."),
             (1, "현재 디버터 동작 상태는 미확인이다."),
             (4, "재전송 사진의 실제 수신 여부는 제공 자료에서 미확인이다."),
             (4, "재전송 사진의 내용 확인 여부는 제공 자료에서 미확인이다."),
         ]),
]

SENDER_TASK = "당신은 합성 교대 인계의 송신자다. 아래 메모 조각을 다음 교대 기록 인수 담당에게 전달할 한국어 인계문 한 편을 작성하라. 채널은 서면 메시지다. 인계문만 출력하고 공백·줄바꿈 포함 1800자 이내로 작성하라."
RECEIVER_TASK = "당신은 합성 교대 인계의 수신자다. 아래 실제 인계문을 받은 다음 교대 기록 인수 담당으로서 한국어 회신 한 편을 작성하라. 채널은 서면 메시지다. 회신만 출력하고 공백·줄바꿈 포함 1800자 이내로 작성하라."
RECEIVER_INITIAL = "나는 다음 교대 기록 인수 담당이다. 별도로 받은 현장 관측 자료나 이전 대화는 없다."
CHECKLIST = "1. 무엇을 전달할지 정리한다.\n2. 누구에게 전달할지 정한다.\n3. 언제 전달할지 정한다.\n4. 어떤 채널로 전달할지 정한다.\n5. 어떻게 수신 확인할지 정한다."
ACCESS_RULE = "이 파일을 한 번 읽는 도구 호출 외에는 도구를 사용하지 말라. 다른 파일·이전 대화·다른 실행을 조회하지 말라."

ledger, coverage, selections, lengths = [], [], [], []
for case in CASES:
    cid = case["id"]
    raw = "\n\n".join(case["memos"]) + "\n"
    write(f"source-memos/{cid}.txt", raw)
    card = cards[case["card"]]
    assert (card["split"], card["status"], card["grade"]) == ("dev", "draft", "L0")
    support = card["know_how"]
    selections.append({"scenario_id": cid, "card_id": card["card_id"], "version": card["version"],
        "split": card["split"], "status": card["status"], "grade": card["grade"],
        "source_file": str(SOURCE.relative_to(HERE.parent.parent)).replace("\\", "/"),
        "exposed_fields": ["know_how"], "excluded_fields": "全 other fields, including card_id, title, rationale, type_payload, provenance and evaluation",
        "exposed_text": support, "exposed_text_sha256": digest(support.encode("utf-8"))})
    for cond, extra in [("none", ""), ("checklist", CHECKLIST), ("t4", support)]:
        packet = {"task": SENDER_TASK, "access_rule": ACCESS_RULE, "notes": case["memos"], "support": extra}
        write(f"sender-packets/{cid}-{cond}.json", packet)
        lengths.append({"scenario_id": cid, "condition": cond, "support_unicode_characters": len(extra),
            "support_utf8_bytes": len(extra.encode("utf-8")), "notes_unicode_characters": len(raw),
            "token_count": "unavailable", "output_requested_unicode_characters_max": 1800})
    write(f"receiver-templates/{cid}.json", {"task": RECEIVER_TASK, "access_rule": ACCESS_RULE,
        "initial": RECEIVER_INITIAL, "handoff": None})
    atoms = []
    for kind, entries in [("fact", case["facts"]), ("unknown", case["unknowns"])]:
        for n, (memo, assertion) in enumerate(entries, 1):
            atoms.append({"atom_id": f"{cid}-{'P' if kind == 'fact' else 'U'}{n:02}", "kind": kind,
                "expected": assertion, "evidence_memo_index": memo, "sender_observability": "notes",
                "sender_required": True, "receiver_end_to_end_required": True,
                "receiver_input_fidelity": "Judge against initial plus actual handoff; a ledger match alone is not support."})
    ledger.append({"scenario_id": cid, "is_synthetic": True, "memo_fragments": case["memos"],
        "initial": RECEIVER_INITIAL, "facts_count": len(case["facts"]), "unknown_count": len(case["unknowns"]),
        "atoms": atoms, "approval_status": "No work, operation, restart or safety approval supplied.",
        "sender_only_observations": True, "receiver_private_observations": [],
        "unexposed_truth": "No invented true value behind missing/conflicting notes; adjudicate uncertainty, not an invented repair."})
    coverage.append({"scenario_id": cid, "family": case["family"], "equipment_codes": case["equipment"],
        "selected_card_id": case["card"], "schema_equipment": card["equipment"],
        "failure_mechanism": case["mechanism"], "parent_event_group": cid,
        "lineage": case["related_pilot"], "repeats_are_independent_scenarios": False,
        "generation": "New memo fragments composed by /root/experiment_design_fresh on 2026-09-26; no prior scripts/holdout opened.",
        "independent_generalization_set": False})

write("evaluation-only/fact-ledger.json", {"author": "/root/experiment_design_fresh", "status": "draft_for_independent_review", "cases": ledger})
write("card-selection.json", {"author": "/root/experiment_design_fresh", "source_cards_sha256": digest(SOURCE.read_bytes()),
    "selection_timing": "Before role execution; no outcome-based card selection", "selections": selections})
write("coverage-and-lineage.json", {"scenarios": coverage,
    "counts": {"common_cards_preserved": 25, "equipment_cards_preserved": 20, "total_cards": 45,
               "selected_cards": 6, "scenarios": 6, "conditions": 3, "repeats_per_scenario_condition": 3},
    "count_policy": "25 and 45 are current inventory, not a target or ceiling. No cards created or edited here.",
    "omissions": "14 equipment cards untested; no full-card exposure, no field study, no validation of every scenario in any family."})
write("input-lengths.json", lengths)

# Three cyclic condition orders; each condition occupies every position once in each scenario.
# Scenario order rotates by two each repeat. Fixed before execution, not randomized after outcomes.
schedule = []
condition_orders = [("none", "checklist", "t4"), ("checklist", "t4", "none"), ("t4", "none", "checklist")]
for rep in range(1, 4):
    rotated = CASES[(rep - 1) * 2:] + CASES[:(rep - 1) * 2]
    for case in rotated:
        for cond in condition_orders[rep - 1]:
            run_id = f"{case['id']}-{cond}-R{rep}"
            schedule.append({"order": len(schedule) + 1, "run_id": run_id, "scenario_id": case["id"],
                "condition": cond, "repeat": rep, "sender_packet": f"sender-packets/{case['id']}-{cond}.json",
                "receiver_template": f"receiver-templates/{case['id']}.json", "roles_in_order": ["sender", "receiver"],
                "fork_turns_for_each_role": "none", "status": "not_run"})
write("run-plan.json", {"status": "not_run_not_frozen", "design_author": "/root/experiment_design_fresh",
    "planned_pairs": 54, "planned_role_calls": 108, "roles_per_pair": 2, "schedule": schedule,
    "maximum_role_attempts_including_one_infrastructure_retry_each": 216,
    "baseline_requested_output_character_total_max": 194400,
    "failed_and_retried_outputs": "Preserve separately without truncation; not counted as replacements that erase attempts.",
    "total_tokens_budget": "unavailable", "total_cost_budget": "unavailable",
    "enforced_total_wall_clock_limit": "unavailable",
    "model_policy": "Use the same resolved model/configuration for all roles; inherit current host default without model override. Record exposed model identity before running. If configuration changes, stop this version.",
    "model_id": "unavailable_until_execution", "model_snapshot": "unavailable", "temperature": "unavailable",
    "top_p": "unavailable", "seed": "unavailable", "max_output_tokens": "unavailable",
    "output_length_metric": "Unicode code points including all spaces and newlines; Python len(text)",
    "requested_max_characters_each_role": 1800,
    "per_role_timeout_seconds": 600, "role_context_rule": "New agent per scenario/condition/repeat/role, fork_turns=none; no role batching or reuse.",
    "turns": "Exactly one sender message and one receiver response. No follow-up answer generation or conversational repair in this protocol."})
write("execution-log-template.json", {"status": "template_not_execution_evidence", "records": [],
    "record_fields": ["run_id", "role", "attempt", "agent_id", "fork_turns", "start_time_utc", "end_time_utc",
        "exposed_model_id", "model_snapshot", "temperature", "top_p", "seed", "max_output_tokens",
        "requested_char_budget", "actual_output_characters", "actual_output_tokens_or_unavailable",
        "actual_packet_path", "actual_packet_sha256", "raw_output_path", "raw_output_sha256",
        "tool_calls_observed", "tool_observation_coverage", "packet_read_count", "protocol_deviation",
        "missing_reason", "eligibility", "retry_of", "retry_reason", "task_prompt_sha256", "task_prompt_path", "actual_packet_utf8_bytes", "notes"],
    "unexposed_setting_value": "unavailable", "no_silent_retry": True})
write("evaluation-only/judgment-template.json", {
    "status": "template_not_results", "judge_id": None, "condition_labels_hidden": None,
    "fixed_ledger_judgments": [],
    "fixed_ledger_fields": ["blind_run_id", "role", "ledger_atom_id", "fixed_denominator_kind",
        "verdict_preserved_omitted_wrong_ambiguous", "actual_input_evidence", "actual_output_quote",
        "rationale", "confidence", "independent_second_judgment", "adjudication", "disagreement_preserved"],
    "actual_receiver_input_atoms": [],
    "actual_receiver_input_atom_fields": ["blind_run_id", "input_atom_id", "source_initial_or_handoff",
        "input_quote", "observation_context_id", "normalized_subject", "normalized_attribute",
        "normalized_value", "epistemic_status", "source_attribution", "deduplication_key",
        "duplicate_quotes", "ledger_atom_links_optional", "ledger_relation_matches_conflicts_unmapped",
        "introduced_by_sender", "sender_error_type_or_none", "included_in_fidelity_denominator",
        "exclusion_reason_or_none", "atomization_locked_before_receiver_output", "atomization_sha256"],
    "receiver_fidelity_judgments": [],
    "receiver_fidelity_fields": ["blind_run_id", "input_atom_id", "verdict_faithful_omitted_distorted_ambiguous",
        "receiver_quote", "inherited_misinformation", "rationale"],
    "claim_judgments": [],
    "claim_fields": ["blind_run_id", "role", "claim_id", "output_quote", "normalized_proposition",
        "deduplication_key", "actual_input_evidence_or_absent", "input_atom_links", "ledger_atom_links",
        "error_types", "inherited_misinformation", "strict_unsupported", "alternative_unsupported",
        "approval_error", "completion_error", "rationale", "independent_second_judgment", "adjudication"],
    "request_and_echo_units": [],
    "request_and_echo_fields": ["blind_run_id", "role", "unit_id", "output_quote", "independent_answer_target",
        "unit_type_new_information_receipt_request_existing_reask_spontaneous_echo", "deduplication_key",
        "input_evidence", "decomposition_rationale", "ambiguity_or_none"],
    "response_summaries": [],
    "response_summary_fields": ["blind_run_id", "role", "fixed_fact_numerator", "fixed_fact_denominator",
        "fixed_unknown_numerator", "fixed_unknown_denominator", "actual_input_fidelity_numerator",
        "actual_input_fidelity_denominator", "inherited_misinformation_claim_ids", "strict_unsupported_claim_count",
        "alternative_unsupported_claim_count", "approval_errors", "completion_errors",
        "new_information_request_units", "receipt_check_request_units", "spontaneous_receipt_echo_units",
        "reask_existing_information_units", "actual_turn_count", "output_characters", "eligibility"],
    "aggregation_rule": "One response summary per run-role; derive from unique claim/unit IDs, never sum repeated response counts across fixed ledger atom rows."
})
print(json.dumps({"status": "assembled_not_frozen", "scenarios": len(CASES), "sender_packets": 18,
    "receiver_templates": 6, "planned_pairs": len(schedule), "role_calls_executed": 0}, ensure_ascii=False))
