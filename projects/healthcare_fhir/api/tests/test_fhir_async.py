"""
test_fhir_async.py
------------------
Demonstrates AsyncPoller applied to FHIR healthcare domain.

Real-world context
------------------
In production FHIR systems, resources are not always immediately
searchable after creation. A POST /Patient returns 201 with an id,
but the search index may take seconds to catch up. Polling for
the resource to become searchable is a real clinical data pattern.

This mirrors the Indeed email delivery pattern:
  POST /Patient → 201 → poll GET /Patient/{id} → available

Architecture recap
------------------
  AsyncPoller   (shared/async/) ← reusable polling strategy
  FhirClient    (Facade)        ← injected via fixture
  FhirValidator (Fluent)        ← chainable assertions
  FhirFactory   (Factory)       ← randomised FHIR payloads
"""

from __future__ import annotations

import importlib

import pytest

from projects.healthcare_fhir.api.assertions.fhir_validator import FhirValidator
from projects.healthcare_fhir.api.client.fhir_client import FhirClient
from projects.healthcare_fhir.api.data.fhir_factory import FhirFactory
from projects.healthcare_fhir.api.models.patient import Patient

_async_poller = importlib.import_module("shared.async.async_poller")
AsyncPoller = _async_poller.AsyncPoller
PollingTimeoutError = _async_poller.PollingTimeoutError


@pytest.mark.healthcare
class TestFhirAsync:
    """
    Async polling patterns applied to FHIR Patient resource.

    Three tests:
      1. Poll until Patient is readable after creation (timeout strategy)
      2. Poll Encounter after Patient created (fixed retry strategy)
      3. Timeout error when condition never met
    """

    # ------------------------------------------------------------------ #
    #  Test 1 — Poll Patient availability after creation                  #
    # ------------------------------------------------------------------ #

    def test_poll_patient_available_after_creation(
        self, fhir_client: FhirClient
    ) -> None:
        """
        Create a Patient then poll until it is readable.

        Simulates real FHIR systems where search index has latency.
        Uses timeout strategy — same pattern as Finix payment polling.

        Assertions
        ----------
        - Patient created successfully (201)
        - AsyncPoller resolves within 10s timeout
        - GET /Patient/{id} returns 200 with correct resourceType
        - CRTP model: id matches created patient
        """
        payload    = FhirFactory.build_patient_dict()
        create_r   = fhir_client.create_patient(payload)
        assert create_r.status_code == 201, (
            f"Setup failed: {create_r.status_code}"
        )
        patient_id = create_r.json()["id"]

        poller = AsyncPoller(
            strategy="timeout",
            timeout_sec=10.0,
            interval_sec=1.0,
        )

        result = poller.poll(
            fn=lambda: fhir_client.read_patient(patient_id),
            until=lambda r: r.status_code == 200,
            description=f"Patient/{patient_id} to be readable",
        )

        FhirValidator(result) \
            .status(200) \
            .resource_type("Patient") \
            .has_field("id")

        patient = Patient.from_fhir_response(result.json())
        assert patient.id == patient_id
        assert patient.full_name, "Expected non-empty name on polled Patient."

        fhir_client.delete_patient(patient_id)

    # ------------------------------------------------------------------ #
    #  Test 2 — Poll Encounter after Patient created (fixed retry)        #
    # ------------------------------------------------------------------ #

    def test_poll_encounter_with_fixed_retry(
        self, fhir_client: FhirClient, created_patient_id: str
    ) -> None:
        """
        Create an Encounter and poll until readable using fixed retry.

        Fixed retry mirrors Indeed email delivery pattern:
        known number of steps, constant delay between retries.

        Assertions
        ----------
        - Encounter created (201)
        - Fixed retry poller resolves within retry budget
        - GET /Encounter/{id} returns 200
        """
        payload    = FhirFactory.build_encounter_dict(
            patient_id=created_patient_id
        )
        create_r   = fhir_client.create_encounter(payload)
        assert create_r.status_code == 201, (
            f"Setup failed: {create_r.status_code}"
        )
        encounter_id = create_r.json()["id"]

        poller = AsyncPoller(
            strategy="fixed",
            retries=5,
            delay_sec=1.0,
        )

        result = poller.poll(
            fn=lambda: fhir_client.read_encounter(encounter_id),
            until=lambda r: r.status_code == 200,
            description=f"Encounter/{encounter_id} to be readable",
        )

        FhirValidator(result) \
            .status(200) \
            .resource_type("Encounter") \
            .has_field("id")

        fhir_client.delete_encounter(encounter_id)

    # ------------------------------------------------------------------ #
    #  Test 3 — PollingTimeoutError on impossible condition               #
    # ------------------------------------------------------------------ #

    def test_polling_timeout_raises_clear_error(
        self, fhir_client: FhirClient
    ) -> None:
        """
        Verify PollingTimeoutError is raised with a clear message
        when the condition is never satisfied.

        Critical for production — timeout errors must be descriptive
        so engineers know exactly what timed out and why.

        Assertions
        ----------
        - PollingTimeoutError is raised
        - Error message contains the description string
        """
        poller = AsyncPoller(
            strategy="timeout",
            timeout_sec=2.0,
            interval_sec=0.5,
        )

        with pytest.raises(PollingTimeoutError) as exc_info:
            poller.poll(
                fn=lambda: fhir_client.get_currencies()
                    if hasattr(fhir_client, 'get_currencies')
                    else fhir_client.read_patient("nonexistent-id-999"),
                until=lambda r: False,
                description="impossible FHIR condition",
            )

        assert "impossible FHIR condition" in str(exc_info.value)
