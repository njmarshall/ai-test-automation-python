"""
payment_client.py
-----------------
httpx client for the payment sandbox API.

Facade pattern: tests never touch raw httpx directly.
All payment operations go through PaymentClient.
"""

from __future__ import annotations

from typing import Optional
from uuid import uuid4

import httpx

from projects.payments.api.models.payment_models import (
    Currency,
    PaymentRequest,
    PaymentResponse,
)


class PaymentClient:
    """
    Facade over httpx for payment sandbox API calls.

    Example
    -------
        client = PaymentClient(base_url="http://localhost:8001")

        response = client.create_payment(
            amount=1000,
            currency="USD",
            merchant_id="merchant-123",
            idempotency_key="order-abc-001",
        )
        assert response.status_code == 201
    """

    def __init__(self, base_url: str = "http://localhost:8001") -> None:
        self._base_url = base_url.rstrip("/")
        self._client   = httpx.Client(timeout=10.0)

    # ── payments ─────────────────────────────────────────────────────

    def create_payment(
        self,
        amount:          int,
        merchant_id:     str,
        idempotency_key: Optional[str] = None,
        currency:        str = "USD",
        description:     str = "",
        use_header:      bool = True,
        initial_status:  Optional[str] = None,
    ) -> httpx.Response:
        """
        Create a payment.

        Parameters
        ----------
        amount:          amount in cents
        merchant_id:     merchant identifier
        idempotency_key: unique key per attempt (generated if not provided)
        currency:        ISO currency code
        description:     optional payment description
        use_header:      send key in X-Idempotency-Key header (recommended)
        initial_status:  status assigned at creation (test hook for async
                          workflows, e.g. "PENDING"); defaults to sandbox
                          behavior (SUCCEEDED) when omitted
        """
        key = idempotency_key or str(uuid4())

        payload = {
            "amount":          amount,
            "currency":        currency,
            "merchant_id":     merchant_id,
            "description":     description,
            "idempotency_key": key,
        }
        if initial_status is not None:
            payload["initial_status"] = initial_status

        headers = {}
        if use_header:
            headers["X-Idempotency-Key"] = key

        return self._client.post(
            f"{self._base_url}/payments",
            json=payload,
            headers=headers,
        )

    def get_payment(self, payment_id: str) -> httpx.Response:
        """Retrieve a payment by ID."""
        return self._client.get(f"{self._base_url}/payments/{payment_id}")

    def delete_payment(self, payment_id: str) -> httpx.Response:
        """Delete a payment (sandbox cleanup)."""
        return self._client.delete(f"{self._base_url}/payments/{payment_id}")

    # ── refunds ──────────────────────────────────────────────────────

    def create_refund(
        self,
        payment_id: str,
        amount:     Optional[int] = None,
        reason:     Optional[str] = None,
    ) -> httpx.Response:
        """
        Refund a payment.

        Parameters
        ----------
        payment_id: ID of the payment to refund
        amount:     amount in cents. Omit for a full refund.
        reason:     optional reason string (max 255 chars)
        """
        payload: dict = {}
        if amount is not None:
            payload["amount"] = amount
        if reason is not None:
            payload["reason"] = reason

        return self._client.post(
            f"{self._base_url}/payments/{payment_id}/refunds",
            json=payload,
        )

    def list_refunds(self, payment_id: str) -> httpx.Response:
        """List all refunds for a payment."""
        return self._client.get(
            f"{self._base_url}/payments/{payment_id}/refunds"
        )

    # ── webhooks ─────────────────────────────────────────────────────

    def list_webhook_events(
        self,
        payment_id:  Optional[str] = None,
        event_type:  Optional[str] = None,
    ) -> httpx.Response:
        """
        Retrieve webhook events from the sandbox event log.

        Parameters
        ----------
        payment_id: filter to events for a specific payment
        event_type: filter to a specific event type
                    e.g. "payment.succeeded", "payment.fully_refunded"
        """
        params: dict = {}
        if payment_id:
            params["payment_id"] = payment_id
        if event_type:
            params["event_type"] = event_type

        return self._client.get(
            f"{self._base_url}/webhooks/events",
            params=params,
        )

    def get_webhook_event(self, event_id: str) -> httpx.Response:
        """Retrieve a single webhook event by its event_id."""
        return self._client.get(
            f"{self._base_url}/webhooks/events/{event_id}"
        )

    # ── sandbox utilities ─────────────────────────────────────────────

    def reset_sandbox(self) -> httpx.Response:
        """Reset all sandbox state between tests."""
        return self._client.delete(f"{self._base_url}/sandbox/reset")

    def get_stats(self) -> httpx.Response:
        """Get sandbox statistics."""
        return self._client.get(f"{self._base_url}/sandbox/stats")

    def health(self) -> httpx.Response:
        """Health check."""
        return self._client.get(f"{self._base_url}/health")

    def close(self) -> None:
        self._client.close()
