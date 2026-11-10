## 2026-11-09
- docs(articles): Article 16 published on LinkedIn. Every Layer Passed. The Patient Still Couldn't Schedule Their Procedure.
  - Covers Phase 7: the CustomerJourneyOracle and the prior authorization sandbox, built and tested in 2026-11-01
  - 16 LinkedIn articles published total
  - Reader input after publication: a seed set of escaped defects with the layer that should have caught each one, and risk based selection of longest path journeys. Both are candidates for upcoming articles

## 2026-11-05
- fix(pytest): add tests/ to testpaths so unit suite runs locally (commit bb922de)
  - pytest.ini testpaths was `projects` only — bare `pytest` from the repo root silently skipped all 132 unit tests in tests/unit/
  - CI was unaffected (Unit Tests job explicitly targets tests/unit), but local dev runs showed 222 tests instead of 364
  - Fix: testpaths = projects tests
  - Badge updated: 362 → 364 (now reflects the full collected count)
  - Month 1 roadmap Item 1 — Foundation Hardening

## 2026-11-04
- docs(changelog): catch-up entries for Nov 1-3 and Oct 30 commits (commit 9bf9e71)
  - Added missing CHANGELOG sections for commits 0127f97, 0ded7e9, de8b6b3, 9cec8ea, 67a8fe8
  - Sections patched: 2026-11-03 (new), 2026-11-01 (extended), 2026-10-30 (extended)

## 2026-11-03
- fix(pytest): register flaky marker to eliminate PytestUnknownMarkWarning (commit 67a8fe8)
  - pytest.ini markers: added flaky with description "Tests quarantined for intermittent failures — run with retries, non-blocking in CI"
  - Root cause: @pytest.mark.flaky(reruns=3, reruns_delay=2) used in projects/fintech/api/ai/generated/test_market_data_ai.py line 193 but marker was not declared
  - Fix confirms pytest-rerunfailures plugin is active — 3 reruns fire correctly on that test class
  - 222 tests collected cleanly, 0 warnings under -W error::pytest.PytestUnknownMarkWarning
  - Month 1 roadmap Item 1 — Foundation Hardening

## 2026-11-02
- docs(readme): Article 16 LinkedIn URL added
  - URL: https://www.linkedin.com/pulse/every-layer-passed-patient-still-couldnt-schedule-neil-marshall-siz0c/
  - Published: November 1, 2026
  - Title: Every Layer Passed. The Patient Still Couldn't Schedule Their Procedure.
  - README Published Articles table row 16 now links to the live article
  - 16 articles in this series

## 2026-11-01
- feat(phase-7): CustomerJourneyOracle and prior authorization oracle tests (Article 16 code)
  - New: shared/oracle/customer_journey_oracle.py. Records step observations and judges the customer outcome separately from step success
  - New: projects/healthcare_fhir/api/prior_auth/. In-process FastAPI sandbox with a toggleable patient-notification defect, Facade client, and 3 tests (approval defect, approval fix, denial defect)
  - Sandbox runs through TestClient, no real port. Records are held in memory
  - Scope: the oracle checks the notification content the workflow produced. It does not show delivery to, or action by, a person
  - The patient scheduling oracle (2026-10-28) remains as a separate companion example
  - New CI job: prior-auth-oracle-tests, wired into test-summary needs list
  - Badge updated: 421 to 424 passing tests
- docs: corrected the 2026-10-21 entry. Article 16 had not yet been published on LinkedIn at that date
- chore: remove split-rent mock domain and held article draft from the public tree (commit 0ded7e9)
  - Removed: projects/fintech/flex/ — Flex chartered bank mock domain (62 tests)
  - Removed: articles/article16_draft.md — article draft no longer needed alongside published version
  - Removed: flex-tests CI job and its test-summary needs entry
  - README, architecture diagram labels, and earlier CHANGELOG sections updated to match
  - Test count: 424 → 362. Recoverable with git revert of this commit
