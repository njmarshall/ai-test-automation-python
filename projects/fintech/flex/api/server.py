"""
Flex Split Payment Mock Server
-------------------------------
Realistic FastAPI mock of Flex's core banking APIs.

Business rules encoded:
  1. Split calculation: installment 1 = ceil(rent * 0.55), installment 2 = remainder
  2. Due dates: installment 1 on rent_due_date - 14 days, installment 2 on rent_due_date - 1 day
  3. Late fee: $35 flat if paid after due_date (Flex published rate as of 2024)
  4. Landlord disbursement ALWAYS goes out on rent_due_date regardless of installment status
  5. Failed installment -> credit float entry created (chartered bank absorbs risk)
  6. Idempotency: same key on installment charge returns same result, no double-charge
  7. Delinquency: plan goes DELINQUENT if both installments fail
  8. Max 3 retry attempts per installment before marking FAILED permanently
"""

import math
import uuid
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Path, Body
from fastapi.responses import JSONResponse

from .models import (
    CreditFloatEntry,
    CreatePlanRequest,
    CreatePlanResponse,
    DisbursementStatus,
    DisbursementTriggerResponse,
    Installment,
    InstallmentNumber,
    LandlordDisbursement,
    PaymentStatus,
    PlanStatus,
    PlanSummaryResponse,
    ProcessInstallmentRequest,
    ProcessInstallmentResponse,
    SplitPaymentPlan,
)

app = FastAPI(
    title="Flex Split Payment API (Mock)",
    description="Chartered bank split-rent payment system. Renter pays twice; landlord always gets paid on time.",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# In-memory store (test-session scoped)
# ---------------------------------------------------------------------------
_plans: Dict[str, SplitPaymentPlan] = {}
_disbursements: Dict[str, LandlordDisbursement] = {}
_float_ledger: List[CreditFloatEntry] = []
_idempotency_cache: Dict[str, ProcessInstallmentResponse] = {}

# ---------------------------------------------------------------------------
# Business logic helpers
# ---------------------------------------------------------------------------

LATE_FEE_CENTS = 3500          # $35.00
MAX_RETRY_ATTEMPTS = 3
FIRST_INSTALLMENT_SPLIT = 0.55  # 55% on 1st installment


def _split_rent(monthly_rent_cents: int):
    """
    Returns (installment_1_cents, installment_2_cents).
    Installment 1 = ceil(rent * 55%), installment 2 = remainder.
    This ensures the two installments always sum to exactly monthly_rent_cents.
    """
    inst1 = math.ceil(monthly_rent_cents * FIRST_INSTALLMENT_SPLIT)
    inst2 = monthly_rent_cents - inst1
    return inst1, inst2


def _installment_due_dates(rent_due_date: date):
    """
    Installment 1 is due 14 days before rent_due_date.
    Installment 2 is due 1 day before rent_due_date.
    This gives Flex time to collect before disbursing.
    """
    due1 = rent_due_date - timedelta(days=14)
    due2 = rent_due_date - timedelta(days=1)
    return due1, due2


def _plan_delinquency_check(plan: SplitPaymentPlan) -> None:
    """Mark plan DELINQUENT if both installments are permanently FAILED."""
    failed = [i for i in plan.installments if i.status == PaymentStatus.FAILED]
    if len(failed) == 2:
        plan.status = PlanStatus.DELINQUENT


def _plan_completion_check(plan: SplitPaymentPlan) -> None:
    """Mark plan COMPLETED when both installments are SUCCEEDED."""
    succeeded = [i for i in plan.installments if i.status == PaymentStatus.SUCCEEDED]
    if len(succeeded) == 2:
        plan.status = PlanStatus.COMPLETED


def _balance_due(plan: SplitPaymentPlan) -> int:
    return sum(
        i.amount_cents + i.late_fee_cents
        for i in plan.installments
        if i.status not in (PaymentStatus.SUCCEEDED, PaymentStatus.WAIVED)
    )

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "service": "flex-split-payment-mock"}


