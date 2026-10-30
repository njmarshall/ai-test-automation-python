"""
test_event_sequencer.py
-----------------------
Unit tests for shared/async/event_sequencer.py

What is tested
--------------
  SequenceResult dataclass    — is_complete(), in_order(), is_valid(), summary()
  EventSequencer constructor  — empty sequence raises ValueError; unknown
                                per_event_timeout key raises ValueError
  validate() whole-sequence   — all events observed; missing event; out-of-order;
                                timed_out flag
  validate() per-event path   — each event uses its own budget; fast failure on
                                first missing event when strict_order=True
  assert_valid()              — passes silently on valid; raises AssertionError
                                with summary() text on invalid
  strict_order=False          — out-of-order events still accepted

All time.sleep calls patched; fetch_events and extract_status are plain lambdas
over in-memory lists — no network, no external deps.
"""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest
import importlib

_event_sequencer = importlib.import_module("shared.async.event_sequencer")
EventSequencer = _event_sequencer.EventSequencer
SequenceResult = _event_sequencer.SequenceResult


class TestSequenceResult:
    def _make(self, **kwargs) -> SequenceResult:
        defaults = dict(
            expected=["A", "B", "C"],
            observed=["A", "B", "C"],
            elapsed_sec=0.5,
            timed_out=False,
            missing=[],
            out_of_order=[],
        )
        defaults.update(kwargs)
        return SequenceResult(**defaults)

    def test_is_complete_when_no_missing_events(self):
        assert self._make(missing=[]).is_complete() is True

    def test_is_not_complete_when_missing_events(self):
        assert self._make(missing=["C"]).is_complete() is False

    def test_in_order_when_no_out_of_order(self):
        assert self._make(out_of_order=[]).in_order() is True

    def test_not_in_order_when_out_of_order_present(self):
        assert self._make(out_of_order=["B"]).in_order() is False

    def test_is_valid_when_complete_in_order_not_timed_out(self):
        assert self._make().is_valid() is True

    def test_is_invalid_when_timed_out(self):
        assert self._make(timed_out=True).is_valid() is False

    def test_is_invalid_when_missing(self):
        assert self._make(missing=["C"]).is_valid() is False

    def test_is_invalid_when_out_of_order(self):
        assert self._make(out_of_order=["B"]).is_valid() is False

    def test_summary_contains_expected_events(self):
        s = self._make(expected=["A", "B", "C"]).summary()
        assert "A" in s and "B" in s and "C" in s

    def test_summary_contains_elapsed_time(self):
        s = self._make(elapsed_sec=3.14).summary()
        assert "3.14" in s or "3.1" in s

    def test_summary_mentions_missing_events(self):
        assert "C" in self._make(missing=["C"]).summary()

    def test_summary_valid_sequence(self):
        s = self._make().summary().lower()
        assert "valid" in s or "complete" in s or "pass" in s


class TestEventSequencerConstructor:
    def test_empty_sequence_raises_value_error(self):
        with pytest.raises(ValueError):
            EventSequencer(expected_sequence=[], timeout_sec=5.0)

    def test_unknown_per_event_key_raises_value_error(self):
        with pytest.raises(ValueError):
            EventSequencer(
                expected_sequence=["A", "B"],
                timeout_sec=5.0,
                per_event_timeout_sec={"Z": 2.0},
            )

    def test_valid_per_event_keys_accepted(self):
        # Should not raise
        EventSequencer(
            expected_sequence=["A", "B"],
            timeout_sec=5.0,
            per_event_timeout_sec={"A": 1.0, "B": 2.0},
        )


