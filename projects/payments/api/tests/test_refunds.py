"""
test_refunds.py
---------------
Refund (reversal) contract tests for the payment sandbox.

Fintech interview context
--------------------------
Refunds are one of the most tested areas in payments interviews.
Key concepts examiners probe:

1. Status gate: only SUCCEEDED payments can be refunded.
   A PENDING or FAILED payment cannot be reversed yet.

2. Full refund: amount omitted — the entire remaining balance
   is returned to the customer.

3. Partial refund: amount specified — only that amount is returned.
   The payment remains in SUCCEEDED state with a reduced effective balance.

4. Over-refund prevention: cumulative refunds cannot exceed the
   original payment amount. A second refund that would breach the cap
   must be rejected with 422.

5. Idempotency of refund_id: each refund gets its own ID so that
   retry-safe refund flows can dedup on the refund, not the payment.

6. Webhook events: every refund transition must emit a structured event
   (payment.partially_refunded or payment.fully_refunded) so that
   downstream systems (ledger, notification service) are notified.

Run
---
    pytest projects/payments/api/tests/test_refunds.py -v
"""
from __future__ import annotations

import pytest

from projects.payments.api.tests.conftest import payment_client, succeeded_payment


# ─────────────────────────────────────────────────────────────────────────────
#  Happy path
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.payments
class TestFullRefund:
    """A SUCCEEDED payment can be fully refunded in one call."""

    def test_full_refund_returns_201(self, payment_client, succeeded_payment):
        response = payment_client.create_refund(succeeded_payment["payment_id"])
        assert response.status_code == 201

    def test_full_refund_amount_matches_payment(self, payment_client, succeeded_payment):
        response = payment_client.create_refund(succeeded_payment["payment_id"])
        refund = response.json()
        assert refund["amount"] == succeeded_payment["amount"]

    def test_full_refund_has_succeeded_status(self, payment_client, succeeded_payment):
        response = payment_client.create_refund(succeeded_payment["payment_id"])
        refund = response.json()
        assert refund["status"] == "SUCCEEDED"

    def test_full_refund_has_refund_id(self, payment_client, succeeded_payment):
        response = payment_client.create_refund(succeeded_payment["payment_id"])
        refund = response.json()
        assert "refund_id" in refund
        assert len(refund["refund_id"]) > 0

    def test_full_refund_currency_matches_payment(self, payment_client, succeeded_payment):
        response = payment_client.create_refund(succeeded_payment["payment_id"])
        refund = response.json()
        assert refund["currency"] == succeeded_payment["currency"]


@pytest.mark.payments
class TestPartialRefund:
    """A partial refund returns only the requested amount."""

    def test_partial_refund_returns_201(self, payment_client, succeeded_payment):
        partial = succeeded_payment["amount"] // 2
        response = payment_client.create_refund(succeeded_payment["payment_id"], amount=partial)
        assert response.status_code == 201

    def test_partial_refund_amount_is_exact(self, payment_client, succeeded_payment):
        partial = succeeded_payment["amount"] // 2
        response = payment_client.create_refund(succeeded_payment["payment_id"], amount=partial)
        assert response.json()["amount"] == partial

    def test_second_partial_refund_succeeds_within_balance(
        self, payment_client, succeeded_payment
    ):
        """Two partial refunds are both accepted when combined <= original amount."""
        payment_id = succeeded_payment["payment_id"]
        half = succeeded_payment["amount"] // 2
        r1 = payment_client.create_refund(payment_id, amount=half)
        assert r1.status_code == 201

        # Refund remaining balance
        remaining = succeeded_payment["amount"] - half
        r2 = payment_client.create_refund(payment_id, amount=remaining)
        assert r2.status_code == 201

    def test_refund_with_reason_is_stored(self, payment_client, succeeded_payment):
        response = payment_client.create_refund(
            succeeded_payment["payment_id"],
            amount=100,
            reason="Customer requested cancellation",
        )
        refund = response.json()
        assert refund["reason"] == "Customer requested cancellation"


# ─────────────────────────────────────────────────────────────────────────────
#  Error cases
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.payments
class TestRefundErrorCases:
    """Refund attempts that must be rejected."""

    def test_refund_nonexistent_payment_returns_404(self, payment_client):
        response = payment_client.create_refund("nonexistent-payment-id")
        assert response.status_code == 404

    def test_refund_pending_payment_returns_409(self, payment_client):
        """A PENDING payment cannot be refunded — adjudication not complete."""
        create = payment_client.create_payment(
            amount=5000,
            merchant_id="merchant-refund-test",
            initial_status="PENDING",
        )
        assert create.status_code == 201
        payment_id = create.json()["payment_id"]

        refund = payment_client.create_refund(payment_id)
        assert refund.status_code == 409
        body = refund.json()
        assert "PAYMENT_NOT_REFUNDABLE" in str(body)

    def test_over_refund_returns_422(self, payment_client, succeeded_payment):
        """A refund that exceeds the original amount is rejected."""
        over_amount = succeeded_payment["amount"] + 1
        response = payment_client.create_refund(
            succeeded_payment["payment_id"], amount=over_amount
        )
        assert response.status_code == 422
        body = response.json()
        assert "REFUND_EXCEEDS_BALANCE" in str(body)

    def test_cumulative_over_refund_returns_422(self, payment_client, succeeded_payment):
        """Two refunds whose combined total exceeds the original are rejected on the second."""
        payment_id = succeeded_payment["payment_id"]
        full = succeeded_payment["amount"]

        # First refund for the full amount
        r1 = payment_client.create_refund(payment_id, amount=full)
        assert r1.status_code == 201

        # Second refund — nothing left to refund
        r2 = payment_client.create_refund(payment_id, amount=1)
        assert r2.status_code == 422

    def test_list_refunds_for_payment(self, payment_client, succeeded_payment):
        """list_refunds returns every refund issued for a payment."""
        payment_id = succeeded_payment["payment_id"]
        payment_client.create_refund(payment_id, amount=100)
        payment_client.create_refund(payment_id, amount=200)

        response = payment_client.list_refunds(payment_id)
        assert response.status_code == 200
        refunds = response.json()
        assert len(refunds) == 2
        amounts = {r["amount"] for r in refunds}
        assert amounts == {100, 200}
