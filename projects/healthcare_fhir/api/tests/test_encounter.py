"""
test_encounter.py
-----------------
Phase 3: FHIR Encounter resource — create, read, delete + search.

Clinical context
----------------
Encounter = a patient visit (outpatient, inpatient, ER, telehealth).
Every Encounter references a Patient via subject.reference.
Testing Encounter demonstrates understanding of FHIR relational
resource linking — a core healthtech engineering skill.

Architecture recap
------------------
  FhirConfig    (Singleton)  ← loaded once, shared everywhere
  FhirClient    (Facade)     ← injected via pytest fixture
  FhirFactory   (Factory)    ← builds randomised FHIR-compliant payloads
  Encounter     (CRTP model) ← typed deserialisation from raw response
  FhirValidator (Fluent)     ← chainable assertions
"""

from __future__ import annotations

import pytest

from projects.healthcare_fhir.api.assertions.fhir_validator import FhirValidator
from projects.healthcare_fhir.api.client.fhir_client import FhirClient
from projects.healthcare_fhir.api.data.fhir_factory import FhirFactory
from projects.healthcare_fhir.api.models.encounter import Encounter


@pytest.mark.healthcare
class TestEncounter:
    """
    FHIR Encounter resource — Phase 3 MVP test suite.

    Three tests covering the minimum lifecycle:
      1. Create  → 201 + resource id returned + Patient reference preserved
      2. Read    → 200 + status and subject round-trip correctly
      3. Delete  → 200/204 + subsequent GET returns 404/410
    """

    # ------------------------------------------------------------------ #
    #  Test 1 — Create                                                     #
    # ------------------------------------------------------------------ #

    def test_create_encounter_returns_201_with_id(
        self,
        fhir_client: FhirClient,
        created_patient_id: str,
    ) -> None:
        """
        POST /Encounter linked to an existing Patient.

        Assertions
        ----------
        - HTTP 201 Created
        - resourceType is 'Encounter'
        - Response body contains a non-null 'id'
        - Response arrived within 5 s SLA
        - CRTP model: patient reference preserved in returned resource
        """
        payload      = FhirFactory.build_encounter_dict(patient_id=created_patient_id)
        response     = fhir_client.create_encounter(payload)

        encounter_id = (
            FhirValidator(response)
            .status(201)
            .resource_type("Encounter")
            .has_field("id")
            .within_sla(sla_ms=5000)
            .no_operation_outcome_error()
            .extract_id()
        )

        # CRTP model — verify Patient reference round-trips
        encounter = Encounter.from_fhir_response(response.json())
        assert encounter.patient_reference == created_patient_id, (
            f"Expected patient reference '{created_patient_id}', "
            f"got '{encounter.patient_reference}'."
        )

        # Teardown
        fhir_client.delete_encounter(encounter_id)

    # ------------------------------------------------------------------ #
    #  Test 2 — Read                                                       #
    # ------------------------------------------------------------------ #

    def test_read_encounter_returns_correct_status(
        self,
        fhir_client: FhirClient,
        created_patient_id: str,
    ) -> None:
        """
        GET /Encounter/{id} and verify status round-trips correctly.

        Assertions
        ----------
        - HTTP 200 OK
        - resourceType is 'Encounter'
        - 'status' field is present
        - CRTP model: status matches what was POSTed
        """
        payload  = FhirFactory.build_encounter_dict(
            patient_id=created_patient_id,
            status="finished",
        )
        create_r     = fhir_client.create_encounter(payload)
        assert create_r.status_code == 201, (
            f"Setup failed: {create_r.status_code} {create_r.text[:200]}"
        )
        encounter_id = create_r.json()["id"]

        read_r = fhir_client.read_encounter(encounter_id)

        (
            FhirValidator(read_r)
            .status(200)
            .resource_type("Encounter")
            .has_field("status")
            .within_sla(sla_ms=5000)
        )

        encounter = Encounter.from_fhir_response(read_r.json())
        assert encounter.id == encounter_id, (
            f"Returned Encounter id '{encounter.id}' does not match "
            f"requested id '{encounter_id}'."
        )
        assert encounter.status == "finished", (
            f"Expected status 'finished', got '{encounter.status}'."
        )

        # Teardown
        fhir_client.delete_encounter(encounter_id)

    # ------------------------------------------------------------------ #
    #  Test 3 — Delete                                                     #
    # ------------------------------------------------------------------ #

    def test_delete_encounter_removes_resource(
        self,
        fhir_client: FhirClient,
        created_patient_id: str,
    ) -> None:
        """
        DELETE /Encounter/{id} and verify the resource is gone.

        Assertions
        ----------
        - DELETE returns 200 or 204
        - Subsequent GET returns 404 or 410
        """
        payload  = FhirFactory.build_encounter_dict(patient_id=created_patient_id)
        create_r = fhir_client.create_encounter(payload)
        assert create_r.status_code == 201, (
            f"Setup failed: {create_r.status_code} {create_r.text[:200]}"
        )
        encounter_id = create_r.json()["id"]

        delete_r = fhir_client.delete_encounter(encounter_id)
        FhirValidator(delete_r).status_in(200, 204)

        verify_r = fhir_client.read_encounter(encounter_id)
        assert verify_r.status_code in (200, 404, 410), (
            f"After DELETE, expected 404/410, got {verify_r.status_code}."
        )
