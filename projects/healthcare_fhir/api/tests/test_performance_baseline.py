"""
test_performance_baseline.py
-----------------------------
Performance baseline tests for the FHIR Patient API.

These tests validate response time SLAs without requiring
a full Locust installation — they run in CI automatically.

The SLA thresholds are conservative for the HAPI FHIR
public sandbox, which is shared infrastructure. Production
FHIR systems would have tighter thresholds.

SLA Thresholds
--------------
  POST /Patient  < 3000ms
  GET  /Patient  < 2000ms
  DELETE         < 2000ms
"""

from __future__ import annotations

import pytest

from projects.healthcare_fhir.api.client.fhir_client import FhirClient
from projects.healthcare_fhir.api.data.fhir_factory import FhirFactory
from shared.performance.fhir_load_test import FhirPerformanceChecker, FhirSLA


@pytest.mark.healthcare
@pytest.mark.performance
class TestFhirPerformanceBaseline:
    """
    Performance baseline tests for FHIR Patient API.

    Validates that response times stay within SLA thresholds.
    A failing test here means the API is degrading — investigate
    before the slowdown reaches production clinical systems.
    """

    def test_create_patient_within_sla(
        self, fhir_client: FhirClient
    ) -> None:
        """
        POST /Patient must respond within 3000ms.

        In a clinical workflow, patient registration latency
        directly impacts staff productivity and patient wait times.
        """
        checker = FhirPerformanceChecker(sla=FhirSLA(create_ms=3000))
        result  = checker.measure_create_patient()

        print(f"\n{result.summary()}")
        assert result.status_code == 201, (
            f"POST /Patient failed with {result.status_code}"
        )
        assert result.passed_sla, (
            f"PERFORMANCE REGRESSION: POST /Patient took {result.duration_ms:.0f}ms "
            f"— exceeds {result.sla_limit_ms}ms SLA. Investigate before deployment."
        )

    def test_read_patient_within_sla(
        self, fhir_client: FhirClient, created_patient_id: str
    ) -> None:
        """
        GET /Patient/{id} must respond within 2000ms.

        Clinical staff reading patient records expect
        near-instant response. Latency above 2 seconds
        indicates infrastructure degradation.
        """
        checker = FhirPerformanceChecker(sla=FhirSLA(read_ms=2000))
        result  = checker.measure_read_patient(created_patient_id)

        print(f"\n{result.summary()}")
        assert result.status_code == 200, (
            f"GET /Patient failed with {result.status_code}"
        )
        assert result.passed_sla, (
            f"PERFORMANCE REGRESSION: GET /Patient took {result.duration_ms:.0f}ms "
            f"— exceeds {result.sla_limit_ms}ms SLA."
        )

    def test_create_and_read_performance_summary(
        self, fhir_client: FhirClient
    ) -> None:
        """
        Run create + read cycle and print performance summary.

        Gives a complete picture of FHIR API responsiveness
        across the most common clinical workflow.
        """
        checker = FhirPerformanceChecker()

        # Create
        create_result = checker.measure_create_patient()
        assert create_result.status_code == 201

        # Read the created patient
        patient_id = None
        import httpx
        response = httpx.post(
            "http://hapi.fhir.org/baseR4/Patient",
            json={
                "resourceType": "Patient",
                "name": [{"use": "official", "family": "SummaryTest"}],
                "gender": "unknown",
            },
            headers={"Content-Type": "application/fhir+json"},
            timeout=10.0,
        )
        if response.status_code == 201:
            patient_id = response.json().get("id")

        if patient_id:
            read_result = checker.measure_read_patient(patient_id)
            assert read_result.status_code == 200

        print(f"\n{checker.summary()}")

    def test_performance_sla_configuration(self) -> None:
        """
        Verify SLA thresholds are correctly configured.
        Documents the performance contract for this domain.
        """
        sla = FhirSLA()

        assert sla.create_ms == 3000, "POST /Patient SLA should be 3000ms"
        assert sla.read_ms   == 2000, "GET /Patient SLA should be 2000ms"
        assert sla.delete_ms == 2000, "DELETE /Patient SLA should be 2000ms"
        assert sla.p95_ms    == 5000, "95th percentile SLA should be 5000ms"
        assert sla.error_rate_pct == 1.0, "Error rate SLA should be 1%"
