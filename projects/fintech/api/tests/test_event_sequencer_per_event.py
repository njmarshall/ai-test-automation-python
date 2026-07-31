"""
test_event_sequencer_per_event.py
---------------------------------
Tests the per-event (per-daemon) timeout budgets added to EventSequencer.

Real-world connection
---------------------
At Indeed, each daemon in the job-alert pipeline had a very different
latency — the notification scheduler could take minutes, delivery seconds.
Giving each event its OWN budget (instead of one conservative timeout for
the whole chain) is what cut suite run time dramatically: a missing fast
event costs only its small budget, not the worst-case ceiling.

These tests use an in-memory fake event source so they run instantly and
need no external services.
"""

from __future__ import annotations

import importlib
import time

import pytest

# 'async' is a reserved keyword, so load shared/async/ dynamically.
_event_sequencer = importlib.import_module("shared.async.event_sequencer")
EventSequencer = _event_sequencer.EventSequencer

EXPECTED = ["QUEUED", "SPAM_CHECK", "DELIVERED"]


def _source(statuses):
    """Return (fetch, extract) that always yields the given statuses."""
    fetch = lambda: {"events": [{"status": s} for s in statuses]}
    extract = lambda r: [e["status"] for e in r["events"]]
    return fetch, extract


@pytest.mark.fintech
class TestEventSequencerPerEvent:

    def test_per_event_fails_fast_vs_conservative(self):
        """A missing fast event should cost only its small budget."""
        fetch, extract = _source(["QUEUED", "SPAM_CHECK"])  # DELIVERED never arrives

        conservative = EventSequencer(EXPECTED, timeout_sec=1.0, poll_interval_sec=0.05)
        t = time.time()
        r_slow = conservative.validate(fetch, extract)
        slow_elapsed = time.time() - t

        per_event = EventSequencer(
            EXPECTED, timeout_sec=1.0, poll_interval_sec=0.05,
            per_event_timeout_sec={"QUEUED": 1.0, "SPAM_CHECK": 1.0, "DELIVERED": 0.2},
        )
        t = time.time()
        r_fast = per_event.validate(fetch, extract)
        fast_elapsed = time.time() - t

        assert r_slow.missing == ["DELIVERED"]
        assert r_fast.missing == ["DELIVERED"]
        # Per-event budgets must be meaningfully faster on the failing case.
        assert fast_elapsed < slow_elapsed / 2

    def test_per_event_happy_path_is_valid(self):
        """When every event arrives, per-event mode still validates cleanly."""
        fetch, extract = _source(EXPECTED)
        seq = EventSequencer(
            EXPECTED, poll_interval_sec=0.05,
            per_event_timeout_sec={"QUEUED": 0.5, "SPAM_CHECK": 0.5, "DELIVERED": 0.5},
        )
        result = seq.validate(fetch, extract)
        assert result.is_valid()
        assert result.observed == EXPECTED

    def test_unknown_event_in_map_raises(self):
        """A budget for an event not in the sequence is a config error."""
        with pytest.raises(ValueError):
            EventSequencer(EXPECTED, per_event_timeout_sec={"TYPO_EVENT": 1.0})
