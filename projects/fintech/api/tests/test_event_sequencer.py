"""
test_event_sequencer.py
-----------------------
Demonstrates event sequence validation using EventSequencer.

Real-world connection
---------------------
These tests demonstrate the same event sequencing patterns used at Indeed:

  Indeed email delivery pipeline:
    QUEUED → SPAM_CHECK → BLACKLIST_CHECK → CONTENT_SCAN → DELIVERED

  The test validates that:
    1. All events in the sequence appear
    2. Events arrive in the correct order
    3. The full sequence completes within the SLA window

  Here we simulate the pipeline using Coinbase price API calls
  as the event source — each API call represents a pipeline stage.

Architecture recap
------------------
  EventSequencer (shared/async/) ← validates event order and completeness
  AsyncPoller    (shared/async/) ← handles the polling mechanics
  FintechClient  (Facade)        ← injected via fixture
"""

from __future__ import annotations

import importlib

import pytest

from projects.fintech.api.client.fintech_client import FintechClient

# 'async' is a reserved keyword, so shared/async/ can't be reached via a
# normal dotted import — load it dynamically instead.
_event_sequencer = importlib.import_module("shared.async.event_sequencer")
EventSequencer = _event_sequencer.EventSequencer
SequenceResult = _event_sequencer.SequenceResult


@pytest.mark.fintech
class TestEventSequencer:
    """
    Event sequence validation tests using simulated pipeline stages.

    Three tests covering core EventSequencer capabilities:
      1. Complete sequence validation (all events in order)
      2. Missing event detection
      3. Out-of-order event detection
    """

    # ------------------------------------------------------------------ #
    #  Test 1 — Complete sequence validation                               #
    # ------------------------------------------------------------------ #

    def test_complete_event_sequence_passes(
        self, fintech_client: FintechClient
    ) -> None:
        """
        Validate a complete event sequence where all events
        arrive in the correct order.

        Simulates Indeed email delivery pipeline:
          QUEUED → SPAM_CHECK → DELIVERED

        Here each Coinbase API call represents a pipeline stage.
        We collect the resource types returned and validate their sequence.

        Assertions
        ----------
        - All expected events observed
        - Events arrive in correct order
        - Sequence completes within timeout
        - result.is_valid() returns True
        """
        # Simulate pipeline stages by collecting API response markers
        pipeline_events = []

        def fetch_pipeline_events():
            # Each call simulates a pipeline stage completing
            if len(pipeline_events) == 0:
                fintech_client.get_currencies()
                pipeline_events.append("STAGE_1_CURRENCIES")
            elif len(pipeline_events) == 1:
                fintech_client.get_exchange_rates("USD")
                pipeline_events.append("STAGE_2_RATES")
            elif len(pipeline_events) == 2:
                fintech_client.get_spot_price("BTC-USD")
                pipeline_events.append("STAGE_3_PRICES")
            return pipeline_events

        sequencer = EventSequencer(
            expected_sequence=[
                "STAGE_1_CURRENCIES",
                "STAGE_2_RATES",
                "STAGE_3_PRICES",
            ],
            timeout_sec=15.0,
            poll_interval_sec=0.5,
        )

        result = sequencer.validate(
            fetch_events=fetch_pipeline_events,
            extract_status=lambda events: events,
        )

        assert result.is_complete(), (
            f"Expected all pipeline stages to complete.\n{result.summary()}"
        )
        assert result.in_order(), (
            f"Expected pipeline stages in correct order.\n{result.summary()}"
        )
        assert result.is_valid(), result.summary()
        assert not result.timed_out

    # ------------------------------------------------------------------ #
    #  Test 2 — Missing event detection                                    #
    # ------------------------------------------------------------------ #

    def test_missing_event_detected(self) -> None:
        """
        Verify EventSequencer correctly detects missing events.

        Simulates Indeed blacklist check being skipped:
          Expected: QUEUED → SPAM_CHECK → BLACKLIST_CHECK → DELIVERED
          Observed: QUEUED → SPAM_CHECK → DELIVERED  (BLACKLIST_CHECK missing!)

        This is a critical test — missing pipeline stages indicate
        data corruption or infrastructure failures.

        Assertions
        ----------
        - result.is_complete() returns False
        - result.missing contains the skipped event
        - result.is_valid() returns False
        """
        # Simulate pipeline that skips BLACKLIST_CHECK
        observed_events = ["QUEUED", "SPAM_CHECK", "DELIVERED"]

        sequencer = EventSequencer(
            expected_sequence=[
                "QUEUED",
                "SPAM_CHECK",
                "BLACKLIST_CHECK",   # this one will be missing
                "DELIVERED",
            ],
            timeout_sec=2.0,
            poll_interval_sec=0.5,
        )

        result = sequencer.validate(
            fetch_events=lambda: observed_events,
            extract_status=lambda events: events,
        )

        assert not result.is_complete(), (
            "Expected incomplete sequence when BLACKLIST_CHECK is missing."
        )
        assert "BLACKLIST_CHECK" in result.missing, (
            f"Expected BLACKLIST_CHECK in missing events: {result.missing}"
        )
        assert not result.is_valid()

    # ------------------------------------------------------------------ #
    #  Test 3 — Out of order detection                                     #
    # ------------------------------------------------------------------ #

    def test_out_of_order_event_detected(self) -> None:
        """
        Verify EventSequencer correctly detects out-of-order events.

        Simulates Indeed pipeline where CONTENT_SCAN fires before SPAM_CHECK:
          Expected: QUEUED → SPAM_CHECK → CONTENT_SCAN → DELIVERED
          Observed: QUEUED → CONTENT_SCAN → SPAM_CHECK → DELIVERED

        Out-of-order events indicate race conditions or pipeline bugs
        that would be invisible to simple status-only checks.

        Assertions
        ----------
        - result.is_complete() returns True (all events present)
        - result.in_order() returns False (wrong order)
        - result.out_of_order contains the misordered event
        - result.is_valid() returns False
        """
        # Simulate pipeline where CONTENT_SCAN fires before SPAM_CHECK
        observed_events = [
            "QUEUED",
            "CONTENT_SCAN",   # arrived too early!
            "SPAM_CHECK",
            "DELIVERED",
        ]

        sequencer = EventSequencer(
            expected_sequence=[
                "QUEUED",
                "SPAM_CHECK",
                "CONTENT_SCAN",
                "DELIVERED",
            ],
            timeout_sec=2.0,
            poll_interval_sec=0.5,
            strict_order=True,
        )

        result = sequencer.validate(
            fetch_events=lambda: observed_events,
            extract_status=lambda events: events,
        )

        assert result.is_complete(), (
            "Expected all events present even if out of order."
        )
        assert not result.in_order(), (
            "Expected out-of-order detection when CONTENT_SCAN fires early."
        )
        assert not result.is_valid()
        assert len(result.out_of_order) > 0, (
            f"Expected out_of_order to be non-empty: {result.out_of_order}"
        )
