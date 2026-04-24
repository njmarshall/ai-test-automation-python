"""
patient.py
----------
FHIR R4 Patient resource model.

Pattern : CRTP (Curiously Recurring Template Pattern)
          Patient extends FhirResource["Patient"]
SOLID   : OCP — FhirResource base is imported, never modified here
          SRP — this module owns only Patient-specific fields

History : Phase 1 — FhirResource base was defined inline here (MVP shortcut)
          Phase 3 — base extracted to fhir_resource.py (correct home);
                    patient.py now imports it — zero behaviour change
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from projects.healthcare_fhir.api.models.fhir_resource import FhirResource


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
    FHIR R4 Patient resource.

    CRTP pattern: Patient is both the generic type argument and the
    concrete implementor of FhirResource[Patient].
    """

    resource_type: str                        = Field(default="Patient", alias="resourceType")
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
