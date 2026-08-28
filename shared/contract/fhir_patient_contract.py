"""
fhir_patient_contract.py
------------------------
Pact contract test for the FHIR Patient API.

What is contract testing?
-------------------------
Your existing tests validate API responses:
  "Does POST /Patient return 201 with a Patient resource?"

Contract tests validate API promises:
  "Does the FHIR server PROMISE to always return 201
   with a Patient resource when I send this payload?
   And will it STILL promise this after deployment?"

The difference matters in healthcare:
  - Response test: checks what happened TODAY
  - Contract test: catches breaking changes BEFORE deployment

If the FHIR server changes the Patient schema without notice,
the contract test fails in CI before any patient data is affected.

Pattern : Consumer-Driven Contract Testing (Pact)
SOLID   : OCP — new contracts added without modifying existing
          SRP — one contract per resource type

Real-world context
------------------
At a major job search platform, API changes between services
caused silent failures that took hours to diagnose. Contract
testing catches these at the boundary — not in production.

Usage
-----
    # Run contract tests
    pytest shared/contract/test_fhir_patient_contract.py -v

    # The Pact file is generated at:
    # pacts/fhir-consumer-fhir-provider.json
"""

from __future__ import annotations

import uuid
from typing import Any, Dict


# ------------------------------------------------------------------ #
#  Contract definitions — what the consumer expects                   #
# ------------------------------------------------------------------ #

class FhirPatientContract:
    """
    Defines the contract between the test consumer and FHIR provider.

    A contract specifies:
      - What request the consumer sends
      - What response the provider MUST return
      - What fields are required (mandatory) vs optional

    If the provider changes a required field, the contract breaks
    and CI fails — before any production deployment.
    """

    CONSUMER_NAME = "fhir-test-consumer"
    PROVIDER_NAME = "hapi-fhir-provider"

    # ------------------------------------------------------------------ #
    #  CREATE Patient contract                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def create_patient_request() -> Dict[str, Any]:
        """
        What the consumer sends when creating a Patient.
        The provider MUST accept this exact structure.
        """
        return {
            "method": "POST",
            "path": "/Patient",
            "headers": {
                "Content-Type": "application/fhir+json",
            },
            "body": {
                "resourceType": "Patient",
                "active": True,
                "name": [
                    {
                        "use": "official",
                        "family": "TestFamily",
                        "given": ["TestGiven"]
                    }
                ],
                "gender": "male",
                "birthDate": "1990-01-01",
                "identifier": [
                    {
                        "system": "urn:oid:2.16.840.1.113883.4.1",
                        "value": str(uuid.uuid4())
                    }
                ]
            }
        }

    @staticmethod
    def create_patient_response() -> Dict[str, Any]:
        """
        What the consumer expects back when creating a Patient.
        The provider MUST return at minimum these fields.

        Required fields (contract guaranteed):
          - status 201
          - resourceType = "Patient"
          - id (any non-empty string)

        Optional fields (contract tolerant):
          - meta, text, identifier — may or may not be present
        """
        return {
            "status": 201,
            "headers": {
                "Content-Type": "application/fhir+json"
            },
            "body": {
                "resourceType": "Patient",  # REQUIRED — must always be "Patient"
                "id": "any-non-empty-string",  # REQUIRED — must always have an id
            }
        }

    # ------------------------------------------------------------------ #
    #  READ Patient contract                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def read_patient_request(patient_id: str = "test-patient-id") -> Dict[str, Any]:
        """
        What the consumer sends when reading a Patient.
        """
        return {
            "method": "GET",
            "path": f"/Patient/{patient_id}",
            "headers": {
                "Accept": "application/fhir+json",
            }
        }

    @staticmethod
    def read_patient_response() -> Dict[str, Any]:
        """
        What the consumer expects when reading a Patient.

        Required fields:
          - status 200
          - resourceType = "Patient"
          - id present
          - name present (at least one entry)
        """
        return {
            "status": 200,
            "body": {
                "resourceType": "Patient",
                "id": "any-non-empty-string",
                "name": []  # must be present, may be empty list
            }
        }

    # ------------------------------------------------------------------ #
    #  DELETE Patient contract                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def delete_patient_request(patient_id: str = "test-patient-id") -> Dict[str, Any]:
        """
        What the consumer sends when deleting a Patient.
        """
        return {
            "method": "DELETE",
            "path": f"/Patient/{patient_id}",
        }

    @staticmethod
    def delete_patient_response() -> Dict[str, Any]:
        """
        What the consumer expects when deleting a Patient.
        FHIR R4 returns 200 with OperationOutcome on successful delete.
        """
        return {
            "status": 200,
        }

    # ------------------------------------------------------------------ #
    #  Contract summary                                                    #
    # ------------------------------------------------------------------ #

    @classmethod
    def describe(cls) -> str:
        """Return a human-readable contract description."""
        return f"""
FHIR Patient API Contract
=========================
Consumer : {cls.CONSUMER_NAME}
Provider : {cls.PROVIDER_NAME}

Interactions:
  1. POST /Patient    → 201 with resourceType=Patient and id
  2. GET  /Patient/id → 200 with resourceType=Patient and id and name
  3. DELETE /Patient/id → 200

Breaking changes that would violate this contract:
  - Removing resourceType from POST response
  - Removing id from any response
  - Changing POST success status from 201 to anything else
  - Removing name field from GET response
  - Requiring new mandatory request fields without versioning
"""
