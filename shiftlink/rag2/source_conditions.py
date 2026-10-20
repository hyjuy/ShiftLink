"""Opt-in R5 condition rendering; not a safety validator or work authorization."""

VERSION = "1.1-safety-20261020"
NOTICE = "【확인·대응 안내 — 실제 작업에는 위 조건 적용, 조건 충족을 확인한 답변은 아님】"


def with_source_conditions(answer: str, valid_cites: list[str], evidence: list[dict], cards: list[dict]) -> tuple[str, list[str]]:
    """Keep the checked answer intact, prepending conditions only from a cited, matching card chunk."""
    by_id = {c["card_id"]: c for c in cards}
    blocks, applied = [], []
    # shortcut: only the two R5-reviewed cards/revision; other cards need their own source review.
    for i, row in enumerate(evidence, 1):
        sid = f"S{i}"
        meta = row.get("metadata", {})
        cid = meta.get("source")
        if not answer or sid not in valid_cites or meta.get("kind") != "card" or cid in applied:
            continue
        card = by_id.get(cid, {})
        if card.get("version") != VERSION or row.get("chunk_id") != f"card_{cid}":
            continue
        text = card.get("know_how", "")
        if cid == "K-1012":
            start = "해당 직접구동형"
            _, found, tail = text.partition(start)
            quote = found + tail
            required = ("MISUMI", "지정 장력 조정 나사", "확인되지 않으면", "정비 담당자")
            work = "운전 중 벨트 보정"
        elif cid == "K-1027":
            _, found, tail = text.partition("2) 아래 3)–5)의 ")
            quote, end, _ = tail.partition("3) 커버")
            if not end:
                continue
            quote = quote.strip()
            required = ("모터 전원을 차단", "재기동을 막은 뒤", "감속기가 식은", "작업 승인")
            work = "볼트 조임·벤트·유면 교정·브리더 재장착"
        else:
            continue
        if not found or not quote or not all(t in quote for t in required) or quote not in row.get("text", ""):
            continue  # stale/mismatched data is not silently combined with a different revision's conditions
        blocks.append(f"【아래 답변의 {work}에 적용되는 수행 조건】\n{quote} [{sid}]")
        applied.append(cid)
    return ("\n\n".join([*blocks, NOTICE + "\n" + answer]), applied) if blocks else (answer, [])
