"""
fhir_client.py
--------------
Facade over httpx that exposes clean, FHIR-aware HTTP operations.

Pattern : Facade
SOLID   : DIP — test code depends on FhirClient (abstraction), not httpx
          OCP  — Phase 3 adds Encounter + Observation methods without
                 touching Patient methods (Phase 1 unchanged)

Phase history
-------------
  Phase 1 : create/read/delete_patient()
  Phase 3 : create/read/delete_encounter()
             create/read_observation()
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

    Tests call high-level methods like create_patient() and read_encounter();
    they never construct URLs, set headers, or handle timeouts directly.
    """

    def __init__(self) -> None:
        cfg = FhirConfig()
        self._cfg      = cfg
        self._base_url = cfg.base_url
        self._session  = httpx.Client(
            headers=_build_headers(cfg),
            timeout=cfg.timeout_sec,
            follow_redirects=True,
        )

    # ------------------------------------------------------------------ #
    #  Patient operations (Phase 1 — unchanged)                           #
    # ------------------------------------------------------------------ #

    def create_patient(self, payload: dict) -> httpx.Response:
        """POST /Patient — create a new Patient resource."""
        return self._session.post(f"{self._base_url}/Patient", json=payload)

    def read_patient(self, patient_id: str) -> httpx.Response:
        """GET /Patient/{id} — retrieve an existing Patient resource."""
        return self._session.get(f"{self._base_url}/Patient/{patient_id}")

    def delete_patient(self, patient_id: str) -> httpx.Response:
        """DELETE /Patient/{id} — remove a Patient resource."""
        return self._session.delete(f"{self._base_url}/Patient/{patient_id}")

    # ------------------------------------------------------------------ #
    #  Encounter operations (Phase 3 — new)                               #
    # ------------------------------------------------------------------ #

    def create_encounter(self, payload: dict) -> httpx.Response:
        """POST /Encounter — create a new Encounter resource."""
        return self._session.post(f"{self._base_url}/Encounter", json=payload)

    def read_encounter(self, encounter_id: str) -> httpx.Response:
        """GET /Encounter/{id} — retrieve an existing Encounter resource."""
        return self._session.get(f"{self._base_url}/Encounter/{encounter_id}")

    def delete_encounter(self, encounter_id: str) -> httpx.Response:
        """DELETE /Encounter/{id} — remove an Encounter resource."""
        return self._session.delete(f"{self._base_url}/Encounter/{encounter_id}")

    def search_encounters_by_patient(self, patient_id: str) -> httpx.Response:
        """GET /Encounter?subject=Patient/{id} — find all Encounters for a Patient."""
        return self._session.get(
            f"{self._base_url}/Encounter",
            params={"subject": f"Patient/{patient_id}"},
        )

    # ------------------------------------------------------------------ #
    #  Observation operations (Phase 3 — new)                             #
    # ------------------------------------------------------------------ #

    def create_observation(self, payload: dict) -> httpx.Response:
        """POST /Observation — create a new Observation resource."""
        return self._session.post(f"{self._base_url}/Observation", json=payload)

    def read_observation(self, observation_id: str) -> httpx.Response:
        """GET /Observation/{id} — retrieve an existing Observation resource."""
        return self._session.get(f"{self._base_url}/Observation/{observation_id}")

    def delete_observation(self, observation_id: str) -> httpx.Response:
        """DELETE /Observation/{id} — remove an Observation resource."""
        return self._session.delete(f"{self._base_url}/Observation/{observation_id}")

    def search_observations_by_patient(self, patient_id: str) -> httpx.Response:
        """GET /Observation?subject=Patient/{id} — find all Observations for a Patient."""
        return self._session.get(
            f"{self._base_url}/Observation",
            params={"subject": f"Patient/{patient_id}"},
        )

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    def close(self) -> None:
        """Close the underlying httpx session."""
        self._session.close()

    def __enter__(self) -> "FhirClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()
