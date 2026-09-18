# Data CLI TDD evidence

## User journey

As a data pipeline developer, I want to run `python -m shiftlink.data all` with source, seed, and version options so later data generation has a stable command interface.

## Evidence

| Stage | Command | Result |
| --- | --- | --- |
| RED | `uv run --python 3.10 --with-requirements requirements.txt python -m pytest tests/test_data_cli.py -q` | `No module named shiftlink.data.__main__` |
| GREEN | same command | `1 passed` |
| Coverage | `uv run --python 3.10 --with-requirements requirements.txt --with pytest-cov python -m pytest tests/test_data_cli.py -q --cov=shiftlink.data --cov-report=term-missing` | `2 passed`, 100% |
| Regression | `uv run --python 3.10 --with-requirements requirements.txt python -m pytest -q` | `13 passed` |

## Test specification

| # | What is guaranteed | Test | Result |
| --- | --- | --- | --- |
| 1 | `python -m shiftlink.data all --from ... --seed ... --version ...` exits successfully and reports the supplied plan | `test_data_cli_smoke_runs_all_with_generation_options` | PASS |
| 2 | The module entry point forwards command-line arguments and applies defaults | `test_data_cli_entrypoint_passes_arguments_to_main` | PASS |

## Known gap

This skeleton parses and reports generation options only. Reading sources, generating data, and writing a manifest are later data-pipeline work.
