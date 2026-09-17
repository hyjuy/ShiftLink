# Pipeline schema v0.9 TDD evidence

## User journey

As a pipeline developer, I want K-01, Event, and artifact payloads validated by Pydantic so invalid generated data is rejected before storage.

## Evidence

| Stage | Command | Result |
| --- | --- | --- |
| RED | `python -c "from src.pipeline.schemas import KnowledgeCard"` | `ModuleNotFoundError: No module named 'src.pipeline.schemas'` |
| GREEN | `uv run --with pytest --with pydantic python -m pytest tests/test_schemas.py -q` | `1 passed` |
| Coverage | `uv run --with pytest --with pydantic --with pytest-cov python -m pytest tests/test_schemas.py -q --cov=src.pipeline.schemas --cov-report=term-missing` | `69 statements, 100%` |

The test guarantees the approved K-01 validation rules, the `grade` acceptance gate, and successful construction of compatible Event and artifact contracts. D-26 through D-29 remain approval-pending comments and are not active schema behavior.

## Known gaps

Cross-record foreign-key and split-inheritance checks belong to the pipeline validation stage and are outside this schema draft.
