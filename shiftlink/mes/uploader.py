"""Upload pending PDA handovers and query logs from local SQLite to Aiven `handover_upload` / `query_upload`.

    python -m shiftlink.mes.uploader [--db mes_data/mock-mes.sqlite3] [--interval 30] [--once]

Offline is normal: a failed connection leaves rows pending and the next cycle retries.
Same ID + same hash on the cloud -> 'uploaded' (retry after a lost ack). Different hash -> 'conflict', held locally.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .storage import MesStorage

# (local rows, mark, cloud table, key column, extra columns from payload)
def _specs(storage: MesStorage):
    return [
        (storage.pending_handovers, storage.mark_handover, "handover_upload", "handover_id", ("equipment_id",)),
        (storage.pending_queries, storage.mark_query, "query_upload", "query_id", ("equipment_id", "latency_ms", "no_knowledge")),
    ]


def upload_pending(storage: MesStorage, connect) -> dict[str, int]:
    """One cycle. `connect()` returns a DB-API connection (autocommit). Network errors end the cycle quietly."""
    specs = _specs(storage)
    counts = {"uploaded": 0, "conflict": 0, "pending": sum(len(rows()) for rows, *_ in specs)}
    if not counts["pending"]:
        return counts
    try:
        conn = connect()
    except Exception:  # noqa: BLE001 - any connect failure means "offline, retry later"
        return counts
    try:
        with conn.cursor() as cur:
            for rows, mark, table, key, extra in specs:
                cols = ", ".join((key, *extra, "created_at", "payload", "content_sha256", "is_synthetic"))
                insert = f"INSERT IGNORE INTO {table} ({cols}) VALUES ({', '.join(['%s'] * (len(extra) + 4))}, TRUE)"
                for row_id, created_at, payload in rows():
                    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
                    utc = datetime.fromisoformat(created_at).astimezone(timezone.utc).replace(tzinfo=None)
                    body = json.loads(payload)
                    cur.execute(insert, (row_id, *(body.get(c) for c in extra), utc, payload, digest))
                    if not cur.rowcount:
                        cur.execute(f"SELECT content_sha256 FROM {table} WHERE {key} = %s", (row_id,))
                        found = cur.fetchone()
                        status = "uploaded" if found and found[0] == digest else "conflict"
                    else:
                        status = "uploaded"
                    mark(row_id, status)
                    counts[status] += 1
                    counts["pending"] -= 1
    except Exception:  # noqa: BLE001 - dropped mid-cycle: rows not yet marked stay pending
        pass
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
    return counts


def main() -> None:
    import sys
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from db.apply_schema import connect  # reads MYSQL_DATABASE_URL / MYSQL_SSL_CA from .env

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=root / "mes_data" / "mock-mes.sqlite3")
    parser.add_argument("--interval", type=float, default=30)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    storage = MesStorage(args.db)
    while True:
        print(json.dumps(upload_pending(storage, connect)), flush=True)
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
