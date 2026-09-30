"""prompts/index.json 생성. 지시문 파일을 LF로 정규화한 뒤 sha256을 기록한다.

카드를 만든 뒤 다시 돌리면 cards.json에서 card_ids를 읽어 채운다. 줄바꿈을 먼저
정규화하는 이유는 CRLF로 저장된 파일이 LF 체크아웃과 다른 해시를 내기 때문이다
(provenance.prompt_version이 가리키는 값이 PC마다 달라지면 추적이 끊긴다).
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
BATCH = "KB-20260930-T4"
SEED = 20260930
MODEL = "claude-opus-5[1m]"
KST = timezone(timedelta(hours=9))

SOURCE_INSTRUCTION = Path("docs/collaboration/t4-handover-cards-prompt-20260930.md")
ASSIGNMENT = Path("docs/collaboration/t4-handover-cards-assignment-20260930.md")

STAGES = {
    "stage-a-records": {"outputs": ["events.json", "artifacts.json"]},
    "stage-b-cards": {"outputs": ["cards.json"]},
}


def normalize_lf(path: Path) -> bytes:
    """CRLF/CR을 LF로 바꿔 저장하고 정규화된 바이트를 돌려준다."""
    raw = path.read_bytes()
    lf = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if lf != raw:
        path.write_bytes(lf)
    return lf


def sha256_of(path: Path, normalize: bool) -> str:
    data = normalize_lf(path) if normalize else path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    # prompts -> 20260930-T4 -> kb -> knowledge_cards -> data -> docs -> 저장소 루트
    repo_root = HERE.parents[5]
    run_at = datetime.now(KST).isoformat(timespec="seconds")

    prompts = {}
    for name, meta in STAGES.items():
        p = HERE / f"{name}.md"
        prompts[name] = {
            "path": str((HERE / f"{name}.md").relative_to(repo_root)).replace("\\", "/"),
            "sha256": sha256_of(p, normalize=True),
            "model": MODEL,
            "run_at": run_at,
            "outputs": meta["outputs"],
        }

    cards_path = HERE.parent / "cards.json"
    if cards_path.exists():
        cards = json.loads(cards_path.read_text(encoding="utf-8"))
        prompts["stage-b-cards"]["card_ids"] = [c["card_id"] for c in cards]

    out = {
        "batch_id": BATCH,
        "seed": SEED,
        "source_instruction": {
            "path": str(SOURCE_INSTRUCTION).replace("\\", "/"),
            "sha256": sha256_of(repo_root / SOURCE_INSTRUCTION, normalize=False),
        },
        "assignment": {
            "path": str(ASSIGNMENT).replace("\\", "/"),
            "sha256": sha256_of(repo_root / ASSIGNMENT, normalize=False),
        },
        "prompts": prompts,
    }
    # 줄바꿈은 LF로 고정한다(해시 대상 파일과 같은 기준, git 저장본과도 일치).
    (HERE / "index.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    for name, meta in prompts.items():
        print(f'{name}: {meta["sha256"]}')
    print(f'source_instruction: {out["source_instruction"]["sha256"]}')
    if "card_ids" in prompts["stage-b-cards"]:
        print(f'card_ids: {len(prompts["stage-b-cards"]["card_ids"])}장')
    else:
        print("card_ids: cards.json 아직 없음 — 카드 생성 후 재실행")


if __name__ == "__main__":
    main()
