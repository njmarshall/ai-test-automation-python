// shared/performance/k6/stress.js
// Phase 3 — Stress: ramp beyond normal load to find breaking point
//
// Purpose: Find where the FHIR API starts to degrade.
//          Unlike load testing, stress testing EXPECTS some failures.
//          The goal is to understand system limits, not prove stability.
//
// Real-world context:
//   At Indeed, we stress-tested the job alert pipeline to understand
//   how many concurrent subscriptions the system could handle before
//   daemon queues started backing up. Same principle applies here.
//
// Run:
//   k6 run shared/performance/k6/stress.js

import http    from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';

import { BASE_URL, HEADERS, buildPatientPayload,
         extractPatientId, fhirChecks } from './utils/fhir_helpers.js';
import { STRESS_THRESHOLDS } from './utils/thresholds.js';

const createDuration = new Trend('fhir_create_duration', true);
const errorRate      = new Rate('fhir_error_rate');

export const options = {
  // Phase 3 — Stress: push beyond normal limits
  stages: [
    { duration: '30s', target: 50  },  // normal load
    { duration: '1m',  target: 100 },  // above normal
    { duration: '1m',  target: 200 },  // stress load
    { duration: '30s', target: 0   },  // recovery
  ],

  thresholds: {
    ...STRESS_THRESHOLDS,
    fhir_create_duration: ['p(95)<8000'],
    fhir_error_rate:      ['rate<0.05'],  // allow up to 5% errors under stress
  },
};

export default function () {
  const createRes = http.post(
    `${BASE_URL}/Patient`,
    buildPatientPayload(),
    { headers: HEADERS },
  );

  createDuration.add(createRes.timings.duration);
  const createOk = check(createRes, {
    'status is 201 or 429 or 503': (r) =>
      r.status === 201 || r.status === 429 || r.status === 503,
  });
  errorRate.add(createRes.status >= 500);

  const patientId = extractPatientId(createRes);
  if (patientId) {
    http.del(`${BASE_URL}/Patient/${patientId}`, null, { headers: HEADERS });
  }

  sleep(0.5);
}
