# Coverage Policy

**Date:** November 24, 2026 · **Plan item:** 12-month plan, Phase A (Q1 2027 roadmap, Month 1 item 5)

## The rule in one sentence

Every package under `shared/` has its own coverage floor, measured on the offline unit suite, and a floor may be raised but never lowered.

## Why per package, not one number

A single 80 percent gate on the whole of `shared/` hides the shape. A package at 100 percent can carry one at 35 percent, and the total still looks healthy. The previous gate had the opposite problem: it measured only `shared/async` and `shared/observability`, 2 of 16 packages. Every other package could lose all its tests and CI would stay green.

## Why measure on the unit suite only

Coverage is measured with `pytest -m unit`: no network, no secrets, about 3 seconds. Integration tests also exercise `shared/`, but their coverage depends on whether a third-party sandbox is up that day. A gate must be deterministic, so it counts only tests that give the same answer every run.

## Floors (measured November 24, 2026)

| Tier | Packages | Floor | Why this level |
|---|---|---|---|
| Safety critical | guardrails, dataprovider, async, jira, observability, config, reporting, ai, assertions | 90 to 95% | These decide what reaches Claude, what data a test trusts, and what a human is told. A gap here is a silent correctness risk. |
| Core logic | oracle 80%, contract 70% | 70 to 80% | Pure decision logic. Should rise toward the safety tier. |
| LLM boundary | agent 78%, evaluation 50%, mcp 50% | 50 to 65% | Lower because the interesting branches sit behind a Claude call or an external service. Raised as seams are added (Phase B). |
| Integration exercised | http 60% | 60% | ApiClient and auth are mostly reached by live API tests, which the gate does not count. Raised from 35% on November 27 when local_sandbox.py arrived with full unit tests. |
| Excluded | performance | none | Locust and k6 driver scripts, run by the k6 and performance jobs. |
| **Overall** | all gated packages | **84%** | Measured 84.3% (raised from 80% on November 24, then 82% to 84% on November 25). |

Floors are set at today's measured value, rounded down. That makes the gate honest on day one and turns every future improvement into a ratchet.

## First ratchet: assertions (closed November 24, 2026)

`shared/assertions/response_validator.py`, the fluent `.status_code().has_field()` checker used by the Petstore suite, started at 35 percent. It is pure logic, so it was unit tested to 100 percent the same day and its floor was raised from 35 to 95.

The new tests found real defects, each confirmed by running the tests against the previous version:

- `field_equals("x", None)` passed when `x` was missing, because `body.get()` returns `None` for a missing key. A test checking that a value was cleared would pass if the API dropped the field.
- A JSON array body made `has_field("id")` check list membership, and made `field_equals` crash with `AttributeError` instead of failing.
- A non-JSON body (for example a gateway HTML error page) and a response without timing data crashed instead of failing with a readable message.

Low coverage was not a cosmetic number here. It was where the bugs were.

## How the gate works

1. CI runs `pytest -m unit --cov=shared --cov-report=json:reports/coverage.json`.
2. `scripts/check_coverage.py` groups lines by package and compares each to `coverage_thresholds.json`.
3. The job fails if any package or the overall total is below its floor, if a new package appears with no floor, or if a floor points at a package that no longer exists.

The "new package with no floor" rule is deliberate. Without it, adding `shared/foo/` with no tests would pass silently.

## Changing a floor

- **Raise:** in the same pull request as the tests that earn it.
- **Lower:** only with an Architecture Decision Record explaining why, for example a package moved behind a live service.
- **Re-measure:** each quarter, alongside the test pyramid audit.

## Not yet measured

Mutation score on `shared/`, planned for Phase D (`mutmut`, target 70 percent). Line coverage says code ran. Mutation score says a test would notice if it were wrong.

## Reproduce locally

```bash
COVERAGE_FILE=/tmp/.coverage pytest -m unit --cov=shared --cov-report=json:reports/coverage.json
python scripts/check_coverage.py reports/coverage.json
```
