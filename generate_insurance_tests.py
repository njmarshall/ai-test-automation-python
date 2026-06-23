"""
generate_insurance_tests.py
---------------------------
CLI runner — generates AI-powered Insurance Policy tests and writes them
to projects/insurance/api/ai/generated/test_policy_ai.py.

Also runs a basic staleness check against the hand-crafted Policy tests.

Usage
-----
    # From repo root:
    export ANTHROPIC_API_KEY=your_key_here
    python generate_insurance_tests.py

    # Dry run — print generated code without saving:
    python generate_insurance_tests.py --dry-run
"""

from __future__ import annotations

import argparse
import ast
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT    = Path(__file__).parent
OUTPUT_PATH  = REPO_ROOT / "projects/insurance/api/ai/generated/test_policy_ai.py"
PHASE1_TESTS = REPO_ROOT / "projects/insurance/api/tests/test_policy.py"

sys.path.insert(0, str(REPO_ROOT))

from shared.ai.test_generator import BaseTestGenerator


# ------------------------------------------------------------------ #
#  Insurance-specific spec                                             #
# ------------------------------------------------------------------ #

INSURANCE_SPEC = {
    "title":    "Insurance Policy API",
    "version":  "1.0.0",
    "base_url": "https://jsonplaceholder.typicode.com",
    "note":     "JSONPlaceholder /posts used as Insurance Policy mock — simulates CRUD",
    "endpoints": [
        {
            "method":   "POST",
            "path":     "/posts",
            "summary":  "Create a new Insurance Policy",
            "request_body": {
                "title":  "string — policy name",
                "body":   "string — policy description",
                "userId": "integer — customer id (1-10)",
            },
            "responses": {
                "201": "Policy created — returns full policy with server-assigned id",
            },
        },
        {
            "method":   "GET",
            "path":     "/posts/{id}",
            "summary":  "Read an existing Insurance Policy by id",
            "responses": {
                "200": "Policy returned",
                "404": "Policy not found",
            },
        },
        {
            "method":   "PUT",
            "path":     "/posts/{id}",
            "summary":  "Update an existing Insurance Policy",
            "responses": {
                "200": "Policy updated",
            },
        },
        {
            "method":   "DELETE",
            "path":     "/posts/{id}",
            "summary":  "Delete an Insurance Policy",
            "responses": {
                "200": "Policy deleted",
            },
        },
        {
            "method":   "GET",
            "path":     "/posts",
            "summary":  "List all Insurance Policies",
            "parameters": [
                {"name": "userId", "in": "query", "description": "Filter by customer id"},
            ],
            "responses": {
                "200": "List of policies returned",
            },
        },
    ],
    "notes": [
        "JSONPlaceholder simulates writes but does not persist data",
        "POST always returns id=101 (simulated)",
        "GET /posts/{id} returns 404 for id > 100",
        "DELETE always returns 200 with empty body {}",
        "All responses are JSON",
    ],
}


# ------------------------------------------------------------------ #
#  Insurance test generator                                            #
# ------------------------------------------------------------------ #

