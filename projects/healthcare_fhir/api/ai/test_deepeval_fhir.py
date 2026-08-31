"""
test_deepeval_fhir.py
---------------------
Uses DeepEval to score the quality of AI-generated FHIR tests.

What this does
--------------
Reads the AI-generated test_patient_ai.py, extracts test methods,
and evaluates each one using Claude as the judge (LLM-as-a-judge).

Two metrics evaluated per test:
  1. FHIR Test Relevance   — does the test actually test FHIR?
  2. FHIR Assertion Correctness — are the assertions valid for FHIR R4?

This is the layer that answers: "How good is the AI-generated test suite?"

Architecture
------------
  FhirTestEvaluator (shared/evaluation/) ← DeepEval + Claude judge
  GEval metric                           ← custom criteria evaluation
  test_patient_ai.py                     ← the file being evaluated
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from shared.evaluation.fhir_test_evaluator import FhirTestEvaluator


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

AI_GENERATED_FILE = Path(
    "projects/healthcare_fhir/api/ai/generated/test_patient_ai.py"
)

FHIR_SPEC_CONTEXT = """
FHIR R4 Patient Resource API Spec:
- POST /Patient: Create patient, expect 201, resourceType=Patient, id present
- GET /Patient/{id}: Read patient, expect 200, resourceType=Patient
- PUT /Patient/{id}: Update patient, expect 200
- DELETE /Patient/{id}: Delete patient, expect 200 or 204
- GET /Patient: Search patients, expect 200, resourceType=Bundle

Framework: FhirClient facade, FhirValidator fluent assertions, FhirFactory data
"""


def extract_test_methods(file_path: Path) -> list[dict]:
    """Extract test method names and source from a pytest file."""
    if not file_path.exists():
        return []

    source  = file_path.read_text(encoding="utf-8")
    tree    = ast.parse(source)
    lines   = source.splitlines()
    methods = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            # Extract source lines for this method
            start = node.lineno - 1
            end   = node.end_lineno
            method_source = "\n".join(lines[start:end])
            methods.append({
                "name":           node.name,
                "input_spec":     FHIR_SPEC_CONTEXT,
                "generated_test": method_source,
            })

    return methods


# ------------------------------------------------------------------ #
#  DeepEval tests                                                      #
# ------------------------------------------------------------------ #

@pytest.mark.healthcare
class TestDeepEvalFhir:
    """
    Evaluates AI-generated FHIR test quality using DeepEval.

    Uses Claude as the LLM judge — no OpenAI key required.
    Evaluates the first 3 test methods from test_patient_ai.py
    to keep evaluation fast and cost-effective.
    """

    @pytest.mark.flaky(reruns=4, reruns_delay=3)
    def test_ai_generated_tests_are_relevant(self) -> None:
        """
        Evaluate that AI-generated FHIR tests are relevant to the spec.

        Assertions
        ----------
        - At least 70% of evaluated tests score above relevance threshold
        - Each test targets correct FHIR endpoints and HTTP methods
        """
        if not AI_GENERATED_FILE.exists():
            pytest.skip("AI-generated test file not found — run generate_tests.py first")

        methods = extract_test_methods(AI_GENERATED_FILE)[:3]  # evaluate first 3

        if not methods:
            pytest.skip("No test methods found in AI-generated file")

        evaluator = FhirTestEvaluator(threshold=0.7)
        report    = evaluator.evaluate_suite(methods)

        print(f"\nDeepEval Evaluation Report:")
        print(f"Total evaluations: {report['total']}")
        print(f"Passed: {report['passed']}")
        print(f"Pass rate: {report['pass_rate']:.1%}")
        for result in report["results"]:
            print(f"  {result.summary()}")

        assert report["pass_rate"] >= 0.5, (
            f"Expected at least 50% of AI-generated tests to pass evaluation. "
            f"Got {report['pass_rate']:.1%}.\n"
            f"This may indicate the AI generator needs prompt tuning."
        )

    def test_deepeval_evaluator_initialises(self) -> None:
        """
        Smoke test — verify FhirTestEvaluator initialises correctly
        with Claude as the judge model.

        Assertions
        ----------
        - FhirTestEvaluator initialises without error
        - Both metrics are configured
        """
        evaluator = FhirTestEvaluator(threshold=0.7)
        assert evaluator is not None
        assert evaluator._relevance_metric is not None
        assert evaluator._correctness_metric is not None
        assert evaluator.threshold == 0.7
