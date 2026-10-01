"""
Flex Split Payment Domain Models
---------------------------------
Flex is a chartered bank that allows renters to split monthly rent into two
installments (1st and 15th). Flex pays the landlord the full rent amount on
the due date regardless of whether the renter has completed their installments.
This is the core chartered-bank guarantee: Flex absorbs the credit risk.
"""

from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import uuid


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    WAIVED = "WAIVED"


class DisbursementStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class PlanStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    DELINQUENT = "DELINQUENT"
    CANCELLED = "CANCELLED"


class InstallmentNumber(int, Enum):
    FIRST = 1
    SECOND = 2


# ---------------------------------------------------------------------------
# Core domain models
# ---------------------------------------------------------------------------

class Installment(BaseModel):
    """One of the two renter payments that together make up a monthly rent."""
    installment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str
    installment_number: InstallmentNumber
    amount_cents: int                          # e.g. 125000 = $1,250.00
    due_date: date
    status: PaymentStatus = PaymentStatus.PENDING
    attempt_count: int = 0
    last_attempted_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    idempotency_key: Optional[str] = None     # caller-supplied dedup key
    late_fee_cents: int = 0


class SplitPaymentPlan(BaseModel):
    """
    A renter's monthly payment plan. Flex splits the rent into two installments:
      - Installment 1: due on the 1st of the month  (55% by default)
      - Installment 2: due on the 15th of the month (45% by default)
    Flex guarantees landlord disbursement on rent_due_date regardless of
    installment status, because Flex is a chartered bank and absorbs credit risk.
    """
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    renter_id: str
    landlord_id: str
    property_id: str
    monthly_rent_cents: int                    # total monthly rent in cents
    rent_due_date: date                        # date landlord expects payment
    installments: List[Installment] = Field(default_factory=list)
    status: PlanStatus = PlanStatus.ACTIVE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    credit_float_cents: int = 0               # Flex's current exposure in cents

    @field_validator("monthly_rent_cents")
    @classmethod
    def rent_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("monthly_rent_cents must be positive")
        return v


class LandlordDisbursement(BaseModel):
    """
    The full-rent payment Flex sends to the landlord/property management company.
    Sent on rent_due_date regardless of renter installment status.
    This is the chartered-bank guarantee.
    """
    disbursement_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str
    landlord_id: str
    amount_cents: int
    scheduled_date: date
    status: DisbursementStatus = DisbursementStatus.SCHEDULED
    sent_at: Optional[datetime] = None
    ach_reference: Optional[str] = None       # ACH trace number


class CreditFloatEntry(BaseModel):
    """
    Tracks Flex's credit exposure when a renter installment has not been
    collected but the landlord disbursement has gone out.
    A chartered bank must reconcile this nightly.
    """
    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str
    renter_id: str
    amount_cents: int
    reason: str                                # e.g. "INSTALLMENT_1_FAILED"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    resolved: bool = False


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class CreatePlanRequest(BaseModel):
    renter_id: str
    landlord_id: str
    property_id: str
    monthly_rent_cents: int
    rent_due_date: date
    idempotency_key: Optional[str] = None


class CreatePlanResponse(BaseModel):
    plan_id: str
    installments: List[Installment]
    disbursement: LandlordDisbursement
    message: str


class ProcessInstallmentRequest(BaseModel):
    idempotency_key: str                       # required — prevents double charge
    force_failure: bool = False               # test hook: simulate ACH failure


class ProcessInstallmentResponse(BaseModel):
    installment_id: str
    status: PaymentStatus
    amount_cents: int
    late_fee_cents: int
    message: str


class PlanSummaryResponse(BaseModel):
    plan: SplitPaymentPlan
    disbursement: LandlordDisbursement
    credit_float: List[CreditFloatEntry]
    renter_balance_due_cents: int              # sum of unpaid installments


class DisbursementTriggerResponse(BaseModel):
    disbursement_id: str
    status: DisbursementStatus
    amount_cents: int
    ach_reference: str
    message: str
