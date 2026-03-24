import time
import httpx
import allure
from shared.config.env_config import EnvConfig
from shared.http.auth_helper import AuthHelper


class ApiClient:
    """
    Central HTTP client — replaces RestAssured ApiClient.java.
    Wraps httpx, handles retries, logging, and Allure attachments.
    """

    def __init__(self):
        timeout = EnvConfig.REQUEST_TIMEOUT_MS / 1000
        self._client = httpx.Client(
            base_url=EnvConfig.BASE_URL,
            timeout=timeout,
            headers=AuthHelper.build_headers(),
        )

    # ── Public CRUD methods ───────────────────────────────────────────────────

    def get(self, path: str, **kwargs) -> httpx.Response:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, json: dict = None, **kwargs) -> httpx.Response:
        return self._request("POST", path, json=json, **kwargs)

    def put(self, path: str, json: dict = None, **kwargs) -> httpx.Response:
        return self._request("PUT", path, json=json, **kwargs)

    def delete(self, path: str, **kwargs) -> httpx.Response:
        return self._request("DELETE", path, **kwargs)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        attempts = 0
        while attempts <= EnvConfig.MAX_RETRIES:
            try:
                start = time.monotonic()
                response = self._client.request(method, path, **kwargs)
                elapsed_ms = (time.monotonic() - start) * 1000

                # Retry on 5xx
                if response.status_code >= 500 and attempts < EnvConfig.MAX_RETRIES:
                    attempts += 1
                    continue

                self._log_and_attach(method, path, response, elapsed_ms)
                response.elapsed_ms = elapsed_ms  # type: ignore[attr-defined]
                return response

            except httpx.TimeoutException:
                attempts += 1
                if attempts > EnvConfig.MAX_RETRIES:
                    raise

    def _log_and_attach(
        self,
        method: str,
        path: str,
        response: httpx.Response,
        elapsed_ms: float,
    ):
        if EnvConfig.LOG_ALL_REQUESTS:
            print(f"\n{method} {path} → {response.status_code} ({elapsed_ms:.0f}ms)")

        allure.attach(
            body=response.text,
            name=f"{method} {path} → {response.status_code}",
            attachment_type=allure.attachment_type.JSON,
        )

    def close(self):
        self._client.close()