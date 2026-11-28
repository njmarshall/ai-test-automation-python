"""
local_sandbox.py
----------------
Starts a local FastAPI sandbox (payments, scheduling, availability,
notification) in a background thread for tests, without the three
habits that made them flaky.

Before (found November 27, 2026 by running the suite in shuffled order):
  1. Fixed ports (8001, 8002, 8003). When a module-scoped server was torn
     down and started again, the new server raced the old one for the same
     port. Parallel workers would collide the same way.
  2. time.sleep(0.5) as "readiness". A guess, not a check. On a slow CI
     runner the first test could arrive before the server was listening.
  3. Teardown that only set should_exit and never waited for the thread,
     so the port could still be held when the next server started.
  Symptoms: payments tests hit httpx.ConnectError "Connection refused"
  during setup in 2 of 3 shuffled runs and on every parallel run. The
  patient scheduling oracle never stopped its servers at all, so a
  second start failed with "address already in use" and its tests
  silently passed against the old server.

Now:
  1. The OS picks a free port (bind to port 0), so servers never collide.
  2. Readiness is uvicorn's own `started` flag, polled with a deadline,
     and a server thread that dies early raises a clear error.
  3. Teardown waits for the thread to exit and closes the socket.
"""

from __future__ import annotations

import socket
import threading
import time
from contextlib import contextmanager
from typing import Iterator

import uvicorn

STARTUP_TIMEOUT_S = 10.0
SHUTDOWN_TIMEOUT_S = 5.0


@contextmanager
def run_sandbox(app) -> Iterator[str]:
    """Run `app` on a free localhost port; yield its base URL."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]

    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()

    deadline = time.monotonic() + STARTUP_TIMEOUT_S
    while not server.started:
        if not thread.is_alive():
            sock.close()
            raise RuntimeError(f"local sandbox exited before startup on port {port}")
        if time.monotonic() > deadline:
            server.should_exit = True
            thread.join(SHUTDOWN_TIMEOUT_S)
            sock.close()
            raise RuntimeError(f"local sandbox not ready after {STARTUP_TIMEOUT_S}s on port {port}")
        time.sleep(0.01)

    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(SHUTDOWN_TIMEOUT_S)
        sock.close()
