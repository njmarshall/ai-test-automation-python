"""
fhir_load_test.py
-----------------
Pytest-safe performance baseline for the FHIR Patient API.

Deliberately has no dependency on `locust` — importing locust
monkey-patches socket/select/threading process-wide via gevent,
which hangs pytest collection. The Locust load test definitions
live in fhir_locustfile.py instead.

What is performance testing?
-----------------------------
Your existing tests validate correctness:
  "Does POST /Patient return 201 with the right fields?"

Performance tests validate behavior under load:
  "Does POST /Patient return 201 within 3 seconds
   when 10 users hit it simultaneously?"

The difference matters in healthcare:
  A FHIR API that works correctly for 1 user may degrade
  or fail entirely under realistic clinical load.
  Catching this in CI prevents production surprises.

Real-world context
------------------
At Indeed, background pipelines that worked fine in isolation
degraded significantly under concurrent load. Per-stage timing
and load baselines caught regressions before they reached users.

Usage
-----
    # Run Locust web UI or headless load test
    # (see fhir_locustfile.py for the Locust user definitions)
    locust -f shared/performance/fhir_locustfile.py \
        --headless \
        --users 10 \
        --spawn-rate 2 \
        --run-time 30s \
        --host https://hapi.fhir.org/baseR4

    # Run pytest performance assertions
    pytest projects/healthcare_fhir/api/tests/test_performance_baseline.py -v

SLA Thresholds (FHIR R4 HAPI sandbox)
--------------------------------------
  POST /Patient  — create    < 3000ms
  GET  /Patient  — read      < 2000ms
  DELETE         — delete    < 2000ms
  95th percentile response   < 5000ms
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from typing import List, Optional


# ------------------------------------------------------------------ #
#  SLA Thresholds                                                      #
# ------------------------------------------------------------------ #

@dataclass
class FhirSLA:
    """
    Service Level Agreement thresholds for FHIR Patient API.

    These are the performance contracts the API must honour.
    Exceeding these thresholds triggers a performance regression alert.
    """
    create_ms:      int = 3000  # POST /Patient
    read_ms:        int = 2000  # GET  /Patient/{id}
    delete_ms:      int = 2000  # DELETE /Patient/{id}
    p95_ms:         int = 5000  # 95th percentile across all requests
    error_rate_pct: float = 1.0  # max 1% error rate


# ------------------------------------------------------------------ #
#  Performance result                                                  #
# ------------------------------------------------------------------ #

@dataclass
class PerformanceResult:
    """Result of a single performance measurement."""
    operation:   str
    duration_ms: float
    status_code: int
    passed_sla:  bool
    sla_limit_ms: int

    def summary(self) -> str:
        status = "PASS" if self.passed_sla else "FAIL"
        return (
            f"{status} | {self.operation} | "
            f"{self.duration_ms:.0f}ms / {self.sla_limit_ms}ms SLA | "
            f"HTTP {self.status_code}"
        )


# ------------------------------------------------------------------ #
#  Lightweight performance checker (no Locust required)               #
# ------------------------------------------------------------------ #

class FhirPerformanceChecker:
    """
    Lightweight performance checker using httpx directly.

    Used by pytest tests so performance assertions run in CI
    without requiring a full Locust installation.

    Example
    -------
        checker = FhirPerformanceChecker(base_url="https://hapi.fhir.org/baseR4")
        result = checker.measure_create_patient()
        assert result.passed_sla, result.summary()
    """

    def __init__(
        self,
        base_url: str = "https://hapi.fhir.org/baseR4",
        sla: Optional[FhirSLA] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.sla      = sla or FhirSLA()
        self._results: List[PerformanceResult] = []

    def _build_patient_payload(self) -> dict:
        """Build a minimal valid FHIR R4 Patient payload."""
        return {
            "resourceType": "Patient",
            "name": [{"use": "official", "family": f"PerfTest{random.randint(1000, 9999)}"}],
            "gender": "unknown",
        }

    def measure_create_patient(self) -> PerformanceResult:
        """Measure POST /Patient response time against SLA."""
        import httpx

        payload = self._build_patient_payload()
        start   = time.time()

        try:
            response = httpx.post(
                f"{self.base_url}/Patient",
                json=payload,
                headers={"Content-Type": "application/fhir+json"},
                timeout=5.0,
                follow_redirects=True,
            )
            duration_ms = (time.time() - start) * 1000
            result = PerformanceResult(
                operation="POST /Patient",
                duration_ms=duration_ms,
                status_code=response.status_code,
                passed_sla=duration_ms <= self.sla.create_ms,
                sla_limit_ms=self.sla.create_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            result = PerformanceResult(
                operation="POST /Patient",
                duration_ms=duration_ms,
                status_code=0,
                passed_sla=False,
                sla_limit_ms=self.sla.create_ms,
            )

        self._results.append(result)
        return result

    def measure_read_patient(self, patient_id: str) -> PerformanceResult:
        """Measure GET /Patient/{id} response time against SLA."""
        import httpx

        start = time.time()
        try:
            response = httpx.get(
                f"{self.base_url}/Patient/{patient_id}",
                headers={"Accept": "application/fhir+json"},
                timeout=5.0,
                follow_redirects=True,
            )
            duration_ms = (time.time() - start) * 1000
            result = PerformanceResult(
                operation="GET /Patient/{id}",
                duration_ms=duration_ms,
                status_code=response.status_code,
                passed_sla=duration_ms <= self.sla.read_ms,
                sla_limit_ms=self.sla.read_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            result = PerformanceResult(
                operation="GET /Patient/{id}",
                duration_ms=duration_ms,
                status_code=0,
                passed_sla=False,
                sla_limit_ms=self.sla.read_ms,
            )

        self._results.append(result)
        return result

    def summary(self) -> str:
        """Return performance summary across all measurements."""
        if not self._results:
            return "No measurements recorded."

        passed = sum(1 for r in self._results if r.passed_sla)
        total  = len(self._results)
        durations = [r.duration_ms for r in self._results]
        avg_ms = sum(durations) / len(durations)

        lines = [
            f"Performance Summary",
            f"  Total measurements : {total}",
            f"  Passed SLA         : {passed}/{total}",
            f"  Average duration   : {avg_ms:.0f}ms",
            f"  Max duration       : {max(durations):.0f}ms",
            f"  Min duration       : {min(durations):.0f}ms",
        ]
        return "\n".join(lines)
