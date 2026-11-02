"""
client.py : prior authorization domain
------------------------------------------
Facade over FastAPI's TestClient for the prior-auth sandbox.

Facade pattern: tests never call the TestClient directly.
All prior-auth operations go through PriorAuthClient.
"""

from __future__ import annotations

from typing import Optional

from fastapi.testclient import TestClient


class PriorAuthClient:
    """
    Facade over the prior-auth sandbox API.

    Example
    -------
        client = PriorAuthClient(TestClient(app))
        response = client.submit(
            patient_id="pat-001", patient_name="Jordan Ellis",
            provider_id="prov-100", procedure_code="29881",
            procedure_description="Knee arthroscopy",
            diagnosis_code="M23.51",
        )
        assert response.status_code == 201
    """

    def __init__(self, test_client: TestClient) -> None:
        self._client = test_client

    def reset_sandbox(self) -> None:
        self._client.delete("/sandbox/reset")

    def configure(self, patient_notification_complete: bool):
        return self._client.post(
            "/sandbox/configure",
            params={"patient_notification_complete": patient_notification_complete},
        )

    def submit(
        self,
        patient_id:             str,
        patient_name:           str,
        provider_id:            str,
        procedure_code:         str,
        procedure_description:  str,
        diagnosis_code:         str,
    ):
        return self._client.post("/prior-auth/requests", json={
            "patient_id":            patient_id,
            "patient_name":          patient_name,
            "provider_id":           provider_id,
            "procedure_code":        procedure_code,
            "procedure_description": procedure_description,
            "diagnosis_code":        diagnosis_code,
        })

    def get_request(self, request_id: str):
        return self._client.get(f"/prior-auth/requests/{request_id}")

    def review(
        self,
        request_id:  str,
        approve:     bool,
        reviewer_id: str,
        reason:      Optional[str] = None,
    ):
        return self._client.post(
            f"/prior-auth/requests/{request_id}/review",
            json={"approve": approve, "reviewer_id": reviewer_id, "reason": reason},
        )

    def notifications(self, request_id: str):
        return self._client.get(f"/prior-auth/requests/{request_id}/notifications")
