"""Guarantees for exporting the full MES configuration to Unity."""
import copy
import contextlib
import io
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import URLError

from shiftlink.mes import configuration
from shiftlink.mes.catalog import Catalog
from shiftlink.mes.server import MesService, _Handler

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs/data/reference/00_plant_and_relations.json"


class UnityExportTests(unittest.TestCase):
    @property
    def exporter(self):
        if hasattr(self, "_exporter"):
            return self._exporter
        path = ROOT / "scripts/export_unity_mes.py"
        if not path.exists():
            raise AssertionError("Unity MES exporter has not been implemented")
        spec = importlib.util.spec_from_file_location("unity_export", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._exporter = module
        return module

    def baseline(self):
        return {"config": configuration.to_payload(configuration.from_catalog(Catalog.load(CATALOG).data)),
                "is_synthetic": True}

    def test_catalog_exports_every_equipment_and_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "Resources/mes-config.json"
            result = self.exporter.export_scene(output=output, catalog=CATALOG)
            saved = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(saved, result)
        self.assertEqual(result["source_mode"], "catalog")
        self.assertTrue(result["is_synthetic"])
        self.assertEqual({e["equipment_id"] for e in result["config"]["equipment"]},
                         {f"EQ-{i:04d}" for i in range(1, 11)})
        self.assertEqual(result["config"]["route"], ["EQ-0006", "EQ-0007", "EQ-0008", "EQ-0009"])
        self.assertIn(("EQ-0008", "EQ-0010"),
                      {(r["from_id"], r["to_id"]) for r in result["config"]["branches"]})

    def test_live_export_uses_applied_configuration_over_catalog(self):
        service = MesService(CATALOG)
        self.addCleanup(service.storage.close)
        replacement = json.loads((ROOT / "tests/fixtures/mes/config_c_add_transport.json").read_text(encoding="utf-8"))
        service.active_config = configuration.from_payload(replacement)
        handler = type("UnityExportHandler", (_Handler,), {"service": service})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                result = self.exporter.export_scene(output=Path(directory) / "scene.json",
                                                    mes_url=f"http://127.0.0.1:{server.server_port}/")
            self.assertEqual(result["source_mode"], "live")
            self.assertEqual(result["config"], service.config()["config"])
            self.assertEqual(len(result["config"]["equipment"]), 11)
        finally:
            server.shutdown()
            worker.join()
            server.server_close()

    def test_identity_and_disabled_equipment_are_preserved(self):
        data = self.baseline()
        data["config"]["equipment"][0]["active"] = False
        # Export shape must preserve records; MES validator may reject a disabled supplier
        # referenced by a required scenario, so remove scenarios for this configuration.
        data["config"]["scenarios"] = []
        result = self.exporter.make_export(data, "live")
        self.assertFalse(result["config"]["equipment"][0]["active"])
        self.assertEqual(result["config"]["equipment"][0]["asset_id"], "AS-EQ-0001-001")
        self.assertEqual(data["config"], result["config"])

    def test_invalid_route_does_not_overwrite_existing_export(self):
        data = self.baseline()
        data["config"]["route"] = ["EQ-MISSING"]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "scene.json"
            output.write_text("previous", encoding="utf-8")
            with patch.object(self.exporter, "read_live", return_value=data):
                with self.assertRaises(ValueError):
                    self.exporter.export_scene(output=output, mes_url="http://localhost:8000")
            self.assertEqual(output.read_text(encoding="utf-8"), "previous")

    def test_duplicate_ids_and_bad_envelopes_are_rejected(self):
        data = self.baseline()
        data["config"]["equipment"].append(copy.deepcopy(data["config"]["equipment"][0]))
        for malformed in (None, [], {}, {"config": []}, data,
                          {**self.baseline(), "is_synthetic": False}):
            with self.subTest(payload=type(malformed).__name__):
                with self.assertRaises((ValueError, TypeError)):
                    self.exporter.make_export(malformed, "live")

    def test_live_failure_never_silently_falls_back_to_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "scene.json"
            with patch.object(self.exporter, "read_live", side_effect=URLError("offline")):
                with self.assertRaises(URLError):
                    self.exporter.export_scene(output=output, mes_url="http://localhost:8000")
            self.assertFalse(output.exists())

    def test_cli_offline_export(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "scene.json"
            result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/export_unity_mes.py"),
                                     "--output", str(output)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(json.loads(output.read_text(encoding="utf-8"))["config"]["equipment"]), 10)


    def test_url_and_source_validation(self):
        for url in ("file:///etc/passwd", "http://localhost:8000?x=1", "localhost:8000"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.exporter.read_live(url)
        with self.assertRaises(ValueError):
            self.exporter.make_export(self.baseline(), "unknown")

    def test_cli_entrypoint_success_and_missing_catalog_error(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "scene.json"
            with patch.object(sys, "argv", ["export_unity_mes.py", "--output", str(output)]):
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    self.exporter.main()
            self.assertIn("Exported 10 equipment", stdout.getvalue())
            self.assertTrue(output.exists())
            original = output.read_text(encoding="utf-8")
            args = ["export_unity_mes.py", "--catalog", str(Path(directory) / "missing.json"),
                    "--output", str(output)]
            with patch.object(sys, "argv", args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    self.exporter.main()
            self.assertEqual(error.exception.code, 2)
            self.assertEqual(output.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()

