"""
conftest.py
-----------
Pytest fixtures for the Fintech API test suite.
"""

from __future__ import annotations

import pytest

from projects.fintech.api.client.fintech_client import FintechClient


@pytest.fixture(scope="session")
def fintech_client() -> FintechClient:           # type: ignore
    """Session-scoped FintechClient — one httpx session per run."""
    client = FintechClient()
    yield client
    client.close()
