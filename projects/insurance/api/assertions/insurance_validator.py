"""
insurance_validator.py
----------------------
Fluent, chainable assertions for Insurance API responses.

Pattern : Fluent Interface (method chaining)
SOLID   : SRP — one class, one job: validate httpx responses
"""

from __future__ import annotations

from typing import Any

import httpx


class InsuranceValidator:
    """
    Fluent assertion wrapper around an httpx.Response.

    Example
    -------
        InsuranceValidator(response) \\
            .status(201) \\
            .has_field("id") \\
            .has_field("title") \\
            .within_sla(sla_ms=3000)
    """

    def __init__(self, response: httpx.Response) -> None:
        self._response   = response
        self._body: dict = {}
        self._parsed     = False

    def _parse(self) -> dict:
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

    def status(self, expected: int) -> "InsuranceValidator":
        actual = self._response.status_code
        assert actual == expected, (
            f"Expected status {expected}, got {actual}.\n"
            f"Body: {self._response.text[:400]}"
        )
        return self

    def status_in(self, *expected: int) -> "InsuranceValidator":
        actual = self._response.status_code
        assert actual in expected, (
            f"Expected status in {expected}, got {actual}."
        )
        return self

    def within_sla(self, sla_ms: float = 3000.0) -> "InsuranceValidator":
        elapsed_ms = self._response.elapsed.total_seconds() * 1000
        assert elapsed_ms <= sla_ms, (
            f"Response time {elapsed_ms:.0f}ms exceeded SLA of {sla_ms:.0f}ms."
        )
        return self

    # ------------------------------------------------------------------ #
    #  Body assertions                                                     #
    # ------------------------------------------------------------------ #

    def has_field(self, field: str) -> "InsuranceValidator":
        body  = self._parse()
        value = body.get(field)
        assert value is not None, (
            f"Expected field '{field}' in response body.\n"
            f"Available keys: {list(body.keys())}"
        )
        return self

    def field_equals(self, field: str, expected: Any) -> "InsuranceValidator":
        body   = self._parse()
        actual = body.get(field)
        assert actual == expected, (
            f"Field '{field}': expected {expected!r}, got {actual!r}."
        )
        return self

    def extract_id(self) -> int:
        """Return the resource id from the response body."""
        body = self._parse()
        rid  = body.get("id")
        assert rid is not None, "Response body did not contain an 'id'."
        return int(rid)
