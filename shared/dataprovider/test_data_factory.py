from faker import Faker

_fake = Faker()


class TestDataFactory:
    """
    Random test data factory — replaces TestDataFactory.java.
    Uses python-faker, same concept as Java Faker.
    """

    @staticmethod
    def random_pet_payload(status: str = "available") -> dict:
        return {
            "id": _fake.random_int(min=10000, max=99999),
            "name": _fake.first_name(),
            "status": status,
            "photoUrls": [_fake.image_url()],
            "tags": [{"id": 1, "name": _fake.word()}],
            "category": {"id": 1, "name": _fake.word()},
        }

    @staticmethod
    def random_order_payload(pet_id: int) -> dict:
        return {
            "id": _fake.random_int(min=1, max=9999),
            "petId": pet_id,
            "quantity": _fake.random_int(min=1, max=5),
            "shipDate": "2025-06-01T00:00:00.000Z",
            "status": "placed",
            "complete": False,
        }