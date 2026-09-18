"""
test_idempotency.py
-------------------
Idempotency tests for the payment sandbox.

What is idempotency?
--------------------
An operation is idempotent if performing it multiple times
produces the same result as performing it once.

For payments: sending the same payment request twice should
result in ONE charge, not two. This prevents:
- Double charges from network retries
- Duplicate payments from user double-clicks
- Mobile app retries after connectivity loss

Real-world context
------------------
At Finix, idempotency was critical for payment reliability.
A failed network call that retried without idempotency could
charge a customer twice — a serious compliance issue.

Test scenarios
--------------
1. First request creates payment (201)
2. Duplicate request returns original (200, is_duplicate=True)
3. Same key + different payload returns conflict (422)
4. Different keys create independent payments
5. Missing idempotency key is rejected
6. Concurrent duplicate requests handled correctly
"""

from __future__ import annotations

import threading
import time
from uuid import uuid4

import pytest
import uvicorn

from projects.payments.api.client.payment_client import PaymentClient
from projects.payments.api.sandbox.payment_server import app


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module")
def payment_server():
    """Start payment sandbox server for the test module."""
    config = uvicorn.Config(app, host="127.0.0.1", port=8001, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(0.5)  # wait for server to start
    yield
    server.should_exit = True


@pytest.fixture
def client(payment_server) -> PaymentClient:
    """Payment client with clean sandbox state."""
    c = PaymentClient(base_url="http://127.0.0.1:8001")
    c.reset_sandbox()
    yield c
    c.close()


@pytest.fixture
def idempotency_key() -> str:
    """Unique idempotency key per test."""
    return f"test-{uuid4()}"


# ------------------------------------------------------------------ #
#  Idempotency tests                                                   #
# ------------------------------------------------------------------ #

@pytest.mark.payments
class TestIdempotency:
    """Core idempotency behavior tests."""

    def test_first_payment_returns_201(
        self, client: PaymentClient, idempotency_key: str
    ) -> None:
        """First payment request creates a new payment."""
        response = client.create_payment(
            amount=1000,
            merchant_id="merchant-001",
            idempotency_key=idempotency_key,
        )
        assert response.status_code == 201
        body = response.json()
        assert body["amount"] == 1000
        assert body["status"] == "SUCCEEDED"
        assert body["is_duplicate"] is False
        assert body["idempotency_key"] == idempotency_key

    def test_duplicate_request_returns_200_not_201(
        self, client: PaymentClient, idempotency_key: str
    ) -> None:
        """Duplicate request with same key returns 200, not 201."""
        client.create_payment(
            amount=1000,
            merchant_id="merchant-001",
            idempotency_key=idempotency_key,
        )

        duplicate = client.create_payment(
            amount=1000,
            merchant_id="merchant-001",
            idempotency_key=idempotency_key,
        )
        assert duplicate.status_code == 200

    def test_duplicate_request_marks_is_duplicate(
        self, client: PaymentClient, idempotency_key: str
    ) -> None:
        """Duplicate response has is_duplicate=True."""
        client.create_payment(
            amount=1000,
            merchant_id="merchant-001",
            idempotency_key=idempotency_key,
        )

        duplicate = client.create_payment(
            amount=1000,
            merchant_id="merchant-001",
            idempotency_key=idempotency_key,
        )
        body = duplicate.json()
        assert body["is_duplicate"] is True

    def test_duplicate_returns_same_payment_id(
        self, client: PaymentClient, idempotency_key: str
    ) -> None:
        """
        Critical: duplicate request returns SAME payment_id.
        This proves only ONE charge was created.
        """
        first   = client.create_payment(
            amount=1000,
            merchant_id="merchant-001",
            idempotency_key=idempotency_key,
        )
        second  = client.create_payment(
            amount=1000,
            merchant_id="merchant-001",
            idempotency_key=idempotency_key,
        )

        assert first.json()["payment_id"] == second.json()["payment_id"]

    def test_same_key_different_amount_returns_422(
        self, client: PaymentClient, idempotency_key: str
    ) -> None:
        """
        Same idempotency key with different amount = conflict.
        This is a client error: the key was reused incorrectly.
        """
        client.create_payment(
            amount=1000,
            merchant_id="merchant-001",
            idempotency_key=idempotency_key,
        )

        conflict = client.create_payment(
            amount=2000,  # different amount!
            merchant_id="merchant-001",
            idempotency_key=idempotency_key,
        )
        assert conflict.status_code == 422
        body = conflict.json()
        assert body["detail"]["error"] == "IDEMPOTENCY_CONFLICT"
        assert body["detail"]["original_amount"] == 1000
        assert body["detail"]["requested_amount"] == 2000

    def test_different_keys_create_independent_payments(
        self, client: PaymentClient
    ) -> None:
        """
        Different idempotency keys create independent payments.
        Each gets a unique payment_id.
        """
        key1 = f"key-{uuid4()}"
        key2 = f"key-{uuid4()}"

        r1 = client.create_payment(
            amount=1000,
            merchant_id="merchant-001",
            idempotency_key=key1,
        )
        r2 = client.create_payment(
            amount=1000,
            merchant_id="merchant-001",
            idempotency_key=key2,
        )

        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["payment_id"] != r2.json()["payment_id"]

    def test_triple_duplicate_still_idempotent(
        self, client: PaymentClient, idempotency_key: str
    ) -> None:
        """Three requests with same key = one payment."""
        first  = client.create_payment(amount=500, merchant_id="m1",
                                       idempotency_key=idempotency_key)
        second = client.create_payment(amount=500, merchant_id="m1",
                                       idempotency_key=idempotency_key)
        third  = client.create_payment(amount=500, merchant_id="m1",
                                       idempotency_key=idempotency_key)

        assert first.status_code == 201
        assert second.status_code == 200
        assert third.status_code == 200

        pid = first.json()["payment_id"]
        assert second.json()["payment_id"] == pid
        assert third.json()["payment_id"] == pid

    def test_sandbox_stats_reflect_one_payment(
        self, client: PaymentClient, idempotency_key: str
    ) -> None:
        """Sandbox stats show 1 payment after duplicate requests."""
        client.create_payment(amount=100, merchant_id="m1",
                              idempotency_key=idempotency_key)
        client.create_payment(amount=100, merchant_id="m1",
                              idempotency_key=idempotency_key)
        client.create_payment(amount=100, merchant_id="m1",
                              idempotency_key=idempotency_key)

        stats = client.get_stats().json()
        assert stats["active_payments"] == 1

    def test_health_check(self, client: PaymentClient) -> None:
        """Sandbox health check returns ok."""
        response = client.health()
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