- chore: ignore coverage and report artifacts (commit de8b6b3)
  - .gitignore: added coverage report directories and JUnit XML output paths
  - Prevents htmlcov/, .coverage, reports/*.xml from appearing in git status after local runs
- docs(readme): add Q1 2027 improvement roadmap link (commit 9cec8ea)
  - Callout block added below intro paragraph pointing to the quarterly roadmap doc
  - New section: Improvement Roadmap table (before Published Articles)
  - Roadmap URL: https://claude.ai/artifact/LRLECcaQ3PRjokMbWyXjqc
  - Goal: show version-to-version framework maturity progress to readers

## 2026-10-30
- ci(shared): CI hardening — pytest-timeout + shared/ coverage gate (Option C)
  - requirements.txt: added pytest-timeout==2.3.* and pytest-cov==5.*
  - unit-tests CI job: added --timeout=10 to prevent indefinitely-hanging tests from blocking CI
  - New CI job: shared-coverage — runs the 3 shared/ unit test files with --cov=shared/async --cov=shared/observability --cov-fail-under=80 (baseline: 96% actual, gate at 80% for regression safety)
  - Coverage report uploaded as artifact: reports/shared-coverage.xml
  - shared-coverage added to test-summary needs list (23 jobs total)
- test(shared): AsyncApiClient unit tests — zero-coverage gap closed (commit 0127f97)
  - New: shared/src/test/java/com/aitesting/shared/http/AsyncApiClientTest.java (Python-side mirror)
  - New: tests/unit/test_async_api_client.py — 15 tests covering the same three polling invariants as the Java suite
  - Invariants: returns on expected status, throws on terminal failure, throws on timeout
  - Technique: unittest.mock.patch("time.sleep") — no real waits, full coverage in <50ms
  - Mirrors Java AsyncApiClientTest.java — same invariants, same mock-clock approach, cross-language parity documented
  - Badge updated: 421 → 436 passing tests

## 2026-10-29
- test(shared): unit tests for three zero-coverage shared/ modules (A+B)
  - New: tests/unit/test_async_poller.py — 18 tests covering TimeoutStrategy, FixedRetryStrategy, ExponentialBackoffStrategy, AsyncPoller.poll(), AsyncPoller.poll_for_status()
  - New: tests/unit/test_event_sequencer.py — 22 tests covering SequenceResult, EventSequencer constructor, whole-sequence validation, per-event budget path, assert_valid()
  - New: tests/unit/test_ai_observer.py — 23 tests covering ObservationRecord, ObservationContext, AiObserver.observe(), is_drifting(), summary()
  - All 83 tests pass in <0.2s (no sleep, no network — time.sleep patched throughout)
  - Key technique: importlib.import_module("shared.async.x") to work around async keyword; patch("time.sleep") globally; itertools.count(step=3.0) for monotonic mock clocks in per-event budget tests
  - Badge updated: 338 → 421 passing tests

## 2026-10-28
- docs(phase-6): Phase 6 design patterns playbook added
  - New: docs/playbooks/phase6_patterns.md — Facade, Builder, Value Object, Template Method
  - Plain-English explanations with concrete code examples from Phase 6 source
  - Interview-ready one-liners and a connection diagram showing how all four wire together
- feat(phase-7): Patient scheduling oracle test added (Article 16 companion code)
  - New: tests/integration/test_patient_scheduling_oracle.py — 6 tests, all CI-runnable
  - Three FastAPI sandboxes (scheduling, availability, notification) — no external staging env
  - Ports 8020-8022 (no collision with existing sandboxes)
  - Oracle: all four services (scheduling, availability, notification, surface) must agree
  - Failure messages are patient-impact assertions ("Patient cannot confirm appointment")
  - Article 16: "Every Layer Passed. The Patient Still Couldn't Schedule."
  - New CI job: scheduling-oracle-tests; wired into test-summary needs list
  - Total tests: 338 (up from 332)

## 2026-09-25

- Article 15 published — The Database Was Correct. The Customer Still Failed.
- Fintech customer journey oracle testing
- Paul Kanaris customer journey oracle insight credited
- 15 LinkedIn articles published total

## 2026-09-26

- Payments domain expanded — refund suite added
- 14 refund tests: full refund, partial refund, over-refund guard, idempotency, 404 on unknown payment
- Total: 206 passed, 1 skipped — new high score

## 2026-09-27

- Payments domain expanded — webhook event suite added
- 15 webhook tests: payment.created, payment.succeeded, partial/full refund events, event retrieval, filtering
- FastAPI sandbox extended with /events endpoint and event log
- Total: 221 passed, 1 skipped — new high score

## 2026-09-27

- CI webhook tests failing — [Errno 98] address already in use on port 8003
- Root cause: conftest.py payment_server fixture scoped to module, not session
- Three test modules (async, refunds, webhooks) each tried to bind port 8003 in one pytest run

## 2026-09-28

- conftest.py fix: payment_server fixture scope changed from module to session
- One server instance now serves all payment test modules in a single pytest run
- Port conflict eliminated — all 44 payment tests now collect and run cleanly

## 2026-09-30

- ANTHROPIC_API_KEY GitHub Actions secret expired — DeepEval CI job failing with 401
- Regenerated API key at console.anthropic.com
- Updated ANTHROPIC_API_KEY secret at github.com/njmarshall/ai-test-automation-python/settings/secrets/actions
- DeepEval CI job green again

## 2026-10-09

- README Published Articles table fixed — Article 10 row restored (Contract Testing and FHIR)
- Article 10 URL placeholder added; Neil to update with LinkedIn URL
- Article 13 identified as the article on hold pending oracle/adaptive testing expert review
- Memory updated to reflect correct article status across series

## 2026-10-20 (README)
- Published Articles table restored to full 15 articles (rows 7-15 were missing)
- Added LinkedIn URLs for articles 7, 8, 9, 10, 11, 12, 13, 14, 15
- Article 7: Async API Testing: 5 Failure Modes Most Test Suites Miss
- Article 8: AI Quality Drift: How I Used AiObserver to Catch It Before It Became a Failure
- Article 9: I Built a Self-Healing Test Agent. The Hard Part Was Teaching It When Not to Heal.
- Article 10: Your API Tests Pass. Your Consumers Still Break. Here Is Why.
- Articles 11-15: titles and URLs confirmed from LinkedIn Articles spreadsheet
- Article 16 removed — not yet published
- Footer updated to "15 articles in this series"

## 2026-10-21
- Article 16 title agreed: Every Layer Passed. The Patient Still Couldn't Schedule Their Procedure.
- Final title agreed upon by both ChatGPT and Claude review
- Topic: healthcare patient journey oracle testing — all API layers pass but the patient-facing outcome fails
- Extends the customer journey oracle pattern from Article 15 into the healthcare domain

## 2026-10-22
- SQL data quality tests wired into CI — new parallel job: SQL Data Quality Tests (15 tests)
- Total CI jobs: 17 parallel
- Total tests: 212 passed, 1 skipped
- README badges updated: tests-212, CI jobs-17
- README Test Coverage section updated with SQL suite entry

## 2026-10-25

- fix: silence pytest-asyncio deprecation warning across all CI jobs
  - Added asyncio_mode = auto and asyncio_default_fixture_loop_scope = function to pytest.ini
  - Removed duplicate insurance and fintech marker entries from pytest.ini
- feat(phase-6): JIRA auto-ticket integration for self-healing deviations
  - New: shared/jira/jira_notifier.py — JiraNotifier Facade, JiraConfig, JiraTicketPayload, JiraTicketResult
  - SelfHealingAgent.heal() now calls JiraNotifier.notify() on every PASS result
  - Dry-run mode activates automatically when JIRA credentials are not set — CI safe
  - 21 new unit tests in tests/unit/test_jira_notifier.py
  - Compliance rationale: HIPAA/PCI/IEC 62304 environments require a human-closeable audit trail for every self-heal
- feat(phase-6): SelfHealReport builder for CI Allure output
  - New: shared/reporting/self_heal_report.py — Builder pattern, immutable BuiltReport
  - BuiltReport.to_markdown() includes compliance footer for Allure attachment
  - 19 new unit tests in tests/unit/test_self_heal_report.py
- Total unit tests: 49 (21 jira_notifier + 19 self_heal_report + 9 base_test_generator)
- Total tests: 332 (up from 292)
