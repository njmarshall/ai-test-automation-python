import httpx
import allure
from shared.config.env_config import EnvConfig


class ResponseValidator:
    """
    Fluent chainable assertions — replaces ResponseValidator.java.
    Usage: ResponseValidator.from_response(r).status_code(200).within_sla().has_field("id")
    """

    def __init__(self, response: httpx.Response):
        self._response = response

    @staticmethod
    def from_response(response: httpx.Response) -> "ResponseValidator":
        return ResponseValidator(response)

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
            elapsed = self._response.elapsed_ms  # type: ignore[attr-defined]
            assert elapsed < sla, (
                f"Response took {elapsed:.0f}ms — exceeded SLA of {sla}ms"
            )
        return self

    def has_field(self, field: str) -> "ResponseValidator":
        with allure.step(f"Assert response body has field '{field}'"):
            body = self._response.json()
            assert field in body, (
                f"Field '{field}' not found in response: {body}"
            )
        return self

    def field_equals(self, field: str, expected) -> "ResponseValidator":
        with allure.step(f"Assert {field} == {expected}"):
            body = self._response.json()
            actual = body.get(field)
            assert actual == expected, (
                f"Expected {field}={expected}, got {actual}"
            )
        return self