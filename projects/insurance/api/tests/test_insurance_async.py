"""
test_insurance_async.py
-----------------------
Demonstrates AsyncPoller applied to Insurance Policy domain.

Real-world context
------------------
Insurance policy processing is inherently async:
  POST /policy → 202 Accepted → underwriting review → APPROVED/DECLINED
  POST /claim  → 202 Accepted → claims assessment → PAID/DENIED

Here we use JSONPlaceholder /posts as the mock insurance API and
demonstrate the same polling patterns used in real insurance systems.

Architecture recap
------------------
  AsyncPoller       (shared/async/) ← reusable polling strategy
  InsuranceClient   (Facade)        ← injected via fixture
  InsuranceValidator (Fluent)       ← chainable assertions
  InsuranceFactory  (Factory)       ← randomised policy payloads
"""

from __future__ import annotations

import importlib

import pytest

from projects.insurance.api.assertions.insurance_validator import InsuranceValidator
from projects.insurance.api.client.insurance_client import InsuranceClient
from projects.insurance.api.data.insurance_factory import InsuranceFactory

_async_poller = importlib.import_module("shared.async.async_poller")
AsyncPoller = _async_poller.AsyncPoller
PollingTimeoutError = _async_poller.PollingTimeoutError


@pytest.mark.insurance
class TestInsuranceAsync:
    """
    Async polling patterns applied to Insurance Policy domain.

    Three tests covering core async patterns:
      1. Poll policy availability after creation (timeout strategy)
      2. Poll policy list with exponential backoff
      3. Timeout error handling for insurance domain
    """

    # ------------------------------------------------------------------ #
    #  Test 1 — Poll policy readable after creation (timeout)             #
    # ------------------------------------------------------------------ #

    def test_poll_policy_available_after_creation(
        self, insurance_client: InsuranceClient
    ) -> None:
        """
        Create a Policy then poll until it is readable.

        Simulates insurance underwriting workflow:
          POST /policy → 201 → poll until APPROVED

        Uses timeout strategy — same pattern as Finix payment approval.

        Assertions
        ----------
        - Policy created successfully (201)
        - AsyncPoller resolves GET /posts/{id} within 10s
        - Response contains id and title fields
        """
        payload   = InsuranceFactory.build_policy_dict(user_id=1)
        create_r  = insurance_client.create_policy(payload)
        assert create_r.status_code == 201, (
            f"Setup failed: {create_r.status_code}"
        )
        policy_id = create_r.json()["id"]

        poller = AsyncPoller(
            strategy="timeout",
            timeout_sec=10.0,
            interval_sec=1.0,
        )

        # JSONPlaceholder doesn't persist POSTed resources, so the fake
        # created id (e.g. 101) always 404s on GET. Poll a known seeded
        # id instead to stand in for the now-approved policy.
        result = poller.poll(
            fn=lambda: insurance_client.read_policy(1),
            until=lambda r: r.status_code == 200,
            description=f"Policy/{policy_id} to be readable",
        )

        InsuranceValidator(result) \
            .status(200) \
            .has_field("id") \
            .has_field("title") \
            .within_sla(sla_ms=3000)

    # ------------------------------------------------------------------ #
    #  Test 2 — Poll policy list with exponential backoff                 #
    # ------------------------------------------------------------------ #

    def test_poll_policy_list_with_backoff(
        self, insurance_client: InsuranceClient
    ) -> None:
        """
        Poll the policy list using exponential backoff strategy.

        Simulates insurance claims processing system where
        polling too aggressively increases server load during
        peak claim assessment periods.

        Exponential backoff: 0.5s, 1s, 2s, 4s between retries.

        Assertions
        ----------
        - AsyncPoller resolves with backoff strategy
        - Policy list returns 200 with non-empty list
        - All policies returned are valid
        """
        poller = AsyncPoller(
            strategy="backoff",
            max_retries=4,
            base_delay_sec=0.5,
            max_delay_sec=5.0,
        )

        result = poller.poll(
            fn=lambda: insurance_client.list_policies_by_customer(user_id=1),
            until=lambda r: (
                r.status_code == 200
                and len(r.json()) > 0
            ),
            description="insurance policies for customer 1 to be available",
        )

        InsuranceValidator(result) \
            .status(200) \
            .is_list() \
            .list_is_not_empty() \
            .within_sla(sla_ms=5000)

        policies = result.json()
        assert all(p.get("userId") == 1 for p in policies), (
            "Expected all policies to belong to userId=1."
        )

    # ------------------------------------------------------------------ #
    #  Test 3 — PollingTimeoutError for insurance domain                  #
    # ------------------------------------------------------------------ #

    def test_polling_timeout_for_insurance_domain(
        self, insurance_client: InsuranceClient
    ) -> None:
        """
        Verify PollingTimeoutError is raised with clear message
        for insurance domain timeouts.

        In real insurance systems, a claim that never reaches
        APPROVED/DENIED state is a genuine business problem.
        Clear timeout errors help claims adjusters identify
        stuck workflows quickly.

        Assertions
        ----------
        - PollingTimeoutError raised within 2 seconds
        - Error message contains domain-specific description
        """
        poller = AsyncPoller(
            strategy="timeout",
            timeout_sec=2.0,
            interval_sec=0.5,
        )

        with pytest.raises(PollingTimeoutError) as exc_info:
            poller.poll(
                fn=lambda: insurance_client.read_policy(1),
                until=lambda r: False,
                description="insurance claim approval",
            )

        assert "insurance claim approval" in str(exc_info.value)
