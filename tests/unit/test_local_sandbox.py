"""
test_local_sandbox.py
---------------------
Unit tests for shared.http.local_sandbox.run_sandbox, the helper that
replaced fixed ports and sleep-based readiness in the payments and
scheduling sandboxes. Loopback only, no external network.
"""

from __future__ import annotations

import socket
import time

import httpx
import pytest
import uvicorn
from fastapi import FastAPI

import shared.http.local_sandbox as local_sandbox
from shared.http.local_sandbox import run_sandbox

pytestmark = pytest.mark.unit


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/ping")
    def ping():
        return {"pong": True}

    return app


def _port(url: str) -> int:
    return int(url.rsplit(":", 1)[1])


def test_server_is_ready_when_the_context_opens():
    with run_sandbox(_app()) as url:
        # No sleep: the first request must succeed immediately.
        assert httpx.get(f"{url}/ping", timeout=2).json() == {"pong": True}


def test_two_sandboxes_get_different_free_ports():
    with run_sandbox(_app()) as a, run_sandbox(_app()) as b:
        assert _port(a) != _port(b)
        assert httpx.get(f"{a}/ping", timeout=2).status_code == 200
        assert httpx.get(f"{b}/ping", timeout=2).status_code == 200


def test_port_is_released_after_the_context_closes():
    with run_sandbox(_app()) as url:
        port = _port(url)
    with pytest.raises(httpx.ConnectError):
        httpx.get(f"{url}/ping", timeout=1)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("127.0.0.1", port))  # would fail if the old server still held it
    finally:
        s.close()


def test_server_that_dies_before_startup_raises_clearly(monkeypatch):
    monkeypatch.setattr(uvicorn.Server, "run", lambda self, sockets=None: None)
    with pytest.raises(RuntimeError, match="exited before startup"):
        with run_sandbox(_app()):
            pass


def test_server_that_never_becomes_ready_times_out_clearly(monkeypatch):
    def slow_run(self, sockets=None):
        while not self.should_exit:
            time.sleep(0.01)

    monkeypatch.setattr(uvicorn.Server, "run", slow_run)
    monkeypatch.setattr(local_sandbox, "STARTUP_TIMEOUT_S", 0.1)
    with pytest.raises(RuntimeError, match="not ready after"):
        with run_sandbox(_app()):
            pass
