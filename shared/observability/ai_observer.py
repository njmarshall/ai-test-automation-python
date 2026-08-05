"""
ai_observer.py
--------------
Observability layer — logs every Claude API call with cost, speed,
and quality metrics.

Real-world context
------------------
In production AI systems, you need to know:
  - How much is each AI call costing?
  - How fast is the AI responding?
  - Is quality drifting over time?
  - Which prompts are most expensive?

This is the "dashboard in a car" for your AI system.
Like Ooyala's engagement dashboard for TV clients —
it records every event so problems show up early.

Pattern : Observer — wraps existing AI calls without modifying them
SOLID   : OCP — add new metrics without changing existing code
          SRP — one class, one job: observe and log AI calls

Usage
-----
    observer = AiObserver()

    # Wrap any Claude API call
    with observer.observe("fhir_test_generation") as obs:
        response = claude.messages.create(...)
        obs.record_tokens(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    # Check metrics
    print(observer.summary())
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Generator, List, Optional


# ------------------------------------------------------------------ #
#  Pricing constants (Claude claude-sonnet-4-6 as of 2026)              #
# ------------------------------------------------------------------ #

INPUT_COST_PER_1K_TOKENS  = 0.003   # $0.003 per 1K input tokens
OUTPUT_COST_PER_1K_TOKENS = 0.015   # $0.015 per 1K output tokens


# ------------------------------------------------------------------ #
#  Observation record                                                  #
# ------------------------------------------------------------------ #

@dataclass
class ObservationRecord:
    """A single AI call observation."""
    call_name:      str
    timestamp:      str
    duration_ms:    float         = 0.0
    input_tokens:   int           = 0
    output_tokens:  int           = 0
    cost_usd:       float         = 0.0
    quality_score:  Optional[float] = None
    error:          Optional[str] = None
    metadata:       dict          = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def passed_quality(self) -> Optional[bool]:
        if self.quality_score is None:
            return None
        return self.quality_score >= 0.7

    def to_dict(self) -> dict:
        return {
            "call_name":     self.call_name,
            "timestamp":     self.timestamp,
            "duration_ms":   round(self.duration_ms, 2),
            "input_tokens":  self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens":  self.total_tokens,
            "cost_usd":      round(self.cost_usd, 6),
            "quality_score": self.quality_score,
            "passed_quality": self.passed_quality,
            "error":         self.error,
            "metadata":      self.metadata,
        }


# ------------------------------------------------------------------ #
#  Observation context manager                                         #
# ------------------------------------------------------------------ #

class ObservationContext:
    """Context manager for a single AI call observation."""

    def __init__(self, record: ObservationRecord) -> None:
        self._record     = record
        self._start_time = time.time()

    def record_tokens(
        self,
        input_tokens:  int,
        output_tokens: int,
    ) -> None:
        """Record token usage from the API response."""
        self._record.input_tokens  = input_tokens
        self._record.output_tokens = output_tokens
        self._record.cost_usd      = (
            (input_tokens  / 1000) * INPUT_COST_PER_1K_TOKENS +
            (output_tokens / 1000) * OUTPUT_COST_PER_1K_TOKENS
        )

    def record_quality(self, score: float) -> None:
        """Record a quality score from DeepEval evaluation."""
        self._record.quality_score = score

    def record_error(self, error: str) -> None:
        """Record an error that occurred during the call."""
        self._record.error = error

    def add_metadata(self, **kwargs) -> None:
        """Add arbitrary metadata to the observation."""
        self._record.metadata.update(kwargs)

    def finish(self) -> None:
        """Finalize the observation — record duration."""
        self._record.duration_ms = (time.time() - self._start_time) * 1000


# ------------------------------------------------------------------ #
#  AI Observer                                                         #
# ------------------------------------------------------------------ #

class AiObserver:
    """
    Observability layer for Claude API calls.

    Records every AI call with cost, speed, and quality metrics.
    Detects drift when quality scores decline over time.

    Example
    -------
        observer = AiObserver()

        with observer.observe("fhir_generation") as obs:
            response = claude.messages.create(
                model="claude-sonnet-4-6",
                messages=[{"role": "user", "content": prompt}]
            )
            obs.record_tokens(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

        print(observer.summary())
    """

    def __init__(self) -> None:
        self._records: List[ObservationRecord] = []

    @contextmanager
    def observe(self, call_name: str) -> Generator[ObservationContext, None, None]:
        """
        Context manager that observes a single AI call.

        Usage
        -----
            with observer.observe("test_generation") as obs:
                response = claude.messages.create(...)
                obs.record_tokens(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )
        """
        record = ObservationRecord(
            call_name=call_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        context = ObservationContext(record)

        try:
            yield context
        except Exception as e:
            context.record_error(str(e))
            raise
        finally:
            context.finish()
            self._records.append(record)

    # ------------------------------------------------------------------ #
    #  Metrics                                                             #
    # ------------------------------------------------------------------ #

    @property
    def total_calls(self) -> int:
        return len(self._records)

    @property
    def total_cost_usd(self) -> float:
        return sum(r.cost_usd for r in self._records)

    @property
    def total_tokens(self) -> int:
        return sum(r.total_tokens for r in self._records)

    @property
    def average_duration_ms(self) -> float:
        if not self._records:
            return 0.0
        return sum(r.duration_ms for r in self._records) / len(self._records)

    @property
    def average_quality_score(self) -> Optional[float]:
        scored = [r.quality_score for r in self._records
                  if r.quality_score is not None]
        if not scored:
            return None
        return sum(scored) / len(scored)

    def is_drifting(self, threshold: float = 0.7, window: int = 5) -> bool:
        """
        Return True if quality is drifting downward.

        Checks the last `window` scored calls — if average
        falls below threshold, drift is detected.

        This mirrors the StalenessDetector pattern — catching
        gradual decline before it becomes a hard failure.
        """
        recent_scores = [
            r.quality_score for r in self._records[-window:]
            if r.quality_score is not None
        ]
        if not recent_scores:
            return False
        return (sum(recent_scores) / len(recent_scores)) < threshold

    def get_records(self) -> List[dict]:
        """Return all observation records as dicts."""
        return [r.to_dict() for r in self._records]

    def summary(self) -> str:
        """Return a human-readable summary of all observations."""
        if not self._records:
            return "No AI calls observed yet."

        lines = [
            f"AI Observer Summary",
            f"  Total calls    : {self.total_calls}",
            f"  Total tokens   : {self.total_tokens:,}",
            f"  Total cost     : ${self.total_cost_usd:.4f}",
            f"  Avg duration   : {self.average_duration_ms:.0f}ms",
        ]

        if self.average_quality_score is not None:
            lines.append(
                f"  Avg quality    : {self.average_quality_score:.2f}"
            )
            lines.append(
                f"  Drifting       : {self.is_drifting()}"
            )

        errors = [r for r in self._records if r.error]
        if errors:
            lines.append(f"  Errors         : {len(errors)}")

        return "\n".join(lines)
