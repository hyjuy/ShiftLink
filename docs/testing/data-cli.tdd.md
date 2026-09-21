# Data CLI TDD evidence

## User journey

As a data pipeline developer, I want to plan all stages or resume from a selected stage with seed and dataset version options.

## Current interface

```sh
python -m shiftlink.data all
python -m shiftlink.data all --from P3 --seed 42 --version v0.x
python -m shiftlink.data --help
```

`--from` is an inclusive starting stage, not a source path. The supported baseline
is P0 through P6, as described in `docs/design/B_data.md` B7. Decimal stages are marked
as unapproved proposals there and are not enabled. The requested option spelling
is `all --from P3`; the documentation's shorthand `from P3` is not a subcommand.
Defaults remain seed `0` and dataset version `0.9`; the starting stage is `P0`.

Output for the second command:

```json
{"status": "planned", "command": "all", "from": "P3", "stages": ["P3", "P4", "P5", "P6"], "seed": 42, "version": "v0.x"}
```

Exit code 0 means the plan was produced (or help was shown), not that generation
completed. Invalid arguments exit with code 2 and do not print a plan.

## Original evidence (superseded contract)

The original tests below verified option echoing, including the incorrect source
path interpretation. Their passing result did not establish requirement correctness.

| Stage | Command | Result |
| --- | --- | --- |
| RED | `uv run --python 3.10 --with-requirements requirements.txt python -m pytest tests/test_data_cli.py -q` | `No module named shiftlink.data.__main__` |
| GREEN | same command | `1 passed` |
| Coverage | `uv run --python 3.10 --with-requirements requirements.txt --with pytest-cov python -m pytest tests/test_data_cli.py -q --cov=shiftlink.data --cov-report=term-missing` | `2 passed`, 100% |
| Regression | `uv run --python 3.10 --with-requirements requirements.txt python -m pytest -q` | `13 passed` |

## Test specification

| # | What is guaranteed | Test | Result |
| --- | --- | --- | --- |
| 1 | Real module execution emits full, P3-resumed, and P6-only plans with seed/version | `test_data_cli_smoke` | PASS |
| 2 | Every baseline starting stage is included through P6 | `test_resume_includes_selected_stage_through_p6` | PASS |
| 3 | Bad stages, paths, missing values, invalid seed, and unknown arguments fail without a plan | `test_invalid_arguments_fail_without_a_plan` | PASS |
| 4 | Help describes plan-only behavior and the options | `test_help_describes_plan_and_options` | PASS |

## Correction evidence

- RED: `uv run --python 3.10 --with-requirements requirements.txt python -m pytest tests/test_data_cli.py -q` → **14 failed, 6 passed** against the original implementation.
- GREEN and regression: `uv run --python 3.10 --with-requirements requirements.txt python -m pytest -q` → **31 passed**, including 20 CLI cases.
- Two subagents independently inspected requirements and tests. The baseline/proposal distinction was resolved using B7 and the document's approval status.
- Coverage was not remeasured for this correction; the earlier 100% figure applies only to the original implementation.

## Known gap

This skeleton produces a plan only (`status: planned`). Stage execution, source reading, random generation, checkpoint loading, and manifest writes are not implemented. A seed in the plan does not establish generated-data reproducibility.
