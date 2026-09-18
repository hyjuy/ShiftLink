"""Command-line entry point for deterministic data generation."""

import argparse
import json
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run ShiftLink data generation.")
    parser.add_argument("command", choices=("all",))
    parser.add_argument("--from", dest="source", default=".")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--version", default="0.9")
    args = parser.parse_args(argv)
    print(
        json.dumps(
            {
                "command": args.command,
                "from": args.source,
                "seed": args.seed,
                "version": args.version,
            },
            ensure_ascii=False,
        )
    )
    return 0
