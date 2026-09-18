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

    def create_payment(
        self,
        amount:          int,
        merchant_id:     str,
        idempotency_key: Optional[str] = None,
        currency:        str = "USD",
        description:     str = "",
        use_header:      bool = True,
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
        """
        key = idempotency_key or str(uuid4())

        payload = {
            "amount":          amount,
            "currency":        currency,
            "merchant_id":     merchant_id,
            "description":     description,
            "idempotency_key": key,
        }

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

    def reset_sandbox(self) -> httpx.Response:
        """Reset sandbox state between tests."""
        return self._client.delete(f"{self._base_url}/sandbox/reset")

    def get_stats(self) -> httpx.Response:
        """Get sandbox statistics."""
        return self._client.get(f"{self._base_url}/sandbox/stats")

    def health(self) -> httpx.Response:
        """Health check."""
        return self._client.get(f"{self._base_url}/health")

    def close(self) -> None:
        self._client.close()
