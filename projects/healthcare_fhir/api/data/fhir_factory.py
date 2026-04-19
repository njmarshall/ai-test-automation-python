"""
fhir_factory.py
---------------
Factory that generates valid, randomised FHIR Patient payloads for tests.

Pattern : Factory Method
SOLID   : SRP — one class, one job: produce test data
          OCP — extend with build_encounter(), build_claim() etc. without
                touching Patient logic
Design  : returns both raw dict (for POST body) and typed Patient model
          (for assertion chaining)
"""

from __future__ import annotations

import uuid
from typing import Optional

from faker import Faker

from projects.healthcare_fhir.api.models.patient import HumanName, Identifier, Patient

_fake = Faker()


class FhirFactory:
    """
    Generates randomised FHIR-compliant test data.

    All methods are static — no state, no instantiation needed.

    Example
    -------
        payload = FhirFactory.build_patient_dict()
        # POST payload["body"] to /Patient
    """

    # ------------------------------------------------------------------ #
    #  Patient                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def build_patient(
        gender: Optional[str] = None,
        active: bool = True,
    ) -> Patient:
        """
        Return a fully populated Patient model with randomised data.

        Parameters
        ----------
        gender : 'male' | 'female' | 'other' | 'unknown' — random if omitted
        active : FHIR active flag (default True)
        """
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
                    system="urn:oid:2.16.840.1.113883.4.1",   # US SSN OID
                    value=str(uuid.uuid4()),                    # synthetic MRN
                )
            ],
        )

    @staticmethod
    def build_patient_dict(
        gender: Optional[str] = None,
        active: bool = True,
    ) -> dict:
        """
        Return a FHIR-compliant dict ready to POST as a request body.

        Alias keys are used (e.g. 'resourceType', 'birthDate') so the
        payload is accepted by any FHIR R4 server without transformation.
        """
        return FhirFactory.build_patient(
            gender=gender,
            active=active,
        ).to_fhir_dict()
