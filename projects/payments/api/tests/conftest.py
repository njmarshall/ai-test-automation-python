"""
conftest.py — payments domain shared fixtures
----------------------------------------------
Shared pytest fixtures for all tests under projects/payments/api/tests/.

Server lifecycle
----------------
payment_server  — module-scoped: starts the FastAPI sandbox once per module
payment_client  — function-scoped: provides a clean PaymentClient,
                  resets sandbox state before each test
succeeded_payment — function-scoped: creates one SUCCEEDED payment and
                    returns its response dict; used by refund and webhook tests

Port: 8001 (same as existing test_idempotency.py; module-scoped server
      prevents conflicts when tests run in the same pytest session)
"""
from __future__ import annotations

import threading
import time
from uuid import uuid4

import pytest
import uvicorn

from projects.payments.api.client.payment_client import PaymentClient
from projects.payments.api.sandbox.payment_server import app


# ── server lifecycle ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def payment_server():
    """Start the payment sandbox once per test module."""
    config = uvicorn.Config(app, host="127.0.0.1", port=8001, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(0.5)  # allow server to bind
    yield
    server.should_exit = True


# ── client ────────────────────────────────────────────────────────────────────

@pytest.fixture
def payment_client(payment_server) -> PaymentClient:
    """
    PaymentClient connected to the sandbox, with state reset before each test.

    Using function scope ensures every test starts with an empty event log
    and no prior payments, which makes event-count assertions reliable.
    """
    client = PaymentClient(base_url="http://127.0.0.1:8001")
    client.reset_sandbox()
    yield client
    client.close()


# ── test data ─────────────────────────────────────────────────────────────────

@pytest.fixture
def succeeded_payment(payment_client) -> dict:
    """
    Create one SUCCEEDED payment and return its response dict.

    Used by refund and webhook tests that need a payment already in
    SUCCEEDED state before the test body runs.

    Amount is fixed at 10000 cents ($100.00) so partial-refund arithmetic
    is predictable across all tests that use this fixture.
    """
    response = payment_client.create_payment(
        amount=10000,
        merchant_id="merchant-fixture",
        currency="USD",
        description="Fixture payment for refund/webhook tests",
    )
    assert response.status_code == 201, (
        f"succeeded_payment fixture failed: expected 201, got {response.status_code}"
    )
    return response.json()
