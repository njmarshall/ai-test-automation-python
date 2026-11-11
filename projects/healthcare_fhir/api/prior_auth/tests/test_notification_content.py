"""
test_notification_content.py
-------------------------------
The cheapest test that would have caught the Article 16 defect.

These tests need no HTTP call, no sandbox state and no oracle. They check
the notification text directly against a stated contract: approval must
carry the authorization number, denial must carry the denial reason, for
every recipient.

Scope: this level can only see the text a template produces. It cannot see
whether the workflow actually used that template, sent it to the right
recipient, or created the record at all. Those gaps belong to the
integration level and to the customer journey oracle.
"""

from __future__ import annotations

import pytest

from projects.healthcare_fhir.api.prior_auth.models import PriorAuthStatus
from projects.healthcare_fhir.api.prior_auth.notification_content import (
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
class TestNotificationContract:

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

    def test_contract_flags_an_approval_that_never_generated_a_number(self):
        """A message cannot carry a number that does not exist."""
        message = patient_message(PriorAuthStatus.APPROVED, None, None, complete=True)
        assert missing_required_detail(
            PriorAuthStatus.APPROVED, message, None, None
        ) == ["authorization number"]

    def test_contract_flags_a_denial_with_no_reason_on_file(self):
        message = patient_message(PriorAuthStatus.DENIED, None, None, complete=True)
        assert missing_required_detail(
            PriorAuthStatus.DENIED, message, None, None
        ) == ["denial reason"]
