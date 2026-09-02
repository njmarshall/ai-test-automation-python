// shared/performance/k6/load.js
// Phase 2 — Load: ramp to 50 users, simulate normal clinical traffic
//
// Purpose: Validate the FHIR API behaves correctly under expected
//          production load. Uses ramping VUs to simulate realistic
//          user arrival patterns.
//
// Run:
//   k6 run shared/performance/k6/load.js

import http    from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

import { BASE_URL, HEADERS, buildPatientPayload,
         extractPatientId, fhirChecks } from './utils/fhir_helpers.js';
import { LOAD_THRESHOLDS } from './utils/thresholds.js';

const createDuration = new Trend('fhir_create_duration', true);
const readDuration   = new Trend('fhir_read_duration',   true);
const errorRate      = new Rate('fhir_error_rate');
const totalPatients  = new Counter('fhir_patients_created');

export const options = {
  // Phase 2 — Load: ramp up to 50 VUs over 2 minutes
  stages: [
    { duration: '30s', target: 10  },  // ramp up to 10 users
    { duration: '1m',  target: 50  },  // ramp to peak load
    { duration: '30s', target: 50  },  // hold at peak
    { duration: '30s', target: 0   },  // ramp down
  ],

  thresholds: {
    ...LOAD_THRESHOLDS,
    fhir_create_duration: ['p(95)<5000'],
    fhir_read_duration:   ['p(95)<3000'],
    fhir_error_rate:      ['rate<0.02'],
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

  if (!createOk) {
    sleep(1);
    return;
  }

  totalPatients.add(1);
  const patientId = extractPatientId(createRes);

  if (patientId) {
    // READ — simulate clinical staff viewing patient record
    const readRes = http.get(
      `${BASE_URL}/Patient/${patientId}`,
      { headers: HEADERS },
    );
    readDuration.add(readRes.timings.duration);
    check(readRes, fhirChecks.readPatient(readRes));

    // DELETE — cleanup to avoid sandbox pollution
    http.del(`${BASE_URL}/Patient/${patientId}`, null, { headers: HEADERS });
  }

  // Simulate clinical workflow pacing
  sleep(Math.random() * 2 + 1);
}
