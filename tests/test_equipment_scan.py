import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from shiftlink.mes.server import MesService, _Handler
from shiftlink.vision import CLASSES
from shiftlink.vision.classify import post_scan

CATALOG = Path("docs/data/reference/00_plant_and_relations.json")


@pytest.fixture
def service():
    s = MesService(CATALOG)
    yield s
    s.storage.close()


def test_every_cnn_class_maps_to_catalog_equipment(service):
    for label in CLASSES:
        scan = service.record_scan({"class": label, "conf": 0.9, "device_id": "pi-01"})["scan"]
        assert scan["code"].startswith(label + "-") and scan["equipment_id"].startswith("EQ-")
    assert [s["class"] for s in service.recent_scans(6)["scans"]] == list(CLASSES)[::-1]


@pytest.mark.parametrize("body", [
    [], {"class": "XX", "conf": 0.9, "device_id": "pi"}, {"class": "HPU", "conf": 1.5, "device_id": "pi"},
    {"class": "HPU", "conf": True, "device_id": "pi"}, {"class": "HPU", "conf": 0.9, "device_id": ""},
    {"class": "HPU", "conf": 0.9, "device_id": "pi", "ts": 123},
])
def test_invalid_scan_rejected(service, body):
    with pytest.raises(ValueError):
        service.record_scan(body)


def test_pi_post_reaches_server_and_recent_shows_it(service):
    handler = type("H", (_Handler,), {"service": service, "web_root": Path("shiftlink/mes/web")})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        assert post_scan(url, "GR", 0.97, "pi-01")
        assert not post_scan(url, "NOPE", 0.97, "pi-01")  # 400도 예외 없이 False
        with urllib.request.urlopen(url + "/api/equipment/scan/recent?limit=5") as resp:
            scans = json.load(resp)["scans"]
        assert [(s["class"], s["code"], s["device_id"]) for s in scans] == [("GR", "GR-01", "pi-01")]
    finally:
        server.shutdown()
        server.server_close()
    assert not post_scan(url, "GR", 0.97, "pi-01", timeout=0.5)  # 서버 꺼짐도 False
