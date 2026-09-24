"""Detect evaluation canaries before retrieved cards reach a model or response."""

import json
from typing import Any


CANARY_PREFIXES = ("zzk9-", "qqz7-")


def has_canary(card: dict[str, Any]) -> bool:
    return any(prefix in json.dumps(card, ensure_ascii=False, default=str) for prefix in CANARY_PREFIXES)
