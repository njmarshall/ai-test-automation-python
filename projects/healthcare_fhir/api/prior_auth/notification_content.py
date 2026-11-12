"""
notification_content.py : what each notification must say
-------------------------------------------------------------
Pure functions that build the notification text, plus one function that
states the content policy: what detail a notification must carry for its
recipient to act on the decision.

Why this module exists
-----------------------
The message text used to be built inline inside the sandbox's review
endpoint, so the only way to check it was to run the whole workflow. Pulling
it into pure functions means the cheapest possible test can check it: no
HTTP, no sandbox state, no oracle.

`patient_message(..., complete=False)` reproduces the seeded defect: the
patient text omits the authorization number on approval and the denial
reason on denial. `complete=True` is the fix.
"""

from __future__ import annotations

from typing import List, Optional

from projects.healthcare_fhir.api.prior_auth.models import PriorAuthStatus


def provider_message(
    status: PriorAuthStatus,
    request_id: str,
    authorization_number: Optional[str],
    denial_reason: Optional[str],
) -> str:
    """Provider-facing text. Always carries the detail."""
    if status == PriorAuthStatus.APPROVED:
        return (f"Request {request_id} approved. "
                f"Authorization number: {authorization_number}.")
    if status == PriorAuthStatus.DENIED:
        return f"Request {request_id} denied. Reason: {denial_reason}."
    raise ValueError(f"Unsupported decision status: {status}")


def patient_message(
    status: PriorAuthStatus,
    authorization_number: Optional[str],
    denial_reason: Optional[str],
    complete: bool,
) -> str:
    """Patient-facing text. With complete=False it omits the detail."""
    if status == PriorAuthStatus.APPROVED:
        if complete:
            return ("Your request has been approved. "
                    f"Authorization number: {authorization_number}.")
        return ("Your request has been approved. "
                "Please contact your provider for next steps.")
    if status == PriorAuthStatus.DENIED:
        if complete:
            return f"Your request has been denied. Reason: {denial_reason}."
        return ("Your request has been denied. "
                "Please contact your provider for more information.")
    raise ValueError(f"Unsupported decision status: {status}")


def contains_detail(message: str, detail: Optional[str]) -> bool:
    """True only if `detail` exists and appears in the message text.
    The single place that answers "does this message carry that detail?"."""
    return bool(detail) and detail in message


def missing_required_detail(
    status: PriorAuthStatus,
    message: str,
    authorization_number: Optional[str],
    denial_reason: Optional[str],
) -> List[str]:
    """
    The content policy. Returns the names of required details that are absent
    from `message`. An empty list means the message carries what its
    recipient needs to act.

    Approval requires the authorization number. Denial requires the denial
    reason. In this sandbox the same policy applies to both recipients. A
    production design would define it per recipient, status and content.

    Fails closed: a status the policy does not cover raises ValueError
    instead of being reported as compliant.
    """
    missing: List[str] = []
    if status == PriorAuthStatus.APPROVED:
        if not contains_detail(message, authorization_number):
            missing.append("authorization number")
    elif status == PriorAuthStatus.DENIED:
        if not contains_detail(message, denial_reason):
            missing.append("denial reason")
    else:
        raise ValueError(f"Unsupported decision status: {status}")
    return missing
