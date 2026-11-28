"""
conftest.py — payments domain shared fixtures
----------------------------------------------
Shared pytest fixtures for all tests under projects/payments/api/tests/.

Server lifecycle
----------------
payment_server    — session-scoped: starts the FastAPI sandbox once, on a
                    free port chosen by the OS (see shared/http/local_sandbox.py).
                    Yields the base URL.
payment_client    — function-scoped: a PaymentClient for that URL, with
                    sandbox state reset before each test.
succeeded_payment — function-scoped: creates one SUCCEEDED payment and
                    returns its response dict; used by refund and webhook tests
"""
from __future__ import annotations

import pytest

from projects.payments.api.client.payment_client import PaymentClient
from projects.payments.api.sandbox.payment_server import app
from shared.http.local_sandbox import run_sandbox


# ── server lifecycle ──────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def payment_server():
    """Start the payment sandbox once per session; yield its base URL."""
    with run_sandbox(app) as base_url:
        yield base_url


# ── client ────────────────────────────────────────────────────────────────────

@pytest.fixture
def payment_client(payment_server) -> PaymentClient:
    """
    PaymentClient connected to the sandbox, with state reset before each test.

    Using function scope ensures every test starts with an empty event log
    and no prior payments, which makes event-count assertions reliable.
    """
    client = PaymentClient(base_url=payment_server)
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
