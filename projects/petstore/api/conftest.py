import pytest
from shared.http.api_client import ApiClient
from shared.dataprovider.test_data_factory import TestDataFactory


@pytest.fixture(scope="session")
def api():
    """
    Session-scoped HTTP client.
    Created ONCE for the entire test run — replaces @BeforeClass ApiClient setup.
    Torn down automatically after all tests finish.
    """
    client = ApiClient()
    yield client          # ← everything after yield is teardown (@AfterClass)
    client.close()


@pytest.fixture(scope="function")
def created_pet(api):
    """
    Creates a real pet before each test, yields its ID, deletes it after.
    Replaces @BeforeMethod / @AfterMethod test data setup in TestNG.

    Usage in a test:  def test_something(self, api, created_pet):
    """
    payload = TestDataFactory.random_pet_payload()
    response = api.post("/pet", json=payload)
    pet_id = response.json()["id"]

    yield pet_id          # ← test runs here with the pet_id

    api.delete(f"/pet/{pet_id}")   # teardown — always runs even if test fails