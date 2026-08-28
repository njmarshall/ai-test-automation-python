"""
test_fhir_patient_contract.py
-----------------------------
Contract tests for the FHIR Patient API.

These tests validate the CONTRACT between consumer and provider —
not just the response for a single call.

The difference:
  Response test  → "Did POST /Patient return 201 today?"
  Contract test  → "Does the server PROMISE to always return
                    201 with resourceType=Patient and an id?"

Why this matters for healthcare:
  If the HAPI FHIR server changes the Patient schema during
  an upgrade — removing a required field or changing a status
  code — this test fails in CI before any deployment.
  Patient data integrity is protected at the boundary.

Architecture:
  FhirPatientContract defines what the consumer expects.
  These tests verify the live provider honours the contract.
  If a test fails here, the provider has broken the contract.
"""

from __future__ import annotations

import pytest

from projects.healthcare_fhir.api.assertions.fhir_validator import FhirValidator
from projects.healthcare_fhir.api.client.fhir_client import FhirClient
from projects.healthcare_fhir.api.data.fhir_factory import FhirFactory
from shared.contract.fhir_patient_contract import FhirPatientContract


@pytest.mark.healthcare
@pytest.mark.contract
class TestFhirPatientContract:
    """
    Contract tests — validates the FHIR provider honours its promises.

    These tests are stricter than response tests:
      - They check required fields explicitly
      - They verify the contract structure is maintained
      - They catch schema drift before production deployment
    """

    def test_create_patient_contract_status(
        self, fhir_client: FhirClient
    ) -> None:
        """
        CONTRACT: POST /Patient MUST return 201.

        If the provider changes this to 200 or 202,
        the contract is broken — fail immediately.
        """
        contract = FhirPatientContract()
        request = contract.create_patient_request()

        response = fhir_client.create_patient(request["body"])

        # Contract: status MUST be 201 — no exceptions
        assert response.status_code == 201, (
            f"CONTRACT VIOLATED: POST /Patient must return 201. "
            f"Provider returned {response.status_code}. "
            f"This is a breaking change."
        )

        # Cleanup
        patient_id = response.json().get("id")
        if patient_id:
            fhir_client.delete_patient(patient_id)

    def test_create_patient_contract_resource_type(
        self, fhir_client: FhirClient
    ) -> None:
        """
        CONTRACT: POST /Patient response MUST contain resourceType=Patient.

        If the provider removes or renames this field,
        every consumer that reads Patient resources breaks.
        """
        payload = FhirPatientContract.create_patient_request()["body"]
        response = fhir_client.create_patient(payload)

        assert response.status_code == 201
        body = response.json()

        # Contract: resourceType MUST be present and MUST be "Patient"
        assert "resourceType" in body, (
            "CONTRACT VIOLATED: resourceType field missing from POST /Patient response."
        )
        assert body["resourceType"] == "Patient", (
            f"CONTRACT VIOLATED: resourceType must be 'Patient'. "
            f"Provider returned '{body['resourceType']}'."
        )

        patient_id = body.get("id")
        if patient_id:
            fhir_client.delete_patient(patient_id)

    def test_create_patient_contract_id_present(
        self, fhir_client: FhirClient
    ) -> None:
        """
        CONTRACT: POST /Patient response MUST contain an id.

        Without an id, the consumer cannot read, update,
        or delete the resource it just created.
        """
        payload = FhirPatientContract.create_patient_request()["body"]
        response = fhir_client.create_patient(payload)

        assert response.status_code == 201
        body = response.json()

        # Contract: id MUST be present and non-empty
        assert "id" in body, (
            "CONTRACT VIOLATED: id field missing from POST /Patient response."
        )
        assert body["id"], (
            "CONTRACT VIOLATED: id field is empty in POST /Patient response."
        )

        fhir_client.delete_patient(body["id"])

    def test_read_patient_contract_required_fields(
        self, fhir_client: FhirClient, created_patient_id: str
    ) -> None:
        """
        CONTRACT: GET /Patient/{id} MUST return:
          - status 200
          - resourceType = "Patient"
          - id field present
          - name field present

        These are the minimum fields every consumer depends on.
        """
        response = fhir_client.read_patient(created_patient_id)

        # Contract: status MUST be 200
        assert response.status_code == 200, (
            f"CONTRACT VIOLATED: GET /Patient must return 200. "
            f"Provider returned {response.status_code}."
        )

        body = response.json()

        # Contract: required fields
        assert body.get("resourceType") == "Patient", (
            "CONTRACT VIOLATED: resourceType must be 'Patient' in GET response."
        )
        assert "id" in body, (
            "CONTRACT VIOLATED: id field missing from GET /Patient response."
        )
        assert "name" in body, (
            "CONTRACT VIOLATED: name field missing from GET /Patient response. "
            "This is a required FHIR R4 field that consumers depend on."
        )

    def test_delete_patient_contract_status(
        self, fhir_client: FhirClient
    ) -> None:
        """
        CONTRACT: DELETE /Patient/{id} MUST return 200.

        If delete returns 204 or 404, consumers that check
        for 200 will incorrectly treat it as a failure.
        """
        payload = FhirPatientContract.create_patient_request()["body"]
        create_response = fhir_client.create_patient(payload)
        assert create_response.status_code == 201

        patient_id = create_response.json()["id"]
        delete_response = fhir_client.delete_patient(patient_id)

        # Contract: DELETE MUST return 200
        assert delete_response.status_code == 200, (
            f"CONTRACT VIOLATED: DELETE /Patient must return 200. "
            f"Provider returned {delete_response.status_code}."
        )

    def test_contract_description_is_readable(self) -> None:
        """
        Verify the contract description is complete and readable.
        Used for documentation and audit purposes.
        """
        description = FhirPatientContract.describe()

        assert "Consumer" in description
        assert "Provider" in description
        assert "POST /Patient" in description
        assert "GET" in description
        assert "DELETE" in description
        assert "Breaking changes" in description
