"""Exercise generated units without registering or starting any services."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess

import pytest


@pytest.fixture
def units(tmp_path):
    repo = tmp_path / "ShiftLink spaced repo"
    deploy = repo / "deploy"
    deploy.mkdir(parents=True)
    source = Path(__file__).resolve().parents[1] / "deploy"
    for script in ("install_service.sh", "install_uploader.sh"):
        shutil.copyfile(source / script, deploy / script)
    if os.name == "nt":
        if not shutil.which("wsl.exe"):
            pytest.skip("WSL bash is unavailable")
        prefix = ["wsl.exe", "bash", "-lc"]
        linux_repo = "/mnt/" + repo.drive[0].lower() + repo.as_posix()[2:]
    else:
        if not shutil.which("bash"):
            pytest.skip("bash is unavailable")
        prefix = ["bash", "-lc"]
        linux_repo = str(repo)
    env_file = linux_repo + "/aiven config.env"
    outputs = {}
    for name, script, args in (
        ("mes", "install_service.sh", "mes"),
        ("uploader", "install_uploader.sh", ""),
    ):
        command = (
            "DRY_RUN=1 PY=/usr/bin/python3 ENV_FILE=" + shlex.quote(env_file)
            + " bash " + shlex.quote(linux_repo + "/deploy/" + script) + " " + args
        )
        result = subprocess.run(prefix + [command], capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert result.returncode == 0, result.stderr
        outputs[name] = result.stdout
    return linux_repo, env_file, outputs


def test_mes_requests_ollama_without_coupling_uploader_lifecycle(units):
    _, _, generated = units
    wants = next(line for line in generated["mes"].splitlines() if line.startswith("Wants="))
    assert "ollama.service" in wants.split("=", 1)[1].split()
    assert "shiftlink-uploader.service" in wants.split("=", 1)[1].split()
    for unit in generated.values():
        assert not any(line.startswith(("Requires=", "BindsTo=", "PartOf=")) for line in unit.splitlines())


def test_spaced_paths_and_shared_default_db(units):
    repo, env_file, generated = units
    for unit in generated.values():
        assert f'WorkingDirectory="{repo}"' in unit.splitlines()
        assert f'--db "{repo}/mes_data/mock-mes.sqlite3"' in unit
    assert f'EnvironmentFile="{env_file}"' in generated["uploader"].splitlines()
