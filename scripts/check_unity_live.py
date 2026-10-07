"""Verify Unity Play Mode against temporary local MES and PDA HTTP services."""
import argparse
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shiftlink.unity_demo import demo_servers, request, unity_arguments, unity_environment
from shiftlink.mes.server import _run_ticks

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    unity_arguments(parser)
    args = parser.parse_args()
    if args.editor is None or not args.editor.is_file():
        parser.error("Set --editor or UNITY_EDITOR to a Unity Editor executable")
    checks = ROOT / "unity/ShiftLinkFactory/Checks"
    checks.mkdir(parents=True, exist_ok=True)
    with demo_servers() as (service, mes, pda):
        request(pda, "/api/control", {"command": "start"})
        scan = request(pda, "/api/equipment/scan",
                       {"class": "GR", "conf": .96, "device_id": "unity-live-check"})["scan"]
        stopped = threading.Event()
        ticks = threading.Thread(target=_run_ticks, args=(service, stopped), daemon=True)
        ticks.start()
        try:
            env = unity_environment(args)
            (checks / "play-check-result.txt").unlink(missing_ok=True)
            result = subprocess.run([
                str(args.editor), "-batchmode", "-force-d3d11",
                "-projectPath", str(ROOT / "unity/ShiftLinkFactory"),
                "-executeMethod", "FactoryChecks.PlayCheck",
                "-logFile", str(checks / "live-check.log"),
                "--mes-url", mes, "--pda-url", pda,
            ], cwd=ROOT, env=env, timeout=180,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            report = {"unity_exit_code": result.returncode, "mes_url": mes, "pda_url": pda,
                      "scan_equipment_id": scan["equipment_id"],
                      "mes_sequence": request(mes, "/api/state")["sequence"],
                      "play_check_result": (checks / "play-check-result.txt").read_text(encoding="utf-8")
                          if (checks / "play-check-result.txt").exists() else None}
            (checks / "live-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
            return result.returncode if result.returncode else (0 if report["play_check_result"] else 1)
        finally:
            stopped.set()
            ticks.join()

if __name__ == "__main__":
    sys.exit(main())
