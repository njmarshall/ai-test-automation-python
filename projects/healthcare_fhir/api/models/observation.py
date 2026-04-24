"""
observation.py
--------------
FHIR R4 Observation resource model.

Pattern : CRTP — Observation extends FhirResource["Observation"]
SOLID   : OCP  — extends the base without modifying it
          SRP  — owns only Observation-specific fields

Clinical context
----------------
An Observation represents a clinical measurement or assertion:
  - Vital signs  (blood pressure, heart rate, temperature, SpO2)
  - Lab results  (glucose, HbA1c, creatinine, CBC)
  - Social history (smoking status, alcohol use)
  - Survey results (PHQ-9, CAGE questionnaire)

Observation is the most-queried resource in real FHIR implementations.
Every patient monitoring, analytics, and population health product
is built on top of Observations. Testing it signals deep FHIR fluency.

Phase 3 MVP fields
------------------
Models vital signs (valueQuantity) only.
Lab results with components (blood pressure systolic/diastolic)
can be added in Phase 4 expansion.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from projects.healthcare_fhir.api.models.fhir_resource import FhirResource


# ------------------------------------------------------------------ #
#  FHIR R4 sub-models                                                  #
# ------------------------------------------------------------------ #

class ObservationStatus:
    """Canonical FHIR R4 Observation status codes."""
    REGISTERED   = "registered"
    PRELIMINARY  = "preliminary"
    FINAL        = "final"
    AMENDED      = "amended"
    CORRECTED    = "corrected"
    CANCELLED    = "cancelled"
    UNKNOWN      = "unknown"


class Quantity(BaseModel):
    """FHIR Quantity — a measured value with unit."""
    value:  Optional[float] = None
    unit:   Optional[str]   = None
    system: Optional[str]   = None   # e.g. "http://unitsofmeasure.org"
    code:   Optional[str]   = None   # UCUM code e.g. "kg", "mm[Hg]", "/min"


class CodeableConcept(BaseModel):
    """Minimal FHIR CodeableConcept — code + display text."""
    coding: Optional[List[dict]] = None
    text:   Optional[str]        = None


class Reference(BaseModel):
    """FHIR Reference — points to another resource."""
    reference: Optional[str] = None   # e.g. "Patient/123"
    display:   Optional[str] = None


# ------------------------------------------------------------------ #
#  Observation resource (CRTP concrete)                                #
# ------------------------------------------------------------------ #

class Observation(FhirResource["Observation"]):
    """
    FHIR R4 Observation resource — Phase 3 MVP fields (vital signs).

    CRTP pattern: Observation is both the generic type argument and
    the concrete implementor of FhirResource[Observation].

    Clinical note: Every Observation must have a subject (Patient)
    and a code (LOINC code identifying what was measured).
    The valueQuantity carries the measurement itself.

    LOINC codes used in Phase 3 tests:
      8867-4  — Heart rate           (beats/min)
      8310-5  — Body temperature     (Cel)
      29463-7 — Body weight          (kg)
      8302-2  — Body height          (cm)
    """

    resource_type:  str                       = Field(default="Observation", alias="resourceType")
    status:         Optional[str]             = None
    code:           Optional[CodeableConcept] = None    # LOINC code
    subject:        Optional[Reference]       = None    # → Patient reference
    value_quantity: Optional[Quantity]        = Field(default=None, alias="valueQuantity")
    effective_date_time: Optional[str]        = Field(default=None, alias="effectiveDateTime")

    @property
    def patient_reference(self) -> str:
        """Return the referenced Patient id, or empty string."""
        if self.subject and self.subject.reference:
            return self.subject.reference.split("/")[-1]
        return ""

    @property
    def measurement_display(self) -> str:
        """Return human-readable measurement string e.g. '72 /min'."""
        if self.value_quantity:
            val  = self.value_quantity.value
            unit = self.value_quantity.unit or ""
            return f"{val} {unit}".strip()
        return ""

    @property
    def observation_type(self) -> str:
        """Return display text of the observation code, or empty string."""
        if self.code and self.code.text:
            return self.code.text
        return ""
