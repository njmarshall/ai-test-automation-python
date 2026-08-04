"""
fhir_test_evaluator.py
----------------------
Evaluates AI-generated FHIR test quality using DeepEval.

Real-world purpose
------------------
When Claude generates tests from a FHIR spec, we need to verify:
  1. RELEVANCE  — do the generated tests actually test FHIR endpoints?
  2. CORRECTNESS — are the assertions valid for FHIR R4?
  3. COVERAGE   — are all key endpoints covered?

This is LLM-as-a-judge evaluation — Claude evaluates Claude's output.
The judge uses Anthropic SDK so no OpenAI key is needed.

Pattern : Strategy — different metrics evaluate different quality dimensions
SOLID   : SRP — one evaluator, one job: score AI-generated test quality
          OCP — add new metrics without modifying existing ones

Usage
-----
    evaluator = FhirTestEvaluator()
    result = evaluator.evaluate_test_case(
        input_spec="POST /Patient — create a new Patient resource",
        generated_test=test_code_string,
    )
    print(result.summary())
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

from deepeval.metrics import GEval
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, SingleTurnParams
from anthropic import Anthropic


# ------------------------------------------------------------------ #
#  Evaluation result                                                   #
# ------------------------------------------------------------------ #

@dataclass
class EvaluationResult:
    """Result of a single test case evaluation."""
    test_name:    str
    metric_name:  str
    score:        float
    threshold:    float
    passed:       bool
    reason:       str

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"[{status}] {self.metric_name}: {self.score:.2f} "
            f"(threshold: {self.threshold}) — {self.reason[:100]}"
        )


# ------------------------------------------------------------------ #
#  Claude judge model (native Anthropic integration for DeepEval)      #
# ------------------------------------------------------------------ #

class ClaudeJudge(DeepEvalBaseLLM):
    """DeepEval judge model backed directly by the Anthropic SDK."""

    def __init__(self):
        self.client = Anthropic()

    def load_model(self):
        return self.client

    def generate(self, prompt: str) -> str:
        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self) -> str:
        return "claude-sonnet-4-6"


# ------------------------------------------------------------------ #
#  FHIR Test Evaluator                                                 #
# ------------------------------------------------------------------ #

class FhirTestEvaluator:
    """
    Evaluates AI-generated FHIR test quality using DeepEval GEval metric.

    Uses Claude as the judge model (no OpenAI key required).
    GEval is a flexible metric that evaluates based on custom criteria
    defined in plain English — perfect for domain-specific evaluation.

    Example
    -------
        evaluator = FhirTestEvaluator()
        results = evaluator.evaluate_test_case(
            input_spec="POST /Patient",
            generated_test="def test_create_patient...",
        )
        for r in results:
            print(r.summary())
    """

    def __init__(self, threshold: float = 0.7) -> None:
        self.threshold = threshold
        self._setup_judge()

    def _setup_judge(self) -> None:
        """Configure Claude as the DeepEval judge model."""
        # Set Anthropic key for DeepEval judge
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY not set. Export it before running evaluations."
            )

        # DeepEval uses OPENAI_API_KEY by default
        # We override with Anthropic by setting the model in GEval
        self._relevance_metric = GEval(
            name="FHIR Test Relevance",
            criteria=(
                "Evaluate whether the generated pytest test code is relevant "
                "to the FHIR API specification provided. "
                "A relevant test should: "
                "1. Test the correct HTTP method (POST, GET, PUT, DELETE) for the "
                "endpoint under test "
                "2. Target the correct FHIR endpoint path (/Patient, /Encounter, etc.) "
                "3. Assert an HTTP status code appropriate to the scenario under test: "
                "201 for a successful POST and 200 for a successful GET/PUT, OR an "
                "appropriate error status (e.g. 400, 404) when the test deliberately "
                "exercises an error path (invalid payload, missing required field, "
                "non-existent resource, etc.) "
                "4. Use FhirClient facade methods, not raw httpx calls "
                "Deliberate error-path/negative tests are just as relevant as happy-path "
                "tests — do NOT penalize a test for expecting a non-2xx status when its "
                "name and docstring show that is the scenario being tested. "
                "Score 1.0 if all criteria met, 0.0 if none met."
            ),
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
            ],
            threshold=self.threshold,
            model=ClaudeJudge(),
        )

        self._correctness_metric = GEval(
            name="FHIR Assertion Correctness",
            criteria=(
                "Evaluate whether the assertions in the generated test are "
                "correct for FHIR R4 API responses, given the scenario the test "
                "targets (happy path or error path). "
                "For a happy-path test, correct assertions should: "
                "1. Check resourceType field matches the resource (Patient, Encounter) "
                "2. Verify the id field is present after creation "
                "For an error-path/negative test, correct assertions should instead: "
                "1. Check resourceType equals 'OperationOutcome' "
                "2. Verify an 'issue' entry describing the failure is present "
                "In both cases, correct assertions should: "
                "3. Use FhirValidator fluent chaining for response-shape assertions "
                "(raw assert statements are acceptable only for preconditions, such as "
                "confirming setup succeeded before teardown) "
                "4. Handle HAPI sandbox quirks (200 OR 204 for DELETE, 200 OR 404 for "
                "delete of a non-existent resource) "
                "Score 1.0 if assertions are correct for the scenario under test, "
                "0.0 if assertions are wrong."
            ),
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
            ],
            threshold=self.threshold,
            model=ClaudeJudge(),
        )

    # ------------------------------------------------------------------ #
    #  Public interface                                                    #
    # ------------------------------------------------------------------ #

    def evaluate_test_case(
        self,
        input_spec:     str,
        generated_test: str,
        test_name:      str = "generated_test",
    ) -> List[EvaluationResult]:
        """
        Evaluate a single AI-generated test against two metrics.

        Parameters
        ----------
        input_spec     : the FHIR spec description that was given to the generator
        generated_test : the pytest test code that was generated
        test_name      : label for this test case in results

        Returns
        -------
        List of EvaluationResult — one per metric
        """
        test_case = LLMTestCase(
            input=input_spec,
            actual_output=generated_test,
        )

        results = []

        for metric in [self._relevance_metric, self._correctness_metric]:
            metric.measure(test_case)
            results.append(EvaluationResult(
                test_name=test_name,
                metric_name=metric.name,
                score=metric.score,
                threshold=self.threshold,
                passed=metric.score >= self.threshold,
                reason=metric.reason or "No reason provided",
            ))

        return results

    def evaluate_suite(
        self,
        test_cases: List[dict],
    ) -> dict:
        """
        Evaluate multiple test cases and return a summary report.

        Parameters
        ----------
        test_cases : list of dicts with keys: name, input_spec, generated_test

        Returns
        -------
        dict with overall pass rate and per-test results
        """
        all_results = []

        for tc in test_cases:
            results = self.evaluate_test_case(
                input_spec=tc["input_spec"],
                generated_test=tc["generated_test"],
                test_name=tc.get("name", "unnamed"),
            )
            all_results.extend(results)

        passed = sum(1 for r in all_results if r.passed)
        total  = len(all_results)

        return {
            "total":     total,
            "passed":    passed,
            "failed":    total - passed,
            "pass_rate": passed / total if total > 0 else 0.0,
            "results":   all_results,
        }
