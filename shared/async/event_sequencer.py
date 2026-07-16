"""
event_sequencer.py
------------------
Validates that async events occur in the correct sequence within a
configurable time window.

Real-world origin
-----------------
This module captures the email delivery pipeline pattern from Indeed:

  Indeed email delivery sequence:
    QUEUED → SPAM_CHECK → BLACKLIST_CHECK → CONTENT_SCAN → DELIVERED
                                                          → BOUNCED
                                                          → BLOCKED

  Each step was validated by polling an event log endpoint and asserting
  that events arrived in the correct order within an SLA window.
  If BLACKLIST_CHECK fired before SPAM_CHECK, the pipeline was broken.
  If DELIVERED arrived but CONTENT_SCAN was missing, data was corrupted.

  This same pattern applies to:
    Finix payments:    CREATED → PENDING → SUCCEEDED (or FAILED)
    HEAVY.AI HA:       FAILOVER_INITIATED → REPLICA_PROMOTED → SERVING
    Any async pipeline where ORDER and COMPLETENESS both matter.

Pattern : Template Method — EventSequencer defines the validation skeleton;
          callers provide the event-fetching function and expected sequence
SOLID   : SRP — one class, one job: validate event sequences
          OCP — extend with new validation rules without modifying core logic

Usage
-----
    # Indeed-style email delivery validation
    sequencer = EventSequencer(
        expected_sequence=["QUEUED", "SPAM_CHECK", "DELIVERED"],
        timeout_sec=30,
        poll_interval_sec=2,
    )

    result = sequencer.validate(
        fetch_events=lambda: email_client.get_events(email_id),
        extract_status=lambda r: [e["status"] for e in r.json()["events"]],
    )

    assert result.is_complete()
    assert result.in_order()
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional


# ------------------------------------------------------------------ #
#  Result object                                                       #
# ------------------------------------------------------------------ #

@dataclass
class SequenceResult:
    """
    Result of an event sequence validation.

    Attributes
    ----------
    expected    : the sequence we expected to see
    observed    : the sequence we actually observed
    elapsed_sec : how long validation took
    timed_out   : whether we hit the timeout before completing
    missing     : events in expected but not observed
    out_of_order: events that arrived in wrong order
    """
    expected:      List[str]
    observed:      List[str]
    elapsed_sec:   float
    timed_out:     bool          = False
    missing:       List[str]     = field(default_factory=list)
    out_of_order:  List[str]     = field(default_factory=list)

    def is_complete(self) -> bool:
        """Return True if all expected events were observed."""
        return len(self.missing) == 0

    def in_order(self) -> bool:
        """Return True if all observed events arrived in correct order."""
        return len(self.out_of_order) == 0

    def is_valid(self) -> bool:
        """Return True if sequence is both complete and in order."""
        return self.is_complete() and self.in_order() and not self.timed_out

    def summary(self) -> str:
        """Return a human-readable summary of the validation result."""
        lines = [
            f"EventSequencer result ({self.elapsed_sec:.1f}s):",
            f"  Expected : {self.expected}",
            f"  Observed : {self.observed}",
            f"  Complete : {self.is_complete()}",
            f"  In order : {self.in_order()}",
            f"  Timed out: {self.timed_out}",
        ]
        if self.missing:
            lines.append(f"  Missing  : {self.missing}")
        if self.out_of_order:
            lines.append(f"  Disorder : {self.out_of_order}")
        return "\n".join(lines)


# ------------------------------------------------------------------ #
#  EventSequencer                                                      #
# ------------------------------------------------------------------ #

class EventSequencer:
    """
    Validates that async events occur in the correct sequence
    within a configurable time window.

    Inspired by Indeed email delivery pipeline testing where events
    had to arrive in a specific order: QUEUED, SPAM_CHECK, DELIVERED.
    Out-of-order or missing events indicated pipeline failures.

    Example
    -------
        sequencer = EventSequencer(
            expected_sequence=["QUEUED", "SPAM_CHECK", "DELIVERED"],
            timeout_sec=30,
            poll_interval_sec=2,
        )

        result = sequencer.validate(
            fetch_events=lambda: client.get_email_events(email_id),
            extract_status=lambda r: [e["status"] for e in r.json()],
        )

        assert result.is_valid(), result.summary()
    """

    def __init__(
        self,
        expected_sequence: List[str],
        timeout_sec:       float = 30.0,
        poll_interval_sec: float = 2.0,
        strict_order:      bool  = True,
    ) -> None:
        """
        Parameters
        ----------
        expected_sequence : ordered list of event statuses to expect
        timeout_sec       : max time to wait for all events
        poll_interval_sec : how often to poll for new events
        strict_order      : if True, events must arrive in exact order
                           if False, all events must appear but order is flexible
        """
        if not expected_sequence:
            raise ValueError("expected_sequence must contain at least one event.")

        self.expected_sequence  = expected_sequence
        self.timeout_sec        = timeout_sec
        self.poll_interval_sec  = poll_interval_sec
        self.strict_order       = strict_order

    # ------------------------------------------------------------------ #
    #  Public interface                                                    #
    # ------------------------------------------------------------------ #

    def validate(
        self,
        fetch_events:   Callable[[], Any],
        extract_status: Callable[[Any], List[str]],
    ) -> SequenceResult:
        """
        Poll fetch_events() until all expected events are observed
        or timeout is reached.

        Parameters
        ----------
        fetch_events   : callable that fetches the current event list
        extract_status : callable that extracts status strings from the response

        Returns
        -------
        SequenceResult with full details of what was observed
        """
        start_time    = time.time()
        observed:     List[str] = []
        timed_out     = False

        while True:
            elapsed = time.time() - start_time

            # Fetch current events
            response       = fetch_events()
            current_events = extract_status(response)

            # Merge new events into observed (preserve order, no duplicates)
            for event in current_events:
                if event not in observed:
                    observed.append(event)

            # Check if all expected events observed
            if self._all_observed(observed):
                break

            # Check timeout
            if elapsed >= self.timeout_sec:
                timed_out = True
                break

            time.sleep(self.poll_interval_sec)

        elapsed_sec  = time.time() - start_time
        missing      = self._find_missing(observed)
        out_of_order = self._find_out_of_order(observed) if self.strict_order else []

        return SequenceResult(
            expected=self.expected_sequence,
            observed=observed,
            elapsed_sec=elapsed_sec,
            timed_out=timed_out,
            missing=missing,
            out_of_order=out_of_order,
        )

    def assert_valid(
        self,
        fetch_events:   Callable[[], Any],
        extract_status: Callable[[Any], List[str]],
    ) -> SequenceResult:
        """
        Like validate() but raises AssertionError if sequence is invalid.

        Convenience method for use directly in pytest tests.

        Example
        -------
            result = sequencer.assert_valid(
                fetch_events=lambda: client.get_events(email_id),
                extract_status=lambda r: [e["status"] for e in r.json()],
            )
            # No assertion needed — assert_valid() raises if invalid
        """
        result = self.validate(fetch_events, extract_status)
        assert result.is_valid(), (
            f"Event sequence validation failed.\n{result.summary()}"
        )
        return result

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _all_observed(self, observed: List[str]) -> bool:
        """Return True if all expected events appear in observed."""
        return all(e in observed for e in self.expected_sequence)

    def _find_missing(self, observed: List[str]) -> List[str]:
        """Return events in expected but not in observed."""
        return [e for e in self.expected_sequence if e not in observed]

    def _find_out_of_order(self, observed: List[str]) -> List[str]:
        """
        Return expected events that arrived out of sequence.

        Algorithm: walk the expected sequence and verify each event
        appears after all preceding expected events in the observed list.
        """
        out_of_order = []
        last_index   = -1

        for expected_event in self.expected_sequence:
            if expected_event not in observed:
                continue
            current_index = observed.index(expected_event)
            if current_index < last_index:
                out_of_order.append(expected_event)
            last_index = current_index

        return out_of_order
