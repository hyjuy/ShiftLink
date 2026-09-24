import io
import sys

from shiftlink.edge.__main__ import main


def test_unsupported_handover_exits_nonzero_on_cp949_console(monkeypatch):
    output = io.TextIOWrapper(io.BytesIO(), encoding="cp949")
    monkeypatch.setattr(sys, "stdout", output)

    status = main(["--case", "F-e2e-004"])

    assert status == 1
    output.flush()
    assert "review_queue" in output.buffer.getvalue().decode("cp949")
