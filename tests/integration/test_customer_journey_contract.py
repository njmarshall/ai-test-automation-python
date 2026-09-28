"""
test_customer_journey_contract.py

Customer journey contract test: prior authorization workflow.
Article 15 — AI Test Automation Series
"The Database Was Correct. The Customer Still Failed."

This test verifies three distinct things:
  1. The workflow reaches its approved business state (via status URL,
     not a direct database query).
  2. The patient can see that state through the portal interface.
  3. The scheduling service accepts the authorization for the procedure.

Design principles:
  - Outside-in: drives through supported application surfaces only.
  - Bounded wait: uses time.monotonic() — immune to system clock changes.
  - Explicit timeouts: every network call has a connect + read timeout.
  - Synthetic data: test_patient fixture provisions and cleans up personas.
  - No direct database queries as the primary oracle for customer success.

Run only in an authorized staging environment with synthetic data.
Do not run against production.
"""
from __future__ import annotations

import time
from datetime import date

import pytest
import requests
from playwright.sync_api import expect

# Connect timeout, read timeout (seconds).
TIMEOUT = (2, 10)

# Maximum seconds the approved state must become visible in the portal
# and usable by the scheduling service. Define this value with your
# business owner before running the test.
VISIBILITY_BUDGET_SECONDS = 300


# ── helpers ───────────────────────────────────────────────────────────────────

def wait_for_approval(api: requests.Session, status_url: str) -> dict:
    """
    Poll the authorization status resource until it reaches APPROVED
    or the journey time budget expires.

    Uses time.monotonic() so a system clock adjustment cannot cause
    the loop to expire early or run forever.

    Raises AssertionError with a customer-impact message on timeout.
    """
    deadline = time.monotonic() + VISIBILITY_BUDGET_SECONDS
    while time.monotonic() < deadline:
        response = api.get(status_url, timeout=TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        if payload["status"] == "APPROVED":
            return payload
        time.sleep(5)
    raise AssertionError(
        f"Authorization did not reach APPROVED within "
        f"{VISIBILITY_BUDGET_SECONDS}s journey budget. "
        f"Customer cannot confirm coverage before appointment."
    )


# ── test ──────────────────────────────────────────────────────────────────────

def test_patient_can_use_approved_authorization(page, test_patient, settings):
    """
    Customer outcome: a patient who submits a prior authorization
    request can confirm approval through the portal and proceed to
    appointment booking without calling or resubmitting.

    Customer journey oracle:
      Actor          — synthetic patient with an eligible plan
      Goal           — confirm approval and book without resubmitting
      Terminal state — portal shows Approved; scheduling reports eligible
      Time budget    — VISIBILITY_BUDGET_SECONDS from submission
      Unacceptable   — approved in backend, not visible in portal;
                       scheduling rejects an approved authorization
    """
    with requests.Session() as api:

        # ── Step 1: Submit the prior authorization request ─────────────────
        # The API returns 202 Accepted because adjudication is asynchronous.
        # 202 proves the request was received, not that it was approved.
        created = api.post(
            f"{settings.authorization_url}/authorizations",
            json={
                "patient_id": test_patient.id,
                "procedure_code": "99213",
                "requested_date": date(2026, 10, 15).isoformat(),
            },
            timeout=TIMEOUT,
        )
        assert created.status_code == 202, (
            f"Expected 202 Accepted for async adjudication, "
            f"got {created.status_code}. Check API contract."
        )
        request_id = created.json()["request_id"]
        status_url = created.json()["status_url"]

        # ── Step 2: Wait for approved business state ───────────────────────
        # Poll the status resource returned by the API.
        # This is the outside-in oracle: the same surface a client would use.
        # A direct database query is not used here.
        approved = wait_for_approval(api, status_url)
        assert approved["procedure_code"] == "99213", (
            f"Status resource returned wrong procedure code: "
            f"{approved.get('procedure_code')}. "
            f"Patient may be turned away at appointment."
        )

        # ── Step 3: Verify portal visibility ──────────────────────────────
        # The patient must be able to see the approved authorization
        # through the portal surface they actually use.
        page.goto(
            f"{settings.portal_url}/patients/{test_patient.id}/authorizations"
        )
        card = page.get_by_test_id(f"authorization_{request_id}")
        expect(card).to_contain_text("Approved", timeout=10_000)

        # ── Step 4: Verify scheduling service accepts the authorization ───
        # An authorization approved in the backend but rejected by the
        # scheduling service leaves the patient unable to book.
        booking = api.post(
            f"{settings.scheduling_url}/appointments/precheck",
            json={
                "patient_id": test_patient.id,
                "procedure_code": "99213",
                "authorization_id": request_id,
            },
            timeout=TIMEOUT,
        )
        booking.raise_for_status()
        assert booking.json()["eligible"] is True, (
            f"Scheduling service rejected authorization {request_id} "
            f"even though it reached APPROVED state. "
            f"Patient cannot complete appointment booking."
        )
