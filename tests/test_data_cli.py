import json
import subprocess
import sys


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
