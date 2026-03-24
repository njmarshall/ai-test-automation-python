import allure
import pytest
from shared.assertions.response_validator import ResponseValidator
from shared.dataprovider.test_data_factory import TestDataFactory


@allure.feature("PetStore")
@allure.story("Pet CRUD")
class TestPet:
    """
    Full CRUD tests for /pet endpoints.
    Mirrors PetTests.java — POST / GET / PUT / DELETE + findByStatus.
    """

    @allure.title("POST /pet — create a new pet")
    @pytest.mark.smoke
    def test_create_pet(self, api):
        payload = TestDataFactory.random_pet_payload()

        response = api.post("/pet", json=payload)

        (ResponseValidator.from_response(response)
            .status_code(200)
            .within_sla()
            .has_field("id")
            .has_field("name"))

    @allure.title("GET /pet/{id} — retrieve pet by id")
    def test_get_pet(self, api, created_pet):
        response = api.get(f"/pet/{created_pet}")

        (ResponseValidator.from_response(response)
            .status_code(200)
            .within_sla()
            .field_equals("id", created_pet))

    @allure.title("PUT /pet — update pet status to sold")
    def test_update_pet(self, api, created_pet):
        payload = TestDataFactory.random_pet_payload(status="sold")
        payload["id"] = created_pet

        response = api.put("/pet", json=payload)

        (ResponseValidator.from_response(response)
            .status_code(200)
            .field_equals("status", "sold"))

    @allure.title("DELETE /pet/{id} — delete a pet")
    def test_delete_pet(self, api, created_pet):
        response = api.delete(f"/pet/{created_pet}")

        ResponseValidator.from_response(response).status_code(200)

    @allure.title("GET /pet/findByStatus — parametrized by status")
    @pytest.mark.parametrize("status", ["available", "pending", "sold"])
    def test_find_by_status(self, api, status):
        """
        Replaces @DataProvider in TestNG — runs 3 times, one per status.
        """
        response = api.get("/pet/findByStatus", params={"status": status})

        (ResponseValidator.from_response(response)
            .status_code(200)
            .within_sla())