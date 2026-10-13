"""시연용: 검수 대기 현장 카드 초안 1장을 카드 묶음(kb_cards.json)에 넣고, 시연 뒤 원래대로 되돌린다.

정식 검수 화면(MES 운영자 웹 '카드 검수' 탭)이 생기기 전까지 쓰는 도구다. 사람이 초안 내용·겹치는 기존 카드·
빈칸을 보고 직접 승격을 정한다(자동 승격 없음). 승격한 카드는 status=accepted, grade=L1, split=kb가 되어
MES를 다시 띄우면 PDA 질의에 쓰인다. 원래 카드 묶음은 첫 승격 때 한 번만 백업하고, restore가 그대로 되돌린다.

    python scripts/field_card_promote.py list [--server URL]
    python scripts/field_card_promote.py promote K-7000 --yes [--server URL] [--kb PATH | --remote jetson@100.115.59.4] [--force]
    python scripts/field_card_promote.py restore [--kb PATH | --remote jetson@100.115.59.4]

--kb: 이 컴퓨터의 카드 묶음(기본: 저장소 docs/.../kb_cards.json). 로컬 MES는 직접 다시 띄운다.
--remote: Jetson. 카드 묶음을 내려받아 고친 뒤 올리고 MES 서비스만 다시 띄운다(업로더는 그대로).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shiftlink.agent.schemas import KnowledgeCard  # noqa: E402

LOCAL_KB = ROOT / "docs/data/knowledge_cards/kb/kb_cards.json"
REMOTE_KB = "~/shiftlink/app/docs/data/knowledge_cards/kb/kb_cards.json"
BACKUP_SUFFIX = ".before-field-promote"
NOTE = "시연용 승격: 현장 조치 기록 초안을 사람이 확인해 넣음(정식 검수 화면 전). restore로 되돌린다."


def promoted_card(row: dict) -> dict:
    """검수 대기 초안 → 카드 묶음에 넣을 카드. 검수 대기(pending_review)가 아니거나 스키마가 틀리면 거절한다."""
    if row.get("status") != "pending_review":
        raise ValueError(f"{row.get('draft_id')}: 검수 대기 초안만 승격할 수 있습니다(지금 {row.get('status')})")
    card = {**row["card"], "status": "accepted", "grade": "L1", "split": "kb"}
    card["rationale"] = card["rationale"] + "\n" + NOTE
    KnowledgeCard.model_validate(card)
    return card


def add_to_kb(kb: dict, card: dict) -> dict:
    """카드 묶음에 카드 1장을 더한 새 묶음. 같은 card_id가 이미 있으면 거절한다."""
    if any(c["card_id"] == card["card_id"] for c in kb["cards"]):
        raise ValueError(f"{card['card_id']}는 이미 카드 묶음에 있습니다")
    meta = dict(kb.get("_meta") or {})
    meta["field_promoted"] = [*meta.get("field_promoted", []), card["card_id"]]
    return {**kb, "_meta": meta, "cards": [*kb["cards"], card]}


def promote_local(kb_path: Path, card: dict) -> Path:
    """백업(처음 한 번만) → 카드 추가. 백업 경로를 돌려준다."""
    backup = kb_path.with_name(kb_path.name + BACKUP_SUFFIX)
    kb = json.loads(kb_path.read_text(encoding="utf-8"))
    new = add_to_kb(kb, card)
    if not backup.exists():
        shutil.copy2(kb_path, backup)
    kb_path.write_text(json.dumps(new, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    return backup


def restore_local(kb_path: Path) -> bool:
    backup = kb_path.with_name(kb_path.name + BACKUP_SUFFIX)
    if not backup.exists():
        return False
    shutil.copy2(backup, kb_path)
    backup.unlink()
    return True


# ── 원격(Jetson) ──────────────────────────────────────────────────────────
def _ssh(host: str, command: str) -> str:
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, command],
                          check=True, capture_output=True, text=True, timeout=60).stdout


def _restart_remote_mes(host: str) -> None:
    # systemctl restart는 sudo 비밀번호가 필요하다. 서비스가 Restart=always라서 프로세스를 끝내면 새로 뜬다.
    _ssh(host, "kill $(systemctl show -p MainPID --value shiftlink-mes); sleep 12; systemctl is-active shiftlink-mes")


def promote_remote(host: str, card: dict) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / "kb_cards.json"
        subprocess.run(["scp", "-o", "BatchMode=yes", f"{host}:{REMOTE_KB}", str(local)], check=True, timeout=60)
        new = add_to_kb(json.loads(local.read_text(encoding="utf-8")), card)
        local.write_text(json.dumps(new, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        _ssh(host, f"test -f {REMOTE_KB}{BACKUP_SUFFIX} || cp -p {REMOTE_KB} {REMOTE_KB}{BACKUP_SUFFIX}")
        subprocess.run(["scp", "-o", "BatchMode=yes", str(local), f"{host}:{REMOTE_KB}"], check=True, timeout=60)
    _restart_remote_mes(host)


def restore_remote(host: str) -> bool:
    if _ssh(host, f"test -f {REMOTE_KB}{BACKUP_SUFFIX} && echo yes || echo no").strip() != "yes":
        return False
    _ssh(host, f"cp -p {REMOTE_KB}{BACKUP_SUFFIX} {REMOTE_KB} && rm {REMOTE_KB}{BACKUP_SUFFIX}")
    _restart_remote_mes(host)
    return True


# ── 화면 출력 ─────────────────────────────────────────────────────────────
def fetch_drafts(server: str) -> list[dict]:
    with urllib.request.urlopen(server.rstrip("/") + "/api/card-drafts", timeout=20) as res:
        return json.load(res)["drafts"]


def describe(row: dict) -> str:
    card, flags = row["card"], row["review_flags"]
    done = flags.get("completeness", {})
    steps = "\n".join(f"     {s['order']}. {s['action']} → {s['expected_result']}" for s in card["type_payload"]["steps"])
    similar = ", ".join(f"{s['card_id']}({s['title'][:24]})" for s in row.get("similar_kb_cards") or []) or "없음"
    return (f"[{card['card_id']}] {card['title']}  ({row['status']})\n"
            f"   증상: {card['symptom']}\n   부품: {card['component']} · 시나리오 {card['scenario']}\n{steps}\n"
            f"   기록: MES 확인 해결 {done.get('resolved_records', 0)}건, 반대 {done.get('contradicting_records', 0)}건 · "
            f"승격 권장 {'예' if done.get('ready') else '아니오'}\n"
            f"   남은 빈칸: {', '.join(done.get('missing', [])) or '없음'}\n"
            f"   운영자 확인: {', '.join(done.get('operator', [])) or '없음'}\n"
            f"   잠금 응답: {flags.get('lockout_answers') or '없음'}\n"
            f"   겹칠 수 있는 기존 카드: {similar}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list")
    ls.add_argument("--server", default="http://127.0.0.1:8010")
    pr = sub.add_parser("promote")
    pr.add_argument("card_id")
    pr.add_argument("--server", default="http://127.0.0.1:8010")
    pr.add_argument("--kb", type=Path, default=LOCAL_KB)
    pr.add_argument("--remote")
    pr.add_argument("--force", action="store_true", help="승격 권장이 아니어도 넣는다(시연 리허설용)")
    pr.add_argument("--yes", action="store_true", help="확인했음. 없으면 내용만 보여 주고 멈춘다")
    rs = sub.add_parser("restore")
    rs.add_argument("--kb", type=Path, default=LOCAL_KB)
    rs.add_argument("--remote")
    args = parser.parse_args(argv)

    if args.cmd == "list":
        drafts = fetch_drafts(args.server)
        print("\n\n".join(describe(r) for r in drafts) or "검수 대기 초안 없음")
        return 0
    if args.cmd == "restore":
        done = restore_remote(args.remote) if args.remote else restore_local(args.kb)
        print("원래 카드 묶음으로 되돌렸습니다." if done else "되돌릴 백업이 없습니다(승격한 적 없음).")
        if done and not args.remote:
            print("로컬 MES를 다시 띄워야 반영됩니다.")
        return 0

    row = next((r for r in fetch_drafts(args.server) if r["draft_id"] == args.card_id), None)
    if row is None:
        print(f"{args.card_id} 초안이 없습니다 ({args.server})", file=sys.stderr)
        return 1
    print(describe(row))
    ready = row["review_flags"].get("completeness", {}).get("ready")
    if not ready and not args.force:
        print("\n승격 권장이 아닙니다(빈칸 또는 MES 확인 해결 2건 미만, 반대 근거). 시연 리허설이면 --force.", file=sys.stderr)
        return 1
    if not args.yes:
        print("\n위 내용을 확인했으면 --yes를 붙여 다시 실행하세요.")
        return 0
    card = promoted_card(row)
    if args.remote:
        promote_remote(args.remote, card)
        print(f"\n{card['card_id']}를 Jetson 카드 묶음에 넣고 MES를 다시 띄웠습니다. 되돌리기: restore --remote {args.remote}")
    else:
        backup = promote_local(args.kb, card)
        print(f"\n{card['card_id']}를 {args.kb}에 넣었습니다(원본 백업 {backup.name}). 로컬 MES를 다시 띄워야 반영됩니다."
              f"\n되돌리기: restore --kb {args.kb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
