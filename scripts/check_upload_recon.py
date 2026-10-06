"""Reconcile the local handover outbox with Aiven `handover_upload` (W3-3 evidence).

    python scripts/check_upload_recon.py [--db mes_data/mock-mes.sqlite3] [--prefix HO-recon-]

Prints counts and IDs only (no memo text, no secrets). Exit 0 = nothing missing, no conflict, nothing pending;
1 = a mismatch; 2 = cloud unreachable (local counts are still printed, e.g. while the cable is out).
"""
import argparse
import hashlib
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def read_local(conn, prefix=""):
    """{handover_id: (status, sha256 of payload)} — the same digest the uploader sends."""
    return {i: (st, hashlib.sha256(p.encode("utf-8")).hexdigest())
            for i, st, p in conn.execute("SELECT handover_id, status, payload FROM handover_outbox") if i.startswith(prefix)}


def read_cloud(connect, prefix=""):
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT handover_id, content_sha256 FROM handover_upload WHERE handover_id LIKE %s", (prefix + "%",))
            return dict(cur.fetchall())
    finally:
        conn.close()


def reconcile(local, cloud):
    """cloud may be None (unreachable). Same ID + same hash = ok; ID is the cloud PK so a duplicate can only be a hash conflict."""
    pending = sorted(i for i, (st, _) in local.items() if st == "pending")
    out = {"local": len(local), "pending": pending, "cloud_reachable": cloud is not None}
    if cloud is not None:
        out["cloud_matching"] = sum(1 for i in local if i in cloud)
        out["missing"] = sorted(i for i in local if i not in cloud)  # includes rows marked 'uploaded' that the cloud lacks
        out["conflict"] = sorted(i for i, (_, sha) in local.items() if i in cloud and cloud[i] != sha)
        out["cloud_only"] = len(set(cloud) - set(local))
    return out


def ok(r):
    return r["cloud_reachable"] and not (r["missing"] or r["conflict"] or r["pending"])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=ROOT / "mes_data" / "mock-mes.sqlite3")
    parser.add_argument("--prefix", default="", help="limit to handover IDs starting with this (e.g. HO-recon-)")
    args = parser.parse_args()
    local = read_local(sqlite3.connect(f"{args.db.resolve().as_uri()}?mode=ro", uri=True), args.prefix)
    try:
        from db.apply_schema import connect
        cloud = read_cloud(connect, args.prefix)
    except Exception as error:  # noqa: BLE001 - any failure = unreachable; class name only, messages may carry the host
        print(f"cloud unreachable ({type(error).__name__})")
        cloud = None
    r = reconcile(local, cloud)
    print(f"local {r['local']} | pending {len(r['pending'])} {r['pending']}")
    if cloud is None:
        sys.exit(2)
    print(f"cloud matching {r['cloud_matching']} | missing {len(r['missing'])} {r['missing']} | "
          f"conflict {len(r['conflict'])} {r['conflict']} | cloud-only {r['cloud_only']}")
    print("RESULT: OK (missing 0, conflict 0, pending 0)" if ok(r) else "RESULT: MISMATCH")
    sys.exit(0 if ok(r) else 1)


if __name__ == "__main__":
    main()
