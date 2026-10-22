"""symptom_concepts.json 검증 (표준 라이브러리만 사용).

실행: python docs/demo/kg/symptoms/check_symptoms.py
입력은 읽기만 하며 실행 전후 해시를 대조한다. 오류가 있으면 비정상 종료한다.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
KB = ROOT / "docs/data/knowledge_cards/kb/kb_cards.json"
CONCEPTS = HERE / "symptom_concepts.json"
KB_SHA = "05cfc4e79a3087e3544fc01e6b830268b542f55ae3be31bd6ad7601fc1d6dd3a"
SLUG = re.compile(r"^sym:[a-z0-9]+(?:-[a-z0-9]+)*$")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(cards, data):
    """cards: KB 카드 목록, data: 매핑 객체. 위반 메시지 목록을 반환한다."""
    err = []
    if set(data) != {"concepts", "card_map", "needs_review"}:
        return [f"최상위 키 불일치: {sorted(data)}"]
    ids = [c["card_id"] for c in cards]
    by_id = {c["card_id"]: c for c in cards}
    concepts = data["concepts"]
    cids = [c.get("id") for c in concepts]
    if len(set(cids)) != len(cids):
        err.append("concepts ID 중복")
    for c in concepts:
        if not SLUG.match(str(c.get("id"))):
            err.append(f"개념 ID 형식 오류: {c.get('id')}")
        if not str(c.get("label", "")).strip() or not str(c.get("definition", "")).strip():
            err.append(f"label/definition 비어 있음: {c.get('id')}")
        if set(c) != {"id", "label", "definition"}:
            err.append(f"개념 필드 불일치: {c.get('id')}")
    cmap = data["card_map"]
    if set(cmap) != set(ids):
        err.append(f"card_map 카드 집합 불일치: 누락 {sorted(set(ids) - set(cmap))} 초과 {sorted(set(cmap) - set(ids))}")
    used = set()
    for cid, refs in cmap.items():
        if len(set(refs)) != len(refs):
            err.append(f"{cid}: 개념 중복")
        for r in refs:
            if r not in cids:
                err.append(f"{cid}: 미정의 개념 {r}")
            used.add(r)
        card = by_id.get(cid)
        if card and refs and (card["safety_flag"] or card["symptom"] is None):
            err.append(f"{cid}: 안전/null 카드는 연결 금지")
    if set(cids) - used:
        err.append(f"참조되지 않는 개념: {sorted(set(cids) - used)}")
    nr = [n.get("card_id") for n in data["needs_review"]]
    if len(nr) != len(set(nr)) or set(nr) != set(ids):
        err.append("needs_review 카드 집합 불일치 또는 중복")
    if any(not str(n.get("reason", "")).strip() for n in data["needs_review"]):
        err.append("needs_review reason 비어 있음")
    return err


def counts(cards, data):
    held = [c for c in cards if c["safety_flag"] or c["symptom"] is None]
    rest = [c for c in cards if c not in held]
    linked = [c for c in rest if data["card_map"][c["card_id"]]]
    return len(cards), sum(c["safety_flag"] for c in cards), sum(c["symptom"] is None for c in cards), len(held), len(rest), len(linked)


def _selfcheck():
    cards = [
        {"card_id": "A", "safety_flag": False, "symptom": "x"},
        {"card_id": "S", "safety_flag": True, "symptom": "y"},
        {"card_id": "N", "safety_flag": False, "symptom": None},
    ]
    good = {
        "concepts": [{"id": "sym:a-b", "label": "l", "definition": "d"}],
        "card_map": {"A": ["sym:a-b"], "S": [], "N": []},
        "needs_review": [{"card_id": i, "reason": "r"} for i in "ASN"],
    }
    assert validate(cards, good) == []
    bad = json.loads(json.dumps(good))
    bad["card_map"]["S"] = ["sym:a-b"]
    assert any("안전/null" in e for e in validate(cards, bad))
    bad = json.loads(json.dumps(good))
    bad["card_map"]["N"] = ["sym:a-b"]
    assert any("안전/null" in e for e in validate(cards, bad))
    bad = json.loads(json.dumps(good))
    bad["card_map"]["A"] = ["sym:none"]
    assert any("미정의" in e for e in validate(cards, bad))
    bad = json.loads(json.dumps(good))
    del bad["card_map"]["A"]
    assert any("카드 집합" in e for e in validate(cards, bad))
    bad = json.loads(json.dumps(good))
    bad["needs_review"][0]["reason"] = " "
    assert any("reason" in e for e in validate(cards, bad))


def main():
    _selfcheck()
    before = sha(KB)
    assert before == KB_SHA, f"KB 해시 불일치: {before}"
    cards = json.loads(KB.read_text(encoding="utf-8"))["cards"]
    data = json.loads(CONCEPTS.read_text(encoding="utf-8"))
    err = validate(cards, data)
    assert sha(KB) == before, "KB가 실행 중 변경됨"
    total, safe, null, held, rest, linked = counts(cards, data)
    print(f"cards={total} safety={safe} null={null} held_union={held} non_safety_string={rest} linked={linked} unlinked={rest - linked} concepts={len(data['concepts'])}")
    assert (total, safe, null, held, rest) == (86, 56, 13, 58, 28), "원본 집계가 계약과 다름"
    for e in err:
        print("ERROR:", e)
    print("ok" if not err else "failed")
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main())
