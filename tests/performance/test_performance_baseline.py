"""
test_performance_baseline.py
-----------------------------
Performance baseline tests for the FHIR Patient API.
Uses FhirPerformanceChecker directly — no conftest fixtures
that make HTTP calls during collection.
"""

from __future__ import annotations

import pytest

from shared.performance.fhir_load_test import FhirPerformanceChecker, FhirSLA


@pytest.mark.healthcare
@pytest.mark.performance
class TestFhirPerformanceBaseline:
    """Performance baseline tests for FHIR Patient API."""

    def test_create_patient_within_sla(self) -> None:
        """POST /Patient must respond within 3000ms."""
        checker = FhirPerformanceChecker(sla=FhirSLA(create_ms=3000))
        result  = checker.measure_create_patient()

        print(f"\n{result.summary()}")
        assert result.status_code == 201, (
            f"POST /Patient failed with {result.status_code}"
        )
        assert result.passed_sla, (
            f"PERFORMANCE REGRESSION: POST /Patient took "
            f"{result.duration_ms:.0f}ms — exceeds {result.sla_limit_ms}ms SLA."
        )

    def test_read_patient_within_sla(self) -> None:
        """GET /Patient/{id} must respond within 2000ms."""
        # First create a patient to read
        creator = FhirPerformanceChecker()
        create_result = creator.measure_create_patient()
        assert create_result.status_code == 201

        import httpx
        response = httpx.post(
            "http://hapi.fhir.org/baseR4/Patient",
            json={
                "resourceType": "Patient",
                "name": [{"use": "official", "family": "ReadPerfTest"}],
                "gender": "unknown",
            },
            headers={"Content-Type": "application/fhir+json"},
            timeout=5.0,
        )
        assert response.status_code == 201
        patient_id = response.json().get("id")

        checker = FhirPerformanceChecker(sla=FhirSLA(read_ms=2000))
        result  = checker.measure_read_patient(patient_id)

        print(f"\n{result.summary()}")
        assert result.status_code == 200
        assert result.passed_sla, (
            f"PERFORMANCE REGRESSION: GET /Patient took "
            f"{result.duration_ms:.0f}ms — exceeds {result.sla_limit_ms}ms SLA."
        )

    def test_performance_sla_configuration(self) -> None:
        """Verify SLA thresholds — no HTTP calls."""
        sla = FhirSLA()
        assert sla.create_ms == 3000
        assert sla.read_ms   == 2000
        assert sla.delete_ms == 2000
        assert sla.p95_ms    == 5000
        assert sla.error_rate_pct == 1.0
