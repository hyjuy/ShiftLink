import json
import runpy
import subprocess
import sys

import pytest


def test_data_cli_smoke_runs_all_with_generation_options() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "shiftlink.data",
            "all",
            "--from",
            "fixtures/source",
            "--seed",
            "42",
            "--version",
            "0.9",
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "command": "all",
        "from": "fixtures/source",
        "seed": 42,
        "version": "0.9",
    }


def test_data_cli_entrypoint_passes_arguments_to_main(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sys, "argv", ["shiftlink.data", "all", "--seed", "7"]
    )

    with pytest.raises(SystemExit) as exit_code:
        runpy.run_module("shiftlink.data.__main__", run_name="__main__")

    assert exit_code.value.code == 0
    assert json.loads(capsys.readouterr().out) == {
        "command": "all",
        "from": ".",
        "seed": 7,
        "version": "0.9",
    }
