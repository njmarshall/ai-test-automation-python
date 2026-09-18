"""
payment_server.py
-----------------
FastAPI payment sandbox with idempotency support.

Real-world context
------------------
At Finix, every payment API call required an idempotency key.
This prevented double charges when:
- Network retries happened automatically
- Users double-clicked the Pay button
- Mobile apps retried on connectivity loss

This sandbox implements the same pattern for testing purposes.

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
from typing import Dict, Tuple
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
)

# ------------------------------------------------------------------ #
#  App                                                                 #
# ------------------------------------------------------------------ #

app = FastAPI(
    title="Payment Sandbox",
    description="Idempotent payment API for testing",
    version="1.0.0",
)

# ------------------------------------------------------------------ #
#  In-memory store                                                     #
# ------------------------------------------------------------------ #

# key: idempotency_key
# value: (PaymentResponse, timestamp, original_request_hash)
_idempotency_store: Dict[str, Tuple[PaymentResponse, float, int]] = {}

TTL_SECONDS = 86_400  # 24 hours


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


# ------------------------------------------------------------------ #
#  Routes                                                              #
# ------------------------------------------------------------------ #

@app.get("/health")
def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "payment-sandbox"}


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

    # Use header key if provided, else fall back to body key
    idem_key = x_idempotency_key or request.idempotency_key
    req_hash = _request_hash(request)

    # Check idempotency store
    if idem_key in _idempotency_store:
        stored_response, timestamp, stored_hash = _idempotency_store[idem_key]

        if _is_expired(timestamp):
            # Expired — treat as new payment
            del _idempotency_store[idem_key]
        elif stored_hash != req_hash:
            # Same key, different payload — conflict
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
            # Same key, same payload — return original (idempotent)
            duplicate = stored_response.model_copy(update={"is_duplicate": True})
            return JSONResponse(
                status_code=200,
                content=duplicate.model_dump(mode="json"),
            )

    # Create new payment
    payment = PaymentResponse(
        payment_id=str(uuid4()),
        amount=request.amount,
        currency=request.currency,
        merchant_id=request.merchant_id,
        description=request.description,
        status=PaymentStatus.SUCCEEDED,
        idempotency_key=idem_key,
        is_duplicate=False,
        created_at=datetime.now(timezone.utc),
        message="Payment processed successfully",
    )

    _idempotency_store[idem_key] = (payment, time.time(), req_hash)
    return payment


@app.get("/payments/{payment_id}", response_model=PaymentResponse)
def get_payment(payment_id: str) -> PaymentResponse:
    """Retrieve a payment by ID."""
    for stored_response, _, _ in _idempotency_store.values():
        if stored_response.payment_id == payment_id:
            return stored_response
    raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")


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
    else:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")


@app.delete("/sandbox/reset", status_code=204)
def reset_sandbox() -> None:
    """Reset sandbox state (testing only)."""
    _idempotency_store.clear()


@app.get("/sandbox/stats")
def sandbox_stats() -> dict:
    """Return sandbox statistics."""
    return {
        "total_payments":   len(_idempotency_store),
        "active_payments":  sum(1 for _, (_, ts, _) in _idempotency_store.items()
                               if not _is_expired(ts)),
        "expired_payments": sum(1 for _, (_, ts, _) in _idempotency_store.items()
                               if _is_expired(ts)),
    }
