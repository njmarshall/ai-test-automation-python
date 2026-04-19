"""
fhir_validator.py
-----------------
Fluent, chainable assertions for FHIR API responses.

Pattern : Fluent Interface (method chaining)
SOLID   : SRP — one class, one job: validate httpx responses
Design  : mirrors RestAssured's ResponseValidator from the Java framework
          but uses Python idioms (snake_case, raises AssertionError natively)

Example
-------
    FhirValidator(response) \\
        .status(201) \\
        .resource_type("Patient") \\
        .has_field("id") \\
        .within_sla(sla_ms=3000)
"""

from __future__ import annotations

import time
from typing import Any

import httpx


class FhirValidator:
    """
    Fluent assertion wrapper around an httpx.Response.

    Every method returns `self` to enable chaining.
    Any failure raises AssertionError with a clear message.
    """

    def __init__(self, response: httpx.Response) -> None:
        self._response    = response
        self._body: dict  = {}
        self._parsed      = False

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _parse(self) -> dict:
        """Lazy-parse the JSON body once and cache it."""
        if not self._parsed:
            try:
                self._body = self._response.json()
            except Exception:
                self._body = {}
            self._parsed = True
        return self._body

    # ------------------------------------------------------------------ #
    #  HTTP-level assertions                                               #
    # ------------------------------------------------------------------ #

    def status(self, expected: int) -> "FhirValidator":
        """Assert the HTTP status code matches expected."""
        actual = self._response.status_code
        assert actual == expected, (
            f"Expected status {expected}, got {actual}.\n"
            f"Body: {self._response.text[:400]}"
        )
        return self

    def status_in(self, *expected: int) -> "FhirValidator":
        """Assert the HTTP status code is one of the provided values."""
        actual = self._response.status_code
        assert actual in expected, (
            f"Expected status in {expected}, got {actual}.\n"
            f"Body: {self._response.text[:400]}"
        )
        return self

    def within_sla(self, sla_ms: float = 3000.0) -> "FhirValidator":
        """Assert the response arrived within the given SLA in milliseconds."""
        elapsed_ms = self._response.elapsed.total_seconds() * 1000
        assert elapsed_ms <= sla_ms, (
            f"Response time {elapsed_ms:.0f}ms exceeded SLA of {sla_ms:.0f}ms."
        )
        return self

    # ------------------------------------------------------------------ #
    #  FHIR body assertions                                                #
    # ------------------------------------------------------------------ #

    def resource_type(self, expected: str) -> "FhirValidator":
        """Assert the FHIR resourceType field matches expected."""
        body   = self._parse()
        actual = body.get("resourceType")
        assert actual == expected, (
            f"Expected resourceType '{expected}', got '{actual}'."
        )
        return self

    def has_field(self, field: str) -> "FhirValidator":
        """Assert the response body contains a non-None value at `field`."""
        body  = self._parse()
        value = body.get(field)
        assert value is not None, (
            f"Expected field '{field}' in response body, but it was absent or null.\n"
            f"Available keys: {list(body.keys())}"
        )
        return self

    def field_equals(self, field: str, expected: Any) -> "FhirValidator":
        """Assert a top-level field equals an expected value."""
        body   = self._parse()
        actual = body.get(field)
        assert actual == expected, (
            f"Field '{field}': expected {expected!r}, got {actual!r}."
        )
        return self

    def no_operation_outcome_error(self) -> "FhirValidator":
        """
        Assert the response is not a FHIR OperationOutcome with severity 'error'
        or 'fatal'. Useful for 200-range responses that may silently carry errors.
        """
        body = self._parse()
        if body.get("resourceType") == "OperationOutcome":
            issues = body.get("issue", [])
            errors = [
                i for i in issues
                if i.get("severity") in ("error", "fatal")
            ]
            assert not errors, (
                f"OperationOutcome contained error-level issues: {errors}"
            )
        return self

    # ------------------------------------------------------------------ #
    #  Convenience extractor                                               #
    # ------------------------------------------------------------------ #

    def extract_id(self) -> str:
        """Return the FHIR resource id from the response body."""
        body = self._parse()
        fhir_id = body.get("id")
        assert fhir_id, "Response body did not contain a FHIR resource 'id'."
        return str(fhir_id)
