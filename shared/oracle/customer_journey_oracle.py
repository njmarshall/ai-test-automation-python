"""
customer_journey_oracle.py
---------------------------
Verifies that a multi-step workflow produced the outcome the CUSTOMER
actually needed, not just that each step returned a success status and
the system recorded the expected state.

Real-world origin
------------------
Article 14 named three separate observations up front: API response,
committed database state, and downstream business effect. The
database-layer tests in that article only built out the first two.

Article 15 extended the framing: committed state is evidence TOWARD the
correct outcome, but it is not the outcome itself. A workflow can pass
every technical checkpoint and still fail the person at the end of it,
if what reached them was incomplete. That article named the missing
piece "Phase 7" and left it unbuilt. This module is Phase 7.

How it works
-------------
1. As the workflow runs, the test records what it observed at each step
   with `record(...)`. A step's `ok` flag means only "this step did not
   technically fail". It makes no claim about the customer outcome.
2. The engineer who owns the business rule supplies two functions once,
   per journey: `outcome_check` (did the customer get what they needed,
   judged across ALL observations?) and `impact_on_failure` (what does a
   failure mean for the customer, in plain language?).
3. `evaluate()` runs the check and returns a JourneyResult. Every step
   can be ok while `customer_outcome_met` is False. That disagreement is
   the whole point.

Scope
------
The oracle judges the observations it is given. It cannot see what
happens after the workflow's own output (for example, what a third
party vendor does with a message), and it cannot show that a person
read or acted on anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class StepObservation:
    """What was observed at one step of the journey."""
    step_name: str
    ok:        bool
    detail:    str            = ""
    data:      Dict[str, Any] = field(default_factory=dict)


@dataclass
class JourneyResult:
    """The oracle's verdict for one journey."""
    journey_name:         str
    steps:                List[StepObservation]
    customer_outcome_met: bool
    customer_impact:      str
    failed_at:            Optional[str]  = None
    evidence:             Dict[str, Any] = field(default_factory=dict)

    def all_steps_technically_ok(self) -> bool:
        return all(s.ok for s in self.steps)

    def summary(self) -> str:
        lines = [
            f"CustomerJourneyOracle result: {self.journey_name}",
            f"  Steps technically ok : {self.all_steps_technically_ok()}",
            f"  Customer outcome met : {self.customer_outcome_met}",
        ]
        if not self.customer_outcome_met:
            lines.append(f"  Customer impact      : {self.customer_impact}")
            if self.failed_at:
                lines.append(f"  Diagnostic pointer   : {self.failed_at}")
        return "\n".join(lines)


class CustomerJourneyOracle:
    """Records step observations, then judges the customer outcome."""

    def __init__(
        self,
        journey_name:      str,
        outcome_check:     Callable[[Dict[str, StepObservation]], bool],
        impact_on_failure: Callable[[Dict[str, StepObservation]], str],
    ) -> None:
        self.journey_name       = journey_name
        self._outcome_check     = outcome_check
        self._impact_on_failure = impact_on_failure
        self._observations: Dict[str, StepObservation] = {}

    def record(
        self, step_name: str, ok: bool, detail: str = "", **data: Any
    ) -> StepObservation:
        obs = StepObservation(step_name=step_name, ok=ok, detail=detail, data=data)
        self._observations[step_name] = obs
        return obs

    def evaluate(self) -> JourneyResult:
        outcome_met = self._outcome_check(self._observations)
        impact = "" if outcome_met else self._impact_on_failure(self._observations)

        failed_at = None
        if not outcome_met:
            for name, obs in reversed(list(self._observations.items())):
                if not obs.ok:
                    failed_at = name
                    break

        return JourneyResult(
            journey_name=self.journey_name,
            steps=list(self._observations.values()),
            customer_outcome_met=outcome_met,
            customer_impact=impact,
            failed_at=failed_at,
            evidence={name: obs.data for name, obs in self._observations.items()},
        )
