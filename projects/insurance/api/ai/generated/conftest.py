"""
conftest.py
-----------
Pytest fixtures for the Insurance API test suite.
"""

from __future__ import annotations

import pytest

from projects.insurance.api.client.insurance_client import InsuranceClient
from projects.insurance.api.data.insurance_factory import InsuranceFactory


@pytest.fixture(scope="session")
def insurance_client() -> InsuranceClient:           # type: ignore
    """Session-scoped InsuranceClient — one httpx session per run."""
    client = InsuranceClient()
    yield client
    client.close()


@pytest.fixture(scope="function")
def created_policy_id(insurance_client: InsuranceClient) -> int:  # type: ignore
    """
    Create a Policy before the test, yield its id, clean up after.

    Note: JSONPlaceholder simulates POST/DELETE but doesn't persist data.
    The returned id is the simulated server-assigned id.
    """
    payload  = InsuranceFactory.build_policy_dict()
    response = insurance_client.create_policy(payload)
    assert response.status_code == 201, (
        f"Fixture setup failed: {response.status_code}"
    )
    policy_id = response.json()["id"]
    yield policy_id
    # JSONPlaceholder simulates delete — no real cleanup needed
    insurance_client.delete_policy(policy_id)
