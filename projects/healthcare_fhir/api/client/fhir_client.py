"""
fhir_client.py
--------------
Facade over httpx that exposes clean, FHIR-aware HTTP operations.

Pattern : Facade
SOLID   : DIP — test code depends on FhirClient (abstraction), not httpx
          OCP  — add get_encounter(), post_claim() etc. without touching
                 Patient methods or any test file
Design  : synchronous httpx client; session reused across the test run
          via module-level instance (_client) initialised from FhirConfig
"""

from __future__ import annotations

import httpx

from projects.healthcare_fhir.api.config.fhir_config import FhirConfig


def _build_headers(cfg: FhirConfig) -> dict:
    """Assemble FHIR-required headers plus optional auth."""
    headers = {
        "Content-Type": "application/fhir+json",
        "Accept":        "application/fhir+json",
    }
    if cfg.bearer_token:
        headers["Authorization"] = f"Bearer {cfg.bearer_token}"
    elif cfg.api_key:
        headers["X-API-Key"] = cfg.api_key
    return headers


class FhirClient:
    """
    Facade that hides httpx complexity from test code.

    Tests call high-level methods like create_patient() and read_patient();
    they never construct URLs, set headers, or handle timeouts directly.

    The underlying httpx.Client is created once and reused, giving
    connection pooling for free across the test run.
    """

    def __init__(self) -> None:
        cfg = FhirConfig()
        self._cfg     = cfg
        self._base_url = cfg.base_url
        self._session  = httpx.Client(
            headers=_build_headers(cfg),
            timeout=cfg.timeout_sec,
            follow_redirects=True,
        )

    # ------------------------------------------------------------------ #
    #  Patient operations (Phase 1 MVP)                                   #
    # ------------------------------------------------------------------ #

    def create_patient(self, payload: dict) -> httpx.Response:
        """POST /Patient — create a new Patient resource."""
        return self._session.post(
            f"{self._base_url}/Patient",
            json=payload,
        )

    def read_patient(self, patient_id: str) -> httpx.Response:
        """GET /Patient/{id} — retrieve an existing Patient resource."""
        return self._session.get(
            f"{self._base_url}/Patient/{patient_id}",
        )

    def delete_patient(self, patient_id: str) -> httpx.Response:
        """DELETE /Patient/{id} — remove a Patient resource."""
        return self._session.delete(
            f"{self._base_url}/Patient/{patient_id}",
        )

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    def close(self) -> None:
        """Close the underlying httpx session. Called by pytest fixture teardown."""
        self._session.close()

    def __enter__(self) -> "FhirClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()
