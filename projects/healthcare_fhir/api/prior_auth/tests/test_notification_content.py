"""
test_notification_content.py
-------------------------------
The cheapest test that would have caught the Article 16 defect: a
notification content test.

These tests need no HTTP call, no sandbox state and no oracle. They check
the notification text directly against a stated content policy: approval must
carry the authorization number, denial must carry the denial reason, for
both recipients in this sandbox.

Scope: this level examines only the text a template produces. It cannot
determine whether the workflow selected the correct template, associated it
with the intended recipient, or created the notification record. Those gaps
belong to the integration level and to the customer journey oracle. Nothing
here proves delivery by an external messaging provider.
"""

from __future__ import annotations

import pytest

from projects.healthcare_fhir.api.prior_auth.models import PriorAuthStatus
from projects.healthcare_fhir.api.prior_auth.notification_content import (
    contains_detail,
    missing_required_detail,
    patient_message,
    provider_message,
)

AUTH = "AUTH-1234567890"
REASON = "Documentation does not establish medical necessity."
REQUEST_ID = "req-001"

# (status, authorization_number, denial_reason, name of the required detail)
CASES = [
    pytest.param(PriorAuthStatus.APPROVED, AUTH, None,
                 "authorization number", id="approval"),
    pytest.param(PriorAuthStatus.DENIED, None, REASON,
                 "denial reason", id="denial"),
]


@pytest.mark.healthcare
class TestNotificationContent:

    @pytest.mark.parametrize("status, auth, reason, detail", CASES)
    def test_defective_patient_message_is_flagged(self, status, auth, reason, detail):
        """The seeded defect, caught without running the workflow."""
        message = patient_message(status, auth, reason, complete=False)
        assert missing_required_detail(status, message, auth, reason) == [detail]

    @pytest.mark.parametrize("status, auth, reason, detail", CASES)
    def test_fixed_patient_message_carries_required_detail(self, status, auth, reason, detail):
        message = patient_message(status, auth, reason, complete=True)
        assert missing_required_detail(status, message, auth, reason) == []

    @pytest.mark.parametrize("status, auth, reason, detail", CASES)
    def test_provider_message_carries_required_detail(self, status, auth, reason, detail):
        """The provider side was always built correctly. This is the test
        that existed in spirit and was never written for the patient."""
        message = provider_message(status, REQUEST_ID, auth, reason)
        assert missing_required_detail(status, message, auth, reason) == []

    def test_content_check_flags_an_approval_that_never_generated_a_number(self):
        """A message cannot carry a number that does not exist."""
        message = patient_message(PriorAuthStatus.APPROVED, None, None, complete=True)
        assert missing_required_detail(
            PriorAuthStatus.APPROVED, message, None, None
        ) == ["authorization number"]

    def test_content_check_flags_a_denial_with_no_reason_on_file(self):
        message = patient_message(PriorAuthStatus.DENIED, None, None, complete=True)
        assert missing_required_detail(
            PriorAuthStatus.DENIED, message, None, None
        ) == ["denial reason"]


UNSUPPORTED = [PriorAuthStatus.SUBMITTED, PriorAuthStatus.PENDING_REVIEW]


@pytest.mark.healthcare
class TestUnsupportedStatusFailsClosed:
    """A content policy must not report a status it does not understand as
    compliant. These three functions raise instead of guessing."""

    @pytest.mark.parametrize("status", UNSUPPORTED)
    def test_patient_message_rejects_unsupported_status(self, status):
        with pytest.raises(ValueError, match="Unsupported"):
            patient_message(status, AUTH, REASON, complete=True)

    @pytest.mark.parametrize("status", UNSUPPORTED)
    def test_provider_message_rejects_unsupported_status(self, status):
        with pytest.raises(ValueError, match="Unsupported"):
            provider_message(status, REQUEST_ID, AUTH, REASON)

    @pytest.mark.parametrize("status", UNSUPPORTED)
    def test_content_check_rejects_unsupported_status(self, status):
        with pytest.raises(ValueError, match="Unsupported"):
            missing_required_detail(status, "any text", AUTH, REASON)


@pytest.mark.healthcare
class TestRecordedFlagsMatchMessageText:
    """The includes_* flags on a notification record must never disagree
    with the message text. They are derived from it, and this test keeps
    them honest if that ever changes."""

    @pytest.mark.parametrize("approve", [True, False], ids=["approval", "denial"])
    @pytest.mark.parametrize("complete", [False, True], ids=["defect", "fixed"])
    def test_flags_match_message_text(self, prior_auth_client, approve, complete):
        prior_auth_client.configure(patient_notification_complete=complete)
        request_id = prior_auth_client.submit(
            patient_id="pat-900", patient_name="Flag Check",
            provider_id="prov-900", procedure_code="29881",
            procedure_description="Knee arthroscopy",
            diagnosis_code="M23.51",
        ).json()["request_id"]
        decision = prior_auth_client.review(
            request_id, approve=approve, reviewer_id="reviewer-1",
            reason=None if approve else REASON,
        ).json()

        for note in prior_auth_client.notifications(request_id).json():
            assert note["includes_authorization_number"] == contains_detail(
                note["message"], decision["authorization_number"])
            assert note["includes_denial_reason"] == contains_detail(
                note["message"], decision["denial_reason"])
