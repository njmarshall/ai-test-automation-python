import httpx
import allure
from shared.config.env_config import EnvConfig

_MISSING = object()


class ResponseValidator:
    """
    Fluent chainable assertions — replaces ResponseValidator.java.
    Usage: ResponseValidator.from_response(r).status_code(200).within_sla().has_field("id")

    Every check fails with an AssertionError and a readable message, never
    with an AttributeError or KeyError from deep inside the validator.
    """

    def __init__(self, response: httpx.Response):
        self._response = response

    @staticmethod
    def from_response(response: httpx.Response) -> "ResponseValidator":
        return ResponseValidator(response)

    def _json_object(self) -> dict:
        """Parse the body and require a JSON object, so field checks mean what they say."""
        try:
            body = self._response.json()
        except ValueError:
            raise AssertionError(
                f"Response body is not valid JSON: {self._response.text[:200]!r}"
            ) from None
        assert isinstance(body, dict), (
            f"Expected a JSON object, got {type(body).__name__}: {str(body)[:200]}"
        )
        return body

    def status_code(self, expected: int) -> "ResponseValidator":
        with allure.step(f"Assert status code == {expected}"):
            actual = self._response.status_code
            assert actual == expected, (
                f"Expected status {expected}, got {actual}\nBody: {self._response.text}"
            )
        return self

    def within_sla(self) -> "ResponseValidator":
        sla = EnvConfig.RESPONSE_TIME_SLA_MS
        with allure.step(f"Assert response time < {sla}ms"):
            elapsed = getattr(self._response, "elapsed_ms", None)
            assert elapsed is not None, (
                "Response has no elapsed_ms. Send the request through ApiClient, "
                "which records the timing."
            )
            assert elapsed < sla, (
                f"Response took {elapsed:.0f}ms — exceeded SLA of {sla}ms"
            )
        return self

    def has_field(self, field: str) -> "ResponseValidator":
        with allure.step(f"Assert response body has field '{field}'"):
            body = self._json_object()
            assert field in body, (
                f"Field '{field}' not found in response: {body}"
            )
        return self

    def field_equals(self, field: str, expected) -> "ResponseValidator":
        with allure.step(f"Assert {field} == {expected}"):
            body = self._json_object()
            actual = body.get(field, _MISSING)
            # A missing field must never pass as "equals None".
            assert actual is not _MISSING, (
                f"Expected {field}={expected!r}, but field '{field}' is missing: {body}"
            )
            assert actual == expected, (
                f"Expected {field}={expected!r}, got {actual!r}"
            )
        return self
