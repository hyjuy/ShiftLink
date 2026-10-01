"""Render a markdown review sheet from a score.py result JSON and a QA file.

    python eval/qa/report.py eval/results/qa_20260929/qa_dev.json eval/qa/20260929/qa_dev.json \
        --out eval/results/qa_20260929/qa_dev.md

Wrong items (not hit, not abstain_ok) come first. Key facts and fabrication stay blank for a person.
Handover-mode results (score.py --mode handover) also show the rendered handover method and a blank for it.
"""
import argparse
import json
from pathlib import Path

OK = ("hit", "abstain_ok")


def verdict(score: dict) -> str:
    """Automatic label: hit, partial, abstain_ok, or miss."""
    if score.get('evaluation_deferred'):
        return 'deferred'
    if score.get("hit"):
        return "hit"
    if score.get("partial"):
        return "partial"
    if score.get("abstain_ok"):
        return "abstain_ok"
    return "miss"


def render_report(result: dict, items: list[dict]) -> str:
    """Markdown review sheet. `items` is qa_dev.json or qa_test.json."""
    by_qid = {item["qid"]: item for item in items}
    missing = [row["qid"] for row in result["rows"] if row["qid"] not in by_qid]
    if missing:
        raise ValueError(f"문항에 없는 qid: {', '.join(missing)}")

    ranked = []
    for row in result["rows"]:
        label = verdict(row["score"])
        ranked.append((0 if label not in OK else 1, row["qid"], row, by_qid[row["qid"]], label))
    ranked.sort(key=lambda item: (item[0], item[1]))

    title = "# QA 검수표 (인계 모드)" if result.get("mode") == "handover" else "# QA 검수표"
    lines = [title, "", _summary_table(result.get("summary") or {}), ""]
    for _, _, row, item, label in ranked:
        lines.extend(_question(row, item, label))
    return "\n".join(lines).rstrip() + "\n"


def _summary_table(summary: dict) -> str:
    labels = [
        ("n", "문항"),
        ("evaluated", "평가 대상"),
        ("deferred", "평가 보류"),
        ("retrieval_rank1_answerable_n", "검색 1위 평가 가능한 답 있음 문항"),
        ("answerable", "답 있음"),
        ("unanswerable", "답 없음"),
        ("citation_hit", "인용 적중"),
        ("citation_partial", "부분 인용"),
        ("retrieval_hit_at_1", "검색 1위 적중"),
        ("retrieval_hit_at_k", "검색 상위 적중"),
        ("wrong_cite_rate", "오인용 비율"),
        ("safety_ok", "안전 카드"),
        ("abstain_ok", "모름 처리"),
        ("review_queue", "review_queue"),
        ("errors", "오류"),
        ("cold_s", "cold_s"),
        ("p50_s", "p50_s"),
        ("p95_s", "p95_s"),
    ]
    rows = ["| 항목 | 값 |", "|---|---|"]
    for key, name in labels:
        if key in summary:
            rows.append(f"| {name} | {summary[key]} |")
    return "\n".join(rows)


def _question(row: dict, item: dict, label: str) -> list[str]:
    top3 = row.get("ranked") or []
    top3 = top3[:3]
    handover = _handover(row["handover_method"]) if "handover_method" in row else []
    return [
        f"## {row['qid']} · {row['eq_id']} · {label}",
        "",
        "| 항목 | 내용 |",
        "|---|---|",
        f"| qid | {row['qid']} |",
        f"| 설비 | {row['eq_id']} |",
        f"| 질문 | {_cell(item['question'])} |",
        f"| 기대 정답 카드 | primary: {_ids(item['primary_card_ids'])} / acceptable: {_ids(item['acceptable_card_ids'])} |",
        *([f"| 완전 정답 조합 | {' 또는 '.join(' + '.join(group) for group in item['primary_card_sets'])} |"] if item.get('primary_card_sets') else []),
        *([f"| 평가 보류 사유 | {_cell(item['defer_reason'])} |"] if item.get('defer_reason') else []),
        *([f"| 확인할 핵심 사실 | {_cell('; '.join(item['key_facts']))} |"] if item.get('key_facts') else []),
        *([f"| 라벨 판단 근거 | {_cell(item['label_note'])} |"] if item.get('label_note') else []),
        f"| 실제 인용 | {_ids(row.get('cited') or [])} |",
        f"| 검색 상위 3 | {_ids(top3)} |",
        f"| 표시된 안전 카드 | {_ids(row.get('safety') or [])} |",
        f"| 자동 판정 | {label} |",
        "",
        "### 답변 원문",
        "",
        "```text",
        row.get("answer") or "",
        "```",
        "",
        *handover,
        "### 사람 판정",
        "",
        "- 핵심 사실: [ ] 전부  [ ] 일부  [ ] 없음",
        "- 지어낸 내용: [ ] 있음  [ ] 없음",
        *(["- 인계 항목: [ ] 메모 상황에 맞음  [ ] 일부  [ ] 안 맞음"] if handover else []),
        "",
    ]


def _handover(method: dict | None) -> list[str]:
    """Rendered T4 handover method for handover-mode rows."""
    lines = ["### 인계 항목", ""]
    if not method:
        return lines + ["없음", ""]
    return lines + [
        "| 항목 | 내용 |",
        "|---|---|",
        f"| 전달 정보 | {_cell('; '.join(method.get('required_context') or [])) or '없음'} |",
        f"| 대상 | {_cell(method.get('recipient_role') or '')} |",
        f"| 시점 | {_cell(method.get('timing') or '')} |",
        f"| 방법 | {_cell(method.get('channel') or '')} |",
        f"| 확인 | {_cell(method.get('acknowledgement') or '')} |",
        "",
    ]


def _ids(values: list) -> str:
    return ", ".join(values) if values else "없음"


def _cell(text: str) -> str:
    return " ".join(text.split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("result_json")
    ap.add_argument("qa_file")
    ap.add_argument("--out")
    args = ap.parse_args()
    result = json.loads(Path(args.result_json).read_text(encoding="utf-8"))
    items = json.loads(Path(args.qa_file).read_text(encoding="utf-8"))
    text = render_report(result, items)
    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
