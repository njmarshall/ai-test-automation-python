"""
Test Suite: Landlord Disbursement
------------------------------------
Covers POST /v1/plans/{plan_id}/disburse

This is the most important behavioral test for Flex as a chartered bank.
The core product promise: landlords get paid on rent_due_date regardless
of whether renters have paid their installments.

Key business rules verified:
  - Disbursement triggers successfully at any installment state
  - Disbursement is for full rent amount (not partial)
  - Second disburse call returns ALREADY_DISBURSED (idempotent)
  - Credit float is recorded when disbursement precedes installment collection
  - Plan cannot be cancelled after disbursement
  - ACH reference is returned on successful disbursement
"""


class TestDisbursementHappyPath:

    def test_disbursement_returns_200(self, client, plan_id):
        resp = client.post(f"/v1/plans/{plan_id}/disburse")
        assert resp.status_code == 200

    def test_disbursement_status_becomes_sent(self, client, plan_id):
        resp = client.post(f"/v1/plans/{plan_id}/disburse")
        assert resp.json()["status"] == "SENT"

    def test_disbursement_amount_is_full_rent(self, client, plan_id, created_plan):
        """Landlord always receives 100% of monthly rent."""
        monthly = 250000   # from standard_plan_payload fixture
        resp = client.post(f"/v1/plans/{plan_id}/disburse")
        assert resp.json()["amount_cents"] == monthly

    def test_disbursement_returns_ach_reference(self, client, plan_id):
        resp = client.post(f"/v1/plans/{plan_id}/disburse")
        ach = resp.json()["ach_reference"]
        assert ach and ach.startswith("ACH")

    def test_disbursement_message_is_sent(self, client, plan_id):
        resp = client.post(f"/v1/plans/{plan_id}/disburse")
        assert resp.json()["message"] == "DISBURSEMENT_SENT"


class TestDisbursementBeforeInstallmentsCollected:
    """
    The chartered bank scenario. Disbursement fires on rent_due_date.
    Renters may not have paid yet. Flex absorbs the float.
    """

    def test_disbursement_succeeds_with_zero_installments_paid(self, client, plan_id):
        """
        Core chartered-bank test: disburse before any installment collected.
        Flex pays landlord; Flex now carries credit float for both installments.
        """
        resp = client.post(f"/v1/plans/{plan_id}/disburse")
        assert resp.json()["status"] == "SENT"

    def test_credit_float_recorded_for_both_unpaid_installments(self, client, plan_id):
        """Two float entries created — one per unpaid installment."""
        client.post(f"/v1/plans/{plan_id}/disburse")
        summary = client.get(f"/v1/plans/{plan_id}").json()
        assert len(summary["credit_float"]) == 2

    def test_credit_float_total_equals_monthly_rent(self, client, plan_id):
        """Float exposure equals full monthly rent when neither installment paid."""
        client.post(f"/v1/plans/{plan_id}/disburse")
        summary = client.get(f"/v1/plans/{plan_id}").json()
        total_float = summary["plan"]["credit_float_cents"]
        assert total_float == 250000

    def test_disbursement_after_installment_1_paid_records_only_inst2_float(
        self, client, plan_id
    ):
        """
        Installment 1 collected before disbursement.
        Disbursement fires. Only installment 2 unpaid -> one float entry.
        """
        client.post(
            f"/v1/plans/{plan_id}/installments/1/charge",
            json={"idempotency_key": "pre-disb"},
        )
        client.post(f"/v1/plans/{plan_id}/disburse")
        summary = client.get(f"/v1/plans/{plan_id}").json()
        assert len(summary["credit_float"]) == 1

    def test_no_float_when_all_installments_paid_before_disbursement(self, client, plan_id):
        """Renter paid both installments early. No float exposure."""
        client.post(
            f"/v1/plans/{plan_id}/installments/1/charge",
            json={"idempotency_key": "c1"},
        )
        client.post(
            f"/v1/plans/{plan_id}/installments/2/charge",
            json={"idempotency_key": "c2"},
        )
        client.post(f"/v1/plans/{plan_id}/disburse")
        summary = client.get(f"/v1/plans/{plan_id}").json()
        assert len(summary["credit_float"]) == 0
        assert summary["plan"]["credit_float_cents"] == 0


class TestDisbursementIdempotency:

    def test_second_disburse_returns_already_disbursed(self, client, plan_id):
        client.post(f"/v1/plans/{plan_id}/disburse")
        resp = client.post(f"/v1/plans/{plan_id}/disburse")
        assert resp.json()["message"] == "ALREADY_DISBURSED"

    def test_second_disburse_does_not_create_duplicate_float(self, client, plan_id):
        """Idempotent disbursement must not double the float entries."""
        client.post(f"/v1/plans/{plan_id}/disburse")
        client.post(f"/v1/plans/{plan_id}/disburse")   # second call
        summary = client.get(f"/v1/plans/{plan_id}").json()
        # Still only 2 float entries (one per installment), not 4
        assert len(summary["credit_float"]) <= 2

    def test_ach_reference_consistent_across_calls(self, client, plan_id):
        resp1 = client.post(f"/v1/plans/{plan_id}/disburse")
        resp2 = client.post(f"/v1/plans/{plan_id}/disburse")
        assert resp1.json()["ach_reference"] == resp2.json()["ach_reference"]


class TestDisbursementBlocksCancellation:

    def test_cancel_after_disburse_returns_409(self, client, plan_id):
        """
        Once the landlord has been paid, the plan cannot be cancelled.
        The money is gone. 409 Conflict is the correct status.
        """
        client.post(f"/v1/plans/{plan_id}/disburse")
        resp = client.delete(f"/v1/plans/{plan_id}")
        assert resp.status_code == 409

    def test_cancel_before_disburse_succeeds(self, client, plan_id):
        resp = client.delete(f"/v1/plans/{plan_id}")
        assert resp.status_code == 204

    def test_unknown_plan_disburse_returns_404(self, client):
        resp = client.post("/v1/plans/nonexistent/disburse")
        assert resp.status_code == 404
