"""파이 화면 서버 + Chromium 키오스크. 로컬 서버가 화면 파일(shiftlink/mes/web)을 주고 /api/* 는 Jetson으로 넘긴다.
화면: /pda.html (PDA, 기본) · / → Jetson MES 대시보드로 이동. 키오스크 창을 닫으면 앱도 끝난다.

    python -m shiftlink.pda [--jetson http://jetson-06.tail0a6af3.ts.net:8000] [--port 8080] [--page pda.html] [--scale 2] [--no-window]

화면 코드는 같은 주소의 /api/... 를 부르므로, 이 프록시 덕분에 화면 코드를 바꾸지 않는다.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "mes" / "web"
_MAX_FACE_JPEG = 1_500_000


def _face_bypass() -> bool:
    """모델이 없을 때 시연만. 서버는 127.0.0.1에만 열린다. 기본은 꺼져 있다."""
    return os.environ.get("SHIFTLINK_FACE_BYPASS") == "1"
# Jetson MES 서버(shiftlink/mes/server.py)와 같은 경로·파일
PAGES = {"/pda.html": "pda.html", "/static/pda.js": "pda.js"}
TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}


_window_proc: subprocess.Popen | None = None


def stop_kiosk() -> None:
    """키오스크 창을 닫고 이 프로세스를 끝낸다."""
    proc = _window_proc
    if proc is not None and proc.poll() is None:
        proc.terminate()
    os._exit(0)


def make_handler(jetson: str, web: Path = WEB, on_exit=None) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _proxy(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None
            req = urllib.request.Request(jetson + self.path, data=body, method=self.command)
            if self.headers.get("Content-Type"):
                req.add_header("Content-Type", self.headers["Content-Type"])
            try:
                with urllib.request.urlopen(req, timeout=180) as res:  # /api/query 는 Jetson LLM 답변이라 오래 걸릴 수 있다
                    self._send(res.status, res.read(), res.headers.get("Content-Type", "application/json"))
            except urllib.error.HTTPError as err:
                self._send(err.code, err.read(), err.headers.get("Content-Type", "application/json"))
            except (urllib.error.URLError, TimeoutError, OSError) as err:
                msg = json.dumps({"error": f"Jetson 연결 실패: {err}"}, ensure_ascii=False).encode()
                self._send(502, msg, "application/json; charset=utf-8")

        def _face_config(self) -> None:
            from shiftlink.face import DEFAULT_THRESHOLD, FACE_FRAMES, FACE_NEED
            body = {"threshold": DEFAULT_THRESHOLD, "need": FACE_NEED, "frames": FACE_FRAMES, "bypass": _face_bypass()}
            self._send(200, json.dumps(body).encode(), "application/json; charset=utf-8")

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path == "/api/face/config":
                self._face_config(); return
            if path.startswith("/api/"):
                self._proxy(); return
            if path in ("/", "/index.html"):  # MES 대시보드는 파이에 두지 않는다 — Jetson 최신 화면으로 보낸다
                self.send_response(302); self.send_header("Location", jetson + "/"); self.send_header("Content-Length", "0")
                self.end_headers(); return
            name = PAGES.get(path)
            if name is None:
                self._send(404, b"not found", "text/plain; charset=utf-8"); return
            self._send(200, (web / name).read_bytes(), f"{TYPES[Path(name).suffix]}; charset=utf-8")

        def _face_frame(self) -> None:
            """브라우저가 잡고 있는 카메라 프레임을 이 기기에서만 점수 낸다. Jetson으로 넘기지 않고 저장하지도 않는다."""
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > _MAX_FACE_JPEG:
                msg = json.dumps({"error": "이미지 크기가 맞지 않습니다"}, ensure_ascii=False).encode()
                self._send(400, msg, "application/json; charset=utf-8")
                return
            jpeg = self.rfile.read(length)
            employee_id = self.headers.get("X-Employee-Id", "")
            try:
                from shiftlink.face.verify import score_login_jpeg
                result = score_login_jpeg(jpeg, employee_id)
            except LookupError as err:
                msg = json.dumps({"error": str(err)}, ensure_ascii=False).encode()
                self._send(404, msg, "application/json; charset=utf-8")
            except ValueError as err:
                msg = json.dumps({"error": str(err)}, ensure_ascii=False).encode()
                self._send(400, msg, "application/json; charset=utf-8")
            except Exception as err:
                # 이미지는 로그에 남기지 않는다. 종류만 찍어 503 원인을 pda.log에서 본다.
                print(f"face frame {type(err).__name__}", file=sys.stderr, flush=True)
                msg = json.dumps({"error": "얼굴 모델을 열 수 없습니다", "bypass": _face_bypass()}, ensure_ascii=False).encode()
                self._send(503, msg, "application/json; charset=utf-8")
            else:
                self._send(200, json.dumps(result).encode(), "application/json; charset=utf-8")

        def _exit(self) -> None:
            self._send(200, b'{"ok":true}', "application/json")
            threading.Thread(target=on_exit or stop_kiosk, daemon=True).start()

        def do_POST(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path == "/api/pda/exit":
                self._exit(); return
            if path == "/api/face/frame":
                self._face_frame(); return
            if self.path.startswith("/api/"):
                self._proxy()
            else:
                self._send(404, b"not found", "text/plain; charset=utf-8")

    return Handler


def wait_for(url: str) -> None:
    """Jetson이 늦게 떠도 화면이 '데이터 로드 실패'로 멈추지 않게, 응답할 때까지 5초마다 기다린다."""
    while True:
        try:
            urllib.request.urlopen(url, timeout=5).close(); return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(5)


def open_window(url: str, scale: float) -> int:
    global _window_proc
    # labwc에서는 --kiosk만으로 일반 창이 떠서 --app·--start-fullscreen을 같이 준다.
    # scale: PDA는 세로 휴대폰 폭 기준이라 2560x1600 모니터에서 2가 높이에 맞다.
    # 전용 프로필: 데스크톱 Chromium에 남은 창 크기를 물려받으면 화면보다 크게 떠서 아래가 잘린다.
    profile = Path.home() / "shiftlink" / "data" / "chromium"
    # 리눅스 Chromium은 --lang 대신 LANGUAGE로 UI 언어를 정한다. 파이가 영어(en_GB)면 한국어 화면에 번역 팝업이 뜬다.
    env = {**os.environ, "LANGUAGE": "ko"}
    if shutil.which("ibus-daemon"):
        env.update(GTK_IM_MODULE="ibus", QT_IM_MODULE="ibus", XMODIFIERS="@im=ibus")
    _window_proc = subprocess.Popen([
        "chromium", f"--user-data-dir={profile}", "--ozone-platform=wayland", f"--force-device-scale-factor={scale}",
        "--lang=ko", "--disable-features=Translate",         "--kiosk", "--start-fullscreen",
        # 카메라 권한 창을 띄우지 않는다. 이 창은 127.0.0.1 페이지만 연다.
        "--use-fake-ui-for-media-stream",
        "--noerrdialogs", "--no-first-run", "--password-store=basic", f"--app={url}",
    ], env=env)
    return _window_proc.wait()


def main() -> None:
    parser = argparse.ArgumentParser(prog="shiftlink-pda")
    parser.add_argument("--jetson", default="http://jetson-06.tail0a6af3.ts.net:8000", help="Jetson MES API 주소")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--page", default="pda.html", help="키오스크로 열 화면 (pda.html=PDA, 빈 값=MES 대시보드)")
    parser.add_argument("--scale", type=float, default=2.0, help="화면 배율 (모니터에 맞춰 조정)")
    parser.add_argument("--no-window", action="store_true", help="서버만 띄운다 (개발·점검용)")
    args = parser.parse_args()
    jetson = args.jetson.rstrip("/")

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(jetson))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{args.port}/{args.page}"
    print(f"PDA: {url} → API: {jetson}", flush=True)
    if args.no_window:
        threading.Event().wait()
    wait_for(jetson + "/api/state")
    sys.exit(open_window(url, args.scale))


if __name__ == "__main__":
    main()
