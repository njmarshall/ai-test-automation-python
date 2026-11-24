"""
test_response_validator.py
--------------------------
Unit tests for shared.assertions.ResponseValidator, built on in-memory
httpx.Response objects. No network.

Two defects these tests pinned down and the validator now fixes:
  1. field_equals("x", None) passed when "x" was missing, because
     body.get() returns None for a missing key.
  2. A JSON array body made has_field() test list membership and
     made field_equals() crash with AttributeError instead of failing.
"""

from __future__ import annotations

import httpx
import pytest

from shared.assertions.response_validator import ResponseValidator
from shared.config.env_config import EnvConfig

pytestmark = pytest.mark.unit

_REQ = httpx.Request("GET", "https://example.test/resource")


def _resp(status: int = 200, *, json=None, text: str | None = None, elapsed_ms: float | None = 50.0):
    if text is not None:
        r = httpx.Response(status, text=text, request=_REQ)
    else:
        r = httpx.Response(status, json=json if json is not None else {}, request=_REQ)
    if elapsed_ms is not None:
        r.elapsed_ms = elapsed_ms  # set by ApiClient in real runs
    return r


class TestFluentChain:
    def test_from_response_returns_validator(self):
        assert isinstance(ResponseValidator.from_response(_resp()), ResponseValidator)

    def test_full_chain_passes_and_returns_self(self):
        v = ResponseValidator.from_response(_resp(json={"id": 7, "status": "available"}))
        out = v.status_code(200).within_sla().has_field("id").field_equals("status", "available")
        assert out is v


class TestStatusCode:
    def test_matching_status_passes(self):
        ResponseValidator(_resp(201)).status_code(201)

    def test_wrong_status_fails_and_shows_body(self):
        with pytest.raises(AssertionError, match=r"Expected status 200, got 404[\s\S]*not found"):
            ResponseValidator(_resp(404, json={"error": "not found"})).status_code(200)


class TestWithinSla:
    def test_fast_response_passes(self):
        ResponseValidator(_resp(elapsed_ms=EnvConfig.RESPONSE_TIME_SLA_MS - 1)).within_sla()

    def test_response_at_sla_fails(self):
        with pytest.raises(AssertionError, match="exceeded SLA"):
            ResponseValidator(_resp(elapsed_ms=EnvConfig.RESPONSE_TIME_SLA_MS)).within_sla()

    def test_missing_timing_fails_with_clear_message(self):
        with pytest.raises(AssertionError, match="no elapsed_ms"):
            ResponseValidator(_resp(elapsed_ms=None)).within_sla()


class TestHasField:
    def test_present_field_passes(self):
        ResponseValidator(_resp(json={"id": 1})).has_field("id")

    def test_present_field_with_null_value_passes(self):
        ResponseValidator(_resp(json={"deletedAt": None})).has_field("deletedAt")

    def test_missing_field_fails(self):
        with pytest.raises(AssertionError, match="Field 'id' not found"):
            ResponseValidator(_resp(json={"name": "x"})).has_field("id")

    def test_json_array_body_fails_instead_of_testing_membership(self):
        # Before the fix, ["id"] passed has_field("id") by list membership.
        with pytest.raises(AssertionError, match="Expected a JSON object, got list"):
            ResponseValidator(_resp(json=["id"])).has_field("id")

    def test_non_json_body_fails_clearly(self):
        with pytest.raises(AssertionError, match="not valid JSON"):
            ResponseValidator(_resp(text="<html>Bad Gateway</html>")).has_field("id")


class TestFieldEquals:
    def test_equal_value_passes(self):
        ResponseValidator(_resp(json={"status": "sold"})).field_equals("status", "sold")

    def test_different_value_fails(self):
        with pytest.raises(AssertionError, match="Expected status='sold', got 'available'"):
            ResponseValidator(_resp(json={"status": "available"})).field_equals("status", "sold")

    def test_explicit_null_equals_none_passes(self):
        ResponseValidator(_resp(json={"deletedAt": None})).field_equals("deletedAt", None)

    def test_missing_field_never_passes_as_none(self):
        # The defect: body.get() made a missing field look like a null one.
        with pytest.raises(AssertionError, match="field 'deletedAt' is missing"):
            ResponseValidator(_resp(json={"id": 1})).field_equals("deletedAt", None)

    def test_json_array_body_fails_instead_of_crashing(self):
        # Before the fix this raised AttributeError: 'list' has no attribute 'get'.
        with pytest.raises(AssertionError, match="Expected a JSON object"):
            ResponseValidator(_resp(json=[{"status": "sold"}])).field_equals("status", "sold")

    @pytest.mark.parametrize("actual, expected", [(1, 1.0), (0, False)])
    def test_uses_python_equality(self, actual, expected):
        # Documented behaviour: == semantics, so 1 == 1.0 and 0 == False.
        ResponseValidator(_resp(json={"v": actual})).field_equals("v", expected)
