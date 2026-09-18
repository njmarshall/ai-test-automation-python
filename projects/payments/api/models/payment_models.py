"""
payment_models.py
-----------------
Pydantic models for the payment sandbox.

Real-world context
------------------
At Finix, payment objects had strict validation rules.
A payment must have an amount, currency, and a unique
idempotency key to prevent duplicate charges.

Idempotency key rules:
- Must be a valid UUID
- Unique per merchant + amount combination
- Expires after 24 hours (configurable)
- Same key + same payload = same result (no new charge)
- Same key + different payload = 422 (conflict)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ------------------------------------------------------------------ #
#  Enums                                                               #
# ------------------------------------------------------------------ #

class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CAD = "CAD"


class PaymentStatus(str, Enum):
    PENDING    = "PENDING"
    SUCCEEDED  = "SUCCEEDED"
    FAILED     = "FAILED"
    DUPLICATE  = "DUPLICATE"


# ------------------------------------------------------------------ #
#  Request models                                                      #
# ------------------------------------------------------------------ #

class PaymentRequest(BaseModel):
    """
    Request to create a payment.

    The idempotency_key ensures that if this request is sent
    multiple times (e.g. due to network retry), only one payment
    is created. Subsequent requests with the same key return
    the original payment result without creating a new charge.
    """
    amount:           int           = Field(..., gt=0, description="Amount in cents")
    currency:         Currency      = Field(default=Currency.USD)
    merchant_id:      str           = Field(..., min_length=1)
    description:      str           = Field(default="")
    idempotency_key:  str           = Field(..., description="Unique key per payment attempt")
    initial_status:   PaymentStatus = Field(
        default=PaymentStatus.SUCCEEDED,
        description="Status assigned at creation (test hook for async workflows)",
    )

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("idempotency_key cannot be empty")
        if len(v) > 255:
            raise ValueError("idempotency_key cannot exceed 255 characters")
        return v.strip()

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: int) -> int:
        if v > 99_999_999:  # $999,999.99 max
            raise ValueError("amount exceeds maximum allowed value")
        return v


# ------------------------------------------------------------------ #
#  Response models                                                     #
# ------------------------------------------------------------------ #

class PaymentResponse(BaseModel):
    """
    Response from creating or retrieving a payment.

    The is_duplicate field indicates whether this response
    was returned from an existing idempotent record rather
    than creating a new payment.
    """
    payment_id:      str
    amount:          int
    currency:        Currency
    merchant_id:     str
    description:     str
    status:          PaymentStatus
    idempotency_key: str
    is_duplicate:    bool         = False
    created_at:      datetime
    message:         str          = ""


class ErrorResponse(BaseModel):
    """Standard error response."""
    error:   str
    detail:  str
    code:    str


class IdempotencyConflictResponse(BaseModel):
    """
    Returned when same idempotency key is used
    with a different payload — indicates a client error.
    """
    error:           str = "IDEMPOTENCY_CONFLICT"
    detail:          str
    original_amount: int
    requested_amount: int
    idempotency_key: str
