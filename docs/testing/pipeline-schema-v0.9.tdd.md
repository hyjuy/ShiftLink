# Pipeline schema v0.9 TDD evidence

## User journey

As a pipeline developer, I want K-01, Event, and artifact payloads validated by Pydantic so invalid generated data is rejected before storage.

## Evidence

| Stage | Command | Result |
| --- | --- | --- |
| Initial RED | `python -c "from src.pipeline.schemas import KnowledgeCard"` | `ModuleNotFoundError: No module named 'src.pipeline.schemas'` |
| Runtime | `uv run --python 3.10 --with-requirements requirements.txt python -c "import sys; print(sys.version)"` | `3.10.21` |
| Package migration RED | `uv run --with pytest --with pydantic python -m pytest tests/test_schemas.py -q` | `ModuleNotFoundError: No module named 'shiftlink.agent.schemas'` |
| Package migration GREEN | `uv run --python 3.10 --with-requirements requirements.txt python -m pytest tests/test_schemas.py -q` | `1 passed` |
| Coverage | `uv run --python 3.10 --with-requirements requirements.txt --with pytest-cov python -m pytest tests/test_schemas.py -q --cov=shiftlink.agent.schemas --cov-report=term-missing` | `69 statements, 100%` |

The test guarantees the approved K-01 validation rules, the `grade` acceptance gate, and successful construction of compatible Event and artifact contracts. D-26 through D-29 are approved requirements, but their extensions are not yet active schema behavior in v0.9. T-27 (mapped to D-27) requires T4 to describe how to hand over; D-26 expands safety conditions, D-28 requires ordered solution steps, and D-29 distinguishes failures by restart type. Detailed field names remain implementation proposals to be fixed in schema v1.0 after the 9/22 contract review; approval does not imply a separate handover axis or a new T6 type.

## Known gaps

Cross-record foreign-key and split-inheritance checks belong to the pipeline validation stage and are outside this schema draft.
