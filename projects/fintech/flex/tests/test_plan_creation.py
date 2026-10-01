"""
Test Suite: Plan Creation
--------------------------
Covers the POST /v1/plans endpoint.

Key business rules verified:
  - Split calculation: inst1 = ceil(rent * 55%), inst2 = remainder
  - Installment due dates: 14 days before and 1 day before rent_due_date
  - Disbursement is scheduled for rent_due_date at full rent amount
  - Idempotency: same key returns same plan_id, no duplicate plan
  - Invalid rent rejected with 422
"""

import math
from datetime import date, timedelta


class TestPlanCreationHappyPath:

    def test_creates_plan_with_201(self, client, standard_plan_payload):
        resp = client.post("/v1/plans", json=standard_plan_payload)
        assert resp.status_code == 201

    def test_response_contains_plan_id(self, client, standard_plan_payload):
        resp = client.post("/v1/plans", json=standard_plan_payload)
        assert "plan_id" in resp.json()
        assert resp.json()["plan_id"]  # non-empty

    def test_two_installments_generated(self, client, standard_plan_payload):
        resp = client.post("/v1/plans", json=standard_plan_payload)
        installments = resp.json()["installments"]
        assert len(installments) == 2

    def test_installment_numbers_are_1_and_2(self, client, standard_plan_payload):
        resp = client.post("/v1/plans", json=standard_plan_payload)
        numbers = sorted(i["installment_number"] for i in resp.json()["installments"])
        assert numbers == [1, 2]

    def test_installments_sum_to_monthly_rent(self, client, standard_plan_payload):
        """Core invariant: installment 1 + installment 2 = monthly_rent_cents."""
        monthly = standard_plan_payload["monthly_rent_cents"]
        resp = client.post("/v1/plans", json=standard_plan_payload)
        total = sum(i["amount_cents"] for i in resp.json()["installments"])
        assert total == monthly

    def test_installment_1_is_55_percent_ceiling(self, client, standard_plan_payload):
        """Flex charges the larger share first (55%, ceiling)."""
        monthly = standard_plan_payload["monthly_rent_cents"]
        expected = math.ceil(monthly * 0.55)
        resp = client.post("/v1/plans", json=standard_plan_payload)
        inst1 = next(
            i for i in resp.json()["installments"] if i["installment_number"] == 1
        )
        assert inst1["amount_cents"] == expected

    def test_installment_1_due_14_days_before_rent(self, client, standard_plan_payload, rent_due_date):
        expected = (rent_due_date - timedelta(days=14)).isoformat()
        resp = client.post("/v1/plans", json=standard_plan_payload)
        inst1 = next(
            i for i in resp.json()["installments"] if i["installment_number"] == 1
        )
        assert inst1["due_date"] == expected

    def test_installment_2_due_1_day_before_rent(self, client, standard_plan_payload, rent_due_date):
        expected = (rent_due_date - timedelta(days=1)).isoformat()
        resp = client.post("/v1/plans", json=standard_plan_payload)
        inst2 = next(
            i for i in resp.json()["installments"] if i["installment_number"] == 2
        )
        assert inst2["due_date"] == expected

    def test_both_installments_start_as_pending(self, client, standard_plan_payload):
        resp = client.post("/v1/plans", json=standard_plan_payload)
        statuses = [i["status"] for i in resp.json()["installments"]]
        assert all(s == "PENDING" for s in statuses)

    def test_disbursement_scheduled_at_full_rent_amount(self, client, standard_plan_payload):
        """
        Chartered bank guarantee: Flex schedules full rent disbursement
        regardless of whether renter has paid their installments.
        """
        monthly = standard_plan_payload["monthly_rent_cents"]
        resp = client.post("/v1/plans", json=standard_plan_payload)
        disb = resp.json()["disbursement"]
        assert disb["amount_cents"] == monthly

    def test_disbursement_scheduled_on_rent_due_date(self, client, standard_plan_payload, rent_due_date):
        resp = client.post("/v1/plans", json=standard_plan_payload)
        disb = resp.json()["disbursement"]
        assert disb["scheduled_date"] == rent_due_date.isoformat()

    def test_disbursement_starts_as_scheduled(self, client, standard_plan_payload):
        resp = client.post("/v1/plans", json=standard_plan_payload)
        assert resp.json()["disbursement"]["status"] == "SCHEDULED"


class TestPlanCreationIdempotency:

    def test_same_idempotency_key_returns_same_plan_id(self, client, standard_plan_payload):
        """Duplicate request with same key must return same plan_id."""
        resp1 = client.post("/v1/plans", json=standard_plan_payload)
        resp2 = client.post("/v1/plans", json=standard_plan_payload)
        assert resp1.json()["plan_id"] == resp2.json()["plan_id"]

    def test_idempotent_response_returns_existing_plan_message(self, client, standard_plan_payload):
        client.post("/v1/plans", json=standard_plan_payload)
        resp2 = client.post("/v1/plans", json=standard_plan_payload)
        assert resp2.json()["message"] == "EXISTING_PLAN_RETURNED"

    def test_different_idempotency_keys_create_different_plans(self, client, standard_plan_payload):
        payload1 = {**standard_plan_payload, "idempotency_key": "key-A"}
        payload2 = {**standard_plan_payload, "idempotency_key": "key-B"}
        resp1 = client.post("/v1/plans", json=payload1)
        resp2 = client.post("/v1/plans", json=payload2)
        assert resp1.json()["plan_id"] != resp2.json()["plan_id"]


class TestPlanCreationValidation:

    def test_zero_rent_rejected(self, client, rent_due_date):
        payload = {
            "renter_id": "R002",
            "landlord_id": "L001",
            "property_id": "P101",
            "monthly_rent_cents": 0,
            "rent_due_date": rent_due_date.isoformat(),
        }
        resp = client.post("/v1/plans", json=payload)
        assert resp.status_code == 422

    def test_negative_rent_rejected(self, client, rent_due_date):
        payload = {
            "renter_id": "R002",
            "landlord_id": "L001",
            "property_id": "P101",
            "monthly_rent_cents": -100,
            "rent_due_date": rent_due_date.isoformat(),
        }
        resp = client.post("/v1/plans", json=payload)
        assert resp.status_code == 422

    def test_missing_renter_id_rejected(self, client, rent_due_date):
        payload = {
            "landlord_id": "L001",
            "property_id": "P101",
            "monthly_rent_cents": 150000,
            "rent_due_date": rent_due_date.isoformat(),
        }
        resp = client.post("/v1/plans", json=payload)
        assert resp.status_code == 422

    def test_odd_cent_rent_splits_correctly(self, client, rent_due_date):
        """$1,001 rent: inst1 = ceil(1001 * 0.55) = 551, inst2 = 450. Sum = 1001."""
        payload = {
            "renter_id": "R003",
            "landlord_id": "L001",
            "property_id": "P102",
            "monthly_rent_cents": 100100,   # $1,001.00
            "rent_due_date": rent_due_date.isoformat(),
        }
        resp = client.post("/v1/plans", json=payload)
        assert resp.status_code == 201
        total = sum(i["amount_cents"] for i in resp.json()["installments"])
        assert total == 100100
