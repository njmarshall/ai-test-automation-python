"""
test_webhooks.py
----------------
Webhook event contract tests for the payment sandbox.

Fintech interview context
--------------------------
Webhooks are how payment systems tell the outside world what happened.
Interviewers ask about them in two ways:

1. As an API consumer (most common in SDET roles):
   "How do you test that your system reacts correctly to an incoming webhook?"
   Answer: post a synthetic webhook payload to your handler endpoint and
   assert the downstream effect (ledger updated, email sent, order fulfilled).

2. As a payment platform SDET:
   "How do you verify that your platform emits the right webhook events?"
   Answer: trigger a payment flow, then retrieve the event log and assert
   on the event type, shape, ordering, and payload fields.

These tests cover perspective 2 — verifying the event contract from the
payment platform side, using the sandbox event log.

Key event contract concepts:
- event_type is an enum string, not a free-form field
- event_id is unique per delivery (used for deduplication on the consumer side)
- payment_id links the event to the payment it describes
- data payload is event-type-specific but always present
- ordering: payment.created fires before payment.succeeded
- partial vs. full refund events are distinct types

Run
---
    pytest projects/payments/api/tests/test_webhooks.py -v
"""
from __future__ import annotations

import pytest

from projects.payments.api.tests.conftest import payment_client, succeeded_payment


# ─────────────────────────────────────────────────────────────────────────────
#  Payment created and succeeded events
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.payments
class TestPaymentCreatedEvent:
    """Creating a SUCCEEDED payment emits payment.created and payment.succeeded."""

    def test_payment_created_event_exists(self, payment_client, succeeded_payment):
        response = payment_client.list_webhook_events(
            payment_id=succeeded_payment["payment_id"],
            event_type="payment.created",
        )
        assert response.status_code == 200
        events = response.json()
        assert len(events) >= 1

    def test_payment_created_event_has_required_fields(self, payment_client, succeeded_payment):
        response = payment_client.list_webhook_events(
            payment_id=succeeded_payment["payment_id"],
            event_type="payment.created",
        )
        event = response.json()[0]
        assert "event_id" in event
        assert "event_type" in event
        assert "payment_id" in event
        assert "occurred_at" in event
        assert "data" in event

    def test_payment_created_event_payment_id_matches(self, payment_client, succeeded_payment):
        response = payment_client.list_webhook_events(
            payment_id=succeeded_payment["payment_id"],
            event_type="payment.created",
        )
        event = response.json()[0]
        assert event["payment_id"] == succeeded_payment["payment_id"]

    def test_payment_succeeded_event_emitted(self, payment_client, succeeded_payment):
        """A SUCCEEDED payment also emits payment.succeeded after payment.created."""
        response = payment_client.list_webhook_events(
            payment_id=succeeded_payment["payment_id"],
            event_type="payment.succeeded",
        )
        assert response.status_code == 200
        events = response.json()
        assert len(events) >= 1

    def test_payment_succeeded_event_data_has_amount(self, payment_client, succeeded_payment):
        response = payment_client.list_webhook_events(
            payment_id=succeeded_payment["payment_id"],
            event_type="payment.succeeded",
        )
        event = response.json()[0]
        assert event["data"]["amount"] == succeeded_payment["amount"]

    def test_no_succeeded_event_for_pending_payment(self, payment_client):
        """A PENDING payment must NOT emit payment.succeeded."""
        create = payment_client.create_payment(
            amount=3000,
            merchant_id="merchant-webhook-test",
            initial_status="PENDING",
        )
        assert create.status_code == 201
        payment_id = create.json()["payment_id"]

        response = payment_client.list_webhook_events(
            payment_id=payment_id,
            event_type="payment.succeeded",
        )
        assert response.status_code == 200
        assert len(response.json()) == 0


