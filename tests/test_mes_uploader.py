import json
import sqlite3
import sys
from types import ModuleType

import pytest

from shiftlink.mes.storage import MesStorage
from shiftlink.mes.uploader import main, upload_pending


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
    assert upload_pending(storage, cloud.connect) == {
        "uploaded": 0, "conflict": 0, "pending": 2, "error": {"class": "OSError"},
    }
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


@pytest.mark.parametrize("exc, expected", [
    (OSError("mysql://user:secret@host/db"), {"class": "OSError"}),
    (RuntimeError(1045, "password=secret; CA=/private/ca.pem"), {"class": "RuntimeError", "code": 1045}),
])
def test_connection_error_reports_only_safe_metadata_and_retries(exc, expected):
    storage, cloud = MesStorage(), FakeCloud()
    storage.save_handover(_note(1))

    def fail():
        raise exc

    result = upload_pending(storage, fail)
    assert result == {"uploaded": 0, "conflict": 0, "pending": 1, "error": expected}
    assert "secret" not in json.dumps(result)
    assert storage.get_handover("HO-test-1")["status"] == "pending"
    assert upload_pending(storage, cloud.connect) == {"uploaded": 1, "conflict": 0, "pending": 0}


def test_midcycle_error_preserves_progress_closes_connection_and_retries():
    storage, cloud = MesStorage(), FakeCloud()
    storage.save_handover(_note(1)); storage.save_handover(_note(2))
    conn = cloud.connect()
    cur = conn.cursor()
    execute = cur.execute
    closed = []

    def fail_second(sql, args):
        if args[0] == "HO-test-2":
            raise OSError(2013, "mysql://user:secret@host/db")
        execute(sql, args)

    cur.execute = fail_second
    conn.cursor = lambda: cur
    conn.close = lambda: closed.append(True)
    result = upload_pending(storage, lambda: conn)
    assert result == {"uploaded": 1, "conflict": 0, "pending": 1,
                      "error": {"class": "OSError", "code": 2013}}
    assert "secret" not in json.dumps(result)
    assert closed == [True]
    assert upload_pending(storage, cloud.connect) == {"uploaded": 1, "conflict": 0, "pending": 0}


@pytest.mark.parametrize("read", ["pending_handovers", "pending_queries"])
def test_pending_read_lock_is_reported_and_next_cycle_retries(monkeypatch, read):
    storage, cloud = MesStorage(), FakeCloud()
    storage.save_handover(_note(1))
    original = getattr(storage, read)

    def locked():
        raise sqlite3.OperationalError("database locked; secret")

    monkeypatch.setattr(storage, read, locked)
    result = upload_pending(storage, cloud.connect)
    assert result == {"uploaded": 0, "conflict": 0, "pending": None,
                      "error": {"class": "OperationalError"}}
    assert "secret" not in json.dumps(result)
    assert cloud.rows == {}
    monkeypatch.setattr(storage, read, original)
    assert upload_pending(storage, cloud.connect) == {"uploaded": 1, "conflict": 0, "pending": 0}


def test_once_prints_safe_json_and_keeps_pending_on_disk(tmp_path, monkeypatch, capsys):
    db = tmp_path / "mes.sqlite3"
    storage = MesStorage(db)
    storage.save_handover(_note(1))

    def fail():
        raise RuntimeError(1045, "mysql://user:secret@host/db")

    schema = ModuleType("db.apply_schema")
    schema.connect = fail
    monkeypatch.setitem(sys.modules, "db.apply_schema", schema)
    monkeypatch.setattr(sys, "argv", ["uploader", "--db", str(db), "--once"])
    main()
    output = capsys.readouterr().out
    assert json.loads(output) == {"uploaded": 0, "conflict": 0, "pending": 1,
                                 "error": {"class": "RuntimeError", "code": 1045}}
    assert "secret" not in output
    assert MesStorage(db).get_handover("HO-test-1")["status"] == "pending"
