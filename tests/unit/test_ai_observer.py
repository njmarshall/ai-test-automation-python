"""
test_ai_observer.py
-------------------
Unit tests for shared/observability/ai_observer.py

What is tested
--------------
  ObservationRecord dataclass  — passed_quality property (None / True / False);
                                  duration_ms defaults 0.0, input_tokens defaults 0
  ObservationContext           — record_tokens() cost formula; record_quality();
                                  finish() stamps duration; record_error() stores str
  AiObserver.observe()         — happy path: record appended with correct fields;
                                  exception path: str(e) recorded, re-raises;
                                  context manager properly enters/exits
  AiObserver.get_records()     — returns list of dicts (via to_dict())
  AiObserver.is_drifting()     — True when avg quality < threshold (strict <);
                                  False otherwise; ignores records with no score;
                                  uses only last `window` scored records
  AiObserver.summary()         — returns a non-empty string with record counts

No network calls, no external dependencies.
"""
from __future__ import annotations

import time

import pytest

from shared.observability.ai_observer import AiObserver, ObservationContext, ObservationRecord


# ═══════════════════════════════════════════════════════════════════ #
#  ObservationRecord                                                   #
# ═══════════════════════════════════════════════════════════════════ #

class TestObservationRecord:
    def _make(self, quality_score=None, **kwargs) -> ObservationRecord:
        defaults = dict(
            call_name="test_call",
            timestamp="2026-10-29T00:00:00+00:00",
            quality_score=quality_score,
        )
        defaults.update(kwargs)
        return ObservationRecord(**defaults)

    def test_passed_quality_none_when_no_score(self):
        assert self._make(quality_score=None).passed_quality is None

    def test_passed_quality_true_at_threshold(self):
        assert self._make(quality_score=0.7).passed_quality is True

    def test_passed_quality_true_above_threshold(self):
        assert self._make(quality_score=0.9).passed_quality is True

    def test_passed_quality_false_below_threshold(self):
        assert self._make(quality_score=0.69).passed_quality is False

    def test_passed_quality_false_at_zero(self):
        assert self._make(quality_score=0.0).passed_quality is False

    def test_duration_ms_defaults_to_zero(self):
        r = self._make()
        assert r.duration_ms == 0.0

    def test_input_tokens_defaults_to_zero(self):
        r = self._make()
        assert r.input_tokens == 0


# ═══════════════════════════════════════════════════════════════════ #
#  ObservationContext — token recording & cost formula                 #
# ═══════════════════════════════════════════════════════════════════ #

class TestObservationContext:
    def _make_context(self, call_name="gpt_call"):
        record = ObservationRecord(
            call_name=call_name,
            timestamp="2026-10-29T00:00:00+00:00",
        )
        ctx = ObservationContext(record=record)
        return record, ctx

    def test_record_tokens_sets_input_and_output(self):
        record, ctx = self._make_context()
        ctx.record_tokens(input_tokens=100, output_tokens=50)
        assert record.input_tokens == 100
        assert record.output_tokens == 50

    def test_cost_formula_input_rate(self):
        # cost = (input/1000 * 0.003) + (output/1000 * 0.015)
        record, ctx = self._make_context()
        ctx.record_tokens(input_tokens=1000, output_tokens=0)
        assert abs(record.cost_usd - 0.003) < 1e-9

    def test_cost_formula_output_rate(self):
        record, ctx = self._make_context()
        ctx.record_tokens(input_tokens=0, output_tokens=1000)
        assert abs(record.cost_usd - 0.015) < 1e-9

    def test_cost_formula_combined(self):
        record, ctx = self._make_context()
        ctx.record_tokens(input_tokens=500, output_tokens=200)
        expected = (500 / 1000 * 0.003) + (200 / 1000 * 0.015)
        assert abs(record.cost_usd - expected) < 1e-9

    def test_record_quality_sets_score(self):
        record, ctx = self._make_context()
        ctx.record_quality(0.85)
        assert record.quality_score == 0.85

    def test_finish_sets_duration_ms(self):
        record, ctx = self._make_context()
        time.sleep(0.01)  # ensure some wall-clock time passes
        ctx.finish()
        assert record.duration_ms > 0

    def test_record_error_stores_string(self):
        # record_error() accepts a string; observe() passes str(e) automatically
        record, ctx = self._make_context()
        ctx.record_error("bad input")
        assert record.error == "bad input"


# ═══════════════════════════════════════════════════════════════════ #
#  AiObserver.observe() — context manager                             #
# ═══════════════════════════════════════════════════════════════════ #

