"""Export the existing MES configuration for the Unity manufacturing scene."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from shiftlink.mes import configuration
from shiftlink.mes.catalog import Catalog

DEFAULT_CATALOG = ROOT / "docs/data/reference/00_plant_and_relations.json"
DEFAULT_OUTPUT = ROOT / "unity/ShiftLinkFactory/Assets/Resources/mes-config.json"


def read_live(mes_url: str) -> dict:
    parsed = urlsplit(mes_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("MES URL must be an HTTP(S) base URL without query or fragment")
    with urlopen(mes_url.rstrip("/") + "/api/config", timeout=10) as response:
        return json.load(response)


def make_export(envelope: dict, source_mode: str) -> dict:
    if source_mode not in ("catalog", "live"):
        raise ValueError("source_mode must be catalog or live")
    if not isinstance(envelope, dict) or not isinstance(envelope.get("config"), dict):
        raise ValueError("MES response must contain a config object")
    if envelope.get("is_synthetic") is not True:
        raise ValueError("This prototype only accepts the current synthetic MES")
    config = envelope["config"]
    errors = configuration.validate(configuration.from_payload(config))
    if errors:
        raise ValueError("; ".join(errors))
    return {"source_mode": source_mode, "is_synthetic": True, "config": config}


def export_scene(*, output: Path = DEFAULT_OUTPUT, catalog: Path = DEFAULT_CATALOG,
                 mes_url: str | None = None) -> dict:
    if mes_url:
        result = make_export(read_live(mes_url), "live")
    else:
        baseline = configuration.from_catalog(Catalog.load(catalog).data)
        result = make_export({"config": configuration.to_payload(baseline), "is_synthetic": True}, "catalog")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mes-url", help="Export active /api/config; no offline fallback on failure")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        result = export_scene(output=args.output, catalog=args.catalog, mes_url=args.mes_url)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(f"Exported {len(result['config']['equipment'])} equipment ({result['source_mode']}) to {args.output}")


if __name__ == "__main__":
    main()

