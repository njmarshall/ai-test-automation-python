"""
Test Suite: Plan Summary and State Transitions
------------------------------------------------
Covers GET /v1/plans/{plan_id} and DELETE /v1/plans/{plan_id}

Verifies that the plan summary reflects real-time state across installments,
disbursement, credit float, and balance due.
"""


class TestPlanSummary:

    def test_get_plan_returns_200(self, client, plan_id):
        resp = client.get(f"/v1/plans/{plan_id}")
        assert resp.status_code == 200

    def test_plan_summary_contains_plan_installments_and_disbursement(self, client, plan_id):
        resp = client.get(f"/v1/plans/{plan_id}").json()
        assert "plan" in resp
        assert "disbursement" in resp
        assert "credit_float" in resp
        assert "renter_balance_due_cents" in resp

    def test_initial_balance_due_equals_monthly_rent(self, client, plan_id):
        """Before any payment, renter owes the full monthly rent."""
        summary = client.get(f"/v1/plans/{plan_id}").json()
        assert summary["renter_balance_due_cents"] == 250000

    def test_balance_due_reduces_after_installment_1(self, client, plan_id, created_plan):
        inst1_amount = next(
            i["amount_cents"] for i in created_plan["installments"]
            if i["installment_number"] == 1
        )
        client.post(
            f"/v1/plans/{plan_id}/installments/1/charge",
            json={"idempotency_key": "c1"},
        )
        summary = client.get(f"/v1/plans/{plan_id}").json()
        assert summary["renter_balance_due_cents"] == 250000 - inst1_amount

    def test_unknown_plan_returns_404(self, client):
        resp = client.get("/v1/plans/does-not-exist")
        assert resp.status_code == 404

    def test_plan_initially_active(self, client, plan_id):
        summary = client.get(f"/v1/plans/{plan_id}").json()
        assert summary["plan"]["status"] == "ACTIVE"

    def test_credit_float_initially_empty(self, client, plan_id):
        summary = client.get(f"/v1/plans/{plan_id}").json()
        assert summary["credit_float"] == []

    def test_credit_float_cents_initially_zero(self, client, plan_id):
        summary = client.get(f"/v1/plans/{plan_id}").json()
        assert summary["plan"]["credit_float_cents"] == 0


class TestPlanCancellation:

    def test_cancel_active_plan_returns_204(self, client, plan_id):
        resp = client.delete(f"/v1/plans/{plan_id}")
        assert resp.status_code == 204

    def test_cancelled_plan_shows_cancelled_status(self, client, plan_id):
        client.delete(f"/v1/plans/{plan_id}")
        summary = client.get(f"/v1/plans/{plan_id}").json()
        assert summary["plan"]["status"] == "CANCELLED"

    def test_cancel_unknown_plan_returns_404(self, client):
        resp = client.delete("/v1/plans/ghost-plan")
        assert resp.status_code == 404
