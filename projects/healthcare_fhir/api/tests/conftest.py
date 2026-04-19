"""
conftest.py
-----------
Pytest fixtures for the Healthcare FHIR test suite.

Scope design
------------
  fhir_client  : session-scoped — one httpx session for the entire run
  created_patient_id : function-scoped — fresh Patient per test that needs one

SOLID / Pattern notes
---------------------
  DIP  : tests receive FhirClient via fixture injection, never instantiate it
  Facade: fixtures are the only place FhirClient is constructed
"""

from __future__ import annotations

import pytest

from projects.healthcare_fhir.api.client.fhir_client import FhirClient
from projects.healthcare_fhir.api.data.fhir_factory import FhirFactory


# ------------------------------------------------------------------ #
#  Session-scoped client (one connection pool for the whole run)      #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="session")
def fhir_client() -> FhirClient:            # type: ignore[return]
    """
    Provide a single FhirClient instance shared across all tests.
    Closed automatically after the session ends.
    """
    client = FhirClient()
    yield client
    client.close()


# ------------------------------------------------------------------ #
#  Function-scoped Patient lifecycle fixture                          #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="function")
def created_patient_id(fhir_client: FhirClient) -> str:     # type: ignore[return]
    """
    Create a Patient before the test; delete it after (teardown).

    Yields the FHIR resource id so tests can read/assert against it.
    Cleanup runs even if the test fails — no orphan resources left on
    the sandbox server.
    """
    payload  = FhirFactory.build_patient_dict()
    response = fhir_client.create_patient(payload)

    assert response.status_code == 201, (
        f"Fixture setup failed: POST /Patient returned {response.status_code}.\n"
        f"{response.text[:400]}"
    )

    patient_id: str = response.json()["id"]
    yield patient_id

    # Teardown — best-effort delete
    fhir_client.delete_patient(patient_id)
