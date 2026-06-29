"""
fintech_validator.py
--------------------
Fluent, chainable assertions for Fintech API responses.

Pattern : Fluent Interface (method chaining)
SOLID   : SRP — one class, one job: validate httpx responses
"""

from __future__ import annotations

from typing import Any

import httpx


class FintechValidator:
    """
    Fluent assertion wrapper for Coinbase API responses.

    Example
    -------
        FintechValidator(response) \\
            .status(200) \\
            .has_data_field("currency") \\
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

    def _data(self) -> dict:
        """Return the 'data' field from Coinbase response."""
        return self._parse().get("data", {})

    # ------------------------------------------------------------------ #
    #  HTTP-level assertions                                               #
    # ------------------------------------------------------------------ #

    def status(self, expected: int) -> "FintechValidator":
        actual = self._response.status_code
        assert actual == expected, (
            f"Expected status {expected}, got {actual}.\n"
            f"Body: {self._response.text[:400]}"
        )
        return self

    def within_sla(self, sla_ms: float = 3000.0) -> "FintechValidator":
        elapsed_ms = self._response.elapsed.total_seconds() * 1000
        assert elapsed_ms <= sla_ms, (
            f"Response time {elapsed_ms:.0f}ms exceeded SLA of {sla_ms:.0f}ms."
        )
        return self

    # ------------------------------------------------------------------ #
    #  Coinbase response structure assertions                              #
    # ------------------------------------------------------------------ #

    def has_data(self) -> "FintechValidator":
        """Assert the response body contains a 'data' field."""
        body = self._parse()
        assert "data" in body, (
            f"Expected 'data' field in response.\n"
            f"Available keys: {list(body.keys())}"
        )
        return self

    def has_data_field(self, field: str) -> "FintechValidator":
        """Assert the 'data' object contains a specific field."""
        data = self._data()
        assert field in data, (
            f"Expected field '{field}' in response data.\n"
            f"Available keys: {list(data.keys())}"
        )
        return self

    def data_field_equals(self, field: str, expected: Any) -> "FintechValidator":
        """Assert a field in 'data' equals expected value."""
        data   = self._data()
        actual = data.get(field)
        assert actual == expected, (
            f"Data field '{field}': expected {expected!r}, got {actual!r}."
        )
        return self

    def data_is_list(self) -> "FintechValidator":
        """Assert the 'data' field is a list."""
        data = self._data()
        assert isinstance(data, list), (
            f"Expected 'data' to be a list, got {type(data).__name__}."
        )
        return self

    def data_list_is_not_empty(self) -> "FintechValidator":
        """Assert the 'data' list is non-empty."""
        data = self._data()
        assert len(data) > 0, "Expected non-empty data list."
        return self

    def data_amount_is_positive(self) -> "FintechValidator":
        """Assert the 'amount' field in data is a positive number."""
        data   = self._data()
        amount = data.get("amount")
        assert amount is not None, "Expected 'amount' field in data."
        try:
            value = float(amount)
        except (ValueError, TypeError):
            raise AssertionError(f"Expected numeric amount, got {amount!r}.")
        assert value > 0, f"Expected positive amount, got {value}."
        return self
