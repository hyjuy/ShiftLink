"""Unity/PDA/MES contract verified against actual localhost HTTP handlers."""
import json
import threading
import unittest
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

from shiftlink.mes.server import MesService, _Handler
from shiftlink.pda.__main__ import make_handler

ROOT = Path(__file__).resolve().parents[1]
OPENER = build_opener(ProxyHandler({}))

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

class UnityMesContract(unittest.TestCase):
    def test_pda_control_and_recognition_reach_same_mes_as_unity(self):
        with demo_servers() as (service, mes, pda):
            config = request(pda, "/api/config")["config"]
            self.assertEqual(config, request(mes, "/api/config")["config"])
            initial = request(mes, "/api/state")
            self.assertEqual(initial["config_id"], config["config_id"])
            request(pda, "/api/control", {"command": "start"})
            service.tick()
            running = request(mes, "/api/state")
            self.assertEqual(running["line_mode"], "running")
            self.assertGreater(running["sequence"], initial["sequence"])
            ids = {e["equipment_id"] for e in config["equipment"] if e["active"]}
            self.assertEqual(ids, {e["equipment_id"] for e in running["equipment"]})
            self.assertTrue(running["coils"])
            for coil in running["coils"]:
                self.assertIn(coil["equipment_id"], ids)
                self.assertGreaterEqual(coil["position"], 0)
                self.assertLessEqual(coil["position"], 1)
            scan = request(pda, "/api/equipment/scan",
                           {"class": "GR", "conf": .96, "device_id": "unity-pda-check"})["scan"]
            self.assertIn(scan["equipment_id"], ids)
            self.assertEqual(request(mes, "/api/equipment/scan/recent?limit=1")["scans"][0], scan)
            request(pda, "/api/control", {"command": "pause"})
            self.assertEqual(request(mes, "/api/state")["line_mode"], "paused")
            with OPENER.open(pda + "/pda.html?equipment_id=" + scan["equipment_id"], timeout=5) as response:
                self.assertIn(b"/static/pda.js", response.read())

def write_fixtures():
    with demo_servers() as (service, mes, pda):
        request(pda, "/api/control", {"command": "start"})
        service.tick()
        request(pda, "/api/equipment/scan",
                {"class": "GR", "conf": .96, "device_id": "unity-pda-check"})
        folder = ROOT / "unity/ShiftLinkFactory/Checks"
        folder.mkdir(parents=True, exist_ok=True)
        for name, path in (("config", "/api/config"), ("state", "/api/state"),
                           ("scans", "/api/equipment/scan/recent?limit=1")):
            (folder / f"{name}.json").write_text(
                json.dumps(request(mes, path), ensure_ascii=False), encoding="utf-8")

if __name__ == "__main__":
    unittest.main()
