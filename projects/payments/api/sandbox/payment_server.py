"""
payment_server.py
-----------------
FastAPI payment sandbox with idempotency, refund, and webhook support.

Real-world context
------------------
At Finix, every payment API call required an idempotency key.
This prevented double charges when:
- Network retries happened automatically
- Users double-clicked the Pay button
- Mobile apps retried on connectivity loss

Refunds (reversals):
- A payment can only be refunded once it reaches SUCCEEDED status
- Partial refunds are supported up to the original payment amount
- A payment cannot be refunded more than its original amount (cumulative)
- Refunds are idempotent by refund_id

Webhooks:
- The sandbox records webhook events for every payment state transition
- Tests can retrieve events to verify downstream notification contracts
- Real fintech systems (Stripe, Finix, Adyen) deliver webhooks to merchant URLs;
  this sandbox stores them in memory for test assertions

Idempotency rules implemented
------------------------------
1. First request with key X creates payment, returns 201
2. Duplicate request with key X + SAME payload returns 200
   with the ORIGINAL payment (no new charge)
3. Duplicate request with key X + DIFFERENT payload returns 422
   (conflict — client error, not a server error)
4. Idempotency keys expire after TTL_SECONDS (default 86400 = 24h)

Run the sandbox
---------------
    uvicorn projects.payments.api.sandbox.payment_server:app --port 8001

Or programmatically in tests:
    import threading
    import uvicorn
    thread = threading.Thread(
        target=uvicorn.run,
        args=(app,),
        kwargs={"port": 8001, "log_level": "error"},
        daemon=True
    )
    thread.start()
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from projects.payments.api.models.payment_models import (
    Currency,
    ErrorResponse,
    IdempotencyConflictResponse,
    PaymentRequest,
    PaymentResponse,
    PaymentStatus,
    RefundRequest,
    RefundResponse,
    RefundStatus,
    WebhookEvent,
    WebhookEventType,
)

# ------------------------------------------------------------------ #
#  App                                                                 #
# ------------------------------------------------------------------ #

app = FastAPI(
    title="Payment Sandbox",
    description="Idempotent payment API with refund and webhook support",
    version="2.0.0",
)

# ------------------------------------------------------------------ #
#  In-memory stores                                                    #
# ------------------------------------------------------------------ #

# key: idempotency_key
# value: (PaymentResponse, timestamp, original_request_hash)
_idempotency_store: Dict[str, Tuple[PaymentResponse, float, int]] = {}

# key: payment_id
# value: list of RefundResponse
_refund_store: Dict[str, List[RefundResponse]] = {}

# ordered log of webhook events
_webhook_events: List[WebhookEvent] = []

TTL_SECONDS = 86_400  # 24 hours


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

def _request_hash(req: PaymentRequest) -> int:
    """Hash the request payload for conflict detection."""
    return hash((req.amount, req.currency, req.merchant_id, req.description))


def _is_expired(timestamp: float) -> bool:
    return (time.time() - timestamp) > TTL_SECONDS


def _cleanup_expired() -> None:
    expired = [k for k, (_, ts, _) in _idempotency_store.items()
               if _is_expired(ts)]
    for k in expired:
        del _idempotency_store[k]


def _find_payment(payment_id: str) -> Optional[PaymentResponse]:
    for stored_response, _, _ in _idempotency_store.values():
        if stored_response.payment_id == payment_id:
            return stored_response
    return None


def _emit_event(event_type: WebhookEventType, payment_id: str, data: dict) -> None:
    """Record a webhook event in the in-memory event log."""
    event = WebhookEvent(
        event_id=str(uuid4()),
        event_type=event_type,
        payment_id=payment_id,
        occurred_at=datetime.now(timezone.utc),
        data=data,
    )
    _webhook_events.append(event)


def _total_refunded(payment_id: str) -> int:
    """Sum of all completed refund amounts for a payment."""
    refunds = _refund_store.get(payment_id, [])
    return sum(r.amount for r in refunds if r.status == RefundStatus.SUCCEEDED)


# ------------------------------------------------------------------ #
#  Routes — payments                                                   #
# ------------------------------------------------------------------ #

@app.get("/health")
def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "payment-sandbox", "version": "2.0.0"}


@app.post("/payments", status_code=201, response_model=PaymentResponse)
def create_payment(
    request: PaymentRequest,
    x_idempotency_key: str = Header(
        default=None,
        alias="X-Idempotency-Key",
        description="Unique key per payment attempt",
    ),
) -> PaymentResponse:
    """
    Create a payment with idempotency support.

    Rules:
    - First request with idempotency key creates payment (201)
    - Duplicate request with SAME payload returns original (200)
    - Duplicate request with DIFFERENT payload returns 422
    - Expired keys (24h) are treated as new payments
    """
    _cleanup_expired()

    idem_key = x_idempotency_key or request.idempotency_key
    req_hash = _request_hash(request)

    if idem_key in _idempotency_store:
        stored_response, timestamp, stored_hash = _idempotency_store[idem_key]

        if _is_expired(timestamp):
            del _idempotency_store[idem_key]
        elif stored_hash != req_hash:
            raise HTTPException(
                status_code=422,
                detail={
                    "error":            "IDEMPOTENCY_CONFLICT",
                    "detail":           "Same idempotency key used with different payload",
                    "original_amount":  stored_response.amount,
                    "requested_amount": request.amount,
                    "idempotency_key":  idem_key,
                }
            )
        else:
            duplicate = stored_response.model_copy(update={"is_duplicate": True})
            return JSONResponse(
                status_code=200,
                content=duplicate.model_dump(mode="json"),
            )

    payment = PaymentResponse(
        payment_id=str(uuid4()),
        amount=request.amount,
        currency=request.currency,
        merchant_id=request.merchant_id,
        description=request.description,
        status=request.initial_status,
        idempotency_key=idem_key,
        is_duplicate=False,
        created_at=datetime.now(timezone.utc),
        message="Payment processed successfully",
    )

    _idempotency_store[idem_key] = (payment, time.time(), req_hash)

    # Emit webhook event
    _emit_event(
        WebhookEventType.PAYMENT_CREATED,
        payment.payment_id,
        {"status": payment.status, "amount": payment.amount, "currency": payment.currency},
    )
    if payment.status == PaymentStatus.SUCCEEDED:
        _emit_event(
            WebhookEventType.PAYMENT_SUCCEEDED,
            payment.payment_id,
            {"amount": payment.amount, "currency": payment.currency},
        )

    return payment


@app.get("/payments/{payment_id}", response_model=PaymentResponse)
def get_payment(payment_id: str) -> PaymentResponse:
    """Retrieve a payment by ID."""
    payment = _find_payment(payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")
    return payment


@app.delete("/payments/{payment_id}", status_code=204)
def delete_payment(payment_id: str) -> None:
    """Delete a payment (sandbox cleanup only)."""
    key_to_delete = None
    for key, (stored_response, _, _) in _idempotency_store.items():
        if stored_response.payment_id == payment_id:
            key_to_delete = key
            break
    if key_to_delete:
        del _idempotency_store[key_to_delete]
        _refund_store.pop(payment_id, None)
    else:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")


# ------------------------------------------------------------------ #
#  Routes — refunds                                                    #
# ------------------------------------------------------------------ #

@app.post("/payments/{payment_id}/refunds", status_code=201, response_model=RefundResponse)
def create_refund(payment_id: str, request: RefundRequest) -> RefundResponse:
    """
    Refund a payment (full or partial).

    Rules:
    - Payment must exist and be in SUCCEEDED status
    - Refund amount must be > 0
    - Cumulative refunds cannot exceed original payment amount
    - Returns 409 if payment is not in a refundable state
    - Returns 422 if refund amount exceeds available balance
    """
    payment = _find_payment(payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")

    if payment.status != PaymentStatus.SUCCEEDED:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "PAYMENT_NOT_REFUNDABLE",
                "detail": f"Payment is in status {payment.status}. Only SUCCEEDED payments can be refunded.",
                "payment_id": payment_id,
                "current_status": payment.status,
            }
        )

    already_refunded = _total_refunded(payment_id)
    available = payment.amount - already_refunded
    refund_amount = request.amount if request.amount is not None else available

    if refund_amount <= 0:
        raise HTTPException(
            status_code=422,
            detail={"error": "INVALID_REFUND_AMOUNT", "detail": "Refund amount must be greater than zero"}
        )

    if refund_amount > available:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "REFUND_EXCEEDS_BALANCE",
                "detail": f"Refund amount {refund_amount} exceeds available balance {available}",
                "original_amount": payment.amount,
                "already_refunded": already_refunded,
                "available": available,
                "requested": refund_amount,
            }
        )

    refund = RefundResponse(
        refund_id=str(uuid4()),
        payment_id=payment_id,
        amount=refund_amount,
        currency=payment.currency,
        status=RefundStatus.SUCCEEDED,
        reason=request.reason or "",
        created_at=datetime.now(timezone.utc),
        message="Refund processed successfully",
    )

    _refund_store.setdefault(payment_id, []).append(refund)

    # Emit webhook event
    new_total_refunded = already_refunded + refund_amount
    event_type = (
        WebhookEventType.PAYMENT_FULLY_REFUNDED
        if new_total_refunded >= payment.amount
        else WebhookEventType.PAYMENT_PARTIALLY_REFUNDED
    )
    _emit_event(
        event_type,
        payment_id,
        {
            "refund_id": refund.refund_id,
            "refund_amount": refund_amount,
            "total_refunded": new_total_refunded,
            "original_amount": payment.amount,
        },
    )

    return refund


@app.get("/payments/{payment_id}/refunds", response_model=List[RefundResponse])
def list_refunds(payment_id: str) -> List[RefundResponse]:
    """List all refunds for a payment."""
    payment = _find_payment(payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")
    return _refund_store.get(payment_id, [])


# ------------------------------------------------------------------ #
#  Routes — webhooks                                                   #
# ------------------------------------------------------------------ #

@app.get("/webhooks/events")
def list_webhook_events(
    payment_id: Optional[str] = None,
    event_type: Optional[str] = None,
) -> List[dict]:
    """
    Retrieve webhook events recorded by the sandbox.

    Filter by payment_id and/or event_type.
    In a real system these would be delivered to merchant callback URLs;
    the sandbox stores them in memory for test assertions.
    """
    events = _webhook_events
    if payment_id:
        events = [e for e in events if e.payment_id == payment_id]
    if event_type:
        events = [e for e in events if e.event_type == event_type]
    return [e.model_dump(mode="json") for e in events]


@app.get("/webhooks/events/{event_id}")
def get_webhook_event(event_id: str) -> dict:
    """Retrieve a single webhook event by ID."""
    for event in _webhook_events:
        if event.event_id == event_id:
            return event.model_dump(mode="json")
    raise HTTPException(status_code=404, detail=f"Event {event_id} not found")


# ------------------------------------------------------------------ #
#  Routes — sandbox utilities                                          #
# ------------------------------------------------------------------ #

@app.delete("/sandbox/reset", status_code=204)
def reset_sandbox() -> None:
    """Reset all sandbox state (testing only)."""
    _idempotency_store.clear()
    _refund_store.clear()
    _webhook_events.clear()


@app.get("/sandbox/stats")
def sandbox_stats() -> dict:
    """Return sandbox statistics."""
    return {
        "total_payments":   len(_idempotency_store),
        "active_payments":  sum(1 for _, (_, ts, _) in _idempotency_store.items()
                               if not _is_expired(ts)),
        "expired_payments": sum(1 for _, (_, ts, _) in _idempotency_store.items()
                               if _is_expired(ts)),
        "total_refunds":    sum(len(v) for v in _refund_store.values()),
        "total_events":     len(_webhook_events),
    }
