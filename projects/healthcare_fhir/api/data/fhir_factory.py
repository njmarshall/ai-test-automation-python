"""
fhir_factory.py
---------------
Factory that generates valid, randomised FHIR resource payloads for tests.

Pattern : Factory Method
SOLID   : SRP — one class, one job: produce test data
          OCP — Phase 3 adds build_encounter() + build_observation()
                without touching build_patient() (Phase 1 unchanged)

Phase history
-------------
  Phase 1 : build_patient(), build_patient_dict()
  Phase 3 : build_encounter(), build_encounter_dict()
             build_observation(), build_observation_dict()
"""

from __future__ import annotations

import uuid
from typing import Optional

from faker import Faker

from projects.healthcare_fhir.api.models.encounter import (
    Encounter, EncounterClass, EncounterStatus, CodeableConcept, Reference,
)
from projects.healthcare_fhir.api.models.observation import (
    Observation, ObservationStatus, Quantity,
    CodeableConcept as ObsCodeableConcept,
    Reference as ObsReference,
)
from projects.healthcare_fhir.api.models.patient import HumanName, Identifier, Patient

_fake = Faker()


class FhirFactory:
    """
    Generates randomised FHIR-compliant test data.

    All methods are static — no state, no instantiation needed.

    Example
    -------
        patient_payload     = FhirFactory.build_patient_dict()
        encounter_payload   = FhirFactory.build_encounter_dict(patient_id="123")
        observation_payload = FhirFactory.build_observation_dict(patient_id="123")
    """

    # ------------------------------------------------------------------ #
    #  Patient (Phase 1 — unchanged)                                       #
    # ------------------------------------------------------------------ #

    @staticmethod
    def build_patient(
        gender: Optional[str] = None,
        active: bool = True,
    ) -> Patient:
        """Return a fully populated Patient model with randomised data."""
        chosen_gender = gender or _fake.random_element(
            ["male", "female", "other", "unknown"]
        )
        return Patient(
            resourceType="Patient",
            active=active,
            gender=chosen_gender,
            birthDate=_fake.date_of_birth(minimum_age=0, maximum_age=100).isoformat(),
            name=[
                HumanName(
                    use="official",
                    family=_fake.last_name(),
                    given=[_fake.first_name()],
                )
            ],
            identifier=[
                Identifier(
                    system="urn:oid:2.16.840.1.113883.4.1",
                    value=str(uuid.uuid4()),
                )
            ],
        )

    @staticmethod
    def build_patient_dict(
        gender: Optional[str] = None,
        active: bool = True,
    ) -> dict:
        """Return a FHIR-compliant dict ready to POST as a request body."""
        return FhirFactory.build_patient(gender=gender, active=active).to_fhir_dict()

    # ------------------------------------------------------------------ #
    #  Encounter (Phase 3 — new)                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def build_encounter(
        patient_id: Optional[str] = None,
        status:     Optional[str] = None,
    ) -> Encounter:
        """
        Return a fully populated Encounter model with randomised data.

        Parameters
        ----------
        patient_id : FHIR Patient resource id to link this Encounter to.
                     Uses a synthetic uuid if omitted (standalone test data).
        status     : FHIR Encounter status. Defaults to 'finished'.
        """
        chosen_status = status or EncounterStatus.COMPLETED
        ref_id        = patient_id or str(uuid.uuid4())

        encounter_types = [
            "Outpatient Visit",
            "Emergency Room Admission",
            "Annual Wellness Visit",
            "Follow-up Appointment",
            "Telehealth Consultation",
        ]

        return Encounter(
            resourceType="Encounter",
            status=chosen_status,
            **{"class": EncounterClass(
                system="http://terminology.hl7.org/CodeSystem/v3-ActCode",
                code="AMB",
                display="ambulatory",
            )},
            type=[
                CodeableConcept(
                    coding=[{
                        "system":  "http://snomed.info/sct",
                        "code":    "11429006",
                        "display": "Consultation",
                    }],
                    text=_fake.random_element(encounter_types),
                )
            ],
            subject=Reference(
                reference=f"Patient/{ref_id}",
                display=_fake.name(),
            ),
        )

    @staticmethod
    def build_encounter_dict(
        patient_id: Optional[str] = None,
        status:     Optional[str] = None,
    ) -> dict:
        """Return a FHIR-compliant Encounter dict ready to POST."""
        return FhirFactory.build_encounter(
            patient_id=patient_id,
            status=status,
        ).to_fhir_dict()

    # ------------------------------------------------------------------ #
    #  Observation (Phase 3 — new)                                         #
    # ------------------------------------------------------------------ #

    # LOINC vital sign codes used in generated observations
    _VITAL_SIGNS = [
        {
            "loinc":   "8867-4",
            "display": "Heart rate",
            "unit":    "/min",
            "ucum":    "/min",
            "min":     40,
            "max":     120,
        },
        {
            "loinc":   "8310-5",
            "display": "Body temperature",
            "unit":    "Cel",
            "ucum":    "Cel",
            "min":     35,
            "max":     41,
        },
        {
            "loinc":   "29463-7",
            "display": "Body weight",
            "unit":    "kg",
            "ucum":    "kg",
            "min":     40,
            "max":     150,
        },
        {
            "loinc":   "8302-2",
            "display": "Body height",
            "unit":    "cm",
            "ucum":    "cm",
            "min":     140,
            "max":     210,
        },
    ]

    @staticmethod
    def build_observation(
        patient_id: Optional[str] = None,
        loinc_code: Optional[str] = None,
        status:     Optional[str] = None,
    ) -> Observation:
        """
        Return a fully populated Observation model with randomised vital sign data.

        Parameters
        ----------
        patient_id : FHIR Patient resource id to link this Observation to.
        loinc_code : LOINC code for the observation type.
                     Picks a random vital sign if omitted.
        status     : FHIR Observation status. Defaults to 'final'.
        """
        chosen_status = status or ObservationStatus.FINAL
        ref_id        = patient_id or str(uuid.uuid4())

        vital = next(
            (v for v in FhirFactory._VITAL_SIGNS if v["loinc"] == loinc_code),
            _fake.random_element(FhirFactory._VITAL_SIGNS),
        )

        value = round(
            _fake.pyfloat(
                min_value=vital["min"],
                max_value=vital["max"],
                right_digits=1,
            ),
            1,
        )

        return Observation(
            resourceType="Observation",
            status=chosen_status,
            code=ObsCodeableConcept(
                coding=[{
                    "system":  "http://loinc.org",
                    "code":    vital["loinc"],
                    "display": vital["display"],
                }],
                text=vital["display"],
            ),
            subject=ObsReference(
                reference=f"Patient/{ref_id}",
            ),
            effectiveDateTime=_fake.date_time_this_year().strftime("%Y-%m-%dT%H:%M:%S"),
            valueQuantity=Quantity(
                value=value,
                unit=vital["unit"],
                system="http://unitsofmeasure.org",
                code=vital["ucum"],
            ),
        )

    @staticmethod
    def build_observation_dict(
        patient_id: Optional[str] = None,
        loinc_code: Optional[str] = None,
        status:     Optional[str] = None,
    ) -> dict:
        """Return a FHIR-compliant Observation dict ready to POST."""
        return FhirFactory.build_observation(
            patient_id=patient_id,
            loinc_code=loinc_code,
            status=status,
        ).to_fhir_dict()
