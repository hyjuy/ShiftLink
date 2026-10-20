import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.mes_research_runtime import freeze_runtime


class ResearchRuntimeTests(unittest.TestCase):
    def test_snapshot_preserves_sources_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/"repo"
            for name in ("shiftlink/__init__.py", "shiftlink/mes/engine.py",
                         "scripts/build_mes_fault_dataset.py",
                         "docs/data/reference/00_plant_and_relations.json"):
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}" if name.endswith("json") else "# frozen\n", encoding="utf-8")
            out = Path(directory)/"runtime"
            result = freeze_runtime(root, out)
            self.assertEqual(len(result["files"]), 4)
            self.assertEqual((out/"shiftlink/mes/engine.py").read_bytes(),
                             (root/"shiftlink/mes/engine.py").read_bytes())
            self.assertEqual(json.loads((out/"provenance.json").read_text())["files"], result["files"])
            with self.assertRaises(FileExistsError):
                freeze_runtime(root, out)

    def test_concurrent_source_change_aborts_without_valid_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root, out = Path(directory)/"repo", Path(directory)/"runtime"
            source = root/"shiftlink/mes/engine.py"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"# original\n")
            original = Path.read_bytes
            reads = []
            def changing(path):
                value = original(path)
                if path == source:
                    reads.append(path)
                    if len(reads) > 1:
                        return value+b"# concurrent change\n"
                return value
            with patch.object(Path, "read_bytes", changing):
                with self.assertRaisesRegex(RuntimeError, "source changed"):
                    freeze_runtime(root, out)
            self.assertFalse((out/"provenance.json").exists())


if __name__ == "__main__":
    unittest.main()
