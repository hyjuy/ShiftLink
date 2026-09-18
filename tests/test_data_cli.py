import json
from pathlib import Path
import subprocess
import sys

import pytest

from shiftlink.data import main


# 전체 실행, 중간 재개, 마지막 단계만 선택하는 세 가지 실제 CLI 사용을 검증한다.
@pytest.mark.parametrize(
    ("options", "start", "stages", "seed", "version"),
    [
        ([], "P0", ["P0", "P1", "P2", "P3", "P4", "P5", "P6"], 0, "0.9"),
        (["--from", "P3", "--seed", "42", "--version", "v0.x"],
         "P3", ["P3", "P4", "P5", "P6"], 42, "v0.x"),
        (["--from", "P6"], "P6", ["P6"], 0, "0.9"),
    ],
)
def test_data_cli_smoke(options, start, stages, seed, version) -> None:
    # 별도 Python 프로세스로 실행해 -m 진입점과 JSON 출력을 함께 확인한다.
    completed = subprocess.run(
        [sys.executable, "-m", "shiftlink.data", "all", *options],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "status": "planned",
        "command": "all",
        "from": start,
        "stages": stages,
        "seed": seed,
        "version": version,
    }


@pytest.mark.parametrize("stage", ["P0", "P1", "P2", "P3", "P4", "P5", "P6"])
def test_resume_includes_selected_stage_through_p6(stage, capsys) -> None:
    # 모든 재개 지점에서 시작 단계가 빠지거나 이전 단계가 섞이지 않아야 한다.
    assert main(["all", "--from", stage]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["stages"] == [f"P{i}" for i in range(int(stage[1:]), 7)]


@pytest.mark.parametrize("argv", [
    [], ["unknown"], ["all", "--from", "P99"],
    ["all", "--from", "fixtures/source"], ["all", "--from", "P1.5"],
    ["all", "--from"], ["all", "--seed", "abc"], ["all", "--version"],
    ["all", "--unknown"],
])
def test_invalid_arguments_fail_without_a_plan(argv, capsys) -> None:
    # 잘못된 요청은 종료 코드 2로 실패해야 하며, 성공처럼 보이는 계획을 출력하면 안 된다.
    with pytest.raises(SystemExit) as error:
        main(argv)
    assert error.value.code == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "error:" in output.err


def test_help_describes_plan_and_options(capsys) -> None:
    # 도움말은 정상 종료하며, 지원 옵션과 계획 출력 기능임을 안내해야 한다.
    with pytest.raises(SystemExit) as error:
        main(["--help"])
    assert error.value.code == 0
    help_text = capsys.readouterr().out
    for text in ("--from", "--seed", "--version", "P0", "P6", "plan"):
        assert text in help_text
