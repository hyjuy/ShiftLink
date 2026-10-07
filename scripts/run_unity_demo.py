"""Start a dedicated local MES/PDA demo and open Unity."""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shiftlink.unity_demo import unity_arguments, unity_environment

PROJECT = ROOT / "unity/ShiftLinkFactory"

def free_port(port):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    unity_arguments(parser)
    parser.add_argument("--mes-url", help="Use an existing MES; no local services or data changes")
    parser.add_argument("--pda-url", help="PDA page origin; default local proxy or MES origin")
    parser.add_argument("--mes-port", type=int, default=8000)
    parser.add_argument("--pda-port", type=int, default=8080)
    args = parser.parse_args()
    if args.editor is None or not args.editor.is_file():
        parser.error("Set --editor or UNITY_EDITOR to a Unity Editor executable")

    children = []
    opener = build_opener(ProxyHandler({}))
    try:
        if args.mes_url:
            mes = args.mes_url.rstrip("/")
            pda = args.pda_url or mes
        else:
            if args.mes_port == args.pda_port:
                parser.error("MES and PDA ports must differ")
            free_port(args.mes_port)
            free_port(args.pda_port)
            mes = f"http://127.0.0.1:{args.mes_port}"
            pda = args.pda_url or f"http://127.0.0.1:{args.pda_port}"
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            children.append(subprocess.Popen(
                [sys.executable, "-B", "-m", "shiftlink.mes", "--port", str(args.mes_port),
                 "--db", str(ROOT / "mes_data/unity-demo.sqlite3")], cwd=ROOT, creationflags=flags))
            deadline = time.monotonic() + 20
            while True:
                if children[0].poll() is not None:
                    raise RuntimeError("Local MES exited before startup")
                try:
                    with opener.open(mes + "/api/state", timeout=1):
                        break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Local MES startup timed out")
                    time.sleep(.2)
            request = Request(mes + "/api/control", data=b'{"command":"start"}',
                              headers={"Content-Type": "application/json"})
            with opener.open(request, timeout=5):
                pass
            children.append(subprocess.Popen(
                [sys.executable, "-B", "-m", "shiftlink.pda", "--jetson", mes,
                 "--port", str(args.pda_port), "--no-window"], cwd=ROOT, creationflags=flags))
        print(f"MES: {mes}\nPDA: {pda}/pda.html\nUnity: {PROJECT}", flush=True)
        editor = subprocess.Popen([str(args.editor), "-projectPath", str(PROJECT),
                                   "-executeMethod", "FactoryChecks.OpenDemo",
                                   "--mes-url", mes, "--pda-url", pda], cwd=ROOT,
                                  env=unity_environment(args))
        editor.wait()
        return editor.returncode
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError) as error:
        print(f"Demo startup failed: {error}", file=sys.stderr)
        sys.exit(1)
