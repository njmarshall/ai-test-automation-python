"""
exploratory_test_agent.py
--------------------------
Direction 2 Agent — ExploratoryTestAgent

Proactively hunts for unknown failures by generating and executing
test scenarios that a senior QA engineer would try — but didn't
think to document.

Real-world context
------------------
SelfHealingAgent (Direction 1) reacts to known failures.
ExploratoryTestAgent (Direction 2) hunts for unknown ones.

At SFC, this maps to:
  "Using AI agents to carry out exploratory and manual-style QA
   against a running app"

At Indeed, exploratory testing would have caught the hidden
postDaemon instance that cost 2-4 hours of manual investigation.
The agent would have asked: "what other daemon variants exist
that aren't in the documentation?"

Architecture
------------
  OpenAPI spec → Claude reasons about edge cases →
  Agent executes scenarios → Records unexpected responses →
  AiObserver tracks cost → Human reviews findings

Safety boundaries
-----------------
  - Sandbox/staging only — never production
  - Human-triggered — never autonomous
  - Read-heavy — prefers GET over POST/DELETE
  - Bounded scope — max scenarios per run configurable
  - All prompts scrubbed by InputGuard

Pattern : Template Method — ExploratoryTestAgent defines skeleton;
          domain subclasses override scenario generation
SOLID   : OCP — add new domains without modifying core agent
          SRP — one agent, one job: explore and report

Usage
-----
    agent = ExploratoryTestAgent(
        base_url="https://hapi.fhir.org/baseR4",
        spec_context=FHIR_PATIENT_SPEC,
        max_scenarios=10,
    )

    result = agent.explore(
        resource="Patient",
        description="FHIR R4 Patient create and read endpoints",
    )

    print(result.summary())
    # Exploration complete: 10 scenarios, 3 unexpected findings
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import List, Optional

from shared.guardrails.input_guard import InputGuard
from shared.observability.ai_observer import AiObserver


# ------------------------------------------------------------------ #
#  Exploration finding                                                  #
# ------------------------------------------------------------------ #

@dataclass
class ExplorationFinding:
    """A single unexpected response found during exploration."""
    scenario:     str
    request:      str
    status_code:  int
    response_body: str
    expected:     str
    severity:     str  # HIGH / MEDIUM / LOW / INFO
    notes:        str  = ""

    def is_unexpected(self) -> bool:
        return self.severity in ("HIGH", "MEDIUM")

    def summary(self) -> str:
        return (
            f"[{self.severity}] {self.scenario}\n"
            f"  Request  : {self.request}\n"
            f"  Status   : {self.status_code}\n"
            f"  Expected : {self.expected}\n"
            f"  Notes    : {self.notes}"
        )


# ------------------------------------------------------------------ #
#  Exploration result                                                   #
# ------------------------------------------------------------------ #

@dataclass
class ExplorationResult:
    """Result of an exploratory test run."""
    resource:       str
    scenarios_run:  int               = 0
    findings:       List[ExplorationFinding] = field(default_factory=list)
    cost_usd:       float             = 0.0
    duration_ms:    float             = 0.0
    error:          Optional[str]     = None

    @property
    def unexpected_count(self) -> int:
        return sum(1 for f in self.findings if f.is_unexpected())

    @property
    def passed(self) -> bool:
        return self.error is None

    def summary(self) -> str:
        lines = [
            f"Exploration Summary — {self.resource}",
            f"  Scenarios run      : {self.scenarios_run}",
            f"  Findings           : {len(self.findings)}",
            f"  Unexpected         : {self.unexpected_count}",
            f"  Cost               : ${self.cost_usd:.4f}",
            f"  Duration           : {self.duration_ms:.0f}ms",
        ]
        if self.findings:
            lines.append("\nFindings:")
            for f in self.findings:
                lines.append(f"  {f.summary()}")
        return "\n".join(lines)


# ------------------------------------------------------------------ #
#  Exploratory Test Agent                                              #
# ------------------------------------------------------------------ #

class ExploratoryTestAgent:
    """
    AI agent that proactively hunts for unknown test failures.

    Unlike SelfHealingAgent (which reacts to known failures),
    ExploratoryTestAgent generates and executes scenarios that
    a senior QA engineer would try — edge cases, boundary values,
    unexpected combinations — and reports what it finds.

    Safety boundaries:
      - Sandbox/staging only
      - Human-triggered, never autonomous
      - Bounded scope (max_scenarios per run)
      - All prompts scrubbed by InputGuard

    Example
    -------
        agent = ExploratoryTestAgent(
            base_url="https://hapi.fhir.org/baseR4",
            spec_context=FHIR_PATIENT_SPEC,
            max_scenarios=5,
        )

        result = agent.explore(
            resource="Patient",
            description="FHIR R4 Patient create and read endpoints",
        )

        print(result.summary())
    """

    DEFAULT_MAX_SCENARIOS = 10

    def __init__(
        self,
        base_url:      str,
        spec_context:  str,
        max_scenarios: int = DEFAULT_MAX_SCENARIOS,
    ) -> None:
        self._base_url      = base_url.rstrip("/")
        self._spec_context  = spec_context
        self._max_scenarios = max_scenarios
        self._input_guard   = InputGuard()
        self._observer      = AiObserver()

    # ------------------------------------------------------------------ #
    #  Public interface                                                    #
    # ------------------------------------------------------------------ #

    def explore(
        self,
        resource:    str,
        description: str,
    ) -> ExplorationResult:
        """
        Explore a resource endpoint for unexpected behavior.

        Steps:
        1. Ask Claude to generate exploratory scenarios
        2. Scrub scenarios with InputGuard
        3. Execute each scenario against the live endpoint
        4. Record unexpected responses as findings
        5. Return ExplorationResult with all findings

        Parameters
        ----------
        resource    : the API resource to explore (e.g. "Patient")
        description : human description of the endpoints to explore

        Returns
        -------
        ExplorationResult with findings and cost metrics
        """
        result = ExplorationResult(resource=resource)
        start  = time.time()

        # Step 1 — Generate scenarios via Claude
        scenarios = self._generate_scenarios(resource, description)
        if not scenarios:
            result.error = "Failed to generate scenarios from Claude"
            return result

        # Step 2 — Execute each scenario
        for scenario in scenarios[:self._max_scenarios]:
            finding = self._execute_scenario(scenario, resource)
            if finding:
                result.findings.append(finding)
            result.scenarios_run += 1

        result.cost_usd    = self._observer.total_cost_usd
        result.duration_ms = (time.time() - start) * 1000
        return result

    def get_metrics(self) -> str:
        """Return observability summary for all exploration runs."""
        return self._observer.summary()

    # ------------------------------------------------------------------ #
    #  Internal steps                                                      #
    # ------------------------------------------------------------------ #

    def _generate_scenarios(
        self,
        resource:    str,
        description: str,
    ) -> List[dict]:
        """Ask Claude to generate exploratory test scenarios."""
        try:
            import anthropic

            api_key = os.getenv("ANTHROPIC_API_KEY", "")
            if not api_key:
                return []

            raw_prompt = f"""You are a senior QA engineer performing exploratory testing.