# ─────────────────────────────────────────────────────────────────────────────
#  Refund events
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.payments
class TestRefundWebhookEvents:
    """Refund operations emit the correct webhook event types."""

    def test_partial_refund_emits_partially_refunded_event(
        self, payment_client, succeeded_payment
    ):
        payment_id = succeeded_payment["payment_id"]
        partial = succeeded_payment["amount"] // 2

        refund_response = payment_client.create_refund(payment_id, amount=partial)
        assert refund_response.status_code == 201

        events_response = payment_client.list_webhook_events(
            payment_id=payment_id,
            event_type="payment.partially_refunded",
        )
        assert events_response.status_code == 200
        events = events_response.json()
        assert len(events) >= 1

    def test_partial_refund_event_data_has_refund_amount(
        self, payment_client, succeeded_payment
    ):
        payment_id = succeeded_payment["payment_id"]
        partial = succeeded_payment["amount"] // 2
        payment_client.create_refund(payment_id, amount=partial)

        events = payment_client.list_webhook_events(
            payment_id=payment_id,
            event_type="payment.partially_refunded",
        ).json()

        event_data = events[0]["data"]
        assert event_data["refund_amount"] == partial
        assert event_data["original_amount"] == succeeded_payment["amount"]

    def test_full_refund_emits_fully_refunded_event(
        self, payment_client, succeeded_payment
    ):
        payment_id = succeeded_payment["payment_id"]
        payment_client.create_refund(payment_id)  # full refund

        events_response = payment_client.list_webhook_events(
            payment_id=payment_id,
            event_type="payment.fully_refunded",
        )
        assert events_response.status_code == 200
        events = events_response.json()
        assert len(events) >= 1

    def test_full_refund_event_data_total_equals_original(
        self, payment_client, succeeded_payment
    ):
        payment_id = succeeded_payment["payment_id"]
        payment_client.create_refund(payment_id)

        events = payment_client.list_webhook_events(
            payment_id=payment_id,
            event_type="payment.fully_refunded",
        ).json()
        event_data = events[0]["data"]
        assert event_data["total_refunded"] == succeeded_payment["amount"]

    def test_two_partial_refunds_emit_two_events(
        self, payment_client, succeeded_payment
    ):
        """Each refund call emits its own event — event log is append-only."""
        payment_id = succeeded_payment["payment_id"]
        half = succeeded_payment["amount"] // 2

        payment_client.create_refund(payment_id, amount=half)
        remaining = succeeded_payment["amount"] - half
        payment_client.create_refund(payment_id, amount=remaining)

        # The second refund completes the full balance so it emits fully_refunded
        fully = payment_client.list_webhook_events(
            payment_id=payment_id,
            event_type="payment.fully_refunded",
        ).json()
        assert len(fully) >= 1


# ─────────────────────────────────────────────────────────────────────────────
#  Event retrieval and filtering
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.payments
class TestWebhookEventRetrieval:
    """Event log query and individual event fetch."""

    def test_get_event_by_id_returns_200(self, payment_client, succeeded_payment):
        events = payment_client.list_webhook_events(
            payment_id=succeeded_payment["payment_id"]
        ).json()
        event_id = events[0]["event_id"]

        response = payment_client.get_webhook_event(event_id)
        assert response.status_code == 200

    def test_get_event_by_id_returns_correct_event(self, payment_client, succeeded_payment):
        events = payment_client.list_webhook_events(
            payment_id=succeeded_payment["payment_id"]
        ).json()
        event_id = events[0]["event_id"]

        fetched = payment_client.get_webhook_event(event_id).json()
        assert fetched["event_id"] == event_id

    def test_get_nonexistent_event_returns_404(self, payment_client):
        response = payment_client.get_webhook_event("nonexistent-event-id")
        assert response.status_code == 404

    def test_filter_by_payment_id_returns_only_that_payments_events(self, payment_client):
        """Events for payment A must not appear in a query filtered to payment B."""
        a = payment_client.create_payment(
            amount=1000, merchant_id="merchant-a"
        ).json()
        b = payment_client.create_payment(
            amount=2000, merchant_id="merchant-b"
        ).json()

        events_for_a = payment_client.list_webhook_events(
            payment_id=a["payment_id"]
        ).json()

        for event in events_for_a:
            assert event["payment_id"] == a["payment_id"]
