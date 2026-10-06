"""Read-only next-shift list of Aiven `handover_upload`.

    python -m shiftlink.mes.handover_board [--port 8810]

SELECT only. Connection failure shows an offline badge and an empty list.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def _memo(payload) -> tuple[str, dict]:
    if isinstance(payload, str):
        payload = json.loads(payload)
    payload = payload or {}
    return payload.get("memo_text") or "", payload.get("required_context") or {}


def _kst(value) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return (value + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")


def list_uploads(cursor, equipment_id: str | None = None) -> list[dict]:
    """Newest first. `cursor` is a DB-API cursor. Does not write."""
    sql = ("SELECT handover_id, equipment_id, created_at, payload, uploaded_at "
           "FROM handover_upload")
    args: tuple = ()
    if equipment_id:
        sql += " WHERE equipment_id = %s"
        args = (equipment_id,)
    sql += " ORDER BY created_at DESC"
    cursor.execute(sql, args)
    rows = []
    for handover_id, equipment, created_at, payload, uploaded_at in cursor.fetchall():
        memo, context = _memo(payload)
        rows.append({
            "handover_id": handover_id,
            "equipment_id": equipment or "",
            "created_kst": _kst(created_at),
            "uploaded_kst": _kst(uploaded_at),
            "memo_text": memo,
            "first_line": memo.splitlines()[0] if memo else "",
            "required_context": context,
        })
    return rows


def render_page(rows: list[dict], *, offline: bool, equipment_id: str = "") -> str:
    badge = '<p class="badge">오프라인 — 클라우드 인계를 읽을 수 없음</p>' if offline else ""
    items = []
    for row in rows:
        ctx = row["required_context"] or {}
        detail = "".join(
            f"<li>{label}: {ctx.get(key, '')}</li>"
            for label, key in (
                ("받는 사람", "recipient_role"), ("시점", "timing"),
                ("방법", "channel"), ("확인", "acknowledgement"),
            )
        )
        items.append(
            "<article><h2>" + _esc(row["equipment_id"] or "설비 없음") + " · "
            + _esc(row["created_kst"]) + "</h2><p>" + _esc(row["first_line"] or "(메모 없음)")
            + "</p><details><summary>전문</summary><pre>" + _esc(row["memo_text"])
            + "</pre><ul>" + detail + "</ul></details></article>"
        )
    body = "".join(items) or "<p>올라온 인계가 없습니다.</p>"
    filt = _esc(equipment_id)
    return (
        "<!doctype html><meta charset=utf-8><title>다음 조 인계</title>"
        "<style>html,body{background:#fff;color:#111;color-scheme:light}"
        "body{font-family:sans-serif;max-width:40rem;margin:2rem auto}"
        "h1,h2,p,li,summary{color:#111}"
        ".badge{background:#3A0F0D;color:#F3F6F9;padding:.6rem 1rem}"
        "article{border-top:1px solid #ccc;padding:1rem 0}</style>"
        "<h1>다음 조 인계</h1>" + badge
        + f'<form><label>설비 <input name="equipment" value="{filt}"></label>'
        + "<button>필터</button></form>" + body
    )


def _esc(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def page(connect, equipment_id: str = "") -> tuple[int, str]:
    try:
        conn = connect()
    except Exception:  # noqa: BLE001 - offline is a badge, not a crash
        return 200, render_page([], offline=True, equipment_id=equipment_id)
    try:
        with conn.cursor() as cur:
            rows = list_uploads(cur, equipment_id or None)
    except Exception:  # noqa: BLE001
        return 200, render_page([], offline=True, equipment_id=equipment_id)
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
    return 200, render_page(rows, offline=False, equipment_id=equipment_id)


def make_handler(connect):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A002
            return

        def do_GET(self):  # noqa: N802
            path, _, query = self.path.partition("?")
            if path != "/":
                self.send_error(404)
                return
            equipment = ""
            for part in query.split("&"):
                if part.startswith("equipment="):
                    equipment = part.split("=", 1)[1]
            status, html = page(connect, equipment)
            data = html.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    return Handler


def main() -> None:
    import sys
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from db.apply_schema import connect

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8810)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(connect))
    print(f"next-shift handovers: http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
