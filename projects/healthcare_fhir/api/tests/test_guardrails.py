"""
test_guardrails.py
------------------
Tests for InputGuard and OutputGuard.

What we're testing
------------------
The guardrail layer that sits on both sides of the AI:

  Input side:  PHI scrubbing before sending to Claude
  Output side: Code validation before writing to disk

Real-world context
------------------
In a healthcare AI system, patient data must never leave
the system boundary unprotected. The InputGuard scrubs PHI.
The OutputGuard ensures generated code is safe to merge.

These are the "AI TSA" checks — security on both sides.
"""

from __future__ import annotations

import pytest

from shared.guardrails.input_guard import InputGuard, ScrubResult
from shared.guardrails.output_guard import OutputGuard, ValidationResult


@pytest.mark.healthcare
class TestInputGuard:
    """Tests for PHI scrubbing input guardrail."""

    def test_clean_input_passes_unchanged(self) -> None:
        """Clean input with no PHI passes through unchanged."""
        guard = InputGuard()
        text  = "Generate tests for POST /Patient endpoint."
        result = guard.scrub_with_report(text)

        assert result.is_safe
        assert not result.was_modified
        assert result.scrubbed == text

    def test_scrubs_ssn(self) -> None:
        """Social Security Numbers are scrubbed."""
        guard  = InputGuard()
        result = guard.scrub_with_report("Patient SSN: 123-45-6789")

        assert result.was_modified
        assert "[SSN]" in result.scrubbed
        assert "123-45-6789" not in result.scrubbed
        assert "ssn" in result.items_found

    def test_scrubs_email(self) -> None:
        """Email addresses are scrubbed."""
        guard  = InputGuard()
        result = guard.scrub_with_report(
            "Contact patient at john.smith@hospital.com"
        )

        assert result.was_modified
        assert "[EMAIL]" in result.scrubbed
        assert "john.smith@hospital.com" not in result.scrubbed

    def test_scrubs_phone_number(self) -> None:
        """Phone numbers are scrubbed."""
        guard  = InputGuard()
        result = guard.scrub_with_report("Call patient at 415-555-1234")

        assert result.was_modified
        assert "[PHONE]" in result.scrubbed
        assert "415-555-1234" not in result.scrubbed

    def test_scrubs_mrn(self) -> None:
        """Medical Record Numbers are scrubbed."""
        guard  = InputGuard()
        result = guard.scrub_with_report("Patient MRN: 987654")

        assert result.was_modified
        assert "[MRN]" in result.scrubbed

    def test_strict_mode_raises_on_phi(self) -> None:
        """Strict mode raises ValueError when PHI is detected."""
        guard = InputGuard(strict=True)

        with pytest.raises(ValueError) as exc_info:
            guard.scrub("Patient SSN: 123-45-6789")

        assert "PHI detected" in str(exc_info.value)

    def test_is_safe_returns_true_for_clean_input(self) -> None:
        """is_safe() returns True for input with no PHI."""
        guard = InputGuard()
        assert guard.is_safe("Generate tests for FHIR Patient endpoint.")

    def test_is_safe_returns_false_for_phi(self) -> None:
        """is_safe() returns False when PHI is detected."""
        guard = InputGuard()
        assert not guard.is_safe("Patient email: test@hospital.com")


@pytest.mark.healthcare
class TestOutputGuard:
    """Tests for AI output validation guardrail."""

    def test_valid_code_passes(self) -> None:
        """Valid pytest code passes all checks."""
        guard = OutputGuard()
        code  = '''
import pytest
from projects.healthcare_fhir.api.client.fhir_client import FhirClient

@pytest.mark.healthcare
class TestPatient:
    def test_create_patient(self, fhir_client: FhirClient) -> None:
        response = fhir_client.create_patient({})
        assert response.status_code == 201
'''
        result = guard.validate(code)
        assert result.passed

    def test_syntax_error_fails(self) -> None:
        """Code with syntax errors fails validation."""
        guard  = OutputGuard()
        result = guard.validate("def test_broken(\n    pass")

        assert not result.passed
        assert any("Syntax" in f for f in result.failures)

    def test_no_test_methods_fails(self) -> None:
        """Code without test methods fails validation."""
        guard  = OutputGuard()
        result = guard.validate(
            "import pytest\n\nclass Helper:\n    def help(self): pass"
        )

        assert not result.passed
        assert any("test methods" in f for f in result.failures)

    def test_hardcoded_password_fails(self) -> None:
        """Code with hardcoded credentials fails validation."""
        guard  = OutputGuard()
        result = guard.validate(
            'def test_login():\n    password = "secret123"\n    assert True'
        )

        assert not result.passed
        assert any("hardcoded password" in f for f in result.failures)

    def test_exposed_api_key_fails(self) -> None:
        """Code with exposed API key fails validation."""
        guard  = OutputGuard()
        result = guard.validate(
            'def test_api():\n    key = "sk-ant-api03-abc123"\n    assert True'
        )

        assert not result.passed
        assert any("Anthropic API key" in f for f in result.failures)

    def test_empty_code_fails(self) -> None:
        """Empty code fails validation."""
        guard  = OutputGuard()
        result = guard.validate("")

        assert not result.passed