@app.post("/v1/plans", response_model=CreatePlanResponse, status_code=201)
def create_plan(req: CreatePlanRequest):
    """
    Create a split payment plan for a renter.
    Generates two installments and schedules a landlord disbursement.
    Idempotent: same idempotency_key returns the same plan_id.
    """
    # Idempotency check at plan level
    if req.idempotency_key:
        existing = next(
            (p for p in _plans.values()
             if getattr(p, "_creation_key", None) == req.idempotency_key),
            None,
        )
        if existing:
            disb = _disbursements[existing.plan_id]
            return CreatePlanResponse(
                plan_id=existing.plan_id,
                installments=existing.installments,
                disbursement=disb,
                message="EXISTING_PLAN_RETURNED",
            )

    if req.monthly_rent_cents <= 0:
        raise HTTPException(status_code=422, detail="monthly_rent_cents must be positive")

    inst1_cents, inst2_cents = _split_rent(req.monthly_rent_cents)
    due1, due2 = _installment_due_dates(req.rent_due_date)

    plan = SplitPaymentPlan(
        renter_id=req.renter_id,
        landlord_id=req.landlord_id,
        property_id=req.property_id,
        monthly_rent_cents=req.monthly_rent_cents,
        rent_due_date=req.rent_due_date,
    )
    plan._creation_key = req.idempotency_key  # type: ignore[attr-defined]

    installment_1 = Installment(
        plan_id=plan.plan_id,
        installment_number=InstallmentNumber.FIRST,
        amount_cents=inst1_cents,
        due_date=due1,
    )
    installment_2 = Installment(
        plan_id=plan.plan_id,
        installment_number=InstallmentNumber.SECOND,
        amount_cents=inst2_cents,
        due_date=due2,
    )
    plan.installments = [installment_1, installment_2]

    disbursement = LandlordDisbursement(
        plan_id=plan.plan_id,
        landlord_id=req.landlord_id,
        amount_cents=req.monthly_rent_cents,
        scheduled_date=req.rent_due_date,
    )

    _plans[plan.plan_id] = plan
    _disbursements[plan.plan_id] = disbursement

    return CreatePlanResponse(
        plan_id=plan.plan_id,
        installments=plan.installments,
        disbursement=disbursement,
        message="PLAN_CREATED",
    )


@app.post(
    "/v1/plans/{plan_id}/installments/{installment_number}/charge",
    response_model=ProcessInstallmentResponse,
)
def charge_installment(
    plan_id: str = Path(...),
    installment_number: int = Path(..., ge=1, le=2),
    req: ProcessInstallmentRequest = Body(...),
):
    """
    Charge one installment from the renter's payment method.

    Idempotency: same idempotency_key always returns the same response.
    force_failure: test hook to simulate ACH failure.
    Late fee: applied if today > installment due_date.
    Max retries: 3 attempts before permanent FAILED.
    """
    plan = _plans.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    installment = next(
        (i for i in plan.installments if i.installment_number == installment_number),
        None,
    )
    if not installment:
        raise HTTPException(status_code=404, detail="Installment not found")

    # Idempotency check
    cache_key = f"{installment.installment_id}:{req.idempotency_key}"
    if req.idempotency_key and cache_key in _idempotency_cache:
        return _idempotency_cache[cache_key]

    # Guard: already terminal
    if installment.status in (PaymentStatus.SUCCEEDED, PaymentStatus.FAILED):
        msg = (
            "ALREADY_SUCCEEDED" if installment.status == PaymentStatus.SUCCEEDED
            else "MAX_RETRIES_EXCEEDED"
        )
        resp = ProcessInstallmentResponse(
            installment_id=installment.installment_id,
            status=installment.status,
            amount_cents=installment.amount_cents,
            late_fee_cents=installment.late_fee_cents,
            message=msg,
        )
        if req.idempotency_key:
            _idempotency_cache[cache_key] = resp
        return resp

    # Guard: max retries exceeded (already at limit from prior attempts)
    if installment.attempt_count >= MAX_RETRY_ATTEMPTS and installment.status != PaymentStatus.SUCCEEDED:
        installment.status = PaymentStatus.FAILED
        installment.failure_reason = "MAX_RETRIES_EXCEEDED"
        _plan_delinquency_check(plan)
        resp = ProcessInstallmentResponse(
            installment_id=installment.installment_id,
            status=PaymentStatus.FAILED,
            amount_cents=installment.amount_cents,
            late_fee_cents=installment.late_fee_cents,
            message="MAX_RETRIES_EXCEEDED",
        )
        if req.idempotency_key:
            _idempotency_cache[cache_key] = resp
        return resp

    # Late fee
    today = date.today()
    late_fee = LATE_FEE_CENTS if today > installment.due_date else 0
    installment.late_fee_cents = late_fee

    # Process
    installment.attempt_count += 1
    installment.last_attempted_at = datetime.utcnow()

    if req.force_failure:
        installment.status = (
            PaymentStatus.FAILED
            if installment.attempt_count >= MAX_RETRY_ATTEMPTS
            else PaymentStatus.RETRYING
        )
        installment.failure_reason = "ACH_RETURNED_R01"  # insufficient funds

        # Create credit float entry if landlord disbursement already sent
        disb = _disbursements.get(plan_id)
        if disb and disb.status in (DisbursementStatus.SENT, DisbursementStatus.CONFIRMED):
            entry = CreditFloatEntry(
                plan_id=plan_id,
                renter_id=plan.renter_id,
                amount_cents=installment.amount_cents,
                reason=f"INSTALLMENT_{installment_number}_FAILED",
            )
            _float_ledger.append(entry)
            plan.credit_float_cents += installment.amount_cents

        _plan_delinquency_check(plan)
        resp = ProcessInstallmentResponse(
            installment_id=installment.installment_id,
            status=installment.status,
            amount_cents=installment.amount_cents,
            late_fee_cents=late_fee,
            message=f"ACH_RETURNED_R01 (attempt {installment.attempt_count}/{MAX_RETRY_ATTEMPTS})",
        )
    else:
        installment.status = PaymentStatus.SUCCEEDED
        installment.paid_at = datetime.utcnow()
        installment.failure_reason = None
        _plan_completion_check(plan)
        resp = ProcessInstallmentResponse(
            installment_id=installment.installment_id,
            status=PaymentStatus.SUCCEEDED,
            amount_cents=installment.amount_cents,
            late_fee_cents=late_fee,
            message="INSTALLMENT_SUCCEEDED",
        )

    if req.idempotency_key:
        _idempotency_cache[cache_key] = resp
    return resp


