"""
Flex test fixtures.
Server runs on port 8010 to avoid collisions with other domains.
"""

import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from projects.fintech.flex.api.server import app


# ---------------------------------------------------------------------------
# Client fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def client():
    """
    Fresh TestClient for each test. Resets in-memory store before each run
    so tests are fully isolated — no shared state bleeds between tests.
    """
    with TestClient(app) as c:
        c.delete("/v1/_test/reset")
        yield c


# ---------------------------------------------------------------------------
# Domain fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rent_due_date():
    """Rent due on the 1st of next month."""
    today = date.today()
    if today.month == 12:
        return date(today.year + 1, 1, 1)
    return date(today.year, today.month + 1, 1)


@pytest.fixture
def standard_plan_payload(rent_due_date):
    """A standard $2,500/month plan for renter R001 at property P100."""
    return {
        "renter_id": "R001",
        "landlord_id": "L001",
        "property_id": "P100",
        "monthly_rent_cents": 250000,   # $2,500.00
        "rent_due_date": rent_due_date.isoformat(),
        "idempotency_key": "plan-idem-001",
    }


@pytest.fixture
def created_plan(client, standard_plan_payload):
    """A plan that has already been created — returns the full response body."""
    resp = client.post("/v1/plans", json=standard_plan_payload)
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def plan_id(created_plan):
    return created_plan["plan_id"]


@pytest.fixture
def installment_1_id(created_plan):
    return created_plan["installments"][0]["installment_id"]


@pytest.fixture
def installment_2_id(created_plan):
    return created_plan["installments"][1]["installment_id"]
