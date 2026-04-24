"""
fhir_resource.py
----------------
Canonical CRTP base for all FHIR R4 resource models.

Pattern : CRTP (Curiously Recurring Template Pattern) via Generic[T]
SOLID   : OCP — new resources (Encounter, Observation, Claim, ...) extend
                FhirResource without modifying it
          SRP — one module, one job: define the shared FHIR resource contract

History : Originally inlined in patient.py (Phase 1 MVP).
          Extracted in Phase 3 so all resource models share one
          canonical base — the right refactor at the right time.

Usage
-----
    from projects.healthcare_fhir.api.models.fhir_resource import FhirResource

    class Patient(FhirResource["Patient"]):
        resource_type: str = Field(default="Patient", alias="resourceType")
        ...
"""

from __future__ import annotations

from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T", bound="FhirResource")


class FhirResource(BaseModel, Generic[T]):
    """
    Generic CRTP base for all FHIR R4 resource models.

    Carries the two fields every FHIR resource shares:
      - resourceType : identifies the resource type on the wire
      - id           : server-assigned identifier (absent on POST request bodies)

    Concrete types inherit and add their own domain fields:
      Patient(FhirResource["Patient"])
      Encounter(FhirResource["Encounter"])
      Observation(FhirResource["Observation"])

    The Generic[T] parameter enables type-safe return signatures in
    factory and client methods without runtime overhead.
    """

    resource_type: str          = Field(alias="resourceType")
    id:            Optional[str] = Field(default=None)

    model_config = {"populate_by_name": True}

    def to_fhir_dict(self) -> dict:
        """
        Serialise to a FHIR-compliant dict.

        Uses alias keys (camelCase) and omits None values so the
        payload is accepted by any FHIR R4 server without transformation.
        """
        return self.model_dump(by_alias=True, exclude_none=True)

    @classmethod
    def from_fhir_response(cls, payload: dict) -> "FhirResource":
        """
        Deserialise a raw FHIR API response dict into this resource type.

        Each concrete subclass inherits this method and returns its own type:
            Patient.from_fhir_response(data)     → Patient
            Encounter.from_fhir_response(data)   → Encounter
            Observation.from_fhir_response(data) → Observation
        """
        return cls.model_validate(payload)
