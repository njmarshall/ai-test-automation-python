"""
test_policy.py
--------------
Phase 1 MVP: Insurance Policy resource — create, read, update, delete, list.

Architecture recap
------------------
  InsuranceConfig    (Singleton) ← loaded once
  InsuranceClient    (Facade)    ← injected via fixture
  InsuranceFactory   (Factory)   ← randomised policy payloads
  Policy             (CRTP)      ← typed deserialisation
  InsuranceValidator (Fluent)    ← chainable assertions

Target API
----------
JSONPlaceholder /posts (https://jsonplaceholder.typicode.com)
Simulates Insurance Policy CRUD — free, public, no auth required.

Note: JSONPlaceholder simulates writes (POST/PUT/DELETE return success
responses) but doesn't actually persist data. This is intentional for
a portfolio demo — the framework design is what matters.
"""

from __future__ import annotations

import pytest

from projects.insurance.api.assertions.insurance_validator import InsuranceValidator
from projects.insurance.api.client.insurance_client import InsuranceClient
from projects.insurance.api.data.insurance_factory import InsuranceFactory
from projects.insurance.api.models.policy import Policy


@pytest.mark.insurance
class TestPolicy:
    """
    Insurance Policy resource — Phase 1 MVP test suite.

    Five tests covering full CRUD + list:
      1. Create  → 201 + id returned
      2. Read    → 200 + fields match
      3. Update  → 200 + title updated
      4. Delete  → 200 resource removed
      5. List    → 200 + policies returned for customer
    """

    # ------------------------------------------------------------------ #
    #  Test 1 — Create                                                     #
    # ------------------------------------------------------------------ #

    def test_create_policy_returns_201_with_id(
        self, insurance_client: InsuranceClient
    ) -> None:
        """
        POST /posts — create a new Insurance Policy.

        Assertions
        ----------
        - HTTP 201 Created
        - Response contains 'id', 'title', 'body', 'userId'
        - CRTP model: policy_name is non-empty
        - Response within 3s SLA
        """
        payload  = InsuranceFactory.build_policy_dict(user_id=1)
        response = insurance_client.create_policy(payload)

        policy_id = (
            InsuranceValidator(response)
            .status(201)
            .has_field("id")
            .has_field("title")
            .has_field("body")
            .has_field("userId")
            .within_sla(sla_ms=3000)
            .extract_id()
        )

        policy = Policy.from_response(response.json())
        assert policy.policy_name, "Expected non-empty policy name."
        assert policy.customer_id == 1, f"Expected customer_id 1, got {policy.customer_id}."

    # ------------------------------------------------------------------ #
    #  Test 2 — Read                                                       #
    # ------------------------------------------------------------------ #

    def test_read_policy_returns_correct_fields(
        self, insurance_client: InsuranceClient
    ) -> None:
        """
        GET /posts/{id} — read an existing Policy by id.

        Assertions
        ----------
        - HTTP 200 OK
        - id matches requested id
        - title and body fields present
        - CRTP model deserialises correctly
        """
        policy_id = 1   # JSONPlaceholder always has id=1
        response  = insurance_client.read_policy(policy_id)

        (
            InsuranceValidator(response)
            .status(200)
            .has_field("id")
            .has_field("title")
            .has_field("body")
            .has_field("userId")
            .field_equals("id", policy_id)
            .within_sla(sla_ms=3000)
        )

        policy = Policy.from_response(response.json())
        assert policy.id == policy_id
        assert policy.policy_name, "Expected non-empty policy name."

    # ------------------------------------------------------------------ #
    #  Test 3 — Update                                                     #
    # ------------------------------------------------------------------ #

    def test_update_policy_returns_200(
        self, insurance_client: InsuranceClient
    ) -> None:
        """
        PUT /posts/{id} — update an existing Policy.

        Assertions
        ----------
        - HTTP 200 OK
        - Updated title reflected in response
        """
        policy_id      = 1
        payload        = InsuranceFactory.build_policy_dict(user_id=1)
        payload["id"]  = policy_id
        new_title      = payload["title"]

        response = insurance_client.update_policy(policy_id, payload)

        (
            InsuranceValidator(response)
            .status(200)
            .has_field("id")
            .has_field("title")
            .field_equals("title", new_title)
            .within_sla(sla_ms=3000)
        )

    # ------------------------------------------------------------------ #
    #  Test 4 — Delete                                                     #
    # ------------------------------------------------------------------ #

    def test_delete_policy_returns_200(
        self, insurance_client: InsuranceClient
    ) -> None:
        """
        DELETE /posts/{id} — delete a Policy.

        Assertions
        ----------
        - HTTP 200 OK
        """
        policy_id = 1
        response  = insurance_client.delete_policy(policy_id)

        InsuranceValidator(response).status(200)

    # ------------------------------------------------------------------ #
    #  Test 5 — List by customer                                           #
    # ------------------------------------------------------------------ #

    def test_list_policies_by_customer_returns_results(
        self, insurance_client: InsuranceClient
    ) -> None:
        """
        GET /posts?userId={id} — list all policies for a customer.

        Assertions
        ----------
        - HTTP 200 OK
        - Returns a list (not empty)
        - All policies belong to the requested customer
        """
        user_id  = 1
        response = insurance_client.list_policies_by_customer(user_id)

        InsuranceValidator(response).status(200).within_sla(sla_ms=3000)

        policies = response.json()
        assert isinstance(policies, list), "Expected a list of policies."
        assert len(policies) > 0, f"Expected policies for userId={user_id}."
        assert all(p["userId"] == user_id for p in policies), (
            f"All policies should belong to userId={user_id}."
        )
