"""Prepare exact role packets and audit manually orchestrated fresh-agent calls."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import sys

HERE = Path(__file__).resolve().parent
CONDITIONS = ("none", "checklist", "equipment_card")


def read(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def save(name, obj):
    (HERE / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(name):
    return hashlib.sha256((HERE / name).read_bytes()).hexdigest()


def freeze():
    if (HERE / "pilot-inputs.json").exists():
        raise ValueError("Frozen inputs already exist; preserve them rather than overwrite an experiment.")
    cases = read("pilot-cases.json")["cases"]
    selected = {"P-HPU": "HPU-01", "P-GR": "GR-03", "P-RT": "RT-01", "P-CV": "CV-01"}
    maps = {m["method_key"]: m for m in read("equipment-map.json")["cards"]}
    cards = {c["card_id"]: c for c in read("cards.json")}
    instructions = (
        "당신은 합성 인계 실험의 송신자입니다. 이 메시지만 사용하고 파일·도구·웹·다른 에이전트에 접근하지 마세요. "
        "아래 네 항목을 서로 독립적인 상황으로 처리하세요. 각 항목의 persona와 sender_facts만 사건 정보이며 "
        "support가 있으면 재사용 방법으로 활용하세요. support의 예시·장비 목록을 새 관측 사실로 바꾸지 마세요. "
        "다음 조 담당자에게 보낼 인계 메시지를 각 900자 이내로 작성하세요. 출력은 JSON 객체 하나: "
        '{"additional_tool_access_used":false,"results":[{"case_id":"...","message":"..."},...]}. '
        "설명이나 코드블록은 쓰지 마세요."
    )
    packets = {}
    for condition in CONDITIONS:
        items = []
        for case in cases:
            support = None
            if condition == "checklist":
                support = "일반 인계 체크리스트: 필요한 맥락과 정보(required_context), 받을 역할(recipient_role), 전달 시점(timing), 전달 채널(channel), 수신 확인 방법(acknowledgement)을 포함해 인계한다."
            elif condition == "equipment_card":
                c = cards[maps[selected[case["case_id"]]]["card_id"]]
                support = {k: c[k] for k in ("card_id", "version", "title", "equipment", "know_how", "type_payload")}
            items.append({"case_id": case["case_id"], "persona": case["persona"], "sender_facts": case["sender_facts"], "support": support})
        packets[condition] = instructions + "\n" + json.dumps(items, ensure_ascii=False, indent=2)
        (HERE / f"pilot-sender-{condition}.txt").write_text(packets[condition], encoding="utf-8")
    save("pilot-inputs.json", {"frozen_at": datetime.now(timezone.utc).isoformat(),
                              "protocol_sha256": sha("pilot-protocol.md"), "cases_sha256": sha("pilot-cases.json"),
                              "cards_sha256": sha("cards.json"), "selected_method_keys": selected,
                              "selected_cards": {cid: cards[maps[key]["card_id"]] for cid, key in selected.items()},
                              "sender_prompts": packets,
                              "context_isolation": "fork_turns=none, no model override, one read of own role-only packet allowed; further tools prohibited; not OS isolation"})
    print("Frozen sender inputs for 4 cases x 3 conditions.")


def receivers():
    senders = read("pilot-senders.json")
    inputs = read("pilot-inputs.json")
    assert inputs["protocol_sha256"] == sha("pilot-protocol.md")
    assert inputs["cases_sha256"] == sha("pilot-cases.json")
    cases = {c["case_id"]: c for c in read("pilot-cases.json")["cases"]}
    instructions = (
        "당신은 합성 인계 실험의 수신자입니다. 이 메시지만 사용하고 파일·도구·웹·다른 에이전트에 접근하지 마세요. "
        "아래 네 항목을 서로 독립적인 상황으로 처리하세요. initial과 received_message만 이용하여 인수 내용을 작성하세요. "
        "전달되지 않은 설비 사실·승인·결과를 추정하지 마세요. 각 항목의 response는 1600자 이내여야 합니다. "
        "response에는 받은 사실, 미확인 항목, 대상별 수신 상태, 필요한 후속 질문, 승인 해석을 포함하세요. "
        '출력은 JSON 객체 하나: {"additional_tool_access_used":false,"results":[{"case_id":"...","response":"..."},...]}. '
        "설명이나 코드블록은 쓰지 마세요."
    )
    prompts = {}
    for condition in CONDITIONS:
        result = senders[condition]
        assert result["additional_tool_access_used"] is False
        assert {r["case_id"] for r in result["results"]} == set(cases)
        items = [{"case_id": r["case_id"], "initial": cases[r["case_id"]]["receiver_initial"],
                  "received_message": r["message"]} for r in result["results"]]
        prompts[condition] = instructions + "\n" + json.dumps(items, ensure_ascii=False, indent=2)
        (HERE / f"pilot-receiver-{condition}.txt").write_text(prompts[condition], encoding="utf-8")
    save("pilot-receiver-inputs.json", {"sender_outputs_sha256": sha("pilot-senders.json"), "receiver_prompts": prompts})
    print("Prepared receiver inputs from actual sender outputs only.")


def audit():
    inputs = read("pilot-inputs.json")
    senders, receivers_out = read("pilot-senders.json"), read("pilot-receivers.json")
    receiver_inputs = read("pilot-receiver-inputs.json")
    assert inputs["protocol_sha256"] == sha("pilot-protocol.md")
    assert inputs["cases_sha256"] == sha("pilot-cases.json")
    assert receiver_inputs["sender_outputs_sha256"] == sha("pilot-senders.json")
    cases = read("pilot-cases.json")["cases"]
    findings, lengths = [], []
    for condition in CONDITIONS:
        assert senders[condition]["additional_tool_access_used"] is False
        assert receivers_out[condition]["additional_tool_access_used"] is False
        assert len(senders[condition]["results"]) == len(receivers_out[condition]["results"]) == len(cases)
        assert {r["case_id"] for r in senders[condition]["results"]} == {c["case_id"] for c in cases}
        assert {r["case_id"] for r in receivers_out[condition]["results"]} == {c["case_id"] for c in cases}
        prompt = inputs["sender_prompts"][condition]
        receiver_prompt = receiver_inputs["receiver_prompts"][condition]
        assert (HERE / f"pilot-sender-{condition}.txt").read_text(encoding="utf-8") == prompt
        assert (HERE / f"pilot-receiver-{condition}.txt").read_text(encoding="utf-8") == receiver_prompt
        for forbidden in ("judge_only_hidden", "required_facts", "required_unknowns", "expected_receipt", "HX-491", "GX-862", "RX-375", "CX-946"):
            assert forbidden not in prompt and forbidden not in receiver_prompt
        for role, rows, field, limit in (("sender", senders[condition]["results"], "message", 900),
                                         ("receiver", receivers_out[condition]["results"], "response", 1600)):
            for row in rows:
                n = len(row[field])
                lengths.append({"condition": condition, "case_id": row["case_id"], "role": role, "characters": n, "requested_limit": limit})
                if n > limit:
                    findings.append({"condition": condition, "case_id": row["case_id"], "issue": "requested length exceeded", "role": role})
                for hidden in ("HX-491", "GX-862", "RX-375", "CX-946"):
                    assert hidden not in row[field]
    files = ["pilot-protocol.md", "pilot-cases.json", "pilot-inputs.json", "pilot-senders.json", "pilot-receiver-inputs.json", "pilot-receivers.json"]
    hashes = {name: sha(name) for name in files}
    prior = read("pilot-audit.json") if (HERE / "pilot-audit.json").exists() else {}
    checked_at = prior["checked_at"] if prior.get("input_hashes") == hashes else datetime.now(timezone.utc).isoformat()
    save("pilot-audit.json", {"checked_at": checked_at, "role_calls": 6, "paired_situations": 4,
                              "condition_results": 12, "forbidden_oracle_keys_in_prompts": 0, "hidden_canary_output_hits": 0,
                              "tool_access": "One bootstrap read of own role packet permitted. All roles self-report no additional access; no security sandbox claim.", "length_checks": lengths,
                              "findings": findings, "input_hashes": hashes,
                              "semantic_leakage_evaluation": "See independent pilot-judgment.json; canary checks alone are not leakage proof."})
    print(json.dumps({"role_calls": 6, "condition_results": 12, "findings": findings}, ensure_ascii=False))


if __name__ == "__main__":
    {"freeze": freeze, "receivers": receivers, "audit": audit}[sys.argv[1]]()
