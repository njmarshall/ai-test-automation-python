"""
fhir_locustfile.py
-------------------
Locust load test definitions for the FHIR Patient API.

Kept separate from fhir_load_test.py because importing `locust`
triggers gevent's process-wide monkey-patching of socket/select/
threading. That's fine for a standalone `locust -f ...` run, but
it corrupts pytest's own use of those primitives (event loops,
capture, xdist, etc.) and hangs collection if pulled in via a
pytest test module. Only pytest-safe classes (FhirPerformanceChecker,
FhirSLA) belong in fhir_load_test.py.

Usage
-----
    locust -f shared/performance/fhir_locustfile.py \
        --headless \
        --users 10 \
        --spawn-rate 2 \
        --run-time 30s \
        --host http://hapi.fhir.org/baseR4
"""

from __future__ import annotations

import random
from typing import List

from locust import HttpUser, between, task


class FhirPatientUser(HttpUser):
    """
    Locust user that simulates a clinical application
    creating, reading, and deleting FHIR Patient resources.

    Wait between 1-3 seconds between tasks to simulate
    realistic clinical workflow pacing.

    Run with:
        locust -f shared/performance/fhir_locustfile.py \
            --headless --users 10 --spawn-rate 2 \
            --run-time 30s \
            --host http://hapi.fhir.org/baseR4
    """

    wait_time = between(1, 3)
    _created_ids: List[str] = []

    def _patient_payload(self) -> dict:
        return {
            "resourceType": "Patient",
            "name": [{"use": "official", "family": f"LocustTest{random.randint(1000, 9999)}"}],
            "gender": "unknown",
        }

    @task(3)
    def create_patient(self) -> None:
        """Weighted 3x — most common clinical operation."""
        with self.client.post(
            "/Patient",
            json=self._patient_payload(),
            headers={"Content-Type": "application/fhir+json"},
            name="POST /Patient",
            catch_response=True,
        ) as response:
            if response.status_code == 201:
                patient_id = response.json().get("id")
                if patient_id:
                    self._created_ids.append(patient_id)
                response.success()
            else:
                response.failure(
                    f"Expected 201, got {response.status_code}"
                )

    @task(2)
    def read_patient(self) -> None:
        """Weighted 2x — common read operation."""
        if not self._created_ids:
            return
        patient_id = random.choice(self._created_ids)
        with self.client.get(
            f"/Patient/{patient_id}",
            headers={"Accept": "application/fhir+json"},
            name="GET /Patient/{id}",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(
                    f"Expected 200, got {response.status_code}"
                )

    @task(1)
    def delete_patient(self) -> None:
        """Weighted 1x — less common cleanup operation."""
        if not self._created_ids:
            return
        patient_id = self._created_ids.pop(0)
        with self.client.delete(
            f"/Patient/{patient_id}",
            name="DELETE /Patient/{id}",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 204):
                response.success()
            else:
                response.failure(
                    f"Expected 200/204, got {response.status_code}"
                )
