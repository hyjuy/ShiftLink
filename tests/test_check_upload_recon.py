import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_upload_recon import ok, read_cloud, read_local, reconcile  # noqa: E402
from shiftlink.mes.storage import MesStorage  # noqa: E402
from shiftlink.mes.uploader import upload_pending  # noqa: E402


class FakeCloud:
    """handover_upload as {id: sha}; online False = cable out."""

    def __init__(self):
        self.rows, self.online = {}, True

    def connect(self):
        if not self.online:
            raise OSError("network unreachable")
        cloud = self

        class Cursor:
            rowcount = 0

            def __enter__(self): return self
            def __exit__(self, *exc): return False

            def execute(self, sql, args):
                if sql.startswith("INSERT IGNORE"):
                    self.rowcount = int(args[0] not in cloud.rows)
                    cloud.rows.setdefault(args[0], args[-1])
                elif "WHERE handover_id = " in sql:
                    self.found = [(cloud.rows.get(args[0]),)]
                else:  # recon: LIKE prefix
                    self.found = [(i, s) for i, s in cloud.rows.items() if i.startswith(args[0][:-1])]

            def fetchone(self): return self.found[0]
            def fetchall(self): return self.found

        class Conn:
            def cursor(self): return Cursor()
            def close(self): pass

        return Conn()


def _note(i):
    return {"handover_id": f"HO-recon-{i}", "memo_text": f"[시험] {i}", "equipment_id": "HPU-01"}


def test_cable_out_then_recovered_ends_with_missing_0_conflict_0():
    storage, cloud = MesStorage(), FakeCloud()
    storage.save_handover(_note(1)); storage.save_handover(_note(2))
    cloud.online = False
    upload_pending(storage, cloud.connect)  # cable out: nothing leaves, rows stay pending
    out = reconcile(read_local(storage.connection, "HO-recon-"), None)
    assert (out["local"], out["pending"], out["cloud_reachable"]) == (2, ["HO-recon-1", "HO-recon-2"], False)
    assert not ok(out)
    cloud.online = True
    out = reconcile(read_local(storage.connection, "HO-recon-"), read_cloud(cloud.connect, "HO-recon-"))
    assert out["missing"] == ["HO-recon-1", "HO-recon-2"] and not ok(out)  # recovered but not yet uploaded
    upload_pending(storage, cloud.connect)
    out = reconcile(read_local(storage.connection, "HO-recon-"), read_cloud(cloud.connect, "HO-recon-"))
    assert (out["local"], out["cloud_matching"], out["missing"], out["conflict"], out["pending"]) == (2, 2, [], [], [])
    assert ok(out)


def test_marked_uploaded_but_absent_in_cloud_is_missing_and_changed_hash_is_conflict():
    storage, cloud = MesStorage(), FakeCloud()
    for i in (1, 2, 3):
        storage.save_handover(_note(i))
    upload_pending(storage, cloud.connect)
    del cloud.rows["HO-recon-1"]            # lost on the cloud side though local says uploaded
    cloud.rows["HO-recon-2"] = "other-hash"  # same ID, different content
    cloud.rows["HO-other-9"] = "x"           # another device's row, outside the prefix
    out = reconcile(read_local(storage.connection, "HO-recon-"), read_cloud(cloud.connect, "HO-recon-"))
    assert out["missing"] == ["HO-recon-1"] and out["conflict"] == ["HO-recon-2"] and out["cloud_only"] == 0
    assert not ok(out)
