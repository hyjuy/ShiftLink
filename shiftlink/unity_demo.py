"""Shared local HTTP services and launch settings for Unity demos and checks."""
import json
import os
import threading
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

from shiftlink.mes.server import MesService, _Handler
from shiftlink.pda.__main__ import make_handler

ROOT = Path(__file__).resolve().parents[1]
OPENER = build_opener(ProxyHandler({}))


def unity_arguments(parser):
    parser.add_argument("--editor", type=Path, default=os.environ.get("UNITY_EDITOR"),
                        help="Unity executable (default: UNITY_EDITOR)")
    parser.add_argument("--temp-dir", default=os.environ.get("UNITY_TEMP_DIR"),
                        help="Override TEMP/TMP; otherwise preserve system settings")
    parser.add_argument("--upm-cache", default=os.environ.get("UPM_CACHE_ROOT"),
                        help="Override Unity package cache (default: UPM_CACHE_ROOT)")


def unity_environment(args):
    env = os.environ.copy()
    if args.temp_dir:
        env.update(TEMP=args.temp_dir, TMP=args.temp_dir)
    if args.upm_cache:
        env["UPM_CACHE_ROOT"] = args.upm_cache
    return env


@contextmanager
def demo_servers():
    service = MesService(ROOT / "docs/data/reference/00_plant_and_relations.json")
    mes_handler = type("UnityMesHandler", (_Handler,), {
        "service": service, "web_root": ROOT / "shiftlink/mes/web",
    })
    mes = ThreadingHTTPServer(("127.0.0.1", 0), mes_handler)
    origin = f"http://127.0.0.1:{mes.server_port}"
    pda = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(origin))
    threads = [threading.Thread(target=server.serve_forever) for server in (mes, pda)]
    for worker in threads:
        worker.start()
    try:
        yield service, origin, f"http://127.0.0.1:{pda.server_port}"
    finally:
        for server, worker in zip((mes, pda), threads):
            server.shutdown()
            worker.join()
            server.server_close()
        service.storage.close()


def request(origin, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    with OPENER.open(Request(origin + path, data=data,
                            headers={"Content-Type": "application/json"}), timeout=5) as response:
        return json.load(response)
