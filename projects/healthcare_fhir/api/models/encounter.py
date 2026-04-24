"""
encounter.py
------------
FHIR R4 Encounter resource model.

Pattern : CRTP — Encounter extends FhirResource["Encounter"]
SOLID   : OCP  — extends the base without modifying it
          SRP  — owns only Encounter-specific fields

Clinical context
----------------
An Encounter represents a patient visit or interaction with a
healthcare provider — hospital admission, outpatient appointment,
emergency visit, telehealth session. It is the backbone of
clinical workflow in every major EHR system (Epic, Cerner, Veeva).

Testing Encounter signals to healthtech hiring managers that you
understand the clinical data model beyond introductory CRUD.

Phase 3 MVP fields
------------------
Only the fields needed for POST/GET/DELETE tests are modelled.
Full R4 Encounter has 30+ fields — expand as capstone grows.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from projects.healthcare_fhir.api.models.fhir_resource import FhirResource


# ------------------------------------------------------------------ #
#  FHIR R4 sub-models                                                  #
# ------------------------------------------------------------------ #

class EncounterStatus:
    """Canonical FHIR R4 Encounter status codes."""
    PLANNED      = "planned"
    IN_PROGRESS  = "in-progress"
    ON_HOLD      = "on-hold"
    DISCHARGED   = "discharged"
    COMPLETED    = "finished"
    CANCELLED    = "cancelled"
    UNKNOWN      = "unknown"


class CodeableConcept(BaseModel):
    """Minimal FHIR CodeableConcept — code + display text."""
    coding: Optional[List[dict]] = None
    text:   Optional[str]        = None


class Reference(BaseModel):
    """FHIR Reference — points to another resource."""
    reference: Optional[str] = None   # e.g. "Patient/123"
    display:   Optional[str] = None


class EncounterClass(BaseModel):
    """FHIR R4 encounter class (ambulatory, inpatient, emergency, etc.)"""
    system:  Optional[str] = None
    code:    Optional[str] = None
    display: Optional[str] = None


# ------------------------------------------------------------------ #
#  Encounter resource (CRTP concrete)                                  #
# ------------------------------------------------------------------ #

class Encounter(FhirResource["Encounter"]):
    """
    FHIR R4 Encounter resource — Phase 3 MVP fields.

    CRTP pattern: Encounter is both the generic type argument and
    the concrete implementor of FhirResource[Encounter].

    Clinical note: Every Encounter must reference a subject (Patient).
    The subject field links the Encounter to a Patient resource via
    a FHIR Reference — this is the core of the FHIR relational model.
    """

    resource_type:  str                          = Field(default="Encounter", alias="resourceType")
    status:         Optional[str]                = None
    encounter_class: Optional[EncounterClass]    = Field(default=None, alias="class")
    type:           Optional[List[CodeableConcept]] = None
    subject:        Optional[Reference]          = None    # → Patient reference
    reason_code:    Optional[List[CodeableConcept]] = Field(default=None, alias="reasonCode")

    @property
    def patient_reference(self) -> str:
        """Return the referenced Patient id, or empty string."""
        if self.subject and self.subject.reference:
            return self.subject.reference.split("/")[-1]
        return ""

    @property
    def encounter_type_display(self) -> str:
        """Return display text of the first encounter type, or empty string."""
        if self.type and self.type[0].text:
            return self.type[0].text
        return ""
