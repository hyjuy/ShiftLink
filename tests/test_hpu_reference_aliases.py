"""Published baseline aliases preserve the original live experiment source."""
import json
from pathlib import Path

import pytest

from hpu_retrieval_live import reference_revision


def test_original_and_published_references_resolve_to_public_commits():
    root=Path(__file__).resolve().parents[1]
    manifest=json.loads((root/'docs/testing/hpu-github-source-map-20261025.json').read_text(encoding='utf-8'))
    for original,published in manifest['reference_aliases'].items():
        assert reference_revision(original)==published
        assert reference_revision(published)==published


def test_arbitrary_reference_is_rejected():
    with pytest.raises(AssertionError):reference_revision('HEAD')