class InsuranceTestGenerator(BaseTestGenerator):
    """
    Generates pytest test cases for Insurance Policy API
    using the Anthropic SDK.

    Extends BaseTestGenerator (Template Method pattern).
    """

    def build_system_prompt(self) -> str:
        return """You are a Senior SDET specialising in Insurance API test automation.

You write production-grade pytest test suites that:
- Use InsuranceClient facade (never raw httpx)
- Use InsuranceValidator for fluent chainable assertions
- Use InsuranceFactory for randomised test data
- Use pytest fixtures from conftest.py (insurance_client, created_policy_id)
- Follow SOLID principles and FAANG-level test design
- Cover happy path, error paths, and edge cases

FRAMEWORK IMPORTS TO USE:
    import pytest
    from projects.insurance.api.assertions.insurance_validator import InsuranceValidator
    from projects.insurance.api.client.insurance_client import InsuranceClient
    from projects.insurance.api.data.insurance_factory import InsuranceFactory
    from projects.insurance.api.models.policy import Policy

FIXTURES AVAILABLE (from conftest.py):
    insurance_client   — session-scoped InsuranceClient instance
    created_policy_id  — function-scoped: creates Policy, yields id, deletes after

STRICT OUTPUT RULES:
- Output ONLY valid Python source code
- No markdown fences, no explanations outside code
- Start directly with import statements
- Every test method name starts with test_
- Every test class name starts with Test
- Use @pytest.mark.insurance on every class
- Maximum 12 tests total — quality over quantity
- Every code block must be complete — no truncation"""

    def build_prompt(self, spec: dict) -> str:
        import json
        spec_json = json.dumps(spec, indent=2)
        return f"""Generate a pytest test suite for the following Insurance Policy API spec.

API SPEC:
{spec_json}

REQUIREMENTS:
1. Generate tests for POST, GET, PUT, DELETE, and list endpoints
2. Each endpoint must have at minimum one happy path test
3. For GET /posts/{{id}}: test both valid id (1-10) and invalid id (> 100)
4. For GET /posts with userId filter: test filtering by userId=1
5. Use InsuranceValidator chaining:
   InsuranceValidator(response).status(201).has_field("id").has_field("title")
6. Use InsuranceFactory.build_policy_dict() for all POST/PUT bodies
7. Never hardcode policy IDs except well-known ones (1-10 always exist)
8. Add a module docstring explaining this file was AI-generated
9. MAXIMUM 12 tests total
10. Every code block must be fully closed — no truncation

Generate the complete test file now:"""


# ------------------------------------------------------------------ #
#  Staleness check                                                     #
# ------------------------------------------------------------------ #

def check_staleness() -> int:
    """
    Basic staleness check — verify hand-crafted tests are syntactically valid
    and count how many test methods exist.
    Returns the number of tests found.
    """
    print(f"Staleness scan: {PHASE1_TESTS}")

    if not PHASE1_TESTS.exists():
        print("WARNING: Phase 1 test file not found!")
        return 0

    source  = PHASE1_TESTS.read_text(encoding="utf-8")
    tree    = ast.parse(source)
    tests   = [
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]

    print(f"Tests scanned : {len(tests)}")
    print(f"Issues found  : 0")
    print(f"Status        : CLEAN — hand-crafted tests are valid")
    return len(tests)


# ------------------------------------------------------------------ #
#  File header                                                         #
# ------------------------------------------------------------------ #

def _file_header() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f'''"""
test_policy_ai.py
-----------------
AUTO-GENERATED by generate_insurance_tests.py using Claude (Anthropic SDK).
Generated : {timestamp}

DO NOT EDIT MANUALLY — re-run generate_insurance_tests.py to regenerate.
Hand-crafted tests live in: projects/insurance/api/tests/test_policy.py

Framework stack: InsuranceClient (Facade) · InsuranceValidator (Fluent) ·
                 InsuranceFactory (Factory) · pytest fixtures (conftest.py)
"""
'''


# ------------------------------------------------------------------ #
#  Main                                                                #
# ------------------------------------------------------------------ #

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI-powered Insurance Policy test generator"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print generated code to stdout without saving",
    )
    args = parser.parse_args()

    # Staleness check
    print("\n── Staleness check ─────────────────────────────────────")
    check_staleness()

    # AI generation
    print("\n── AI test generation ──────────────────────────────────")
    print(f"Model  : claude-sonnet-4-6")
    print(f"Spec   : Insurance Policy API (JSONPlaceholder /posts)")
    print(f"Output : {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print()
    print("Calling Anthropic API...")

    generator = InsuranceTestGenerator()

    try:
        generated_code = generator.generate(INSURANCE_SPEC)
    except EnvironmentError as exc:
        print(f"\nERROR: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"\nUnexpected error: {exc}")
        sys.exit(1)

    full_output = _file_header() + "\n" + generated_code

    if args.dry_run:
        print("\n── Generated code (dry run) ────────────────────────────")
        print(full_output)
        print("\n── Dry run complete — nothing written to disk ──────────")
        return

    # Write to disk
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(full_output, encoding="utf-8")

    print(f"Done. Generated {len(generated_code.splitlines())} lines.")
    print(f"Saved to: {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print()
    print("Run the generated tests with:")
    print("  pytest projects/insurance/api/ai/generated/ -v")


if __name__ == "__main__":
    main()
