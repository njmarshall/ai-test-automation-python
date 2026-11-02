"""
test_customer_journey_oracle.py
----------------------------------
Phase 7: proves the customer journey oracle catches what response and
state tests cannot.

Each "defect" test below passes three checks a typical suite would stop
at (API response status, request status, and "was a patient notification
record created") before the oracle catches the actual failure: the
patient notification did not carry the one detail the patient needed to
act on their own approval or denial.

Scope: these tests inspect the notification record the workflow produced.
They do not prove delivery to, or action by, a person.
"""

from __future__ import annotations

import pytest

from projects.healthcare_fhir.api.prior_auth.models import (
    NotificationRecipient,
    PriorAuthStatus,
)
from shared.oracle.customer_journey_oracle import CustomerJourneyOracle


def _patient_notification(notifications: list[dict]) -> dict:
    for n in notifications:
        if n["recipient"] == NotificationRecipient.PATIENT.value:
            return n
    raise AssertionError("No patient notification was recorded.")


@pytest.mark.healthcare
class TestPriorAuthApprovalJourney:

    def test_response_and_state_checks_pass_but_oracle_catches_incomplete_notification(
        self, prior_auth_client
    ):
        """
        The defect, reproduced: approval succeeds at every layer a typical
        suite checks, and the patient still cannot schedule their procedure
        because their notification omits the authorization number.
        """
        # Sandbox defaults to the defect: patient_notification_complete=False
        submit_resp = prior_auth_client.submit(
            patient_id="pat-001", patient_name="Jordan Ellis",
            provider_id="prov-100", procedure_code="29881",
            procedure_description="Knee arthroscopy",
            diagnosis_code="M23.51",
        )
        assert submit_resp.status_code == 201
        request_id = submit_resp.json()["request_id"]

        review_resp = prior_auth_client.review(
            request_id, approve=True, reviewer_id="reviewer-7",
        )
        notifications_resp = prior_auth_client.notifications(request_id)

        # Layer 1: API response. This is what most suites check.
        assert review_resp.status_code == 200
        review_body = review_resp.json()

        # Layer 2: recorded state. Article 14's layer. Also passes.
        assert review_body["status"] == PriorAuthStatus.APPROVED.value
        assert review_body["authorization_number"] is not None

        # Layer 3: was a patient notification record created? Also passes.
        notifications = notifications_resp.json()
        patient_note = _patient_notification(notifications)
        assert patient_note is not None

        # Layer 4: the customer journey oracle. This is Phase 7.
        oracle = CustomerJourneyOracle(
            journey_name="prior_authorization_approval",
            outcome_check=lambda obs: (
                obs["review"].data.get("status") == PriorAuthStatus.APPROVED.value
                and obs["patient_notification"].data.get(
                    "includes_authorization_number"
                ) is True
            ),
            impact_on_failure=lambda obs: (
                "The request was approved and an authorization number "
                "was generated, but the patient's notification did not "
                "include it. The patient cannot schedule the procedure "
                "without this number, even though the system shows the "
                "approval as complete."
            ),
        )
        oracle.record("submit", ok=submit_resp.status_code == 201,
                      status=submit_resp.json()["status"])
        oracle.record("review", ok=review_resp.status_code == 200,
                      status=review_body["status"],
                      authorization_number=review_body["authorization_number"])
        oracle.record("patient_notification", ok=True,
                      includes_authorization_number=patient_note["includes_authorization_number"])

        result = oracle.evaluate()

        # Every technical layer above passed, and the oracle still
        # correctly reports failure.
        assert result.all_steps_technically_ok() is True
        assert result.customer_outcome_met is False
        assert "authorization number" in result.customer_impact

    def test_oracle_passes_once_patient_notification_is_complete(
        self, prior_auth_client
    ):
        """The fix: same journey, patient notification now carries the
        authorization number. The oracle agrees the customer outcome was met."""
        prior_auth_client.configure(patient_notification_complete=True)

        submit_resp = prior_auth_client.submit(
            patient_id="pat-002", patient_name="Casey Nolan",
            provider_id="prov-100", procedure_code="29881",
            procedure_description="Knee arthroscopy",
            diagnosis_code="M23.51",
        )
        request_id = submit_resp.json()["request_id"]
        review_resp = prior_auth_client.review(
            request_id, approve=True, reviewer_id="reviewer-7",
        )
        patient_note = _patient_notification(
            prior_auth_client.notifications(request_id).json()
        )

        oracle = CustomerJourneyOracle(
            journey_name="prior_authorization_approval",
            outcome_check=lambda obs: (
                obs["review"].data.get("status") == PriorAuthStatus.APPROVED.value
                and obs["patient_notification"].data.get(
                    "includes_authorization_number"
                ) is True
            ),
            impact_on_failure=lambda obs: "authorization number missing from patient notification",
        )
        oracle.record("submit", ok=True, status=submit_resp.json()["status"])
        oracle.record("review", ok=True, status=review_resp.json()["status"])
        oracle.record("patient_notification", ok=True,
                      includes_authorization_number=patient_note["includes_authorization_number"])

        result = oracle.evaluate()
        assert result.customer_outcome_met is True, result.customer_impact


@pytest.mark.healthcare
class TestPriorAuthDenialJourney:

    def test_oracle_catches_denial_without_reason_reaching_the_patient(
        self, prior_auth_client
    ):
        """
        Same defect class, different manifestation: the request is correctly
        denied with a reason on file, the provider is told the reason, and
        the patient notification omits it, leaving the patient with no way
        to understand or appeal the decision.
        """
        submit_resp = prior_auth_client.submit(
            patient_id="pat-003", patient_name="Sam Rivera",
            provider_id="prov-200", procedure_code="64483",
            procedure_description="Epidural steroid injection",
            diagnosis_code="M54.5",
        )
        request_id = submit_resp.json()["request_id"]

        review_resp = prior_auth_client.review(
            request_id, approve=False, reviewer_id="reviewer-9",
            reason="Documentation does not establish medical necessity.",
        )
        assert review_resp.status_code == 200
        assert review_resp.json()["status"] == PriorAuthStatus.DENIED.value

        patient_note = _patient_notification(
            prior_auth_client.notifications(request_id).json()
        )

        oracle = CustomerJourneyOracle(
            journey_name="prior_authorization_denial",
            outcome_check=lambda obs: (
                obs["review"].data.get("status") == PriorAuthStatus.DENIED.value
                and obs["patient_notification"].data.get("includes_denial_reason") is True
            ),
            impact_on_failure=lambda obs: (
                "The request was denied and a reason was recorded, but "
                "the patient's notification did not include it, so the "
                "patient has no way to understand or appeal the decision."
            ),
        )
        oracle.record("submit", ok=True, status=submit_resp.json()["status"])
        oracle.record("review", ok=True, status=review_resp.json()["status"])
        oracle.record("patient_notification", ok=True,
                      includes_denial_reason=patient_note["includes_denial_reason"])

        result = oracle.evaluate()
        assert result.all_steps_technically_ok() is True
        assert result.customer_outcome_met is False
        assert "appeal" in result.customer_impact
