"""
test_observability.py
---------------------
Tests for the AiObserver observability layer.

What we're testing
------------------
The observability layer that records every Claude API call
with cost, speed, and quality metrics.

Like Ooyala's engagement dashboard — records every event
so problems show up early. Drift detection catches slow
quality decline before it becomes a hard failure.
"""

from __future__ import annotations

import time
import pytest

from shared.observability.ai_observer import AiObserver


@pytest.mark.healthcare
class TestAiObserver:
    """Tests for AI call observability."""

    def test_observe_records_call(self) -> None:
        """Observer records a single AI call."""
        observer = AiObserver()

        with observer.observe("test_call") as obs:
            obs.record_tokens(input_tokens=100, output_tokens=50)

        assert observer.total_calls == 1
        assert observer.total_tokens == 150

    def test_observe_records_cost(self) -> None:
        """Observer calculates cost from token usage."""
        observer = AiObserver()

        with observer.observe("cost_test") as obs:
            obs.record_tokens(input_tokens=1000, output_tokens=500)

        assert observer.total_cost_usd > 0
        expected = (1000 / 1000 * 0.003) + (500 / 1000 * 0.015)
        assert abs(observer.total_cost_usd - expected) < 0.0001

    def test_observe_records_duration(self) -> None:
        """Observer records call duration in milliseconds."""
        observer = AiObserver()

        with observer.observe("duration_test") as obs:
            time.sleep(0.05)
            obs.record_tokens(input_tokens=10, output_tokens=10)

        record = observer.get_records()[0]
        assert record["duration_ms"] >= 50

    def test_observe_records_quality_score(self) -> None:
        """Observer records quality score from evaluation."""
        observer = AiObserver()

        with observer.observe("quality_test") as obs:
            obs.record_tokens(input_tokens=100, output_tokens=100)
            obs.record_quality(0.85)

        assert observer.average_quality_score == 0.85

    def test_drift_detection_triggers_below_threshold(self) -> None:
        """Drift detected when recent quality scores fall below threshold."""
        observer = AiObserver()

        for score in [0.9, 0.8, 0.6, 0.5, 0.4]:
            with observer.observe("drift_test") as obs:
                obs.record_tokens(input_tokens=10, output_tokens=10)
                obs.record_quality(score)

        assert observer.is_drifting(threshold=0.7, window=3)

    def test_no_drift_when_quality_stable(self) -> None:
        """No drift detected when quality scores are stable."""
        observer = AiObserver()

        for score in [0.9, 0.85, 0.88, 0.92, 0.87]:
            with observer.observe("stable_test") as obs:
                obs.record_tokens(input_tokens=10, output_tokens=10)
                obs.record_quality(score)

        assert not observer.is_drifting(threshold=0.7, window=5)

    def test_multiple_calls_tracked(self) -> None:
        """Multiple calls are all tracked correctly."""
        observer = AiObserver()

        for i in range(3):
            with observer.observe(f"call_{i}") as obs:
                obs.record_tokens(input_tokens=100, output_tokens=50)

        assert observer.total_calls == 3
        assert observer.total_tokens == 450

    def test_error_recorded_on_exception(self) -> None:
        """Errors are recorded when exceptions occur."""
        observer = AiObserver()

        with pytest.raises(ValueError):
            with observer.observe("error_test"):
                raise ValueError("API timeout")

        assert observer.total_calls == 1
        record = observer.get_records()[0]
        assert record["error"] == "API timeout"

    def test_summary_returns_string(self) -> None:
        """Summary returns a readable string."""
        observer = AiObserver()

        with observer.observe("summary_test") as obs:
            obs.record_tokens(input_tokens=500, output_tokens=200)
            obs.record_quality(0.88)

        summary = observer.summary()
        assert "Total calls" in summary
        assert "Total cost" in summary
        assert "Avg quality" in summary

    def test_empty_observer_summary(self) -> None:
        """Empty observer returns sensible summary."""
        observer = AiObserver()
        assert "No AI calls" in observer.summary()
