import allure
import pytest
from shared.assertions.response_validator import ResponseValidator
from shared.dataprovider.test_data_factory import TestDataFactory


@allure.feature("PetStore")
@allure.story("Store Orders")
class TestStore:
    """
    Order lifecycle tests for /store endpoints.
    Mirrors StoreTests.java — POST / GET / DELETE /store/order.
    """

    @allure.title("GET /store/inventory — retrieve inventory")
    @pytest.mark.smoke
    def test_get_inventory(self, api):
        response = api.get("/store/inventory")

        (ResponseValidator.from_response(response)
            .status_code(200)
            .within_sla())

    @allure.title("POST /store/order — place a new order")
    def test_place_order(self, api, created_pet):
        payload = TestDataFactory.random_order_payload(pet_id=created_pet)

        response = api.post("/store/order", json=payload)

        (ResponseValidator.from_response(response)
            .status_code(200)
            .within_sla()
            .has_field("id")
            .field_equals("status", "placed"))

    @allure.title("GET /store/order/{id} — retrieve order by id")
    def test_get_order(self, api, created_pet):
        # Place an order first
        payload = TestDataFactory.random_order_payload(pet_id=created_pet)
        order_id = api.post("/store/order", json=payload).json()["id"]

        response = api.get(f"/store/order/{order_id}")

        (ResponseValidator.from_response(response)
            .status_code(200)
            .field_equals("id", order_id))

    @allure.title("DELETE /store/order/{id} — cancel an order")
    def test_delete_order(self, api, created_pet):
        payload = TestDataFactory.random_order_payload(pet_id=created_pet)
        order_id = api.post("/store/order", json=payload).json()["id"]

        response = api.delete(f"/store/order/{order_id}")

        ResponseValidator.from_response(response).status_code(200)