"""questions_raw + labels -> qa_dev.json(30) / qa_test.json(30) / reserve.json(10) / review.md. Same seed -> same bytes."""
import json
import random
from collections import defaultdict
from pathlib import Path

SEED = 20260929
N_PER_SPLIT = 30
HERE = Path(__file__).parent
ROOT = HERE.parents[2]
CARDS = ROOT / "docs/data/knowledge_cards/kb/20260929-A/cards.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def main():
    questions = load(HERE / "questions_raw.json")
    labels = {x["qid"]: x for x in load(HERE / "labels.json")}
    assert len(questions) == len(labels), "every question needs a label"
    items = [{**q, **{k: v for k, v in labels[q["qid"]].items() if k != "qid"}} for q in questions]

    # KB covers ~1/3 of blind questions (9/30), so drop only unanswerable ones to reach 60.
    # ponytail: selection uses today's labels; after card batch B, relabel in place (keep split) instead of rerunning.
    rng = random.Random(SEED)
    no = sorted((x for x in items if not x["answerable"]), key=lambda x: x["qid"])
    rng.shuffle(no)
    dropped = {x["qid"] for x in no[:len(items) - 2 * N_PER_SPLIT]}
    selected = [x for x in items if x["qid"] not in dropped]
    reserve = [x for x in items if x["qid"] in dropped]

    # Stratify by (answerable, equipment); inside a stratum order by difficulty, then deal alternately
    # so both splits match on citation vs "모름", equipment, and difficulty.
    strata = defaultdict(list)
    for x in sorted(selected, key=lambda x: x["qid"]):
        strata[(x["answerable"], x["eq_id"])].append(x)
    dev, test, turn = [], [], 0
    for key in sorted(strata):
        group = strata[key]
        rng.shuffle(group)
        group.sort(key=lambda x: ("easy", "medium", "hard").index(x["difficulty"]))  # stable: shuffle breaks ties
        for x in group:
            (dev if turn % 2 == 0 else test).append(x)
            turn += 1
    for name, rows in (("dev", dev), ("test", test)):
        for x in rows:
            x["split"] = name
    by_qid = lambda rows: sorted(rows, key=lambda x: x["qid"])  # noqa: E731
    dump(HERE / "qa_dev.json", by_qid(dev))
    dump(HERE / "qa_test.json", by_qid(test))
    dump(HERE / "reserve.json", by_qid(reserve))
    write_review(by_qid(test) + by_qid(dev))  # test first: 전혜민 reviews test formally
    print(f"dev={len(dev)} test={len(test)} reserve={len(reserve)} "
          f"unanswerable dev={sum(not x['answerable'] for x in dev)} test={sum(not x['answerable'] for x in test)}")


def write_review(rows):
    cards = {c["card_id"]: c for c in load(CARDS)}
    title = lambda cid: f"{cid} {cards[cid]['title']}"  # noqa: E731
    out = ["# 평가셋 검수표 (eval/qa/20260929)", "",
           "문항마다 **판정** 칸에 `채택` / `수정: 내용` / `제외: 이유` 중 하나를 적는다. 질문 문구는 고치지 않는다(문제 있으면 제외).",
           f"**평가용(test) {sum(r['split'] == 'test' for r in rows)}건 — 전혜민 정식 검수**, 이어서 개발용(dev) {sum(r['split'] == 'dev' for r in rows)}건 — 최재영 가벼운 확인. 예비 문항은 `reserve.json`.", ""]
    for r in rows:
        out += [f"## {r['qid']} · {r['split']} · {r['eq_id']} · {r['intent']} · {r['persona_id']} · {r['difficulty']}", "",
                f"> {r['question']}", ""]
        if r["observations"]:
            out.append(f"- 관측값: `{json.dumps(r['observations'], ensure_ascii=False)}`")
        out.append(f"- 답 있음: {'예' if r['answerable'] else '아니오 (모름 처리 기대)'}")
        for key, label in (("primary_card_ids", "정답 카드"), ("acceptable_card_ids", "보조 카드"), ("safety_card_ids", "필수 안전 카드")):
            if r[key]:
                out.append(f"- {label}: " + "; ".join(title(c) for c in r[key]))
        if r["key_facts"]:
            out.append("- 핵심 사실: " + " / ".join(r["key_facts"]))
        out += [f"- 라벨 근거: {r['label_note']}", "- **판정**: ", ""]
    (HERE / "review.md").write_text("\n".join(out), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
