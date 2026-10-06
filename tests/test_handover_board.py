"""Cloud handover list is read-only and survives a dead connection."""

from shiftlink.mes.handover_board import list_uploads, page, render_page


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.sql = ""
        self.args = ()

    def execute(self, sql, args=()):
        self.sql = sql
        self.args = args

    def fetchall(self):
        if self.args:
            return [row for row in self.rows if row[1] == self.args[0]]
        return self.rows


def test_list_is_select_only_and_newest_order_is_the_callers():
    payload = {"memo_text": "첫 줄\n나머지", "required_context": {"recipient_role": "야간조"}}
    cur = FakeCursor([("HO-1", "EQ-1", "2026-10-06 01:00:00", payload, None)])
    rows = list_uploads(cur)
    assert cur.sql.startswith("SELECT") and "INSERT" not in cur.sql and "DELETE" not in cur.sql
    assert rows[0]["first_line"] == "첫 줄"
    assert rows[0]["created_kst"] == "2026-10-06 10:00"
    assert rows[0]["required_context"]["recipient_role"] == "야간조"
    filtered = list_uploads(cur, "EQ-9")
    assert filtered == []


def test_offline_badge_does_not_crash():
    status, html = page(lambda: (_ for _ in ()).throw(OSError("down")))
    assert status == 200 and "오프라인 — 클라우드 인계를 읽을 수 없음" in html
    assert "올라온 인계가 없습니다" in html


def test_page_renders_rows():
    class Conn:
        def cursor(self):
            return self
        def __enter__(self):
            return FakeCursor([("HO-2", "EQ-2", "2026-10-06 00:00:00",
                                '{"memo_text":"필터 교체"}', None)])
        def __exit__(self, *args):
            return False
        def close(self):
            return None
    # page() uses `with conn.cursor()`.
    class Real:
        def cursor(self):
            return _Ctx()
        def close(self):
            return None
    class _Ctx:
        def __enter__(self):
            return FakeCursor([("HO-2", "EQ-2", "2026-10-06 00:00:00",
                                '{"memo_text":"필터 교체"}', None)])
        def __exit__(self, *a):
            return False
    status, html = page(lambda: Real())
    assert status == 200 and "필터 교체" in html and "오프라인" not in html
    assert "쓰기" not in render_page([], offline=False)
