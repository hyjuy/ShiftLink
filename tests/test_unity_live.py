"""Regression checks for Unity result freshness and portable launch settings."""
import contextlib
import io
import os
import tempfile
import unittest
import argparse
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import check_unity_live, run_unity_demo
from shiftlink.unity_demo import unity_arguments, unity_environment


class UnityLiveCheck(unittest.TestCase):
    def launch(self, *, stale=False, fresh=False, code=0, extra=()):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            editor = root / "Unity.exe"
            editor.touch()
            result_file = root / "unity/ShiftLinkFactory/Checks/play-check-result.txt"
            result_file.parent.mkdir(parents=True)
            if stale:
                result_file.write_text("PASS: old run", encoding="utf-8")
            captured = {}

            def run(command, **kwargs):
                captured.update(kwargs)
                if fresh:
                    result_file.write_text("PASS: current run", encoding="utf-8")
                return SimpleNamespace(returncode=code)

            with patch.object(check_unity_live, "ROOT", root), \
                 patch("sys.argv", ["check_unity_live", "--editor", str(editor), *extra]), \
                 patch.object(check_unity_live.subprocess, "run", side_effect=run), \
                 patch.dict(os.environ, {"TEMP": folder, "TMP": folder}, clear=True), \
                 contextlib.redirect_stdout(io.StringIO()):
                status = check_unity_live.main()
            return status, captured

    def test_old_pass_cannot_pass_a_run_without_a_result(self):
        self.assertEqual(self.launch(stale=True)[0], 1)

    def test_current_pass_succeeds(self):
        self.assertEqual(self.launch(stale=True, fresh=True)[0], 0)

    def test_editor_failure_is_preserved(self):
        self.assertEqual(self.launch(fresh=True, code=7)[0], 7)

    def test_system_temp_and_cache_are_preserved(self):
        _, captured = self.launch(fresh=True)
        self.assertEqual(captured["env"]["TEMP"], captured["env"]["TMP"])
        self.assertNotEqual(captured["env"]["TEMP"], "D:/obsd/Unity/Temp")
        self.assertNotIn("UPM_CACHE_ROOT", captured["env"])

    def test_explicit_temp_and_cache_overrides(self):
        _, captured = self.launch(fresh=True, extra=("--temp-dir", "custom-temp", "--upm-cache", "custom-cache"))
        self.assertEqual(captured["env"]["TEMP"], "custom-temp")
        self.assertEqual(captured["env"]["TMP"], "custom-temp")
        self.assertEqual(captured["env"]["UPM_CACHE_ROOT"], "custom-cache")

    def test_environment_defaults_and_cli_precedence(self):
        parser = argparse.ArgumentParser()
        with patch.dict(os.environ, {"UNITY_EDITOR": "env-editor", "UNITY_TEMP_DIR": "env-temp",
                                     "UPM_CACHE_ROOT": "env-cache"}, clear=True):
            unity_arguments(parser)
            args = parser.parse_args([])
            self.assertEqual(args.editor, Path("env-editor"))
            self.assertEqual(unity_environment(args)["TEMP"], "env-temp")
            self.assertEqual(unity_environment(args)["UPM_CACHE_ROOT"], "env-cache")
            args = parser.parse_args(["--editor", "cli-editor", "--temp-dir", "cli-temp", "--upm-cache", "cli-cache"])
            self.assertEqual(args.editor, Path("cli-editor"))
            self.assertEqual(unity_environment(args)["TEMP"], "cli-temp")
            self.assertEqual(unity_environment(args)["UPM_CACHE_ROOT"], "cli-cache")

    def test_missing_editor_reports_configuration_error(self):
        with patch.dict(os.environ, {}, clear=True), patch("sys.argv", ["check_unity_live"]), \
             contextlib.redirect_stderr(io.StringIO()) as errors:
            with self.assertRaises(SystemExit) as result:
                check_unity_live.main()
        self.assertEqual(result.exception.code, 2)
        self.assertIn("--editor or UNITY_EDITOR", errors.getvalue())

    def test_demo_launcher_uses_shared_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            editor = Path(folder) / "Unity.exe"
            editor.touch()
            with patch.dict(os.environ, {"UNITY_EDITOR": str(editor), "TEMP": folder,
                                         "TMP": folder, "UPM_CACHE_ROOT": "existing-cache"}, clear=True), \
                 patch("sys.argv", ["run_unity_demo", "--mes-url", "http://example.test:8000"]), \
                 patch.object(run_unity_demo.subprocess, "Popen") as launch, \
                 contextlib.redirect_stdout(io.StringIO()):
                launch.return_value.returncode = 0
                self.assertEqual(run_unity_demo.main(), 0)
                self.assertEqual(launch.call_args.kwargs["env"]["TEMP"], folder)
                self.assertEqual(launch.call_args.kwargs["env"]["UPM_CACHE_ROOT"], "existing-cache")
                self.assertEqual(launch.call_args.args[0][0], str(editor))
