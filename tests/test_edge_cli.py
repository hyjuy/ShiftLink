import io
import sys
import urllib.error

from shiftlink.edge.__main__ import main


def test_model_failure_exits_nonzero_on_cp949_console(monkeypatch):
    output = io.TextIOWrapper(io.BytesIO(), encoding="cp949")
    monkeypatch.setattr(sys, "stdout", output)

    def refuse(request, timeout=None):
        raise urllib.error.URLError(ConnectionRefusedError(61, "refused"))

    monkeypatch.setattr("urllib.request.urlopen", refuse)

    status = main(["--case", "F-e2e-004"])

    assert status == 1
    output.flush()
    assert "review_queue" in output.buffer.getvalue().decode("cp949")
