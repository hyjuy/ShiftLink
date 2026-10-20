import json
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
