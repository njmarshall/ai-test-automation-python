"""
conftest.py — customer journey contract test fixtures

Provisions synthetic test personas and environment settings for
integration tests that exercise full customer journeys through
supported application surfaces.

These fixtures are stubs. Wire them to your staging environment
configuration before running against a real environment.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from playwright.sync_api import Page, sync_playwright


# ── data classes ──────────────────────────────────────────────────────────────

@dataclass
class SyntheticPatient:
    """A controlled test persona with no connection to real patient data."""
    id: str
    plan_id: str
    name: str


@dataclass
class EnvironmentSettings:
    """
    Base URLs for each application surface under test.
    Load from environment variables or a secrets manager in CI.
    """
    authorization_url: str
    portal_url: str
    scheduling_url: str


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def test_patient() -> SyntheticPatient:
    """
    Provision a synthetic patient persona for one test.

    In a real environment this fixture would call a test-data API
    to register the persona and register a finalizer that deletes it.
    The persona must have an eligible plan and no pre-existing
    authorization for the procedure under test.
    """
    patient_id = f"TEST-PAT-{uuid.uuid4().hex[:8].upper()}"
    patient = SyntheticPatient(
        id=patient_id,
        plan_id="PLAN-ELIGIBLE-001",
        name=f"Synthetic Patient {patient_id}",
    )
    yield patient
    # Teardown: remove synthetic records created during the test.
    # Implement cleanup call here before production use.


@pytest.fixture(scope="session")
def settings() -> EnvironmentSettings:
    """
    Return environment base URLs.

    Override with real staging URLs via environment variables:
        AUTHORIZATION_URL, PORTAL_URL, SCHEDULING_URL
    """
    import os
    return EnvironmentSettings(
        authorization_url=os.getenv("AUTHORIZATION_URL", "http://localhost:8000"),
        portal_url=os.getenv("PORTAL_URL", "http://localhost:8001"),
        scheduling_url=os.getenv("SCHEDULING_URL", "http://localhost:8002"),
    )


@pytest.fixture(scope="function")
def page(settings):
    """
    Provide a Playwright page for portal surface verification.
    Scoped to function so each test gets a clean browser context.
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        pg = context.new_page()
        yield pg
        context.close()
        browser.close()
