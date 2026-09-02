// shared/performance/k6/utils/fhir_helpers.js
// FHIR R4 helpers for correlation and parameterization

import { uuidv4 } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

export const BASE_URL = 'https://hapi.fhir.org/baseR4';

export const HEADERS = {
  'Content-Type': 'application/fhir+json',
  'Accept':       'application/fhir+json',
};

// ------------------------------------------------------------------ //
//  Parameterization — randomized FHIR payloads                        //
// ------------------------------------------------------------------ //

const FIRST_NAMES = ['Alice', 'Bob', 'Carol', 'David', 'Emma',
                     'Frank', 'Grace', 'Henry', 'Isabel', 'James'];
const LAST_NAMES  = ['Smith', 'Jones', 'Williams', 'Brown', 'Davis',
                     'Miller', 'Wilson', 'Moore', 'Taylor', 'Anderson'];
const GENDERS     = ['male', 'female', 'other', 'unknown'];

export function buildPatientPayload() {
  const firstName = FIRST_NAMES[Math.floor(Math.random() * FIRST_NAMES.length)];
  const lastName  = LAST_NAMES[Math.floor(Math.random() * LAST_NAMES.length)];
  const gender    = GENDERS[Math.floor(Math.random() * GENDERS.length)];
  const runId     = uuidv4();

  return JSON.stringify({
    resourceType: 'Patient',
    identifier: [{
      system: 'https://k6-perf-test.example.com',
      value:  `k6-${runId}`,          // unique per request — avoids 412 duplicates
    }],
    name: [{
      use:    'official',
      family: lastName,
      given:  [firstName],
    }],
    gender:    gender,
    birthDate: '1990-01-01',
  });
}

// ------------------------------------------------------------------ //
//  Correlation — extract IDs from responses                           //
// ------------------------------------------------------------------ //

export function extractPatientId(response) {
  try {
    const body = JSON.parse(response.body);
    return body.id || null;
  } catch {
    return null;
  }
}

export function isValidFhirResponse(response, expectedStatus) {
  if (response.status !== expectedStatus) return false;
  try {
    const body = JSON.parse(response.body);
    return body.resourceType !== undefined;
  } catch {
    return false;
  }
}

// ------------------------------------------------------------------ //
//  Check functions for k6 assertions                                  //
// ------------------------------------------------------------------ //

export const fhirChecks = {
  createPatient: (r) => ({
    'POST /Patient status 201':      r.status === 201,
    'POST /Patient has resourceType': JSON.parse(r.body || '{}').resourceType === 'Patient',
    'POST /Patient has id':           JSON.parse(r.body || '{}').id !== undefined,
    'POST /Patient duration < 3000ms': r.timings.duration < 3000,
  }),

  readPatient: (r) => ({
    'GET /Patient status 200':        r.status === 200,
    'GET /Patient has resourceType':  JSON.parse(r.body || '{}').resourceType === 'Patient',
    'GET /Patient duration < 2000ms': r.timings.duration < 2000,
  }),

  deletePatient: (r) => ({
    'DELETE /Patient status 200':     r.status === 200,
    'DELETE /Patient duration < 2000ms': r.timings.duration < 2000,
  }),
};