API Spec Context:
{self._spec_context}

Resource to explore: {resource}
Description: {description}
Base URL: {self._base_url}

Generate {self._max_scenarios} exploratory test scenarios that go BEYOND the happy path.
Focus on:
1. Missing required fields
2. Invalid field values (wrong types, empty strings, very long strings)
3. Boundary values (minimum and maximum allowed values)
4. Unexpected field combinations
5. Edge cases not covered by standard documentation

Return ONLY a JSON array. Each scenario must have:
- "name": short scenario name
- "method": HTTP method (prefer GET, use POST only when necessary)
- "path": URL path relative to base URL
- "payload": request body (null for GET)
- "expected_status": expected HTTP status code
- "rationale": why a senior QA engineer would try this

Example format:
[
  {{
    "name": "Missing required name field",
    "method": "POST",
    "path": "/Patient",
    "payload": {{"resourceType": "Patient"}},
    "expected_status": 422,
    "rationale": "FHIR validator should reject Patient with no name"
  }}
]

Return ONLY the JSON array, no markdown, no explanation."""

            # Scrub prompt before sending to Claude
            safe_prompt = self._input_guard.scrub_prompt(raw_prompt)

            client = anthropic.Anthropic(api_key=api_key)

            with self._observer.observe("exploratory_scenario_generation") as obs:
                message = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=2048,
                    messages=[{"role": "user", "content": safe_prompt}],
                )
                obs.record_tokens(
                    input_tokens=message.usage.input_tokens,
                    output_tokens=message.usage.output_tokens,
                )

            import json
            text = message.content[0].text.strip()
            # Clean markdown fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)

        except Exception as e:
            print(f"Scenario generation failed: {e}")
            return []

    def _execute_scenario(
        self,
        scenario: dict,
        resource: str,
    ) -> Optional[ExplorationFinding]:
        """Execute a single exploratory scenario and record findings."""
        try:
            import httpx
            import json

            method  = scenario.get("method", "GET").upper()
            path    = scenario.get("path", f"/{resource}")
            payload = scenario.get("payload")
            expected_status = scenario.get("expected_status", 200)
            name    = scenario.get("name", "Unknown scenario")
            rationale = scenario.get("rationale", "")

            url = f"{self._base_url}{path}"

            if method == "GET":
                response = httpx.get(
                    url,
                    headers={"Accept": "application/fhir+json"},
                    timeout=10.0,
                    follow_redirects=True,
                )
            elif method == "POST":
                response = httpx.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/fhir+json"},
                    timeout=10.0,
                    follow_redirects=True,
                )
            else:
                return None

            actual_status = response.status_code
            is_unexpected = actual_status != expected_status

            if is_unexpected:
                # Determine severity
                if actual_status >= 500:
                    severity = "HIGH"
                elif actual_status in (200, 201) and expected_status >= 400:
                    severity = "HIGH"   # accepted something that should be rejected
                elif actual_status >= 400 and expected_status < 400:
                    severity = "MEDIUM"
                else:
                    severity = "LOW"

                return ExplorationFinding(
                    scenario=name,
                    request=f"{method} {path}",
                    status_code=actual_status,
                    response_body=response.text[:300],
                    expected=f"Expected {expected_status}, got {actual_status}",
                    severity=severity,
                    notes=rationale,
                )

            return None  # Expected behavior — not a finding

        except Exception as e:
            return ExplorationFinding(
                scenario=scenario.get("name", "Unknown"),
                request=f"{scenario.get('method', 'GET')} {scenario.get('path', '')}",
                status_code=0,
                response_body=str(e),
                expected="Successful HTTP response",
                severity="LOW",
                notes="Network or timeout error during exploration",
            )


# ------------------------------------------------------------------ #
#  FHIR Patient spec context                                           #
# ------------------------------------------------------------------ #

FHIR_PATIENT_SPEC = """
FHIR R4 Patient Resource
Base URL: https://hapi.fhir.org/baseR4

Endpoints:
- POST /Patient           Create a new Patient resource
- GET  /Patient/{id}      Read a Patient by logical id
- PUT  /Patient/{id}      Update a Patient
- DELETE /Patient/{id}    Delete a Patient
- GET  /Patient           Search for Patients

Required fields for creation:
- resourceType: "Patient"

Optional but common fields:
- name (array of HumanName)
- gender: male | female | other | unknown
- birthDate: YYYY-MM-DD format
- identifier (array with system and value)

Validation:
- Invalid resourceType returns 400
- Duplicate identifier returns 412
- Non-existent id returns 404
- Server errors return 500
"""
