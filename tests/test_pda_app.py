"""파이 PDA 앱: 화면은 로컬에서 주고 /api/* 는 Jetson으로 넘긴다."""

import http.client
import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from shiftlink.pda.__main__ import make_handler


class FakeJetson(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return

    def _reply(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._reply(200 if self.path.startswith("/api/state") else 404, {"path": self.path})

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self._reply(201, {"path": self.path, "got": json.loads(body), "ct": self.headers["Content-Type"]})


def serve(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"


def fetch(url, data=None):
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def test_pages_local_and_api_proxied():
    jetson, jetson_url = serve(FakeJetson)
    pda, pda_url = serve(make_handler(jetson_url))
    try:
        status, body = fetch(pda_url + "/pda.html")
        assert status == 200 and b"/static/pda.js" in body and b'href="/"' in body
        assert fetch(pda_url + "/static/pda.js")[0] == 200
        conn = http.client.HTTPConnection(pda_url.split("//")[1]); conn.request("GET", "/")
        res = conn.getresponse()  # 대시보드는 파이에 두지 않고 Jetson 화면으로 보낸다
        assert res.status == 302 and res.getheader("Location") == jetson_url + "/"
        conn.close()
        assert fetch(pda_url + "/static/../server.py")[0] == 404  # 화면 파일만 준다

        status, body = fetch(pda_url + "/api/state?x=1")
        assert status == 200 and json.loads(body)["path"] == "/api/state?x=1"
        assert fetch(pda_url + "/api/nope")[0] == 404  # Jetson 응답 코드를 그대로 전달

        status, body = fetch(pda_url + "/api/equipment/scan", json.dumps({"class": "HPU"}).encode())
        got = json.loads(body)
        assert status == 201 and got["got"] == {"class": "HPU"} and got["ct"] == "application/json"
    finally:
        pda.shutdown(); jetson.shutdown()


def test_jetson_down_is_502():
    pda, pda_url = serve(make_handler("http://127.0.0.1:9"))
    try:
        status, body = fetch(pda_url + "/api/state")
        assert status == 502 and "Jetson" in json.loads(body)["error"]
    finally:
        pda.shutdown()
