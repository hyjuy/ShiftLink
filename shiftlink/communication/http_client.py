"""Small HTTP client shared by Pi recognition and Python PDA programs."""

import json
import math
from datetime import datetime, timezone
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import ProxyHandler, Request, build_opener


class HTTPClientError(Exception):
    """An HTTP rejection or failed request; status is None without an HTTP error."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class MesHTTPClient:
    def __init__(self, base_url: str, timeout: float = 5.0, query_timeout: float = 125.0):
        try:
            url = urlsplit(base_url)
            valid = (url.scheme in ("http", "https") and url.hostname
                     and url.username is None and url.password is None
                     and url.path in ("", "/") and not url.query and not url.fragment)
            port = url.port
        except (TypeError, ValueError, AttributeError):
            raise ValueError("base_url must be an HTTP(S) origin without credentials") from None
        if not valid or (port is not None and port == 0) or "?" in base_url or "#" in base_url or any(char.isspace() for char in base_url):
            raise ValueError("base_url must be an HTTP(S) origin without credentials, path, query or fragment")
        for value in (timeout, query_timeout):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError("timeouts must be positive finite numbers")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.query_timeout = query_timeout
        # Local-device requests must not go through a configured internet proxy.
        self._opener = build_opener(ProxyHandler({}))

    def _request(self, path: str, payload: dict | None = None, *, timeout: float | None = None) -> dict:
        data = None if payload is None else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        request = Request(self.base_url + path, data=data, headers={
            "Accept": "application/json", **({"Content-Type": "application/json; charset=utf-8"} if data is not None else {})
        })
        try:
            with self._opener.open(request, timeout=self.timeout if timeout is None else timeout) as response:
                body = response.read()
        except HTTPError as error:
            with error:
                detail = error.read().decode("utf-8", errors="replace")
            raise HTTPClientError(f"HTTP {error.code}: {detail or error.reason}", error.code) from error
        except (URLError, OSError, HTTPException) as error:
            raise HTTPClientError(f"HTTP request failed: {error}") from error
        try:
            result = json.loads(body)
        except (ValueError, UnicodeError) as error:
            raise HTTPClientError("Server returned invalid JSON") from error
        if not isinstance(result, dict):
            raise HTTPClientError("Server JSON response must be an object")
        return result

    def get_state(self) -> dict:
        return self._request("/api/state")

    def get_events(self, after_sequence: int = -1) -> dict:
        return self._request("/api/events?" + urlencode({"after_sequence": after_sequence}))

    def get_recent_scans(self, limit: int = 5) -> dict:
        return self._request("/api/equipment/scan/recent?" + urlencode({"limit": limit}))

    def send_scan(self, label: str, confidence: float, device_id: str, ts: str | None = None) -> dict:
        return self._request("/api/equipment/scan", {
            "class": label, "conf": confidence, "device_id": device_id,
            "ts": datetime.now(timezone.utc).isoformat() if ts is None else ts,
        })

    def query(self, question: str, equipment_id: str | None = None, scan_id: str | None = None, k: int = 5) -> dict:
        if equipment_id is not None and scan_id is not None:
            raise ValueError("select equipment_id or scan_id, not both")
        payload = {"question": question, "k": k}
        if equipment_id is not None:
            payload["equipment_id"] = equipment_id
        if scan_id is not None:
            payload["scan_id"] = scan_id
        return self._request("/api/query", payload, timeout=self.query_timeout)

    def save_handover(self, handover_id: str, memo_text: str) -> dict:
        # Caller keeps this ID on explicit retransmission; POSTs are never retried here.
        return self._request("/api/handover", {"handover_id": handover_id, "memo_text": memo_text})
