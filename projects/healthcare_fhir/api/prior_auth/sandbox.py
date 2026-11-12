"""
sandbox.py : prior authorization sandbox
-------------------------------------------
FastAPI mock of a prior-authorization workflow: submission, review,
decision, and notification dispatch.

Real-world context
-------------------
Every stage of this workflow can be technically correct (the request is
submitted, a reviewer decides, the decision is recorded) while the thing
the patient actually needed to act on the decision never reaches them
intact. This sandbox reproduces that gap on purpose, as a toggle, so
tests can demonstrate both the defect and the fix against the same server.

The defect: the sandbox's patient-facing notification template was built
and tested from the provider's side of the workflow. The provider
notification always includes the authorization number (on approval) and
the denial reason (on denial). The patient notification, by default, does
not. Set `patient_notification_complete=True` via POST /sandbox/configure
to simulate the fix.

Note: records are kept in memory. The sandbox stands in for the system of
record; it does not use a database.

Run the sandbox
-----------------
    uvicorn projects.healthcare_fhir.api.prior_auth.sandbox:app --port 8004

Or in tests, via FastAPI's TestClient (no real port needed):
    from fastapi.testclient import TestClient
    client = TestClient(app)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from projects.healthcare_fhir.api.prior_auth.notification_content import (
    contains_detail,
    patient_message,
    provider_message,
)
from projects.healthcare_fhir.api.prior_auth.models import (
    NotificationChannel,
    NotificationRecipient,
    NotificationRecord,
    PriorAuthRequest,
    PriorAuthStatus,
    PriorAuthSubmission,
    ReviewDecisionRequest,
)

app = FastAPI(
    title="Prior Authorization Sandbox",
    description="Prior-authorization workflow with a toggleable "
                 "patient-notification completeness defect",
    version="1.0.0",
)

_requests:      Dict[str, PriorAuthRequest]         = {}
_notifications: Dict[str, List[NotificationRecord]] = {}

# When False (the default, the defect), the PATIENT notification omits the
# authorization number on approval and the denial reason on denial, even
# though the PROVIDER notification always includes them.
_sandbox_state = {"patient_notification_complete": False}


def _reset() -> None:
    _requests.clear()
    _notifications.clear()
    _sandbox_state["patient_notification_complete"] = False


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "prior-auth-sandbox", "version": "1.0.0"}


@app.delete("/sandbox/reset", status_code=204)
def reset_sandbox() -> None:
    """Reset all sandbox state (testing only)."""
    _reset()


@app.post("/sandbox/configure")
def configure_sandbox(patient_notification_complete: bool) -> dict:
    """
    Toggle the patient-notification completeness defect.

    False (default): the patient notification omits the authorization
        number / denial reason, even though the request is approved /
        denied correctly.
    True: simulates the fix. The patient notification carries the same
        detail the provider notification always carried.
    """
    _sandbox_state["patient_notification_complete"] = patient_notification_complete
    return dict(_sandbox_state)


@app.post("/prior-auth/requests", status_code=201, response_model=PriorAuthRequest)
def submit_request(submission: PriorAuthSubmission) -> PriorAuthRequest:
    """Submit a new prior authorization request. Starts PENDING_REVIEW."""
    request = PriorAuthRequest(
        request_id=str(uuid4()),
        patient_id=submission.patient_id,
        patient_name=submission.patient_name,
        provider_id=submission.provider_id,
        procedure_code=submission.procedure_code,
        procedure_description=submission.procedure_description,
        diagnosis_code=submission.diagnosis_code,
        status=PriorAuthStatus.PENDING_REVIEW,
        created_at=datetime.now(timezone.utc),
    )
    _requests[request.request_id] = request
    _notifications[request.request_id] = []
    return request


@app.get("/prior-auth/requests/{request_id}", response_model=PriorAuthRequest)
def get_request(request_id: str) -> PriorAuthRequest:
    request = _requests.get(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail=f"Request {request_id} not found")
    return request


@app.post("/prior-auth/requests/{request_id}/review", response_model=PriorAuthRequest)
def review_request(request_id: str, decision: ReviewDecisionRequest) -> PriorAuthRequest:
    """
    Record a reviewer's decision and dispatch notifications.

    On approval, both patient and provider are notified. The provider
    notification always includes the authorization number. The patient
    notification includes it only if patient_notification_complete has
    been set True (the fix). On denial, the same asymmetry applies to the
    denial reason.
    """
    request = _requests.get(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail=f"Request {request_id} not found")

    if request.status != PriorAuthStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "REQUEST_NOT_REVIEWABLE",
                "detail": f"Request is in status {request.status}, not PENDING_REVIEW.",
            },
        )

    complete = _sandbox_state["patient_notification_complete"]
    now = datetime.now(timezone.utc)

    if decision.approve:
        request.status = PriorAuthStatus.APPROVED
        request.authorization_number = f"AUTH-{uuid4().hex[:10].upper()}"
        provider_text = provider_message(
            PriorAuthStatus.APPROVED, request_id,
            request.authorization_number, None)
        patient_text = patient_message(
            PriorAuthStatus.APPROVED, request.authorization_number,
            None, complete)

        _notifications[request_id].append(NotificationRecord(
            notification_id=str(uuid4()),
            request_id=request_id,
            recipient=NotificationRecipient.PROVIDER,
            channel=NotificationChannel.PORTAL,
            message=provider_text,
            includes_authorization_number=contains_detail(
                provider_text, request.authorization_number),
            includes_denial_reason=False,
            sent_at=now,
        ))
        _notifications[request_id].append(NotificationRecord(
            notification_id=str(uuid4()),
            request_id=request_id,
            recipient=NotificationRecipient.PATIENT,
            channel=NotificationChannel.PORTAL,
            message=patient_text,
            includes_authorization_number=contains_detail(
                patient_text, request.authorization_number),
            includes_denial_reason=False,
            sent_at=now,
        ))

    else:
        if not decision.reason:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "DENIAL_REASON_REQUIRED",
                    "detail": "A reason is required to deny a request.",
                },
            )
        request.status = PriorAuthStatus.DENIED
        request.denial_reason = decision.reason
        provider_text = provider_message(
            PriorAuthStatus.DENIED, request_id, None, decision.reason)
        patient_text = patient_message(
            PriorAuthStatus.DENIED, None, decision.reason, complete)

        _notifications[request_id].append(NotificationRecord(
            notification_id=str(uuid4()),
            request_id=request_id,
            recipient=NotificationRecipient.PROVIDER,
            channel=NotificationChannel.PORTAL,
            message=provider_text,
            includes_authorization_number=False,
            includes_denial_reason=contains_detail(
                provider_text, decision.reason),
            sent_at=now,
        ))
        _notifications[request_id].append(NotificationRecord(
            notification_id=str(uuid4()),
            request_id=request_id,
            recipient=NotificationRecipient.PATIENT,
            channel=NotificationChannel.PORTAL,
            message=patient_text,
            includes_authorization_number=False,
            includes_denial_reason=contains_detail(
                patient_text, decision.reason),
            sent_at=now,
        ))

    return request


@app.get("/prior-auth/requests/{request_id}/notifications", response_model=List[NotificationRecord])
def list_notifications(request_id: str) -> List[NotificationRecord]:
    if request_id not in _requests:
        raise HTTPException(status_code=404, detail=f"Request {request_id} not found")
    return _notifications.get(request_id, [])
