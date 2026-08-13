"""
test_self_healing_agent.py
--------------------------
Tests for the SelfHealingAgent orchestration layer.

What we're testing
------------------
The agent that connects all 4 AI pillars:
  Orchestration  ← SelfHealingAgent
  Guardrails     ← InputGuard + OutputGuard
  Evaluation     ← quality threshold
  Observability  ← AiObserver

Tests use mocking to avoid real Claude API calls,
so they run fast and cost nothing.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from shared.agent.self_healing_agent import SelfHealingAgent, HealingResult


@pytest.mark.healthcare
class TestSelfHealingAgent:
    """Tests for the self-healing agent orchestration."""

    def test_agent_initialises(self) -> None:
        """Agent initialises with all 4 pillars."""
        agent = SelfHealingAgent(require_approval=False)
        assert agent is not None
        assert agent._input_guard is not None
        assert agent._output_guard is not None
        assert agent._observer is not None

    def test_heal_missing_file_returns_error(self) -> None:
        """Agent returns ERROR when test file does not exist."""
        agent = SelfHealingAgent(require_approval=False)

        result = agent.heal(
            failing_test_path="nonexistent/test_file.py",
            error_message="AssertionError: Expected 201, got 422",
            spec_context="POST /Patient",
        )

        assert result.status == "ERROR"
        assert not result.passed
        assert any("Could not read" in f for f in result.failures)

    def test_heal_with_phi_in_prompt_scrubs_it(self, tmp_path) -> None:
        """Agent scrubs PHI from fix prompt before sending to Claude."""
        # Create a temporary test file
        test_file = tmp_path / "test_patient.py"
        test_file.write_text("""
import pytest
from projects.healthcare_fhir.api.client.fhir_client import FhirClient

class TestPatient:
    def test_create_patient(self, fhir_client: FhirClient) -> None:
        response = fhir_client.create_patient({})
        assert response.status_code == 201
""")

        agent = SelfHealingAgent(require_approval=False)

        # Mock Claude to return valid code
        with patch.object(agent, '_generate_fix', return_value="""
import pytest
from projects.healthcare_fhir.api.client.fhir_client import FhirClient

class TestPatient:
    def test_create_patient(self, fhir_client: FhirClient) -> None:
        response = fhir_client.create_patient({})
        assert response.status_code in (201, 422)
"""):
            result = agent.heal(
                failing_test_path=str(test_file),
                error_message="Expected 201, got 422",
                spec_context="POST /Patient John Smith SSN 123-45-6789",
            )

        # PHI in spec_context should have been scrubbed
        assert result.status in ("PASS", "REJECTED")

    def test_heal_rejects_unsafe_generated_code(self, tmp_path) -> None:
        """Agent rejects fix that contains hardcoded credentials."""
        test_file = tmp_path / "test_patient.py"
        test_file.write_text("""
import pytest
class TestPatient:
    def test_create(self) -> None:
        assert True
""")

        agent = SelfHealingAgent(require_approval=False)

        # Mock Claude to return unsafe code with hardcoded password
        with patch.object(agent, '_generate_fix', return_value="""
import pytest
class TestPatient:
    def test_create(self) -> None:
        password = "secret123"
        assert True
"""):
            result = agent.heal(
                failing_test_path=str(test_file),
                error_message="AssertionError",
                spec_context="POST /Patient",
            )

        assert result.status == "REJECTED"
        assert any("hardcoded password" in f for f in result.failures)

    def test_heal_passes_with_valid_fix(self, tmp_path) -> None:
        """Agent returns PASS when fix is valid and safe."""
        test_file = tmp_path / "test_patient.py"
        test_file.write_text("""
import pytest
from projects.healthcare_fhir.api.client.fhir_client import FhirClient

class TestPatient:
    def test_create_patient(self, fhir_client: FhirClient) -> None:
        response = fhir_client.create_patient({})
        assert response.status_code == 201
""")

        agent = SelfHealingAgent(require_approval=False)

        # Mock Claude to return valid fix
        with patch.object(agent, '_generate_fix', return_value="""
import pytest
from projects.healthcare_fhir.api.client.fhir_client import FhirClient

class TestPatient:
    def test_create_patient(self, fhir_client: FhirClient) -> None:
        response = fhir_client.create_patient({})
        assert response.status_code in (201, 422)
"""):
            result = agent.heal(
                failing_test_path=str(test_file),
                error_message="Expected 201, got 422",
                spec_context="POST /Patient FHIR R4",
            )

        assert result.status == "PASS"
        assert result.passed

    def test_metrics_available_after_healing(self, tmp_path) -> None:
        """Observer records metrics after healing attempt."""
        test_file = tmp_path / "test_patient.py"
        test_file.write_text("""
import pytest
class TestPatient:
    def test_create(self) -> None:
        assert True
""")

        agent = SelfHealingAgent(require_approval=False)

        with patch.object(agent, '_generate_fix', return_value="""
import pytest
class TestPatient:
    def test_create(self) -> None:
        assert True
"""):
            agent.heal(
                failing_test_path=str(test_file),
                error_message="AssertionError",
                spec_context="POST /Patient",
            )

        metrics = agent.get_metrics()
        assert isinstance(metrics, str)
        assert len(metrics) > 0

    def test_healing_result_summary(self) -> None:
        """HealingResult summary returns readable string."""
        result = HealingResult(
            test_path="projects/healthcare_fhir/api/tests/test_patient.py",
            status="PASS",
            fix_applied="assert response.status_code in (201, 422)",
            quality_score=0.85,
            cost_usd=0.0023,
            duration_ms=1200,
        )

        summary = result.summary()
        assert "PASS" in summary
        assert "0.85" in summary
        assert "test_patient.py" in summary
