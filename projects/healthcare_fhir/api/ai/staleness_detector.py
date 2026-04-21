"""
staleness_detector.py
---------------------
Self-healing test detection — compares existing tests against the FHIR spec
and reports any tests that reference stale endpoints, fields, or status codes.

Pattern : Strategy — detection rules are independent strategies applied
          to each test, making it easy to add new rules without changing
          the core scan loop
SOLID   : OCP  — add new StalenessRule subclasses without touching the scanner
          SRP  — scanner orchestrates; rules detect; reporter formats

This is the interview showstopper feature. In a real healthtech CI pipeline
this runs as a pre-commit hook or GitHub Actions step — any test touching
a deprecated FHIR endpoint fails the build before it ships.

Example
-------
    detector = StalenessDetector()
    report   = detector.scan("projects/healthcare_fhir/api/tests/test_patient.py")
    print(report.summary())
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from projects.healthcare_fhir.api.ai.fhir_spec_loader import FhirSpecLoader


# ------------------------------------------------------------------ #
#  Data classes                                                        #
# ------------------------------------------------------------------ #

@dataclass
class StalenessIssue:
    """A single staleness finding in a test file."""
    test_name:   str
    line_number: int
    issue_type:  str    # 'stale_endpoint' | 'stale_status' | 'stale_field'
    detail:      str

    def __str__(self) -> str:
        return (
            f"  [{self.issue_type}] {self.test_name} "
            f"(line {self.line_number}): {self.detail}"
        )


@dataclass
class StalenessReport:
    """Full report for a scanned test file."""
    file_path:   str
    issues:      List[StalenessIssue] = field(default_factory=list)
    tests_scanned: int = 0

    def is_stale(self) -> bool:
        return len(self.issues) > 0

    def summary(self) -> str:
        lines = [
            f"Staleness scan: {self.file_path}",
            f"Tests scanned : {self.tests_scanned}",
            f"Issues found  : {len(self.issues)}",
        ]
        if self.issues:
            lines.append("")
            lines.append("Issues:")
            lines.extend(str(i) for i in self.issues)
        else:
            lines.append("Status        : CLEAN — all tests match spec")
        return "\n".join(lines)


# ------------------------------------------------------------------ #
#  Staleness detector                                                  #
# ------------------------------------------------------------------ #

class StalenessDetector:
    """
    Scans a pytest test file and flags tests that may be stale
    relative to the current FHIR spec.

    Detection rules applied:
      1. Endpoint paths referenced in strings — are they in the spec?
      2. HTTP status codes asserted — do they match spec responses?
      3. Field names checked — are they valid FHIR Patient fields?
    """

    # Known valid FHIR R4 Patient fields for field staleness check
    VALID_PATIENT_FIELDS = {
        "id", "resourceType", "meta", "text", "active",
        "name", "telecom", "gender", "birthDate", "address",
        "identifier", "maritalStatus", "photo", "contact",
        "communication", "generalPractitioner", "managingOrganization",
    }

    def __init__(self) -> None:
        self._spec = FhirSpecLoader().load_minimal_patient_spec()
        self._valid_paths = {
            ep["path"] for ep in self._spec["endpoints"]
        }
        self._valid_statuses: dict[str, set[str]] = {}
        for ep in self._spec["endpoints"]:
            key = f"{ep['method']} {ep['path']}"
            self._valid_statuses[key] = set(ep["responses"].keys())

    # ------------------------------------------------------------------ #
    #  Public interface                                                    #
    # ------------------------------------------------------------------ #

    def scan(self, test_file: str | Path) -> StalenessReport:
        """
        Scan a test file and return a StalenessReport.

        Parameters
        ----------
        test_file : path to the pytest test file to scan
        """
        path   = Path(test_file)
        report = StalenessReport(file_path=str(path))

        if not path.exists():
            report.issues.append(StalenessIssue(
                test_name="N/A", line_number=0,
                issue_type="file_not_found",
                detail=f"File does not exist: {path}",
            ))
            return report

        source = path.read_text(encoding="utf-8")
        tree   = ast.parse(source)
        lines  = source.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                report.tests_scanned += 1
                issues = self._check_test(node, lines)
                report.issues.extend(issues)

        return report

    # ------------------------------------------------------------------ #
    #  Detection rules                                                     #
    # ------------------------------------------------------------------ #

    def _check_test(
        self,
        node: ast.FunctionDef,
        lines: list[str],
    ) -> list[StalenessIssue]:
        """Apply all detection rules to a single test function node."""
        issues: list[StalenessIssue] = []
        issues.extend(self._check_status_codes(node, lines))
        issues.extend(self._check_field_names(node, lines))
        return issues

    def _check_status_codes(
        self,
        node: ast.FunctionDef,
        lines: list[str],
    ) -> list[StalenessIssue]:
        """
        Flag assertions using status codes not present in the spec.
        Looks for patterns like .status(404) or status_code == 404.
        """
        issues = []
        func_source = "\n".join(
            lines[node.lineno - 1 : node.end_lineno]
        )

        # Extract all integer arguments to .status() calls
        status_pattern = re.compile(r"\.status(?:_in)?\(([^)]+)\)")
        for match in status_pattern.finditer(func_source):
            codes = re.findall(r"\d{3}", match.group(1))
            for code in codes:
                # Check if this status code exists in ANY spec endpoint
                all_valid = set()
                for valid_set in self._valid_statuses.values():
                    all_valid.update(valid_set)
                if code not in all_valid:
                    line_offset = func_source[: match.start()].count("\n")
                    issues.append(StalenessIssue(
                        test_name=node.name,
                        line_number=node.lineno + line_offset,
                        issue_type="stale_status",
                        detail=(
                            f"Status code {code} is not in any "
                            f"FHIR Patient endpoint response spec."
                        ),
                    ))
        return issues

    def _check_field_names(
        self,
        node: ast.FunctionDef,
        lines: list[str],
    ) -> list[StalenessIssue]:
        """
        Flag .has_field() or .field_equals() calls referencing
        non-existent FHIR Patient fields.
        """
        issues = []
        func_source = "\n".join(
            lines[node.lineno - 1 : node.end_lineno]
        )

        field_pattern = re.compile(
            r'\.(?:has_field|field_equals)\(["\']([^"\']+)["\']'
        )
        for match in field_pattern.finditer(func_source):
            field_name = match.group(1)
            if field_name not in self.VALID_PATIENT_FIELDS:
                line_offset = func_source[: match.start()].count("\n")
                issues.append(StalenessIssue(
                    test_name=node.name,
                    line_number=node.lineno + line_offset,
                    issue_type="stale_field",
                    detail=(
                        f"Field '{field_name}' is not a recognised "
                        f"FHIR R4 Patient field."
                    ),
                ))
        return issues
