"""파이 PDA 앱: 화면은 로컬에서 주고 /api/* 는 Jetson으로 넘긴다."""

import http.client
import json
import os
import threading
import urllib.error
import urllib.request
from unittest.mock import patch
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
        assert b'id="loginName"' in body and b'id="loginId"' in body and b'id="faceVideo"' in body
        assert fetch(pda_url + "/static/pda.js")[0] == 200
        conn = http.client.HTTPConnection(pda_url.split("//")[1]); conn.request("GET", "/")
        res = conn.getresponse()  # 대시보드는 파이에 두지 않고 Jetson 화면으로 보낸다
        assert res.status == 302 and res.getheader("Location") == jetson_url + "/?from=pda"
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


def test_face_config_is_local(monkeypatch):
    jetson, jetson_url = serve(FakeJetson)
    pda, pda_url = serve(make_handler(jetson_url))
    try:
        monkeypatch.delenv("SHIFTLINK_FACE_BYPASS", raising=False)
        status, body = fetch(pda_url + "/api/face/config")
        got = json.loads(body)
        assert status == 200 and got == {"threshold": 0.363, "need": 3, "frames": 5, "bypass": False}
        monkeypatch.setenv("SHIFTLINK_FACE_BYPASS", "1")
        status, body = fetch(pda_url + "/api/face/config")
        assert status == 200 and json.loads(body)["bypass"] is True
        assert fetch(pda_url + "/api/state")[0] == 200
    finally:
        pda.shutdown(); jetson.shutdown()


def test_no_face_weights_in_git():
    import subprocess
    tracked = subprocess.check_output(["git", "ls-files"], text=True, cwd=os.path.dirname(__file__) + "/..")
    bad = [line for line in tracked.splitlines() if line.endswith((".onnx", ".npz", ".engine"))]
    assert bad == []


def test_face_frame_is_local_and_rejects_unknown_id():
    jetson, jetson_url = serve(FakeJetson)
    pda, pda_url = serve(make_handler(jetson_url))
    try:
        status, body = fetch(pda_url + "/api/face/frame", b"")
        assert status == 400 and "이미지" in json.loads(body)["error"]
        req = urllib.request.Request(
            pda_url + "/api/face/frame", data=b"not-a-jpeg",
            headers={"Content-Type": "image/jpeg", "X-Employee-Id": "NO-SUCH"},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                status, body = res.status, res.read()
        except urllib.error.HTTPError as err:
            status, body = err.code, err.read()
        assert status == 404 and "등록" in json.loads(body)["error"]
        status, _ = fetch(pda_url + "/api/state")
        assert status == 200  # 얼굴 경로는 Jetson 프록시를 타지 않는다
    finally:
        pda.shutdown(); jetson.shutdown()


def test_pda_exit_stays_local():
    called = []
    jetson, jetson_url = serve(FakeJetson)
    pda, pda_url = serve(make_handler(jetson_url, on_exit=lambda: called.append(1)))
    try:
        status, body = fetch(pda_url + "/api/pda/exit", b"{}")
        assert status == 200 and json.loads(body)["ok"] is True
        for _ in range(20):
            if called:
                break
            threading.Event().wait(0.05)
        assert called == [1]
        assert fetch(pda_url + "/api/state")[0] == 200
    finally:
        pda.shutdown(); jetson.shutdown()


def test_jetson_down_is_502():
    pda, pda_url = serve(make_handler("http://127.0.0.1:9"))
    try:
        status, body = fetch(pda_url + "/api/state")
        assert status == 502 and "Jetson" in json.loads(body)["error"]
    finally:
        pda.shutdown()


def test_sensor_timeout_is_short_but_query_keeps_llm_budget():
    pda, pda_url = serve(make_handler("http://jetson:8000"))
    try:
        real_open = urllib.request.urlopen
        with patch("shiftlink.pda.__main__.urllib.request.urlopen", side_effect=TimeoutError) as upstream:
            for path, expected in [("/api/state", 8), ("/api/query?x=1", 180)]:
                req = urllib.request.Request(pda_url + path, data=b"{}" if "query" in path else None)
                try:
                    real_open(req, timeout=5)
                except urllib.error.HTTPError as err:
                    assert err.code == 502
                else:
                    raise AssertionError("timeout must become HTTP 502")
                assert upstream.call_args.kwargs["timeout"] == expected
    finally:
        pda.shutdown()


def test_restart_page_relaunches_the_kiosk_app():
    jetson, jetson_url = serve(FakeJetson)
    called = []
    pda, pda_url = serve(make_handler(jetson_url, on_restart=lambda: called.append(1)))
    try:
        status, body = fetch(pda_url + "/pda/restart")
        assert status == 200 and "다시 시작".encode() in body
    finally:
        pda.shutdown(); jetson.shutdown()
    assert called == [1]


def test_face_camera_state_is_visible_to_screen_switching():
    """pda.js 의 faceRun 은 최상위에 있어야 show()→stopFaceCamera()가 오류 없이 돈다(10/7 키오스크 멈춤)."""
    import subprocess
    result = subprocess.run(["node", "tests/pda_face_camera.cjs"], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
