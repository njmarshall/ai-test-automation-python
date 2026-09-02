// shared/performance/k6/baseline.js
// Phase 1 — Baseline: 1 user, verify SLAs under no load
//
// Purpose: Establish response time baselines before load testing.
//          If baseline fails, load and stress tests are meaningless.
//
// Run:
//   k6 run shared/performance/k6/baseline.js
//
// Expected: All SLAs pass at 1 virtual user

import http    from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';

import { BASE_URL, HEADERS, buildPatientPayload,
         extractPatientId, fhirChecks } from './utils/fhir_helpers.js';
import { BASELINE_THRESHOLDS } from './utils/thresholds.js';

// Custom metrics
const createDuration = new Trend('fhir_create_duration', true);
const readDuration   = new Trend('fhir_read_duration',   true);
const deleteDuration = new Trend('fhir_delete_duration', true);
const errorRate      = new Rate('fhir_error_rate');

export const options = {
  // Phase 1 — Baseline: single user, short duration
  vus:      1,
  duration: '30s',

  thresholds: {
    ...BASELINE_THRESHOLDS,
    fhir_create_duration: ['p(95)<3000'],
    fhir_read_duration:   ['p(95)<2000'],
    fhir_delete_duration: ['p(95)<2000'],
    fhir_error_rate:      ['rate<0.01'],
  },
};

export default function () {
  // ---------------------------------------------------------------- //
  //  Step 1 — CREATE Patient (with parameterized payload)             //
  // ---------------------------------------------------------------- //
  const createRes = http.post(
    `${BASE_URL}/Patient`,
    buildPatientPayload(),
    { headers: HEADERS },
  );

  createDuration.add(createRes.timings.duration);
  const createOk = check(createRes, fhirChecks.createPatient(createRes));
  errorRate.add(!createOk);

  if (!createOk) {
    console.error(`CREATE failed: ${createRes.status} — ${createRes.body?.substring(0, 200)}`);
    sleep(1);
    return;
  }

  // ---------------------------------------------------------------- //
  //  Step 2 — CORRELATE — extract patient ID for subsequent requests  //
  // ---------------------------------------------------------------- //
  const patientId = extractPatientId(createRes);
  if (!patientId) {
    console.error('Could not extract patient ID — skipping read and delete');
    sleep(1);
    return;
  }

  // ---------------------------------------------------------------- //
  //  Step 3 — READ Patient (using correlated ID)                      //
  // ---------------------------------------------------------------- //
  const readRes = http.get(
    `${BASE_URL}/Patient/${patientId}`,
    { headers: HEADERS },
  );

  readDuration.add(readRes.timings.duration);
  const readOk = check(readRes, fhirChecks.readPatient(readRes));
  errorRate.add(!readOk);

  // ---------------------------------------------------------------- //
  //  Step 4 — DELETE Patient (cleanup — avoids duplicate buildup)     //
  // ---------------------------------------------------------------- //
  const deleteRes = http.del(
    `${BASE_URL}/Patient/${patientId}`,
    null,
    { headers: HEADERS },
  );

  deleteDuration.add(deleteRes.timings.duration);
  check(deleteRes, fhirChecks.deletePatient(deleteRes));

  sleep(1);
}

export function handleSummary(data) {
  console.log('\n=== BASELINE SUMMARY ===');
  console.log(`Total requests    : ${data.metrics.http_reqs?.values?.count}`);
  console.log(`Avg duration      : ${data.metrics.http_req_duration?.values?.avg?.toFixed(0)}ms`);
  console.log(`p95 duration      : ${data.metrics.http_req_duration?.values['p(95)']?.toFixed(0)}ms`);
  console.log(`Error rate        : ${(data.metrics.http_req_failed?.values?.rate * 100)?.toFixed(2)}%`);
  console.log('========================\n');
}
