"""Exercise the Pi HTTP client against a real local server, without hardware."""

import json
import socket
import threading
import time
import unittest
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from shiftlink.communication.http_client import HTTPClientError, MesHTTPClient


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.respond()

    def do_POST(self):
        self.respond()

    def respond(self):
        size = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(size)) if size else None
        self.server.calls.append((self.command, self.path, body, self.headers.get("Content-Type")))
        if self.server.disconnect:
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
            return
        if self.server.delay:
            time.sleep(self.server.delay)
        self.send_response(self.server.status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        response = self.server.raw_response
        if response is None:
            response = json.dumps(self.server.response, ensure_ascii=False).encode("utf-8")
        try:
            self.wfile.write(response)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


class CommunicationHTTPClientTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.server.calls = []
        self.server.response = {"message": "설비 상태 정상"}
        self.server.raw_response = None
        self.server.status = 200
        self.server.disconnect = False
        self.server.delay = 0
        self.worker = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01})
        self.worker.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.client = MesHTTPClient(self.url, timeout=1, query_timeout=1)

    def tearDown(self):
        self.server.shutdown()
        self.worker.join()
        self.server.server_close()

    def test_state_events_and_recent_scans_preserve_response_and_cursor(self):
        response = {"run_id": "run-2", "events": [{"sequence": 7}, {"sequence": 7}]}
        self.server.response = response
        self.assertEqual(self.client.get_state(), response)
        self.assertEqual(self.client.get_events(after_sequence=6), response)
        self.assertEqual(self.client.get_events(), response)
        self.assertEqual(self.client.get_recent_scans(limit=3), response)
        self.assertEqual(self.client.get_recent_scans(), response)
        paths = [urlsplit(call[1]) for call in self.server.calls]
        self.assertEqual([path.path for path in paths], [
            "/api/state", "/api/events", "/api/events",
            "/api/equipment/scan/recent", "/api/equipment/scan/recent",
        ])
        self.assertEqual([parse_qs(path.query) for path in paths[1:]], [
            {"after_sequence": ["6"]}, {"after_sequence": ["-1"]},
            {"limit": ["3"]}, {"limit": ["5"]},
        ])
        self.assertTrue(all(call[0] == "GET" and call[2] is None for call in self.server.calls))

    def test_scan_handles_created_status_and_preserves_explicit_timestamp(self):
        self.server.status = 201
        self.server.response = {"scan_id": "SC-1", "equipment_id": "GR-01"}
        timestamp = "2026-10-02T07:00:00+00:00"
        self.assertEqual(self.client.send_scan("GR", 0.95, "pi-01", ts=timestamp), self.server.response)
        self.assertEqual(self.server.calls[0][:3], ("POST", "/api/equipment/scan", {
            "class": "GR", "conf": 0.95, "device_id": "pi-01", "ts": timestamp,
        }))
        self.assertIn("application/json", self.server.calls[0][3])
        self.client.send_scan("GR", 0.95, "pi-01")
        generated = datetime.fromisoformat(self.server.calls[1][2]["ts"].replace("Z", "+00:00"))
        self.assertIsNotNone(generated.utcoffset())
        self.assertEqual(generated.utcoffset().total_seconds(), 0)

    def test_query_unicode_and_optional_equipment_selectors(self):
        self.assertEqual(self.client.query("분쇄기 상태는?", equipment_id="GR-01", k=3), self.server.response)
        self.client.query("점검 사항", scan_id="SC-1")
        self.client.query("현재 상태")
        self.assertEqual([call[:3] for call in self.server.calls], [
            ("POST", "/api/query", {"question": "분쇄기 상태는?", "equipment_id": "GR-01", "k": 3}),
            ("POST", "/api/query", {"question": "점검 사항", "scan_id": "SC-1", "k": 5}),
            ("POST", "/api/query", {"question": "현재 상태", "k": 5}),
        ])
        with self.assertRaises(ValueError):
            self.client.query("질문", equipment_id="GR-01", scan_id="SC-1")
        self.assertEqual(len(self.server.calls), 3)

    def test_handover_explicit_retry_keeps_same_id_and_memo(self):
        self.server.response = {"handover_id": "HO-1", "duplicate": False}
        self.assertEqual(self.client.save_handover("HO-1", "교대 전 점검"), self.server.response)
        self.server.response = {"handover_id": "HO-1", "duplicate": True}
        self.assertTrue(self.client.save_handover("HO-1", "교대 전 점검")["duplicate"])
        expected = ("POST", "/api/handover", {"handover_id": "HO-1", "memo_text": "교대 전 점검"})
        self.assertEqual([call[:3] for call in self.server.calls], [expected, expected])

    def test_http_errors_keep_status_without_retrying_posts(self):
        for status in (400, 409):
            with self.subTest(status=status):
                self.server.status = status
                self.server.response = {"error": "입력 오류"}
                count = len(self.server.calls)
                with self.assertRaises(HTTPClientError) as caught:
                    self.client.save_handover("HO-1", "점검")
                self.assertEqual(caught.exception.status_code, status)
                self.assertEqual(len(self.server.calls), count + 1)

    def test_post_disconnect_is_reported_without_automatic_resend(self):
        self.server.disconnect = True
        with self.assertRaises(HTTPClientError) as caught:
            self.client.send_scan("GR", 0.95, "pi-01")
        self.assertIsNone(caught.exception.status_code)
        self.assertEqual(len(self.server.calls), 1)

    def test_bad_json_or_non_object_response_is_reported(self):
        for body in (b"not JSON", b"[]", b"null", b"\xff"):
            with self.subTest(body=body):
                self.server.raw_response = body
                with self.assertRaises(HTTPClientError) as caught:
                    self.client.get_state()
                self.assertIsNone(caught.exception.status_code)

    def test_timeout_is_reported_without_resending(self):
        self.server.delay = 0.1
        client = MesHTTPClient(self.url, timeout=0.01, query_timeout=0.01)
        with self.assertRaises(HTTPClientError) as caught:
            client.query("현재 상태")
        self.assertIsNone(caught.exception.status_code)
        self.assertEqual(len(self.server.calls), 1)

    def test_query_uses_longer_timeout_than_sensor_reads(self):
        self.server.delay = 0.08
        client = MesHTTPClient(self.url, timeout=0.01, query_timeout=1)
        self.assertEqual(client.query("현재 상태"), self.server.response)
        with self.assertRaises(HTTPClientError) as caught:
            client.get_state()
        self.assertIsNone(caught.exception.status_code)

    def test_origin_and_timeout_validation(self):
        self.assertEqual(MesHTTPClient(self.url + "/").get_state(), self.server.response)
        for url in ("", "jetson-06:8000", "ftp://jetson-06", "http://", "http://host:wrong",
                    "http://host:70000", "http://host:0", "http://host/api", "http://host?q=x", "http://host/#x",
                    "http://host?", "http://host#", " http://host", "http://ho st",
                    "http://user:password@host"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                MesHTTPClient(url)
        for key in ("timeout", "query_timeout"):
            for value in (0, -1, float("inf"), float("nan"), True):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    MesHTTPClient(self.url, **{key: value})


if __name__ == "__main__":
    unittest.main()
