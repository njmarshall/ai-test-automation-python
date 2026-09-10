"""
test_exploratory_agent.py
--------------------------
Tests for the ExploratoryTestAgent.

Tests use mocking to avoid real Claude API calls and
real HTTP requests — so they run fast and cost nothing.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from shared.agent.exploratory_test_agent import (
    ExploratoryTestAgent,
    ExplorationFinding,
    ExplorationResult,
    FHIR_PATIENT_SPEC,
)


@pytest.mark.healthcare
class TestExploratoryTestAgent:
    """Tests for the exploratory test agent."""

    def test_agent_initialises(self) -> None:
        """Agent initialises with base URL and spec context."""
        agent = ExploratoryTestAgent(
            base_url="https://hapi.fhir.org/baseR4",
            spec_context=FHIR_PATIENT_SPEC,
            max_scenarios=5,
        )
        assert agent is not None
        assert agent._max_scenarios == 5

    def test_exploration_result_summary(self) -> None:
        """ExplorationResult summary returns readable string."""
        result = ExplorationResult(
            resource="Patient",
            scenarios_run=5,
            cost_usd=0.0023,
            duration_ms=1500,
        )
        summary = result.summary()
        assert "Patient" in summary
        assert "5" in summary
        assert "0.0023" in summary

    def test_exploration_finding_severity(self) -> None:
        """Finding identifies unexpected behavior correctly."""
        finding = ExplorationFinding(
            scenario="Missing required field",
            request="POST /Patient",
            status_code=201,
            response_body="{}",
            expected="Expected 422, got 201",
            severity="HIGH",
            notes="Should have rejected invalid payload",
        )
        assert finding.is_unexpected()
        assert "HIGH" in finding.summary()

    def test_info_finding_not_unexpected(self) -> None:
        """INFO severity finding is not flagged as unexpected."""
        finding = ExplorationFinding(
            scenario="Normal read",
            request="GET /Patient/123",
            status_code=200,
            response_body="{}",
            expected="Expected 200",
            severity="INFO",
        )
        assert not finding.is_unexpected()

    def test_explore_returns_result_without_api_key(self) -> None:
        """Explore returns error result when API key not set."""
        agent = ExploratoryTestAgent(
            base_url="https://hapi.fhir.org/baseR4",
            spec_context=FHIR_PATIENT_SPEC,
            max_scenarios=3,
        )

        import os
        original = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            result = agent.explore(
                resource="Patient",
                description="FHIR R4 Patient endpoints",
            )
            assert result.resource == "Patient"
            assert result.error is not None
        finally:
            if original:
                os.environ["ANTHROPIC_API_KEY"] = original

    def test_explore_with_mocked_claude(self) -> None:
        """Explore generates and executes scenarios with mocked Claude."""
        agent = ExploratoryTestAgent(
            base_url="https://hapi.fhir.org/baseR4",
            spec_context=FHIR_PATIENT_SPEC,
            max_scenarios=2,
        )

        mock_scenarios = [
            {
                "name": "Missing resourceType",
                "method": "POST",
                "path": "/Patient",
                "payload": {"name": [{"family": "Test"}]},
                "expected_status": 400,
                "rationale": "Should reject payload without resourceType"
            },
            {
                "name": "Read non-existent patient",
                "method": "GET",
                "path": "/Patient/nonexistent-id-99999",
                "payload": None,
                "expected_status": 404,
                "rationale": "Non-existent ID should return 404"
            }
        ]

        with patch.object(agent, '_generate_scenarios', return_value=mock_scenarios):
            with patch.object(agent, '_execute_scenario') as mock_execute:
                mock_execute.return_value = None  # No unexpected findings
                result = agent.explore(
                    resource="Patient",
                    description="FHIR R4 Patient endpoints",
                )

        assert result.resource == "Patient"
        assert result.scenarios_run == 2
        assert result.passed

    def test_unexpected_finding_detected(self) -> None:
        """Agent correctly records HIGH severity finding."""
        agent = ExploratoryTestAgent(
            base_url="https://hapi.fhir.org/baseR4",
            spec_context=FHIR_PATIENT_SPEC,
            max_scenarios=1,
        )

        mock_scenarios = [{
            "name": "Server error scenario",
            "method": "GET",
            "path": "/Patient/trigger-500",
            "payload": None,
            "expected_status": 200,
            "rationale": "Should return 200 but might trigger 500"
        }]

        high_finding = ExplorationFinding(
            scenario="Server error scenario",
            request="GET /Patient/trigger-500",
            status_code=500,
            response_body="Internal Server Error",
            expected="Expected 200, got 500",
            severity="HIGH",
        )

        with patch.object(agent, '_generate_scenarios', return_value=mock_scenarios):
            with patch.object(agent, '_execute_scenario', return_value=high_finding):
                result = agent.explore(
                    resource="Patient",
                    description="FHIR R4 Patient endpoints",
                )

        assert result.unexpected_count == 1
        assert result.findings[0].severity == "HIGH"

    def test_metrics_available_after_exploration(self) -> None:
        """Observer records metrics after exploration attempt."""
        agent = ExploratoryTestAgent(
            base_url="https://hapi.fhir.org/baseR4",
            spec_context=FHIR_PATIENT_SPEC,
        )
        metrics = agent.get_metrics()
        assert isinstance(metrics, str)
        assert len(metrics) > 0

    def test_fhir_patient_spec_context_exists(self) -> None:
        """FHIR Patient spec context is non-empty and contains key terms."""
        assert "Patient" in FHIR_PATIENT_SPEC
        assert "resourceType" in FHIR_PATIENT_SPEC
        assert "POST" in FHIR_PATIENT_SPEC
        assert "GET" in FHIR_PATIENT_SPEC
