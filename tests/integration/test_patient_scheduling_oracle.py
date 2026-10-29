"""
test_patient_scheduling_oracle.py

Patient journey oracle: appointment scheduling workflow.
Article 16 — AI Test Automation Series
"The Appointment Was Confirmed. The Patient Still Couldn't Come."

What this test verifies
------------------------
A patient who requests an appointment with an eligible slot:
  1. Receives a confirmed booking (not just an HTTP 200).
  2. Can see the confirmation on the scheduling surface they use.
  3. The provider availability service reflects the slot as taken.
  4. The patient notification service records that a reminder was queued.

Why this is different from Article 15 (prior authorization)
------------------------------------------------------------
Article 15 verified a business state (APPROVED) that appeared after
asynchronous adjudication. The oracle polled until the state appeared.

Article 16 verifies a *patient-outcome* state that spans four services:
  - Scheduling service     — creates the booking
  - Availability service   — marks the slot as taken
  - Notification service   — queues a reminder
  - Scheduling surface     — shows the patient their confirmation

All four must agree. Any one failing means the patient either shows up
to an appointment that isn't in the system, or misses one they thought
was booked. The customer-impact assertion is the oracle.

Design principles
-----------------
  Outside-in:  drives through supported surfaces, not database tables.
  Bounded wait: uses time.monotonic() — immune to system clock changes.
  Self-contained: all three microservices run as FastAPI sandboxes in
                  the same process, no external staging environment needed.
  CI safe:     no secrets, no external network calls, runs in 3–4 seconds.

Run locally
-----------
    pytest tests/integration/test_patient_scheduling_oracle.py -v

Run in CI
---------
    pytest tests/integration/test_patient_scheduling_oracle.py \\
        --junitxml=reports/scheduling-oracle-tests.xml -v
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import pytest
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

# ── ports (avoid collision with payments sandbox on 8001-8003) ─────────────
_SCHEDULING_PORT   = 8020
_AVAILABILITY_PORT = 8021
_NOTIFICATION_PORT = 8022

TIMEOUT = (2, 10)   # (connect, read) seconds per request


# ═══════════════════════════════════════════════════════════════════════════ #
#  Sandbox microservices                                                      #
# ═══════════════════════════════════════════════════════════════════════════ #

# ── Scheduling service ────────────────────────────────────────────────────

scheduling_state: Dict[str, Any] = {}   # booking_id → booking dict

scheduling_app = FastAPI(title="Scheduling Sandbox")


@scheduling_app.post("/bookings")
def create_booking(payload: dict):
    """
    Accept a booking request.  Returns 202 Accepted — the booking is
    pending until the availability service confirms the slot.
    """
    booking_id = f"BK-{uuid.uuid4().hex[:8].upper()}"
    booking = {
        "booking_id": booking_id,
        "patient_id":  payload.get("patient_id"),
        "provider_id": payload.get("provider_id"),
        "slot_id":     payload.get("slot_id"),
        "procedure":   payload.get("procedure"),
        "status":      "CONFIRMED",          # sandbox: immediately confirmed
        "booked_at":   datetime.now(timezone.utc).isoformat(),
    }
    scheduling_state[booking_id] = booking
    return JSONResponse(content=booking, status_code=202)


@scheduling_app.get("/bookings/{booking_id}")
def get_booking(booking_id: str):
    booking = scheduling_state.get(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@scheduling_app.post("/reset")
def reset_scheduling():
    scheduling_state.clear()
    return {"reset": True}


# ── Availability service ───────────────────────────────────────────────────

availability_state: Dict[str, Dict] = {}   # slot_id → {available, booking_id}

availability_app = FastAPI(title="Availability Sandbox")

# Pre-seed one open slot
_OPEN_SLOT = "SLOT-2026-11-05-0900"
availability_state[_OPEN_SLOT] = {"available": True, "booking_id": None}


@availability_app.get("/slots/{slot_id}")
def get_slot(slot_id: str):
    slot = availability_state.get(slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    return {"slot_id": slot_id, **slot}


@availability_app.post("/slots/{slot_id}/reserve")
def reserve_slot(slot_id: str, payload: dict):
    """Mark a slot as taken by a booking."""
    slot = availability_state.get(slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    if not slot["available"]:
        raise HTTPException(status_code=409, detail="Slot already reserved")
    availability_state[slot_id] = {
        "available": False,
        "booking_id": payload.get("booking_id"),
    }
    return {"slot_id": slot_id, "reserved": True, "booking_id": payload.get("booking_id")}


@availability_app.post("/reset")
def reset_availability():
    availability_state.clear()
    availability_state[_OPEN_SLOT] = {"available": True, "booking_id": None}
    return {"reset": True}


# ── Notification service ───────────────────────────────────────────────────

notification_log: List[Dict] = []

notification_app = FastAPI(title="Notification Sandbox")


@notification_app.post("/reminders")
def queue_reminder(payload: dict):
    """Record that a reminder was queued for a patient."""
    record = {
        "reminder_id":  f"REM-{uuid.uuid4().hex[:8].upper()}",
        "patient_id":   payload.get("patient_id"),
        "booking_id":   payload.get("booking_id"),
        "channel":      payload.get("channel", "sms"),
        "queued_at":    datetime.now(timezone.utc).isoformat(),
    }
    notification_log.append(record)
    return {"status": "queued", **record}


@notification_app.get("/reminders")
def list_reminders(patient_id: Optional[str] = None):
    if patient_id:
        return [r for r in notification_log if r["patient_id"] == patient_id]
    return notification_log


@notification_app.post("/reset")
def reset_notifications():
    notification_log.clear()
    return {"reset": True}


# ═══════════════════════════════════════════════════════════════════════════ #
#  Fixtures                                                                   #
# ═══════════════════════════════════════════════════════════════════════════ #

def _start_server(app_instance, port: int) -> None:
    """Launch a uvicorn server in a daemon thread."""
    import uvicorn
    config = uvicorn.Config(app_instance, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    server.run()


@pytest.fixture(scope="module")
def sandbox_servers():
    """Start all three sandbox microservices once for the module."""
    for app_instance, port in [
        (scheduling_app,   _SCHEDULING_PORT),
        (availability_app, _AVAILABILITY_PORT),
        (notification_app, _NOTIFICATION_PORT),
    ]:
        t = threading.Thread(target=_start_server, args=(app_instance, port), daemon=True)
        t.start()
    time.sleep(0.8)   # allow all three servers to bind
    yield


@pytest.fixture
def clean_state(sandbox_servers):
    """Reset all three sandboxes before each test."""
    requests.post(f"http://127.0.0.1:{_SCHEDULING_PORT}/reset",   timeout=TIMEOUT)
    requests.post(f"http://127.0.0.1:{_AVAILABILITY_PORT}/reset",  timeout=TIMEOUT)
    requests.post(f"http://127.0.0.1:{_NOTIFICATION_PORT}/reset",  timeout=TIMEOUT)
    yield


@dataclass
class SchedulingClient:
    """Thin client for the three scheduling microservices."""
    scheduling_url:   str = f"http://127.0.0.1:{_SCHEDULING_PORT}"
    availability_url: str = f"http://127.0.0.1:{_AVAILABILITY_PORT}"
    notification_url: str = f"http://127.0.0.1:{_NOTIFICATION_PORT}"

    def book(self, patient_id: str, provider_id: str, slot_id: str,
             procedure: str) -> requests.Response:
        return requests.post(
            f"{self.scheduling_url}/bookings",
            json={"patient_id": patient_id, "provider_id": provider_id,
                  "slot_id": slot_id, "procedure": procedure},
            timeout=TIMEOUT,
        )

    def get_booking(self, booking_id: str) -> requests.Response:
        return requests.get(
            f"{self.scheduling_url}/bookings/{booking_id}", timeout=TIMEOUT
        )

    def reserve_slot(self, slot_id: str, booking_id: str) -> requests.Response:
        return requests.post(
            f"{self.availability_url}/slots/{slot_id}/reserve",
            json={"booking_id": booking_id},
            timeout=TIMEOUT,
        )

    def get_slot(self, slot_id: str) -> requests.Response:
        return requests.get(
            f"{self.availability_url}/slots/{slot_id}", timeout=TIMEOUT
        )

    def queue_reminder(self, patient_id: str, booking_id: str,
                       channel: str = "sms") -> requests.Response:
        return requests.post(
            f"{self.notification_url}/reminders",
            json={"patient_id": patient_id, "booking_id": booking_id,
                  "channel": channel},
            timeout=TIMEOUT,
        )

    def get_reminders(self, patient_id: str) -> requests.Response:
        return requests.get(
            f"{self.notification_url}/reminders",
            params={"patient_id": patient_id},
            timeout=TIMEOUT,
        )


@pytest.fixture
def client(clean_state) -> SchedulingClient:
    return SchedulingClient()


# ═══════════════════════════════════════════════════════════════════════════ #
#  Tests                                                                      #
# ═══════════════════════════════════════════════════════════════════════════ #

PATIENT_ID  = "TEST-PAT-SCHED-001"
PROVIDER_ID = "PROVIDER-DR-CHEN"
SLOT_ID     = _OPEN_SLOT       # "SLOT-2026-11-05-0900"
PROCEDURE   = "annual-wellness-visit"


class TestPatientSchedulingOracle:
    """
    Patient journey oracle: appointment scheduling.

    Each test asserts a patient-facing outcome, not an individual
    service response code.  The oracle question is always:
    "Can the patient actually come to this appointment?"
    """

    def test_patient_receives_confirmed_booking(self, client: SchedulingClient):
        """
        Customer outcome: A patient who submits a valid booking request
        receives a CONFIRMED booking ID they can reference.

        Oracle: booking status == CONFIRMED, booking_id present.
        Failure impact: Patient has no reference number; cannot verify
        or modify appointment; must call to confirm manually.
        """
        response = client.book(PATIENT_ID, PROVIDER_ID, SLOT_ID, PROCEDURE)

        assert response.status_code == 202, (
            f"Expected 202 Accepted for async booking, got {response.status_code}. "
            f"Patient received no booking acknowledgement."
        )
        payload = response.json()
        assert "booking_id" in payload, (
            "Response missing booking_id. "
            "Patient cannot track or reference their appointment."
        )
        assert payload["status"] == "CONFIRMED", (
            f"Booking status is '{payload.get('status')}', expected CONFIRMED. "
            f"Patient does not know if their appointment is accepted."
        )
        assert payload["patient_id"] == PATIENT_ID, (
            f"Booking patient_id mismatch: got {payload.get('patient_id')}. "
            f"Appointment may be attributed to the wrong patient."
        )

    def test_scheduling_surface_shows_booking(self, client: SchedulingClient):
        """
        Customer outcome: After booking, the patient can retrieve their
        appointment details through the scheduling surface.

        Oracle: GET /bookings/{id} returns the confirmed booking.
        Failure impact: Booking exists in the system but patient cannot
        verify it — they will call the office or book again (double-booking).
        """
        book_resp = client.book(PATIENT_ID, PROVIDER_ID, SLOT_ID, PROCEDURE)
        booking_id = book_resp.json()["booking_id"]

        retrieve = client.get_booking(booking_id)

        assert retrieve.status_code == 200, (
            f"Could not retrieve booking {booking_id}: status {retrieve.status_code}. "
            f"Patient cannot confirm their appointment through the scheduling surface."
        )
        payload = retrieve.json()
        assert payload["slot_id"] == SLOT_ID, (
            f"Retrieved booking has wrong slot: {payload.get('slot_id')}. "
            f"Patient may show up at wrong time or location."
        )

    def test_availability_reflects_slot_as_taken(self, client: SchedulingClient):
        """
        Customer outcome: After a booking is confirmed, the slot is no
        longer available to other patients.

        Oracle: slot.available == False in the availability service.
        Failure impact: Two patients are booked for the same slot.
        One of them will be turned away.  This is the classic
        double-booking scenario — the appointment was confirmed but
        the patient still couldn't come.
        """
        book_resp = client.book(PATIENT_ID, PROVIDER_ID, SLOT_ID, PROCEDURE)
        booking_id = book_resp.json()["booking_id"]

        # In a real system the scheduling service would call the
        # availability service automatically.  Here we call it
        # explicitly to test the contract between the two services.
        reserve_resp = client.reserve_slot(SLOT_ID, booking_id)
        assert reserve_resp.status_code == 200, (
            f"Availability service failed to reserve slot: {reserve_resp.status_code}. "
            f"Double-booking is now possible."
        )

        slot_resp = client.get_slot(SLOT_ID)
        slot = slot_resp.json()

        assert slot["available"] is False, (
            f"Slot {SLOT_ID} is still marked available after booking {booking_id}. "
            f"Another patient can book the same slot — one will be turned away."
        )
        assert slot["booking_id"] == booking_id, (
            f"Slot references booking {slot.get('booking_id')}, expected {booking_id}. "
            f"Slot ownership record is inconsistent."
        )

    def test_notification_service_queues_reminder(self, client: SchedulingClient):
        """
        Customer outcome: After a confirmed booking, the patient receives
        a reminder through their preferred channel.

        Oracle: notification service has ≥1 reminder queued for this patient.
        Failure impact: Patient forgets the appointment (no reminder),
        shows up late or not at all — avoidable no-show.
        """
        book_resp = client.book(PATIENT_ID, PROVIDER_ID, SLOT_ID, PROCEDURE)
        booking_id = book_resp.json()["booking_id"]

        reminder_resp = client.queue_reminder(PATIENT_ID, booking_id, channel="sms")
        assert reminder_resp.status_code == 200, (
            f"Notification service rejected reminder request: {reminder_resp.status_code}. "
            f"Patient will not receive an appointment reminder."
        )

        reminders_resp = client.get_reminders(PATIENT_ID)
        reminders = reminders_resp.json()

        patient_reminders = [r for r in reminders if r["booking_id"] == booking_id]
        assert len(patient_reminders) >= 1, (
            f"No reminder found for booking {booking_id} in notification log. "
            f"Patient will not be reminded of their appointment."
        )
        assert patient_reminders[0]["channel"] == "sms", (
            f"Reminder channel is '{patient_reminders[0].get('channel')}', expected 'sms'. "
            f"Patient may not receive notification on their preferred channel."
        )

    def test_double_booking_is_rejected(self, client: SchedulingClient):
        """
        Customer outcome: A slot that has already been reserved cannot
        be booked by a second patient.

        Oracle: second reserve call returns 409 Conflict.
        Failure impact: Without this guard the availability oracle in
        test_availability_reflects_slot_as_taken passes but two patients
        are still booked — the system accepted both.
        """
        # First booking — should succeed
        book_resp = client.book(PATIENT_ID, PROVIDER_ID, SLOT_ID, PROCEDURE)
        booking_id = book_resp.json()["booking_id"]
        client.reserve_slot(SLOT_ID, booking_id)

        # Second patient tries to reserve the same slot
        second_booking_id = f"BK-SECOND-{uuid.uuid4().hex[:6].upper()}"
        conflict_resp = client.reserve_slot(SLOT_ID, second_booking_id)

        assert conflict_resp.status_code == 409, (
            f"Expected 409 Conflict for double-booking, got {conflict_resp.status_code}. "
            f"Two patients are now booked for slot {SLOT_ID} — one will be turned away."
        )

    def test_full_scheduling_journey(self, client: SchedulingClient):
        """
        End-to-end customer journey oracle.

        Actor:          patient with an eligible slot
        Goal:           confirmed appointment with reminder queued and
                        slot marked unavailable for others
        Terminal state: booking CONFIRMED, slot reserved, reminder queued
        Time budget:    3 seconds (all services local, no I/O)
        Unacceptable:   any one of the four services disagrees about
                        the patient's appointment state

        This is the oracle test. The others verify individual service
        contracts; this one verifies that all four agree.
        """
        deadline = time.monotonic() + 3.0

        # ── 1. Book appointment ────────────────────────────────────────────
        book_resp = client.book(PATIENT_ID, PROVIDER_ID, SLOT_ID, PROCEDURE)
        assert book_resp.status_code == 202, (
            f"Booking failed: {book_resp.status_code}. "
            f"Journey cannot begin — patient received no booking."
        )
        booking_id = book_resp.json()["booking_id"]

        # ── 2. Verify scheduling surface ───────────────────────────────────
        surface_resp = client.get_booking(booking_id)
        assert surface_resp.status_code == 200, (
            f"Booking {booking_id} not found on scheduling surface. "
            f"Patient cannot confirm their appointment."
        )
        assert surface_resp.json()["status"] == "CONFIRMED", (
            f"Scheduling surface shows '{surface_resp.json().get('status')}'. "
            f"Patient does not see a confirmed appointment."
        )

        # ── 3. Reserve slot in availability service ────────────────────────
        reserve_resp = client.reserve_slot(SLOT_ID, booking_id)
        assert reserve_resp.status_code == 200, (
            f"Availability service rejected slot reservation. "
            f"Double-booking is possible."
        )
        slot = client.get_slot(SLOT_ID).json()
        assert slot["available"] is False, (
            f"Slot still available after booking. "
            f"Another patient can claim the same appointment."
        )

        # ── 4. Queue reminder ──────────────────────────────────────────────
        client.queue_reminder(PATIENT_ID, booking_id)
        reminders = client.get_reminders(PATIENT_ID).json()
        assert any(r["booking_id"] == booking_id for r in reminders), (
            f"No reminder queued for booking {booking_id}. "
            f"Patient will not be reminded — avoidable no-show."
        )

        # ── 5. Assert all four services agreed within the time budget ──────
        assert time.monotonic() < deadline, (
            "Scheduling journey exceeded 3-second budget. "
            "At least one service was too slow for a responsive booking flow."
        )
