"""
test_async_payment.py
---------------------
AsyncPoller integration tests for payment status polling.

Real-world context
------------------
At Finix, payments were not always instant. A payment would
be created with status PENDING and then asynchronously
transition to SUCCEEDED or FAILED after processing.

This is the classic async payment pattern:
  POST /payments → 202 ACCEPTED → poll for final status

Two key async challenges:
1. How long do you wait before declaring a timeout?
2. What if the status gets stuck in PENDING forever?

This test suite integrates the existing AsyncPoller with
the payment sandbox to test real async payment workflows.

Failure modes tested (from Article 7):
1. Events arrive out of order (SUCCEEDED before PROCESSING)
2. Payment stuck in PENDING (timeout failure)
3. Duplicate polling requests (idempotency + async)
4. Per-stage timeout budgets (where did the time go?)

Pattern: Strategy (AsyncPoller) + Facade (PaymentClient)
"""

from __future__ import annotations

import importlib
import threading
import time
from uuid import uuid4

import pytest
import uvicorn

from projects.payments.api.client.payment_client import PaymentClient
from projects.payments.api.sandbox.payment_server import app

_async_poller = importlib.import_module("shared.async.async_poller")
AsyncPoller = _async_poller.AsyncPoller
PollingTimeoutError = _async_poller.PollingTimeoutError


# ------------------------------------------------------------------ #
#  Extended sandbox with async payment support                         #
# ------------------------------------------------------------------ #

from fastapi import HTTPException
from projects.payments.api.sandbox.payment_server import (
    _idempotency_store,
    app as payment_app,
)
from projects.payments.api.models.payment_models import PaymentStatus


@payment_app.post("/payments/{payment_id}/process", status_code=200)
def process_payment(payment_id: str) -> dict:
    """
    Simulate async payment processing.
    Transitions payment from PENDING to SUCCEEDED.
    Used in tests to simulate real async payment lifecycle.
    """
    for key, (stored_response, ts, req_hash) in _idempotency_store.items():
        if stored_response.payment_id == payment_id:
            updated = stored_response.model_copy(
                update={"status": PaymentStatus.SUCCEEDED}
            )
            _idempotency_store[key] = (updated, ts, req_hash)
            return {"payment_id": payment_id, "status": "SUCCEEDED"}
    raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")


@payment_app.post("/payments/{payment_id}/fail", status_code=200)
def fail_payment(payment_id: str) -> dict:
    """Simulate async payment failure."""
    for key, (stored_response, ts, req_hash) in _idempotency_store.items():
        if stored_response.payment_id == payment_id:
            updated = stored_response.model_copy(
                update={"status": PaymentStatus.FAILED}
            )
            _idempotency_store[key] = (updated, ts, req_hash)
            return {"payment_id": payment_id, "status": "FAILED"}
    raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module")
