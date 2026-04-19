"""
patient.py
----------
FHIR Patient resource model.

Pattern : CRTP (Curiously Recurring Template Pattern) via Generic[T]
          FhirResource[T] is the typed base; Patient extends it.
SOLID   : OCP — new resource types (Encounter, Claim) extend FhirResource,
          never modify it.

Only the fields needed for Phase 1 MVP tests are modelled.
Expand as capstone grows.
"""

from __future__ import annotations

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T", bound="FhirResource")


# ------------------------------------------------------------------ #
#  CRTP base                                                           #
# ------------------------------------------------------------------ #

class FhirResource(BaseModel, Generic[T]):
    """
    Generic base for all FHIR resources.

    Carries the fields every FHIR resource shares.
    Concrete types (Patient, Encounter, …) inherit and add their own.
    """

    resource_type: str = Field(alias="resourceType")
    id: Optional[str]  = Field(default=None)

    model_config = {"populate_by_name": True}

    def to_fhir_dict(self) -> dict:
        """Serialise to a FHIR-compliant dict (camelCase keys, no None values)."""
        return self.model_dump(by_alias=True, exclude_none=True)


# ------------------------------------------------------------------ #
#  FHIR R4 sub-models                                                  #
# ------------------------------------------------------------------ #

class HumanName(BaseModel):
    use:    Optional[str]       = None
    family: Optional[str]       = None
    given:  Optional[List[str]] = None

    def display(self) -> str:
        given = " ".join(self.given or [])
        return f"{given} {self.family or ''}".strip()


class Identifier(BaseModel):
    system: Optional[str] = None
    value:  Optional[str] = None


# ------------------------------------------------------------------ #
#  Patient resource (CRTP concrete)                                    #
# ------------------------------------------------------------------ #

class Patient(FhirResource["Patient"]):
    """
    FHIR R4 Patient resource — Phase 1 MVP fields only.

    CRTP pattern: Patient is both the generic type argument and the
    concrete implementor of FhirResource[Patient].
    """

    resource_type: str             = Field(default="Patient", alias="resourceType")
    name:          Optional[List[HumanName]]  = None
    gender:        Optional[str]              = None
    birth_date:    Optional[str]              = Field(default=None, alias="birthDate")
    identifier:    Optional[List[Identifier]] = None
    active:        Optional[bool]             = None

    @property
    def full_name(self) -> str:
        """Return display name from the first name entry, or empty string."""
        if self.name:
            return self.name[0].display()
        return ""

    @classmethod
    def from_fhir_response(cls, payload: dict) -> "Patient":
        """Deserialise a raw FHIR API response dict into a Patient."""
        return cls.model_validate(payload)
