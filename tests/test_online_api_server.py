from __future__ import annotations

import contextlib
import json
import socket
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from online_api_server import OnlineApiHandler
from online_backend import OnlineBackend


@contextlib.contextmanager
def _serve_backend(db_path: Path):
    backend = OnlineBackend(db_path)

    class BoundHandler(OnlineApiHandler):
        pass

    BoundHandler.backend = backend

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    host, port = sock.getsockname()
    sock.close()

    server = ThreadingHTTPServer((host, port), BoundHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)


def _request(method: str, url: str, payload: dict | None = None):
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url=url, data=body, method=method, headers=headers)
    return urlopen(req)


def test_get_response_includes_cors_headers(tmp_path: Path):
    with _serve_backend(tmp_path / "api.db") as base_url:
        with _request("GET", f"{base_url}/health") as resp:
            assert resp.status == 200
            assert resp.headers.get("Access-Control-Allow-Origin") == "*"
            assert "GET" in str(resp.headers.get("Access-Control-Allow-Methods"))


def test_options_preflight_returns_204_with_cors_headers(tmp_path: Path):
    with _serve_backend(tmp_path / "api.db") as base_url:
        with _request("OPTIONS", f"{base_url}/health") as resp:
            assert resp.status == 204
            assert resp.headers.get("Access-Control-Allow-Origin") == "*"
            assert "POST" in str(resp.headers.get("Access-Control-Allow-Methods"))


def test_rate_limit_returns_429_when_exceeded(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(OnlineApiHandler, "RATE_LIMIT_WINDOW_S", 120.0)
    monkeypatch.setattr(OnlineApiHandler, "RATE_LIMIT_PER_IP", 2)
    OnlineApiHandler._ip_hits.clear()
    OnlineApiHandler._player_hits.clear()

    with _serve_backend(tmp_path / "api.db") as base_url:
        with _request("GET", f"{base_url}/health") as first:
            assert first.status == 200
        with _request("GET", f"{base_url}/health") as second:
            assert second.status == 200

        with pytest.raises(HTTPError) as exc:
            _request("GET", f"{base_url}/health")
        assert exc.value.code == 429
        exc.value.close()
