"""
test_async_polling.py
---------------------
Demonstrates async polling patterns using the shared AsyncPoller.

Real-world connection
---------------------
These tests demonstrate the same async patterns used in production:

  Finix (payments)     → TimeoutStrategy  (15s payment approval)
  Indeed (email)       → FixedRetryStrategy (event sequence validation)
  HEAVY.AI (GPU HA)    → ExponentialBackoffStrategy (cluster recovery)

Target API
----------
Coinbase public spot price API — used as a live async data source.
Price updates simulate the async state changes seen in:
  - Payment processing (status: PENDING → SUCCEEDED)
  - Email delivery    (status: QUEUED → DELIVERED)
  - HA cluster        (status: FAILOVER → PROMOTED)

Architecture recap
------------------
  AsyncPoller   (shared/async/) ← reusable Strategy pattern
  FintechClient (Facade)        ← injected via fixture
  FintechValidator (Fluent)     ← chainable assertions
"""

from __future__ import annotations

import importlib

import pytest

from projects.fintech.api.assertions.fintech_validator import FintechValidator
from projects.fintech.api.client.fintech_client import FintechClient

# `async` is a reserved keyword, so `shared/async/` can't be reached with a
# normal dotted import — load it dynamically instead.
_async_poller = importlib.import_module("shared.async.async_poller")
AsyncPoller = _async_poller.AsyncPoller
PollingTimeoutError = _async_poller.PollingTimeoutError


@pytest.mark.fintech
class TestAsyncPolling:
    """
    Async polling pattern tests using Coinbase price API.

    Three tests — one per strategy:
      1. Timeout strategy    (Finix payment approval pattern)
      2. Fixed retry         (Indeed email delivery pattern)
      3. Exponential backoff (HEAVY.AI HA cluster pattern)
    """

    # ------------------------------------------------------------------ #
    #  Test 1 — Timeout strategy (Finix pattern)                          #
    # ------------------------------------------------------------------ #

    def test_timeout_polling_btc_spot_price(
        self, fintech_client: FintechClient
    ) -> None:
        """
        Poll BTC-USD spot price using timeout strategy.

        Mirrors Finix payment processing pattern:
          POST /transfers → 202 → poll until SUCCEEDED (max 15s)

        Here we poll until we get a valid positive price
        within a 10 second timeout window.

        Assertions
        ----------
        - AsyncPoller returns a valid response within timeout
        - Response status is 200
        - Price amount is positive
        """
        poller = AsyncPoller(
            strategy="timeout",
            timeout_sec=10.0,
            interval_sec=1.0,
        )

        result = poller.poll(
            fn=lambda: fintech_client.get_spot_price("BTC-USD"),
            until=lambda r: (
                r.status_code == 200
                and float(r.json().get("data", {}).get("amount", 0)) > 0
            ),
            description="BTC-USD spot price to be available",
        )

        (
            FintechValidator(result)
            .status(200)
            .has_data()
            .data_amount_is_positive()
            .within_sla(sla_ms=10_000)
        )

    # ------------------------------------------------------------------ #
    #  Test 2 — Fixed retry strategy (Indeed pattern)                     #
    # ------------------------------------------------------------------ #

    def test_fixed_retry_polling_eth_spot_price(
        self, fintech_client: FintechClient
    ) -> None:
        """
        Poll ETH-USD spot price using fixed retry strategy.

        Mirrors Indeed email delivery pipeline pattern:
          POST /email → 202 → poll 5 times with 2s gaps
          until DELIVERED status confirmed

        Here we poll until ETH price is positive,
        with 3 fixed retries and 1 second delay.

        Assertions
        ----------
        - AsyncPoller resolves within fixed retry budget
        - ETH price is positive number
        - base and currency fields correct
        """
        poller = AsyncPoller(
            strategy="fixed",
            retries=3,
            delay_sec=1.0,
        )

        result = poller.poll(
            fn=lambda: fintech_client.get_spot_price("ETH-USD"),
            until=lambda r: (
                r.status_code == 200
                and float(r.json().get("data", {}).get("amount", 0)) > 0
            ),
            description="ETH-USD spot price to be available",
        )

        (
            FintechValidator(result)
            .status(200)
            .has_data()
            .data_amount_is_positive()
            .data_field_equals("base", "ETH")
            .data_field_equals("currency", "USD")
        )

    # ------------------------------------------------------------------ #
    #  Test 3 — Exponential backoff (HEAVY.AI HA pattern)                 #
    # ------------------------------------------------------------------ #

    def test_exponential_backoff_polling_exchange_rates(
        self, fintech_client: FintechClient
    ) -> None:
        """
        Poll USD exchange rates using exponential backoff strategy.

        Mirrors HEAVY.AI GPU cluster HA recovery pattern:
          POST /cluster/failover → poll with increasing delays
          1s → 2s → 4s → 8s until REPLICA_PROMOTED

        Exponential backoff is critical for distributed systems —
        hammering a recovering server worsens the situation.

        Here we poll exchange rates with backoff until
        we confirm EUR rate is positive.

        Assertions
        ----------
        - AsyncPoller resolves with exponential backoff
        - USD exchange rates contain EUR
        - EUR rate is positive
        """
        poller = AsyncPoller(
            strategy="backoff",
            max_retries=3,
            base_delay_sec=0.5,
            max_delay_sec=4.0,
        )

        result = poller.poll(
            fn=lambda: fintech_client.get_exchange_rates("USD"),
            until=lambda r: (
                r.status_code == 200
                and "EUR" in r.json().get("data", {}).get("rates", {})
            ),
            description="USD exchange rates with EUR to be available",
        )

        (
            FintechValidator(result)
            .status(200)
            .has_data()
            .has_data_field("rates")
        )

        rates = result.json()["data"]["rates"]
        assert float(rates.get("EUR", 0)) > 0, (
            "Expected positive EUR rate in USD exchange rates."
        )

    # ------------------------------------------------------------------ #
    #  Test 4 — Timeout error handling                                     #
    # ------------------------------------------------------------------ #

    def test_polling_raises_timeout_error_when_condition_never_met(
        self, fintech_client: FintechClient
    ) -> None:
        """
        Verify AsyncPoller raises PollingTimeoutError when condition
        is never satisfied within the timeout window.

        This validates the error handling path — critical for
        production use where payments genuinely fail or time out.

        Assertions
        ----------
        - PollingTimeoutError is raised
        - Error message describes what was being polled
        """
        poller = AsyncPoller(
            strategy="timeout",
            timeout_sec=2.0,
            interval_sec=0.5,
        )

        with pytest.raises(PollingTimeoutError) as exc_info:
            poller.poll(
                fn=lambda: fintech_client.get_spot_price("BTC-USD"),
                until=lambda r: False,  # condition never met
                description="impossible condition",
            )

        assert "impossible condition" in str(exc_info.value), (
            "Expected timeout error to mention what was being polled."
        )
