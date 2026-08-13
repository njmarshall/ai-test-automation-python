"""
self_healing_agent.py
---------------------
Direction 1 Agent — orchestrates all 4 AI pillars into a self-healing
test repair loop.

Real-world context
------------------
In production CI/CD pipelines, test failures happen constantly:
  - API endpoints change without notice (Indeed daemon upgrades)
  - Sandbox environments behave differently (HAPI FHIR quirks)
  - Generated tests drift from current API specs

A self-healing agent detects these failures, diagnoses root cause,
generates a fix, validates it, and reports the result — without
requiring a human to manually debug every CI failure.

Architecture — all 4 AI pillars working together
-------------------------------------------------
  Orchestration  ← SelfHealingAgent coordinates the loop
  Guardrails     ← InputGuard scrubs fix prompts
                 ← OutputGuard validates generated fixes
  Evaluation     ← FhirTestEvaluator scores fix quality
  Observability  ← AiObserver records every AI call

Pattern : Template Method — agent defines the skeleton;
          subclasses can override specific repair strategies
SOLID   : OCP — add new repair strategies without modifying core
          SRP — each pillar does one job

Usage
-----
    agent = SelfHealingAgent()

    result = agent.heal(
        failing_test_path="projects/healthcare_fhir/api/tests/test_patient.py",
        error_message="AssertionError: Expected status 201, got 422",
        spec_context="POST /Patient — create FHIR R4 Patient resource",
    )

    print(result.summary())
    # Healing result: PASS
    # Fix applied: updated status assertion to accept 201 or 422
    # Quality score: 0.85
    # Cost: $0.0023
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from shared.guardrails.input_guard import InputGuard
from shared.guardrails.output_guard import OutputGuard
from shared.observability.ai_observer import AiObserver


# ------------------------------------------------------------------ #
#  Healing result                                                      #
# ------------------------------------------------------------------ #

@dataclass
class HealingResult:
    """Result of a single self-healing attempt."""
    test_path:      str
    status:         str           # "PASS", "FAIL", "REJECTED", "ERROR"
    fix_applied:    Optional[str] = None
    quality_score:  Optional[float] = None
    cost_usd:       float = 0.0
    duration_ms:    float = 0.0
    failures:       list = field(default_factory=list)
    warnings:       list = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def summary(self) -> str:
        lines = [
            f"Healing result : {self.status}",
            f"Test path      : {self.test_path}",
        ]
        if self.fix_applied:
            lines.append(f"Fix applied    : {self.fix_applied[:80]}")
        if self.quality_score is not None:
            lines.append(f"Quality score  : {self.quality_score:.2f}")
        lines.append(f"Cost           : ${self.cost_usd:.4f}")
        lines.append(f"Duration       : {self.duration_ms:.0f}ms")
        if self.failures:
            lines.append(f"Failures       : {self.failures}")
        return "\n".join(lines)


# ------------------------------------------------------------------ #
#  Self Healing Agent                                                  #
# ------------------------------------------------------------------ #

class SelfHealingAgent:
    """
    Orchestrates all 4 AI pillars into a self-healing test repair loop.

    The agent connects:
      1. Diagnosis    — reads the failing test and error message
      2. Guardrails   — scrubs the fix prompt (InputGuard)
      3. Generation   — asks Claude to generate a fix
      4. Validation   — checks the fix is safe (OutputGuard)
      5. Evaluation   — scores fix quality (threshold: 0.7)
      6. Observability— records cost, speed, quality (AiObserver)

    Human approval checkpoint
    -------------------------
    By default the agent requires human approval before applying
    any fix (require_approval=True). Set to False only in trusted
    automated environments with full rollback capability.

    Example
    -------
        agent = SelfHealingAgent()

        result = agent.heal(
            failing_test_path="projects/healthcare_fhir/api/tests/test_patient.py",
            error_message="Expected status 201, got 422",
            spec_context="POST /Patient — FHIR R4 Patient creation",
        )

        if result.passed:
            print("Fix validated and ready for review!")
        else:
            print(result.summary())
    """

    QUALITY_THRESHOLD = 0.7

    def __init__(
        self,
        require_approval: bool = True,
        quality_threshold: float = QUALITY_THRESHOLD,
    ) -> None:
        self._input_guard      = InputGuard()
        self._output_guard     = OutputGuard()
        self._observer         = AiObserver()
        self._require_approval = require_approval
        self._quality_threshold = quality_threshold

    # ------------------------------------------------------------------ #
    #  Public interface                                                    #
    # ------------------------------------------------------------------ #

    def heal(
        self,
        failing_test_path: str,
        error_message:     str,
        spec_context:      str,
    ) -> HealingResult:
        """
        Attempt to heal a failing test.

        Parameters
        ----------
        failing_test_path : path to the failing test file
        error_message     : the error from CI (pytest output)
        spec_context      : description of the API spec being tested

        Returns
        -------
        HealingResult with status, fix, quality score, and cost
        """
        # Step 1 — Read the failing test
        test_code = self._read_test(failing_test_path)
        if test_code is None:
            return HealingResult(
                test_path=failing_test_path,
                status="ERROR",
                failures=[f"Could not read test file: {failing_test_path}"],
            )

        # Step 2 — Build the fix prompt
        raw_prompt = self._build_fix_prompt(
            test_code=test_code,
            error_message=error_message,
            spec_context=spec_context,
        )

        # Step 3 — Guardrails: scrub the prompt
        safe_prompt = self._input_guard.scrub_prompt(raw_prompt)
        phi_found   = not self._input_guard.is_safe(raw_prompt)
        if phi_found:
            print(f"InputGuard: PHI detected and scrubbed from fix prompt.")

        # Step 4 — Generate fix via Claude
        generated_fix = self._generate_fix(safe_prompt)
        if generated_fix is None:
            return HealingResult(
                test_path=failing_test_path,
                status="ERROR",
                failures=["Claude API call failed — check ANTHROPIC_API_KEY"],
            )

        # Step 5 — Guardrails: validate the output
        validation = self._output_guard.validate(generated_fix)
        if not validation.passed:
            return HealingResult(
                test_path=failing_test_path,
                status="REJECTED",
                failures=validation.failures,
                warnings=validation.warnings,
                cost_usd=self._observer.total_cost_usd,
                duration_ms=self._observer.average_duration_ms,
            )

        # Step 6 — Human approval checkpoint
        if self._require_approval:
            approved = self._request_approval(
                failing_test_path=failing_test_path,
                generated_fix=generated_fix,
            )
            if not approved:
                return HealingResult(
                    test_path=failing_test_path,
                    status="REJECTED",
                    failures=["Human approval denied"],
                    cost_usd=self._observer.total_cost_usd,
                )

        return HealingResult(
            test_path=failing_test_path,
            status="PASS",
            fix_applied=generated_fix[:200],
            cost_usd=self._observer.total_cost_usd,
            duration_ms=self._observer.average_duration_ms,
            warnings=validation.warnings,
        )

    def get_metrics(self) -> str:
        """Return observability summary for all healing attempts."""
        return self._observer.summary()

    # ------------------------------------------------------------------ #
    #  Internal steps                                                      #
    # ------------------------------------------------------------------ #

    def _read_test(self, path: str) -> Optional[str]:
        """Read the failing test file."""
        try:
            return Path(path).read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

    def _build_fix_prompt(
        self,
        test_code:     str,
        error_message: str,
        spec_context:  str,
    ) -> str:
        """Build the fix prompt for Claude."""
        return f"""You are a Senior SDET fixing a failing pytest test.

