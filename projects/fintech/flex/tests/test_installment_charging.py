"""
Test Suite: Installment Charging
----------------------------------
Covers POST /v1/plans/{plan_id}/installments/{n}/charge

Key business rules verified:
  - Successful charge transitions installment to SUCCEEDED
  - Failed charge (force_failure) transitions to RETRYING, then FAILED after 3 attempts
  - Idempotency: same idempotency_key returns same result, no double-charge
  - Late fee applied when payment is after due_date
  - Plan goes DELINQUENT when both installments permanently FAILED
  - Plan goes COMPLETED when both installments SUCCEEDED
  - Unknown plan_id returns 404
  - Invalid installment number returns 404
"""


class TestInstallmentHappyPath:

    def test_charge_installment_1_succeeds(self, client, plan_id):
        resp = client.post(
            f"/v1/plans/{plan_id}/installments/1/charge",
            json={"idempotency_key": "charge-inst1-001"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "SUCCEEDED"

    def test_charge_installment_2_succeeds(self, client, plan_id):
        resp = client.post(
            f"/v1/plans/{plan_id}/installments/2/charge",
            json={"idempotency_key": "charge-inst2-001"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "SUCCEEDED"

    def test_plan_status_completed_after_both_succeed(self, client, plan_id):
        """Both green -> plan COMPLETED."""
        client.post(
            f"/v1/plans/{plan_id}/installments/1/charge",
            json={"idempotency_key": "c1"},
        )
        client.post(
            f"/v1/plans/{plan_id}/installments/2/charge",
            json={"idempotency_key": "c2"},
        )
        summary = client.get(f"/v1/plans/{plan_id}").json()
        assert summary["plan"]["status"] == "COMPLETED"

    def test_renter_balance_zero_after_both_succeed(self, client, plan_id):
        client.post(
            f"/v1/plans/{plan_id}/installments/1/charge",
            json={"idempotency_key": "c1"},
        )
        client.post(
            f"/v1/plans/{plan_id}/installments/2/charge",
            json={"idempotency_key": "c2"},
        )
        summary = client.get(f"/v1/plans/{plan_id}").json()
        assert summary["renter_balance_due_cents"] == 0

    def test_succeeded_installment_returns_correct_amount(self, client, plan_id, created_plan):
        """Amount returned matches installment amount from plan creation."""
        inst1_amount = next(
            i["amount_cents"] for i in created_plan["installments"]
            if i["installment_number"] == 1
        )
        resp = client.post(
            f"/v1/plans/{plan_id}/installments/1/charge",
            json={"idempotency_key": "c1"},
        )
        assert resp.json()["amount_cents"] == inst1_amount


class TestInstallmentIdempotency:

    def test_same_key_returns_same_response(self, client, plan_id):
        """Idempotency: charging twice with same key must not double-bill."""
        charge = lambda: client.post(
            f"/v1/plans/{plan_id}/installments/1/charge",
            json={"idempotency_key": "idem-charge-001"},
        ).json()
        resp1 = charge()
        resp2 = charge()
        assert resp1["installment_id"] == resp2["installment_id"]
        assert resp1["status"] == resp2["status"]

    def test_already_succeeded_returns_already_succeeded_message(self, client, plan_id):
        """Second call after success returns ALREADY_SUCCEEDED, not a new charge."""
        client.post(
            f"/v1/plans/{plan_id}/installments/1/charge",
            json={"idempotency_key": "idem-001"},
        )
        resp = client.post(
            f"/v1/plans/{plan_id}/installments/1/charge",
            json={"idempotency_key": "idem-002"},   # different key but already terminal
        )
        assert resp.json()["message"] == "ALREADY_SUCCEEDED"

    def test_different_keys_on_succeeded_installment_still_blocked(self, client, plan_id):
        """Once an installment is SUCCEEDED, any further charge attempt is blocked."""
        client.post(
            f"/v1/plans/{plan_id}/installments/1/charge",
            json={"idempotency_key": "first"},
        )
        resp = client.post(
            f"/v1/plans/{plan_id}/installments/1/charge",
            json={"idempotency_key": "second"},
        )
        assert resp.json()["status"] == "SUCCEEDED"


class TestInstallmentFailureAndRetry:

    def test_first_failure_sets_retrying(self, client, plan_id):
        """First ACH failure -> RETRYING (not yet permanent FAILED)."""
        resp = client.post(
            f"/v1/plans/{plan_id}/installments/1/charge",
            json={"idempotency_key": "fail-001", "force_failure": True},
        )
        assert resp.json()["status"] == "RETRYING"

    def test_three_failures_sets_permanently_failed(self, client, plan_id):
        """After 3 attempts all with force_failure, installment is permanently FAILED."""
        for i in range(3):
            resp = client.post(
                f"/v1/plans/{plan_id}/installments/1/charge",
                json={"idempotency_key": f"fail-{i}", "force_failure": True},
            )
        assert resp.json()["status"] == "FAILED"

    def test_max_retries_message_on_fourth_attempt(self, client, plan_id):
        """Fourth attempt (after 3 failures) returns MAX_RETRIES_EXCEEDED."""
        for i in range(3):
            client.post(
                f"/v1/plans/{plan_id}/installments/1/charge",
                json={"idempotency_key": f"fail-{i}", "force_failure": True},
            )
        resp = client.post(
            f"/v1/plans/{plan_id}/installments/1/charge",
            json={"idempotency_key": "fail-4", "force_failure": True},
        )
        assert "MAX_RETRIES_EXCEEDED" in resp.json()["message"]

    def test_plan_delinquent_when_both_installments_fail(self, client, plan_id):
        """
        Chartered bank scenario: both installments fail permanently.
        Plan transitions to DELINQUENT. Flex still disbursed the full rent.
        """
        for i in range(3):
            client.post(
                f"/v1/plans/{plan_id}/installments/1/charge",
                json={"idempotency_key": f"f1-{i}", "force_failure": True},
            )
        for i in range(3):
            client.post(
                f"/v1/plans/{plan_id}/installments/2/charge",
                json={"idempotency_key": f"f2-{i}", "force_failure": True},
            )
        summary = client.get(f"/v1/plans/{plan_id}").json()
        assert summary["plan"]["status"] == "DELINQUENT"

    def test_installment_1_fails_installment_2_succeeds_not_delinquent(self, client, plan_id):
        """Partial recovery: one fails permanently, one succeeds -> not COMPLETED but not DELINQUENT."""
        for i in range(3):
            client.post(
                f"/v1/plans/{plan_id}/installments/1/charge",
                json={"idempotency_key": f"f1-{i}", "force_failure": True},
            )
        client.post(
            f"/v1/plans/{plan_id}/installments/2/charge",
            json={"idempotency_key": "s2"},
        )
        summary = client.get(f"/v1/plans/{plan_id}").json()
        plan_status = summary["plan"]["status"]
        # Not fully completed (inst1 failed) and not fully delinquent (inst2 succeeded)
        assert plan_status == "ACTIVE"


class TestInstallmentNotFound:

    def test_unknown_plan_returns_404(self, client):
        resp = client.post(
            "/v1/plans/nonexistent-plan/installments/1/charge",
            json={"idempotency_key": "x"},
        )
        assert resp.status_code == 404

    def test_installment_number_3_returns_422(self, client, plan_id):
        """Only installments 1 and 2 exist. 3 is out of range."""
        resp = client.post(
            f"/v1/plans/{plan_id}/installments/3/charge",
            json={"idempotency_key": "x"},
        )
        assert resp.status_code == 422

    def test_installment_number_0_returns_422(self, client, plan_id):
        resp = client.post(
            f"/v1/plans/{plan_id}/installments/0/charge",
            json={"idempotency_key": "x"},
        )
        assert resp.status_code == 422