@app.post(
    "/v1/plans/{plan_id}/disburse",
    response_model=DisbursementTriggerResponse,
)
def trigger_disbursement(plan_id: str = Path(...)):
    """
    Trigger landlord disbursement for a plan.
    This represents Flex's chartered-bank guarantee: the landlord is paid
    in full on rent_due_date regardless of renter installment status.
    In production this fires on a scheduled job; here it is manually triggered for testing.
    """
    plan = _plans.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    disb = _disbursements.get(plan_id)
    if not disb:
        raise HTTPException(status_code=404, detail="Disbursement record not found")

    if disb.status in (DisbursementStatus.SENT, DisbursementStatus.CONFIRMED):
        return DisbursementTriggerResponse(
            disbursement_id=disb.disbursement_id,
            status=disb.status,
            amount_cents=disb.amount_cents,
            ach_reference=disb.ach_reference or "",
            message="ALREADY_DISBURSED",
        )

    # Generate ACH trace number (mock format)
    ach_ref = f"ACH{uuid.uuid4().hex[:12].upper()}"
    disb.status = DisbursementStatus.SENT
    disb.sent_at = datetime.utcnow()
    disb.ach_reference = ach_ref

    # If any installments are still unpaid, record credit float exposure
    unpaid = [
        i for i in plan.installments
        if i.status not in (PaymentStatus.SUCCEEDED, PaymentStatus.WAIVED)
    ]
    for i in unpaid:
        entry = CreditFloatEntry(
            plan_id=plan_id,
            renter_id=plan.renter_id,
            amount_cents=i.amount_cents,
            reason=f"DISBURSED_BEFORE_INSTALLMENT_{i.installment_number}_COLLECTED",
        )
        _float_ledger.append(entry)
        plan.credit_float_cents += i.amount_cents

    return DisbursementTriggerResponse(
        disbursement_id=disb.disbursement_id,
        status=disb.status,
        amount_cents=disb.amount_cents,
        ach_reference=ach_ref,
        message="DISBURSEMENT_SENT",
    )


@app.get("/v1/plans/{plan_id}", response_model=PlanSummaryResponse)
def get_plan(plan_id: str = Path(...)):
    """Retrieve full plan state including installments, disbursement, and credit float."""
    plan = _plans.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    disb = _disbursements.get(plan_id)
    float_entries = [e for e in _float_ledger if e.plan_id == plan_id]

    return PlanSummaryResponse(
        plan=plan,
        disbursement=disb,
        credit_float=float_entries,
        renter_balance_due_cents=_balance_due(plan),
    )


@app.delete("/v1/plans/{plan_id}", status_code=204)
def cancel_plan(plan_id: str = Path(...)):
    """Cancel an active plan. Not allowed if disbursement already sent."""
    plan = _plans.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    disb = _disbursements.get(plan_id)
    if disb and disb.status in (DisbursementStatus.SENT, DisbursementStatus.CONFIRMED):
        raise HTTPException(
            status_code=409,
            detail="Cannot cancel plan: landlord disbursement already sent",
        )

    plan.status = PlanStatus.CANCELLED
    return JSONResponse(status_code=204, content=None)


# ---------------------------------------------------------------------------
# Test utility: reset store between test runs
# ---------------------------------------------------------------------------
@app.delete("/v1/_test/reset", status_code=200, include_in_schema=False)
def reset_store():
    """Test-only endpoint. Clears all in-memory state."""
    _plans.clear()
    _disbursements.clear()
    _float_ledger.clear()
    _idempotency_cache.clear()
    return {"reset": True}
