"""
conftest.py : prior-auth domain shared fixtures
--------------------------------------------------
No real network port is used: the sandbox runs in-process via FastAPI's
TestClient, the same pattern used by the API-to-database integration test
in Article 14.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from projects.healthcare_fhir.api.prior_auth.client import PriorAuthClient
from projects.healthcare_fhir.api.prior_auth.sandbox import app


@pytest.fixture
def prior_auth_client() -> PriorAuthClient:
    """PriorAuthClient wired to a fresh, reset sandbox for each test."""
    with TestClient(app) as test_client:
        client = PriorAuthClient(test_client)
        client.reset_sandbox()
        yield client
