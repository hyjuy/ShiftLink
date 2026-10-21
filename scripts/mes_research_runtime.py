"""Freeze only MES research code; never roll back a shared working checkout."""
import argparse
import hashlib
import json
from pathlib import Path


def freeze_runtime(root, out):
    root, out = Path(root).resolve(), Path(out).resolve()
    paths = list((root/"shiftlink/mes").rglob("*.py"))
    paths += list((root/"scripts").glob("mes_*.py"))
    paths += [root/name for name in ("shiftlink/__init__.py", "scripts/build_mes_fault_dataset.py",
              "scripts/evaluate_mes_fault_models.py", "docs/data/reference/00_plant_and_relations.json")]
    captured = {path.relative_to(root).as_posix(): path.read_bytes()
                for path in sorted(set(paths)) if path.is_file()}
    out.mkdir(parents=True, exist_ok=False)
    for name, data in captured.items():
        target = out/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    if any((root/name).read_bytes() != data for name, data in captured.items()):
        raise RuntimeError("MES source changed while freezing; preserve this incomplete snapshot and retry separately")
    result = {"source": str(root), "sampling": "current working copy; no historical restoration",
              "files": {name: hashlib.sha256(data).hexdigest() for name, data in captured.items()}}
    (out/"provenance.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    snapshot = freeze_runtime(Path(__file__).resolve().parents[1], args.out)
    print("frozen MES sources:", len(snapshot["files"]))