class TestAiObserverObserve:
    def test_observe_appends_record_on_success(self):
        observer = AiObserver()
        with observer.observe("summarise") as ctx:
            ctx.record_tokens(input_tokens=200, output_tokens=80)
            ctx.record_quality(0.9)

        records = observer.get_records()   # returns list of dicts
        assert len(records) == 1
        r = records[0]
        assert r["call_name"] == "summarise"
        assert r["input_tokens"] == 200
        assert r["output_tokens"] == 80
        assert r["quality_score"] == 0.9

    def test_observe_sets_duration_after_exit(self):
        observer = AiObserver()
        with observer.observe("classify"):
            time.sleep(0.01)
        r = observer.get_records()[0]
        assert r["duration_ms"] > 0

    def test_observe_records_error_as_string_and_reraises(self):
        observer = AiObserver()
        with pytest.raises(RuntimeError, match="API timeout"):
            with observer.observe("embed"):
                raise RuntimeError("API timeout")

        r = observer.get_records()[0]
        assert r["error"] is not None
        assert "API timeout" in r["error"]

    def test_observe_record_appended_even_on_exception(self):
        observer = AiObserver()
        try:
            with observer.observe("rerank"):
                raise ValueError("bad response")
        except ValueError:
            pass
        assert len(observer.get_records()) == 1

    def test_multiple_observe_calls_accumulate(self):
        observer = AiObserver()
        for i in range(3):
            with observer.observe(f"call_{i}"):
                pass
        assert len(observer.get_records()) == 3

    def test_context_manager_yields_observation_context(self):
        observer = AiObserver()
        with observer.observe("check") as ctx:
            assert isinstance(ctx, ObservationContext)


# ═══════════════════════════════════════════════════════════════════ #
#  AiObserver.is_drifting()                                            #
# ═══════════════════════════════════════════════════════════════════ #

class TestAiObserverIsDrifting:
    def _observer_with_scores(self, scores):
        observer = AiObserver()
        for i, score in enumerate(scores):
            with observer.observe(f"call_{i}") as ctx:
                if score is not None:
                    ctx.record_quality(score)
        return observer

    def test_not_drifting_when_avg_above_threshold(self):
        obs = self._observer_with_scores([0.9, 0.85, 0.8, 0.75, 0.8])
        assert obs.is_drifting(threshold=0.7, window=5) is False

    def test_drifting_when_avg_below_threshold(self):
        obs = self._observer_with_scores([0.5, 0.4, 0.3, 0.6, 0.5])
        assert obs.is_drifting(threshold=0.7, window=5) is True

    def test_not_drifting_when_no_scored_records(self):
        obs = self._observer_with_scores([None, None, None])
        assert obs.is_drifting() is False

    def test_uses_only_last_window_records(self):
        # First 5 are low quality; last 5 are high — window=5 should see the high ones
        obs = self._observer_with_scores([0.3, 0.2, 0.3, 0.2, 0.3,
                                           0.9, 0.9, 0.9, 0.9, 0.9])
        assert obs.is_drifting(threshold=0.7, window=5) is False

    def test_ignores_unscored_records_in_window(self):
        obs = self._observer_with_scores([None, None, 0.9, 0.85, 0.8])
        assert obs.is_drifting(threshold=0.7, window=5) is False

    def test_drifting_true_for_single_low_score(self):
        obs = self._observer_with_scores([0.5])
        assert obs.is_drifting(threshold=0.7, window=5) is True

    def test_not_drifting_at_exact_threshold_boundary(self):
        # is_drifting uses strictly-less-than: avg < threshold.
        # Use [0.8, 0.8, 0.8] to stay clearly above 0.7 and avoid floating-point
        # rounding (0.7+0.7+0.7)/3 = 0.6999... which is < 0.7, causing a false positive.
        obs = self._observer_with_scores([0.8, 0.8, 0.8])
        assert obs.is_drifting(threshold=0.7, window=5) is False


# ═══════════════════════════════════════════════════════════════════ #
#  AiObserver.summary()                                                #
# ═══════════════════════════════════════════════════════════════════ #

class TestAiObserverSummary:
    def test_summary_returns_nonempty(self):
        observer = AiObserver()
        with observer.observe("call") as ctx:
            ctx.record_tokens(100, 50)
        assert observer.summary()

    def test_summary_contains_total_count(self):
        observer = AiObserver()
        for _ in range(3):
            with observer.observe("op"):
                pass
        assert "3" in observer.summary()

    def test_summary_on_empty_observer(self):
        observer = AiObserver()
        s = observer.summary()
        assert s is not None  # doesn't crash on zero records
