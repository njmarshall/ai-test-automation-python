// shared/performance/k6/endurance.js
// Phase 4 — Endurance: sustained load to detect memory leaks and degradation
//
// Purpose: Run at moderate load for an extended period to detect:
//   - Memory leaks (response times increase over time)
//   - Connection pool exhaustion
//   - Gradual performance degradation
//   - Resource cleanup failures
//
// Real-world context:
//   At HEAVY.AI, GPU cluster HA testing required endurance runs to
//   detect memory pressure that only appeared after sustained load.
//   Short tests would pass; 30-minute runs would reveal the leak.
//
// Run:
//   k6 run shared/performance/k6/endurance.js
//
// Note: Full endurance run is 30 minutes. For CI use --duration 5m

import http    from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate, Gauge } from 'k6/metrics';

import { BASE_URL, HEADERS, buildPatientPayload,
         extractPatientId, fhirChecks } from './utils/fhir_helpers.js';
import { ENDURANCE_THRESHOLDS } from './utils/thresholds.js';

const createDuration  = new Trend('fhir_create_duration', true);
const errorRate       = new Rate('fhir_error_rate');
const activePatients  = new Gauge('fhir_active_patients');

let createdIds = [];

export const options = {
  // Phase 4 — Endurance: moderate load for extended period
  stages: [
    { duration: '2m',  target: 20 },  // ramp up
    { duration: '25m', target: 20 },  // sustained load
    { duration: '3m',  target: 0  },  // ramp down
  ],

  thresholds: {
    ...ENDURANCE_THRESHOLDS,
    fhir_create_duration: ['p(95)<5000'],
    fhir_error_rate:      ['rate<0.01'],
  },
};

export default function () {
  // CREATE
  const createRes = http.post(
    `${BASE_URL}/Patient`,
    buildPatientPayload(),
    { headers: HEADERS },
  );

  createDuration.add(createRes.timings.duration);
  const createOk = check(createRes, fhirChecks.createPatient(createRes));
  errorRate.add(!createOk);

  const patientId = extractPatientId(createRes);
  if (patientId) {
    createdIds.push(patientId);
    activePatients.add(createdIds.length);
  }

  // READ every other iteration
  if (createdIds.length > 0 && Math.random() > 0.5) {
    const readId  = createdIds[Math.floor(Math.random() * createdIds.length)];
    const readRes = http.get(
      `${BASE_URL}/Patient/${readId}`,
      { headers: HEADERS },
    );
    check(readRes, fhirChecks.readPatient(readRes));
  }

  // CLEANUP — delete oldest patients to avoid sandbox pollution
  if (createdIds.length > 10) {
    const oldId = createdIds.shift();
    http.del(`${BASE_URL}/Patient/${oldId}`, null, { headers: HEADERS });
    activePatients.add(createdIds.length);
  }

  sleep(2);
}

export function teardown() {
  // Cleanup remaining patients
  console.log(`Cleaning up ${createdIds.length} remaining patients...`);
  for (const id of createdIds) {
    http.del(`${BASE_URL}/Patient/${id}`, null, { headers: HEADERS });
  }
}
