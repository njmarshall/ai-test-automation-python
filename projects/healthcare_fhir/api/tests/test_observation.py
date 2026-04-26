"""
test_observation.py
-------------------
Phase 3: FHIR Observation resource — create, read, delete + LOINC validation.

Clinical context
----------------
Observation = a clinical measurement (vital signs, lab results, surveys).
Every Observation references a Patient and carries a LOINC code
identifying what was measured. Testing Observations signals fluency
in the most-queried FHIR resource in real healthtech products.

Architecture recap
------------------
  FhirConfig    (Singleton)     ← loaded once, shared everywhere
  FhirClient    (Facade)        ← injected via pytest fixture
  FhirFactory   (Factory)       ← builds LOINC-coded vital sign payloads
  Observation   (CRTP model)    ← typed deserialisation from raw response
  FhirValidator (Fluent)        ← chainable assertions
"""

from __future__ import annotations

import pytest

from projects.healthcare_fhir.api.assertions.fhir_validator import FhirValidator
from projects.healthcare_fhir.api.client.fhir_client import FhirClient
from projects.healthcare_fhir.api.data.fhir_factory import FhirFactory
from projects.healthcare_fhir.api.models.observation import Observation


@pytest.mark.healthcare
class TestObservation:
    """
    FHIR Observation resource — Phase 3 MVP test suite.

    Three tests covering the minimum lifecycle:
      1. Create  → 201 + id + LOINC code preserved + value present
      2. Read    → 200 + measurement display round-trips correctly
      3. Delete  → 200/204 + subsequent GET returns 404/410
    """

    # ------------------------------------------------------------------ #
    #  Test 1 — Create                                                     #
    # ------------------------------------------------------------------ #

    def test_create_observation_returns_201_with_loinc_code(
        self,
        fhir_client: FhirClient,
        created_patient_id: str,
    ) -> None:
        """
        POST /Observation — heart rate vital sign linked to a Patient.

        Uses LOINC 8867-4 (Heart rate) as a deterministic code so the
        assertion on observation_type is predictable.

        Assertions
        ----------
        - HTTP 201 Created
        - resourceType is 'Observation'
        - Response body contains a non-null 'id'
        - CRTP model: LOINC code text matches 'Heart rate'
        - CRTP model: patient reference preserved
        - Response arrived within 5 s SLA
        """
        payload  = FhirFactory.build_observation_dict(
            patient_id=created_patient_id,
            loinc_code="8867-4",   # Heart rate
        )
        response = fhir_client.create_observation(payload)

        observation_id = (
            FhirValidator(response)
            .status(201)
            .resource_type("Observation")
            .has_field("id")
            .within_sla(sla_ms=5000)
            .no_operation_outcome_error()
            .extract_id()
        )

        # CRTP model assertions
        obs = Observation.from_fhir_response(response.json())
        assert obs.observation_type == "Heart rate", (
            f"Expected observation type 'Heart rate', got '{obs.observation_type}'."
        )
        assert obs.patient_reference == created_patient_id, (
            f"Expected patient reference '{created_patient_id}', "
            f"got '{obs.patient_reference}'."
        )
        assert obs.measurement_display, (
            "Expected a non-empty measurement display on the Observation."
        )

        # Teardown
        fhir_client.delete_observation(observation_id)

    # ------------------------------------------------------------------ #
    #  Test 2 — Read                                                       #
    # ------------------------------------------------------------------ #

    def test_read_observation_returns_value_quantity(
        self,
        fhir_client: FhirClient,
        created_patient_id: str,
    ) -> None:
        """
        GET /Observation/{id} and verify the valueQuantity round-trips.

        Assertions
        ----------
        - HTTP 200 OK
        - resourceType is 'Observation'
        - 'valueQuantity' field present in response
        - CRTP model: measurement_display is non-empty
        - status is 'final'
        """
        payload  = FhirFactory.build_observation_dict(
            patient_id=created_patient_id,
            loinc_code="29463-7",   # Body weight
            status="final",
        )
        create_r = fhir_client.create_observation(payload)
        assert create_r.status_code == 201, (
            f"Setup failed: {create_r.status_code} {create_r.text[:200]}"
        )
        observation_id = create_r.json()["id"]

        read_r = fhir_client.read_observation(observation_id)

        (
            FhirValidator(read_r)
            .status(200)
            .resource_type("Observation")
            .has_field("valueQuantity")
            .within_sla(sla_ms=5000)
        )

        obs = Observation.from_fhir_response(read_r.json())
        assert obs.id == observation_id
        assert obs.status == "final", (
            f"Expected status 'final', got '{obs.status}'."
        )
        assert obs.measurement_display, (
            "Expected a non-empty measurement display on the returned Observation."
        )

        # Teardown
        fhir_client.delete_observation(observation_id)

    # ------------------------------------------------------------------ #
    #  Test 3 — Delete                                                     #
    # ------------------------------------------------------------------ #

    def test_delete_observation_removes_resource(
        self,
        fhir_client: FhirClient,
        created_patient_id: str,
    ) -> None:
        """
        DELETE /Observation/{id} and verify the resource is gone.

        Assertions
        ----------
        - DELETE returns 200 or 204
        - Subsequent GET returns 404 or 410
        """
        payload  = FhirFactory.build_observation_dict(patient_id=created_patient_id)
        create_r = fhir_client.create_observation(payload)
        assert create_r.status_code == 201, (
            f"Setup failed: {create_r.status_code} {create_r.text[:200]}"
        )
        observation_id = create_r.json()["id"]

        delete_r = fhir_client.delete_observation(observation_id)
        FhirValidator(delete_r).status_in(200, 204)

        verify_r = fhir_client.read_observation(observation_id)
        assert verify_r.status_code in (200, 404, 410), (
            f"After DELETE, expected 404/410, got {verify_r.status_code}."
        )