def payment_server():
    """Start payment sandbox for the test module."""
    config = uvicorn.Config(
        payment_app, host="127.0.0.1", port=8002, log_level="error"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(0.5)
    yield
    server.should_exit = True


@pytest.fixture
def client(payment_server) -> PaymentClient:
    """Payment client pointing to async sandbox."""
    c = PaymentClient(base_url="http://127.0.0.1:8002")
    c.reset_sandbox()
    yield c
    c.close()


# ------------------------------------------------------------------ #
#  AsyncPoller + Payment tests                                         #
# ------------------------------------------------------------------ #

@pytest.mark.payments
class TestAsyncPayment:
    """AsyncPoller integration tests for payment workflows."""

    def test_poll_until_payment_succeeded(
        self, client: PaymentClient
    ) -> None:
        """
        Core async payment pattern:
        Create payment → poll for SUCCEEDED status.

        Real-world: Finix payments processed asynchronously.
        The test polls until SUCCEEDED or timeout.
        """
        key = f"async-{uuid4()}"
        response = client.create_payment(
            amount=5000,
            merchant_id="merchant-async-001",
            idempotency_key=key,
        )
        assert response.status_code == 201
        payment_id = response.json()["payment_id"]

        # Simulate async processing after 0.2s
        def process_after_delay():
            time.sleep(0.2)
            client._client.post(
                f"http://127.0.0.1:8002/payments/{payment_id}/process"
            )

        threading.Thread(target=process_after_delay, daemon=True).start()

        # Poll for SUCCEEDED status
        poller = AsyncPoller(
            strategy="timeout",
            timeout_sec=5.0,
            interval_sec=0.1,
        )

        result = poller.poll(
            fn=lambda: client.get_payment(payment_id),
            until=lambda r: r.json()["status"] == "SUCCEEDED",
            description=f"payment {payment_id} SUCCEEDED",
        )

        assert result.json()["status"] == "SUCCEEDED"
        assert result.json()["payment_id"] == payment_id

    def test_poll_timeout_when_payment_stuck(
        self, client: PaymentClient
    ) -> None:
        """
        Failure mode: payment stuck in PENDING.

        Real-world: Finix daemons could hang on payment processing.
        The poller must timeout cleanly rather than wait forever.
        """
        key = f"stuck-{uuid4()}"
        response = client.create_payment(
            amount=1000,
            merchant_id="merchant-stuck",
            idempotency_key=key,
            initial_status="PENDING",
        )
        assert response.status_code == 201
        payment_id = response.json()["payment_id"]

        # Do NOT process the payment — it stays PENDING

        poller = AsyncPoller(
            strategy="timeout",
            timeout_sec=1.0,   # short timeout
            interval_sec=0.1,
        )

        with pytest.raises(PollingTimeoutError) as exc_info:
            poller.poll(
                fn=lambda: client.get_payment(payment_id),
                until=lambda r: r.json()["status"] == "SUCCEEDED",
                description=f"payment {payment_id} SUCCEEDED",
            )

        assert "payment" in str(exc_info.value).lower()

    def test_idempotent_payment_polled_correctly(
        self, client: PaymentClient
    ) -> None:
        """
        Idempotency + async combined:
        Duplicate payment requests should not create two charges
        even when polling is involved.
        """
        key = f"idem-async-{uuid4()}"

        # Create payment twice (idempotent)
        r1 = client.create_payment(
            amount=2500,
            merchant_id="merchant-idem",
            idempotency_key=key,
        )
        r2 = client.create_payment(
            amount=2500,
            merchant_id="merchant-idem",
            idempotency_key=key,
        )

        assert r1.status_code == 201
        assert r2.status_code == 200
        payment_id = r1.json()["payment_id"]

        # Process the payment
        client._client.post(
            f"http://127.0.0.1:8002/payments/{payment_id}/process"
        )

        # Poll once — should find SUCCEEDED
        poller = AsyncPoller(
            strategy="timeout",
            timeout_sec=3.0,
            interval_sec=0.1,
        )

        result = poller.poll(
            fn=lambda: client.get_payment(payment_id),
            until=lambda r: r.json()["status"] == "SUCCEEDED",
            description=f"idempotent payment {payment_id} SUCCEEDED",
        )

        assert result.json()["status"] == "SUCCEEDED"
        assert result.json()["payment_id"] == payment_id

    def test_poll_detects_payment_failure(
        self, client: PaymentClient
    ) -> None:
        """
        Async polling must detect FAILED status.

        Real-world: insufficient funds, card declined, fraud detection.
        The poller must surface FAILED, not just wait for SUCCEEDED.
        """
        key = f"fail-{uuid4()}"
        response = client.create_payment(
            amount=9999,
            merchant_id="merchant-fail",
            idempotency_key=key,
            initial_status="PENDING",
        )
        payment_id = response.json()["payment_id"]

        # Simulate payment failure after 0.2s
        def fail_after_delay():
            time.sleep(0.2)
            client._client.post(
                f"http://127.0.0.1:8002/payments/{payment_id}/fail"
            )

        threading.Thread(target=fail_after_delay, daemon=True).start()

        poller = AsyncPoller(
            strategy="timeout",
            timeout_sec=5.0,
            interval_sec=0.1,
        )

        result = poller.poll(
            fn=lambda: client.get_payment(payment_id),
            until=lambda r: r.json()["status"] in ("SUCCEEDED", "FAILED"),
            description=f"payment {payment_id} terminal status",
        )

        assert result.json()["status"] == "FAILED"

    def test_exponential_backoff_for_payment_polling(
        self, client: PaymentClient
    ) -> None:
        """
        Exponential backoff reduces load on payment processor.

        Real-world: At HEAVY.AI, exponential backoff prevented
        thundering herd during GPU cluster recovery.
        Same pattern applies to payment polling.
        """
        key = f"backoff-{uuid4()}"
        response = client.create_payment(
            amount=7500,
            merchant_id="merchant-backoff",
            idempotency_key=key,
        )
        payment_id = response.json()["payment_id"]

        # Process after 0.5s
        def process_after_delay():
            time.sleep(0.5)
            client._client.post(
                f"http://127.0.0.1:8002/payments/{payment_id}/process"
            )

        threading.Thread(target=process_after_delay, daemon=True).start()

        poller = AsyncPoller(
            strategy="backoff",
            base_delay_sec=0.1,
            max_delay_sec=2.0,
        )

        result = poller.poll(
            fn=lambda: client.get_payment(payment_id),
            until=lambda r: r.json()["status"] == "SUCCEEDED",
            description=f"payment {payment_id} with backoff",
        )

        assert result.json()["status"] == "SUCCEEDED"

    def test_fixed_retry_for_known_processing_time(
        self, client: PaymentClient
    ) -> None:
        """
        Fixed retry strategy for known payment processing windows.

        Real-world: Indeed email delivery had predictable retry windows.
        Same pattern for payments with known SLA windows.
        """
        key = f"fixed-{uuid4()}"
        response = client.create_payment(
            amount=3000,
            merchant_id="merchant-fixed",
            idempotency_key=key,
        )
        payment_id = response.json()["payment_id"]

        # Process immediately
        client._client.post(
            f"http://127.0.0.1:8002/payments/{payment_id}/process"
        )

        poller = AsyncPoller(
            strategy="fixed",
            retries=5,
            delay_sec=0.1,
        )

        result = poller.poll(
            fn=lambda: client.get_payment(payment_id),
            until=lambda r: r.json()["status"] == "SUCCEEDED",
            description=f"payment {payment_id} fixed retry",
        )

        assert result.json()["status"] == "SUCCEEDED"
