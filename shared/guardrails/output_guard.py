"""
output_guard.py
---------------
Output guardrail — validates AI output before it reaches the codebase.

Real-world context
------------------
When Claude generates test code, the output must be validated before
it gets written to disk or merged into the codebase. Bad AI output
can include:

  - Hallucinated method names that don't exist in the framework
  - Wrong import paths
  - Hardcoded credentials or test data
  - Incomplete code blocks (truncated output)
  - Non-Python content mixed with code

This guardrail sits AFTER the AI call:
  Claude API → OutputGuard → Validated code → Written to disk

Pattern : Chain of Responsibility — each validator checks one rule
SOLID   : SRP — one validator, one rule
          OCP — add new validators without modifying existing ones

Usage
-----
    guard = OutputGuard()
    result = guard.validate(generated_code)

    if result.passed:
        write_to_disk(result.content)
    else:
        print(result.failures)
        # Re-generate or reject
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import List, Optional


# ------------------------------------------------------------------ #
#  Validation result                                                   #
# ------------------------------------------------------------------ #

@dataclass
class ValidationResult:
    """Result of output validation."""
    content:   str
    passed:    bool
    failures:  List[str] = field(default_factory=list)
    warnings:  List[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.passed:
            return f"Output passed all checks. Warnings: {len(self.warnings)}"
        return (
            f"Output FAILED validation.\n"
            f"Failures: {self.failures}\n"
            f"Warnings: {self.warnings}"
        )


# ------------------------------------------------------------------ #
#  Output Guard                                                        #
# ------------------------------------------------------------------ #

class OutputGuard:
    """
    Validates AI-generated test code before it reaches the codebase.

    Runs multiple checks on generated pytest code:
      1. Syntax check   — is it valid Python?
      2. Import check   — does it use correct framework imports?
      3. Complete check — is the code complete (not truncated)?
      4. Safety check   — no hardcoded credentials or PHI?
      5. Structure check — does it have at least one test method?

    Example
    -------
        guard = OutputGuard()
        result = guard.validate(generated_code)

        if not result.passed:
            print(result.summary())
            # Re-generate or flag for review
    """

    # Required imports for the FHIR framework
    VALID_IMPORTS = [
        "projects.healthcare_fhir",
        "projects.insurance",
        "projects.fintech",
        "projects.petstore",
        "shared.",
        "pytest",
        "typing",
        "datetime",
    ]

    # Patterns that should never appear in generated code
    UNSAFE_PATTERNS = [
        (r"password\s*=\s*['\"][^'\"]+['\"]", "hardcoded password"),
        (r"api_key\s*=\s*['\"][^'\"]+['\"]", "hardcoded API key"),
        (r"secret\s*=\s*['\"][^'\"]+['\"]", "hardcoded secret"),
        (r"\b\d{3}-\d{2}-\d{4}\b", "SSN pattern"),
        (r"sk-ant-api", "exposed Anthropic API key"),
    ]

    def validate(self, code: str) -> ValidationResult:
        """
        Run all validation checks on generated code.

        Parameters
        ----------
        code : the AI-generated Python code to validate

        Returns
        -------
        ValidationResult with pass/fail status and details
        """
        failures: List[str] = []
        warnings: List[str] = []

        # Check 1 — Syntax
        syntax_error = self._check_syntax(code)
        if syntax_error:
            failures.append(f"Syntax error: {syntax_error}")

        # Check 2 — Completeness
        if not self._check_complete(code):
            failures.append(
                "Code appears truncated — no closing class or function found."
            )

        # Check 3 — Has test methods
        if not self._check_has_tests(code):
            failures.append(
                "No test methods found — generated code must contain "
                "at least one function starting with test_"
            )

        # Check 4 — Safety
        safety_issues = self._check_safety(code)
        failures.extend(safety_issues)

        # Check 5 — Imports (warnings only)
        import_warnings = self._check_imports(code)
        warnings.extend(import_warnings)

        return ValidationResult(
            content=code,
            passed=len(failures) == 0,
            failures=failures,
            warnings=warnings,
        )

    # ------------------------------------------------------------------ #
    #  Individual checks                                                   #
    # ------------------------------------------------------------------ #

    def _check_syntax(self, code: str) -> Optional[str]:
        """Return error message if code has syntax errors, None if clean."""
        try:
            ast.parse(code)
            return None
        except SyntaxError as e:
            return f"Line {e.lineno}: {e.msg}"

    def _check_complete(self, code: str) -> bool:
        """Return True if code appears complete (not truncated)."""
        stripped = code.strip()
        if not stripped:
            return False
        # Code should end with a complete statement
        # Truncated code often ends mid-line without proper closure
        last_line = stripped.split("\n")[-1]
        incomplete_endings = ["...", "# TODO", "pass #"]
        return not any(last_line.strip().endswith(e) for e in incomplete_endings)

    def _check_has_tests(self, code: str) -> bool:
        """Return True if code contains at least one test method."""
        return bool(re.search(r"def test_\w+", code))

    def _check_safety(self, code: str) -> List[str]:
        """Return list of safety issues found in code."""
        issues = []
        for pattern, label in self.UNSAFE_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                issues.append(f"Unsafe content detected: {label}")
        return issues

    def _check_imports(self, code: str) -> List[str]:
        """Return warnings for suspicious import patterns."""
        warnings = []
        import_lines = [
            line.strip() for line in code.split("\n")
            if line.strip().startswith("import ") or
               line.strip().startswith("from ")
        ]
        for line in import_lines:
            if not any(valid in line for valid in self.VALID_IMPORTS):
                warnings.append(f"Unexpected import: {line}")
        return warnings
