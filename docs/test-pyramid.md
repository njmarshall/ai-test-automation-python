# Test Pyramid Audit

**Date:** November 23, 2026 · **Suite:** 477 tests collected · **Plan item:** 12-month plan, Phase A (Q1 2027 roadmap, Month 1 item 4)

## Method

Labels can lie, so this audit classifies tests by **evidence**, not by folder or marker.

1. Count tests by marker with `pytest --co -q -m <marker>`.
2. Run every test that is **not** marked `unit` or `ui` on a machine with **no outbound internet**.
3. A file whose tests all pass offline does not need the network. A file whose tests fail with proxy or connection errors does.
4. Offline files are then split by whether they start a local server (FastAPI sandbox, SQLite) or run in pure memory.

## Result

| Layer | What it means | Tests | Share |
|---|---|---|---|
| Unit | Pure memory. No server, no network, no secrets. Milliseconds. | 297 | 62% |
| Local integration | Starts a sandbox the suite owns (FastAPI payments and scheduling servers, SQLite). No internet. | 68 | 14% |
| Live external integration | Calls an API the suite does not own (Petstore, HAPI FHIR, public market data, Claude). | 100 | 21% |
| UI end to end | Playwright against a running browser. | 12 | 3% |
| **Total** | | **477** | |

Local integration detail: payments sandbox 44 (webhooks 15, refunds 14, idempotency 9, async 6), SQL data quality 15, patient scheduling oracle 6, per-event sequencer 3.

The shape is a healthy pyramid: a wide unit base, a thin UI top. The Q1 roadmap warned against integration above 60 percent. Measured integration is 35 percent (local plus live).

## Finding: 70 tests were in the wrong layer

Before this audit, `pytest -m unit` selected 227 tests and the labelled integration layer held 238 (50 percent). The offline run showed that **70 of those 238 never touch the network** and finish in milliseconds. They were missing the `unit` marker:

| File | Tests | Offline runtime |
|---|---|---|
| prior_auth/tests/test_notification_content.py | 18 | 0.02s |
| tests/test_guardrails.py | 14 | 0.00s |
| tests/test_observability.py | 10 | 0.06s |
| tests/test_exploratory_agent.py | 9 | 0.00s |
| tests/test_mcp_connector.py | 9 | 0.00s |
| tests/test_self_healing_agent.py | 7 | 0.01s |
| prior_auth/tests/test_customer_journey_oracle.py | 3 | 0.03s |

All paths under `projects/healthcare_fhir/api/`. Each file now carries a module-level `pytestmark` with `unit`. Result: `pytest -m unit` selects **297** tests and runs them in under 2 seconds. Because the nightly health check runs `-m "unit or excel"`, it now covers these 70 tests at no extra cost.

**Why it mattered:** the mislabel made the suite look more integration-heavy than it is, and it kept fast, deterministic tests out of the nightly run that needs no secrets.

## Risk: the live external layer

The 100 live external tests are the ones that go red when someone else's sandbox is down. Two groups deserve attention:

- **35 AI-generated tests call live APIs** (fintech market data 15, insurance policy 12, FHIR patient 8). A generated test that depends on a third-party sandbox mixes two questions: is the generated test correct, and is the sandbox up? Candidate fix: run generated tests against recorded responses first, live second.
- **13 fintech market data tests** depend on a public data API with no contract snapshot. Candidate fix: a consumer contract snapshot, the same pattern as `test_fhir_patient_contract.py`.

## Rules going forward

- A test that needs no network and no secrets is marked `unit`, whatever folder it lives in.
- A test that starts its own sandbox is local integration and must pass offline.
- A new live external test needs a written reason it cannot use a sandbox or a recording.
- Re-run this audit each quarter. Record the four counts in this file and in CHANGELOG.

## How to reproduce

```bash
pytest --co -q -m unit                    # unit layer count
pytest --co -q -m ui                      # UI layer count
pytest -m "not unit and not ui" --timeout=15 --junitxml=reports/pyramid.xml
# then group results by file: all pass offline = local, any network failure = live external
```
