"""PDA 앱 실행. 로컬 서버가 화면 파일(shiftlink/mes/web)을 주고 /api/* 는 Jetson으로 넘긴다.
화면은 Chromium 앱 창(주소창 없음, 전체 화면)으로 띄우고, 창을 닫으면 앱도 끝난다.

    python -m shiftlink.pda [--jetson http://jetson-06.tail0a6af3.ts.net:8000] [--port 8080] [--scale 2] [--no-window]

화면 코드(pda.js)는 같은 주소의 /api/... 를 부르므로, 이 프록시 덕분에 화면 코드를 바꾸지 않는다.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# PyInstaller 실행파일이면 묶인 임시 폴더, 아니면 저장소의 shiftlink/mes/web
WEB = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2])) / "shiftlink" / "mes" / "web"
PAGES = {"/": "pda.html", "/pda.html": "pda.html", "/static/pda.js": "pda.js"}


def make_handler(jetson: str, web: Path = WEB) -> type[BaseHTTPRequestHandler]:
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
                with urllib.request.urlopen(req, timeout=60) as res:  # 질의(LLM)는 오래 걸릴 수 있다
                    self._send(res.status, res.read(), res.headers.get("Content-Type", "application/json"))
            except urllib.error.HTTPError as err:
                self._send(err.code, err.read(), err.headers.get("Content-Type", "application/json"))
            except (urllib.error.URLError, TimeoutError, OSError) as err:
                msg = json.dumps({"error": f"Jetson 연결 실패: {err}"}, ensure_ascii=False).encode()
                self._send(502, msg, "application/json; charset=utf-8")

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path.startswith("/api/"):
                self._proxy(); return
            name = PAGES.get(path)
            if name is None:
                self._send(404, b"not found", "text/plain; charset=utf-8"); return
            kind = "text/html" if name.endswith(".html") else "text/javascript"
            self._send(200, (web / name).read_bytes(), f"{kind}; charset=utf-8")

        def do_POST(self) -> None:  # noqa: N802
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
    # labwc에서는 --kiosk만으로 일반 창이 떠서 --app·--start-fullscreen을 같이 준다.
    # scale: PDA는 세로 휴대폰 폭 기준이라 2560x1600 모니터에서 2가 높이에 맞다.
    # 전용 프로필: 데스크톱 Chromium에 남은 창 크기를 물려받으면 화면보다 크게 떠서 아래가 잘린다.
    profile = Path.home() / "shiftlink" / "data" / "chromium"
    return subprocess.call([
        "chromium", f"--user-data-dir={profile}", "--ozone-platform=wayland", f"--force-device-scale-factor={scale}",
        "--lang=ko", "--disable-features=Translate", "--kiosk", "--start-fullscreen",
        "--noerrdialogs", "--no-first-run", "--password-store=basic", f"--app={url}",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(prog="shiftlink-pda")
    parser.add_argument("--jetson", default="http://jetson-06.tail0a6af3.ts.net:8000", help="Jetson MES API 주소")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--scale", type=float, default=2.0, help="화면 배율 (모니터에 맞춰 조정)")
    parser.add_argument("--no-window", action="store_true", help="서버만 띄운다 (개발·점검용)")
    args = parser.parse_args()
    jetson = args.jetson.rstrip("/")

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(jetson))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{args.port}/pda.html"
    print(f"PDA: {url} → API: {jetson}", flush=True)
    if args.no_window:
        threading.Event().wait()
    wait_for(jetson + "/api/state")
    sys.exit(open_window(url, args.scale))


if __name__ == "__main__":
    main()
