"""Local Pi-client -> PDA proxy -> Jetson MES contract checks; no hardware required."""

import tempfile
import threading
import unittest
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from shiftlink.agent.response import AgentResponse
from shiftlink.communication.http_client import HTTPClientError, MesHTTPClient
from shiftlink.mes.server import MesService, _Handler
from shiftlink.mes.storage import MesStorage
from shiftlink.pda.__main__ import make_handler


ROOT = Path(__file__).resolve().parents[1]


class Pipeline:
    def run(self, payload):
        self.payload = payload
        return SimpleNamespace(output=AgentResponse(
            mode="query", answer="센서값 확인", cited_card_ids=["K-1"],
            safety_notices=[{"card_id": "K-S", "safety_basis": "작업 전 정지"}],
        ))


@contextmanager
def http_server(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        worker.join()
        server.server_close()


@contextmanager
def mes_server(database):
    service = MesService(ROOT / "docs/data/reference/00_plant_and_relations.json", MesStorage(database))
    service.query_pipeline = Pipeline()
    handler = type("CommunicationHandler", (_Handler,), {"service": service, "api_only": True})
    try:
        with http_server(handler) as url:
            yield service, url
    finally:
        service.storage.close()


class CommunicationIntegrationTests(unittest.TestCase):
    def test_scan_query_and_mes_reads_direct_and_through_pda_proxy(self):
        with tempfile.TemporaryDirectory() as directory:
            with mes_server(Path(directory) / "mes.sqlite3") as (service, url):
                with http_server(make_handler(url)) as proxy_url:
                    for address in (url, proxy_url):
                        with self.subTest(address=address):
                            client = MesHTTPClient(address)
                            timestamp = "2026-10-02T07:00:00+00:00"
                            scan = client.send_scan("GR", .95, "pi-test", ts=timestamp)["scan"]
                            self.assertEqual(scan["ts"], timestamp)
                            self.assertEqual(client.get_recent_scans(limit=1)["scans"][0], scan)
                            state = client.get_state()
                            self.assertEqual(client.get_events(after_sequence=-1), service.events(-1))
                            self.assertEqual(state["run_id"], service.engine.run.run_id)
                            result = client.query("베어링 온도", scan_id=scan["scan_id"], k=3)
                            self.assertEqual(service.query_pipeline.payload["eq_id"], scan["equipment_id"])
                            self.assertEqual(service.query_pipeline.payload["question"], "베어링 온도")
                            self.assertTrue(service.query_pipeline.payload["observations"])
                            self.assertEqual(result["scan"]["scan_id"], scan["scan_id"])
                            self.assertEqual(result["answer"], "센서값 확인")
                            self.assertEqual(result["cited_card_ids"], ["K-1"])
                            self.assertEqual(result["safety_notices"][0]["card_id"], "K-S")
                            measurements = {row["signal"]: row["value"] for row in state["measurements"]
                                            if row["equipment_id"] == scan["equipment_id"]}
                            self.assertTrue(result["evidence"]["measurements"])
                            for row in result["evidence"]["measurements"]:
                                self.assertEqual(row["equipment_id"], scan["equipment_id"])
                                self.assertEqual(row["value"], measurements[row["signal"]])
                            manual = client.query("온도", equipment_id="EQ-0004")
                            self.assertIsNone(manual["scan"])
                            self.assertEqual(service.query_pipeline.payload["eq_id"], "EQ-0004")

    def test_handover_retry_survives_server_restart_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "mes.sqlite3"
            with mes_server(database) as (_, url):
                first = MesHTTPClient(url).save_handover("HO-COMM-1", "시동 전 점검")
                self.assertFalse(first["duplicate"])
            with mes_server(database) as (service, url):
                with http_server(make_handler(url)) as proxy_url:
                    client = MesHTTPClient(proxy_url)
                    retry = client.save_handover("HO-COMM-1", "시동 전 점검")
                    self.assertTrue(retry["duplicate"])
                    self.assertEqual(retry["created_at"], first["created_at"])
                    with self.assertRaises(HTTPClientError) as caught:
                        client.save_handover("HO-COMM-1", "수정된 메모")
                    self.assertEqual(caught.exception.status_code, 409)
                    self.assertIn("different content", str(caught.exception))
                    self.assertEqual(service.storage.get_handover("HO-COMM-1")["payload"]["memo_text"],
                                     "시동 전 점검")
                    count = service.storage.connection.execute("SELECT COUNT(*) FROM handover_outbox").fetchone()[0]
                    self.assertEqual(count, 1)

    def test_query_selection_errors_preserved_through_proxy(self):
        with tempfile.TemporaryDirectory() as directory:
            with mes_server(Path(directory) / "mes.sqlite3") as (_, url):
                with http_server(make_handler(url)) as proxy_url:
                    client = MesHTTPClient(proxy_url)
                    with self.assertRaises(HTTPClientError) as caught:
                        client.query("온도")
                    self.assertEqual(caught.exception.status_code, 400)
                    self.assertIn("no recent equipment scan", str(caught.exception))
                    first = client.send_scan("HPU", .9, "pi-test")["scan"]
                    client.send_scan("GR", .9, "pi-test")
                    with self.assertRaises(HTTPClientError) as caught:
                        client.query("온도", scan_id=first["scan_id"])
                    self.assertEqual(caught.exception.status_code, 400)
                    self.assertIn("equipment scan changed", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