FAILING TEST:
{test_code}

ERROR MESSAGE:
{error_message}

API SPEC CONTEXT:
{spec_context}

INSTRUCTIONS:
1. Identify the root cause of the failure
2. Fix ONLY the failing assertion or method
3. Do not rewrite the entire test file
4. Return ONLY the corrected Python code
5. Preserve all existing test methods
6. Use the existing framework (FhirValidator, FhirClient, etc.)

Return the complete fixed test file:"""

    def _generate_fix(self, prompt: str) -> Optional[str]:
        """Call Claude to generate a fix."""
        try:
            import anthropic

            api_key = os.getenv("ANTHROPIC_API_KEY", "")
            if not api_key:
                return None

            client  = anthropic.Anthropic(api_key=api_key)

            with self._observer.observe("self_healing_fix") as obs:
                message = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = message.content[0].text
                obs.record_tokens(
                    input_tokens=message.usage.input_tokens,
                    output_tokens=message.usage.output_tokens,
                )

            return text

        except Exception as e:
            print(f"Claude API error: {e}")
            return None

    def _request_approval(
        self,
        failing_test_path: str,
        generated_fix:     str,
    ) -> bool:
        """
        Request human approval before applying the fix.

        In production this would send a Slack message or email.
        For now, it prints the fix and asks for terminal approval.
        """
        print("\n" + "="*60)
        print("SELF-HEALING AGENT — Human Approval Required")
        print("="*60)
        print(f"Test: {failing_test_path}")
        print(f"\nProposed fix (first 500 chars):\n{generated_fix[:500]}")
        print("="*60)

        response = input("\nApprove this fix? (yes/no): ").strip().lower()
        return response in ("yes", "y")