class TestWholeSequenceValidation:
    """validate() receives fetch_events and extract_status as arguments."""

    def _run(self, events, expected=("A", "B", "C"), timeout_sec=5.0,
             strict_order=True):
        seq = EventSequencer(
            expected_sequence=list(expected),
            timeout_sec=timeout_sec,
            strict_order=strict_order,
        )
        return seq.validate(
            fetch_events=lambda: events,
            extract_status=lambda evts: evts,
        )

    def test_all_events_observed_in_order_returns_valid(self):
        with patch("time.sleep"):
            result = self._run(["A", "B", "C"])
        assert result.is_valid() is True
        assert result.missing == []
        assert result.out_of_order == []

    def test_missing_event_returns_invalid(self):
        with patch("time.sleep"), patch("time.time") as mt:
            mt.side_effect = [0.0, 6.0, 6.1, 6.2, 6.3]
            result = self._run(["A", "B"], timeout_sec=5.0)
        assert result.is_valid() is False
        assert "C" in result.missing

    def test_out_of_order_events_detected(self):
        with patch("time.sleep"):
            result = self._run(["A", "C", "B"])
        assert result.in_order() is False

    def test_timed_out_flag_set_on_timeout(self):
        with patch("time.sleep"), patch("time.time") as mt:
            mt.side_effect = [0.0, 6.0, 6.1, 6.2, 6.3]
            result = self._run([], timeout_sec=5.0)
        assert result.timed_out is True

    def test_duplicate_events_handled_gracefully(self):
        with patch("time.sleep"):
            result = self._run(["A", "A", "B", "C"])
        assert result.is_complete() is True

    def test_strict_order_false_accepts_out_of_order(self):
        seq = EventSequencer(
            expected_sequence=["A", "B", "C"],
            timeout_sec=5.0,
            strict_order=False,
        )
        with patch("time.sleep"):
            result = seq.validate(
                fetch_events=lambda: ["A", "C", "B"],
                extract_status=lambda evts: evts,
            )
        assert result.is_complete() is True
        assert result.is_valid() is True


class TestPerEventValidation:
    """per_event_timeout_sec routes to the per-daemon budget path."""

    def _run(self, events, expected=("A", "B", "C"),
             per_event=None, strict_order=True):
        if per_event is None:
            per_event = {e: 2.0 for e in expected}
        seq = EventSequencer(
            expected_sequence=list(expected),
            timeout_sec=30.0,
            per_event_timeout_sec=per_event,
            strict_order=strict_order,
        )
        return seq.validate(
            fetch_events=lambda: events,
            extract_status=lambda evts: evts,
        )

    def test_all_events_valid_with_per_event_budget(self):
        with patch("time.sleep"):
            result = self._run(["A", "B", "C"])
        assert result.is_valid() is True

    def test_fast_fail_on_first_missing_event_strict_order(self):
        # Use a monotonically-increasing mock clock (step=3.0 per call).
        # Each time.time() call returns a value 3.0 higher than the previous,
        # so (time.time() - event_start) is always >=3.0 > budget (2.0) after
        # the first poll — the budget check fires and the loop exits cleanly.
        import itertools
        times = itertools.count(start=0.0, step=3.0)
        with patch("time.sleep"), patch("time.time", side_effect=times):
            result = self._run(["B", "C"])  # A missing
        assert result.is_complete() is False
        assert "A" in result.missing

    def test_partial_sequence_detected(self):
        import itertools
        times = itertools.count(start=0.0, step=3.0)
        with patch("time.sleep"), patch("time.time", side_effect=times):
            result = self._run(["A"])  # B and C missing
        assert result.is_complete() is False
        assert "B" in result.missing or "C" in result.missing


class TestAssertValid:
    def test_passes_silently_on_valid_sequence(self):
        seq = EventSequencer(expected_sequence=["A", "B"], timeout_sec=5.0)
        with patch("time.sleep"):
            seq.assert_valid(
                fetch_events=lambda: ["A", "B"],
                extract_status=lambda evts: evts,
            )  # should not raise

    def test_raises_assertion_error_with_summary_on_invalid(self):
        seq = EventSequencer(expected_sequence=["A", "B", "C"], timeout_sec=5.0)
        with patch("time.sleep"), patch("time.time") as mt:
            mt.side_effect = [0.0, 6.0, 6.1, 6.2, 6.3]
            with pytest.raises(AssertionError) as exc_info:
                seq.assert_valid(
                    fetch_events=lambda: ["A"],
                    extract_status=lambda evts: evts,
                )
        msg = str(exc_info.value)
        assert "B" in msg or "C" in msg or "missing" in msg.lower()
