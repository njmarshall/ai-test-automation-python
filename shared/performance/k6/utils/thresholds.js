// shared/performance/k6/utils/thresholds.js
// Shared SLA thresholds for all k6 test phases

export const FHIR_THRESHOLDS = {
  // Response time SLAs
  http_req_duration: [
    'p(95)<5000',  // 95th percentile under 5 seconds
    'p(99)<8000',  // 99th percentile under 8 seconds
    'avg<3000',    // average under 3 seconds
  ],
  // Error rate SLA
  http_req_failed: ['rate<0.01'],  // less than 1% errors
  // Request rate
  http_reqs: ['rate>1'],           // at least 1 request per second
};

export const BASELINE_THRESHOLDS = {
  http_req_duration: [
    'p(95)<3000',
    'avg<2000',
  ],
  http_req_failed: ['rate<0.01'],
};

export const LOAD_THRESHOLDS = {
  http_req_duration: [
    'p(95)<5000',
    'avg<3000',
  ],
  http_req_failed: ['rate<0.02'],
};

export const STRESS_THRESHOLDS = {
  http_req_duration: [
    'p(95)<8000',
    'avg<5000',
  ],
  http_req_failed: ['rate<0.05'],  // allow up to 5% under stress
};

export const ENDURANCE_THRESHOLDS = {
  http_req_duration: [
    'p(95)<5000',
    'avg<3000',
  ],
  http_req_failed: ['rate<0.01'],
};
