from shiftlink.mes.storage import MesStorage
from shiftlink.mes.uploader import upload_pending


class FakeCloud:
    """handover_upload as a dict; `online` False makes connect() fail like a pulled cable."""

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
                else:
                    self.row = (cloud.rows.get(args[0]),)

            def fetchone(self): return self.row

        class Conn:
            def cursor(self): return Cursor()
            def close(self): pass

        return Conn()


def _note(i, memo="HPU-01 갈리는 소리"):
    return {"handover_id": f"HO-test-{i}", "memo_text": memo, "equipment_id": "HPU-01"}


def test_offline_then_recover_uploads_each_handover_once():
    storage, cloud = MesStorage(), FakeCloud()
    cloud.online = False
    storage.save_handover(_note(1)); storage.save_handover(_note(2))
    assert upload_pending(storage, cloud.connect) == {"uploaded": 0, "conflict": 0, "pending": 2}
    cloud.online = True
    assert upload_pending(storage, cloud.connect)["uploaded"] == 2
    assert upload_pending(storage, cloud.connect) == {"uploaded": 0, "conflict": 0, "pending": 0}
    assert sorted(cloud.rows) == ["HO-test-1", "HO-test-2"]
    assert storage.get_handover("HO-test-1")["status"] == "uploaded"


def test_lost_ack_is_uploaded_and_changed_content_is_held_as_conflict():
    storage, cloud = MesStorage(), FakeCloud()
    storage.save_handover(_note(1)); storage.save_handover(_note(2))
    upload_pending(storage, cloud.connect)
    storage.mark_handover("HO-test-1", "pending")  # ack lost: cloud has it, local still pending
    cloud.rows["HO-test-2"] = "other-hash"; storage.mark_handover("HO-test-2", "pending")
    assert upload_pending(storage, cloud.connect) == {"uploaded": 1, "conflict": 1, "pending": 0}
    assert storage.get_handover("HO-test-2")["status"] == "conflict"


def test_query_log_is_uploaded_with_latency():
    storage, cloud = MesStorage(), FakeCloud()
    query_id = storage.save_query({"question": "HPU 소리", "equipment_id": "HPU-01", "latency_ms": 2100, "no_knowledge": False})
    assert upload_pending(storage, cloud.connect) == {"uploaded": 1, "conflict": 0, "pending": 0}
    assert list(cloud.rows) == [query_id]
