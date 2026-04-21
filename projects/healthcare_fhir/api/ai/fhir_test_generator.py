"""
fhir_test_generator.py
----------------------
FHIR-specific AI test generator — extends BaseTestGenerator.

Pattern : Template Method (concrete implementation of the variant steps)
SOLID   : OCP — adds FHIR domain knowledge without touching the base class
          SRP — one class, one job: craft FHIR-specific prompts

The generated tests:
  - Use the same framework stack as Phase 1 (FhirClient, FhirValidator,
    FhirFactory, pytest fixtures) so they run out of the box
  - Cover happy path, error path, and edge cases per endpoint
  - Include docstrings explaining what each test validates
  - Are written to ai/generated/test_patient_ai.py by generate_tests.py
"""

from __future__ import annotations

import json

from projects.healthcare_fhir.api.ai.fhir_spec_loader import FhirSpecLoader
from shared.ai.test_generator import BaseTestGenerator


class FhirTestGenerator(BaseTestGenerator):
    """
    Generates pytest test cases for FHIR R4 Patient endpoints
    using the Anthropic SDK.

    Inherits the generate() Template Method from BaseTestGenerator.
    Implements build_system_prompt() and build_prompt() for FHIR domain.

    Example
    -------
        generator = FhirTestGenerator()
        loader    = FhirSpecLoader()
        spec      = loader.load_minimal_patient_spec()
        code      = generator.generate(spec)
        print(code)
    """

    # ------------------------------------------------------------------ #
    #  Template Method variant steps                                       #
    # ------------------------------------------------------------------ #

    def build_system_prompt(self) -> str:
        return """You are a Senior SDET specialising in FHIR R4 healthcare API test automation.

You write production-grade pytest test suites that:
- Use the existing FhirClient facade (never raw httpx)
- Use FhirValidator for fluent chainable assertions
- Use FhirFactory for randomised FHIR-compliant test data
- Use pytest fixtures from conftest.py (fhir_client, created_patient_id)
- Follow SOLID principles and FAANG-level test design
- Cover happy path, error paths, and edge cases
- Include clear docstrings explaining what each test validates

STRICT OUTPUT RULES:
- Output ONLY valid Python source code
- No markdown fences, no explanations, no comments outside the code
- Start directly with the import statements
- Every test method name starts with test_
- Every test class name starts with Test
- Use @pytest.mark.healthcare on every class"""

    def build_prompt(self, spec: dict) -> str:
        spec_json = json.dumps(spec, indent=2)
        return f"""Generate a comprehensive pytest test suite for the following FHIR R4 API spec.

FHIR API SPEC:
{spec_json}

FRAMEWORK IMPORTS TO USE:
    import pytest
    from projects.healthcare_fhir.api.assertions.fhir_validator import FhirValidator
    from projects.healthcare_fhir.api.client.fhir_client import FhirClient
    from projects.healthcare_fhir.api.data.fhir_factory import FhirFactory
    from projects.healthcare_fhir.api.models.patient import Patient

FIXTURE AVAILABLE (from conftest.py):
    fhir_client        — session-scoped FhirClient instance
    created_patient_id — function-scoped: creates Patient, yields id, deletes after

REQUIREMENTS:
1. Generate tests for ALL endpoints in the spec
2. Each endpoint must have at minimum:
   - One happy path test
   - One error path test (wrong id, missing field, bad input)
3. For GET /Patient (search): test at least 2 query parameters
4. For PUT /Patient/{{id}}: test both update and field validation
5. Use FhirValidator chaining:
   FhirValidator(response).status(200).resource_type("Patient").has_field("id")
6. Use FhirFactory.build_patient_dict() for all POST/PUT bodies
7. Never hardcode patient IDs — always use fixtures or extract from responses
8. Add a module docstring explaining this file was AI-generated

Generate the complete test file now:"""

    # ------------------------------------------------------------------ #
    #  Convenience class method                                            #
    # ------------------------------------------------------------------ #

    @classmethod
    def generate_from_minimal_spec(cls) -> str:
        """
        One-liner: generate tests from the built-in minimal Patient spec.
        No network, no file needed — works anywhere.

        Example
        -------
            code = FhirTestGenerator.generate_from_minimal_spec()
        """
        generator = cls()
        spec      = FhirSpecLoader().load_minimal_patient_spec()
        return generator.generate(spec)
