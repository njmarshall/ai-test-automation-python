## 2026-10-30
- ci(shared): CI hardening — pytest-timeout + shared/ coverage gate (Option C)
  - requirements.txt: added pytest-timeout==2.3.* and pytest-cov==5.*
  - unit-tests CI job: added --timeout=10 to prevent indefinitely-hanging tests from blocking CI
  - New CI job: shared-coverage — runs the 3 shared/ unit test files with --cov=shared/async --cov=shared/observability --cov-fail-under=80 (baseline: 96% actual, gate at 80% for regression safety)
  - Coverage report uploaded as artifact: reports/shared-coverage.xml
  - shared-coverage added to test-summary needs list (23 jobs total)

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

## 2026-10-01

- Flex split-rent domain added — projects/fintech/flex/
- FastAPI mock of Flex chartered bank API
- Business rules: ceil(rent × 55%) split, 3-retry max, credit float ledger, landlord disbursement guarantee
- 62 tests across 4 suites: plan creation, installment charging, disbursement, plan summary
- State machine: ACTIVE → COMPLETED / DELINQUENT / CANCELLED
- Total: 269 passed, 1 skipped — new high score
- All 19 CI jobs green

## 2026-10-08

- Article 16 first draft added — articles/article16_draft.md
- Topic: I Built a Chartered Bank in Python. Here Is What the Tests Had to Prove.
- Covers: three-party transaction model, state machine, credit float ledger, idempotency, retry guard, split calculation, 62-test suite
- Written as interview prep for Flex Risk Team round 3

## 2026-10-09

- README Published Articles table fixed — Article 10 row restored (Contract Testing and FHIR)
- Article 10 URL placeholder added; Neil to update with LinkedIn URL
- Article 13 identified as the article on hold pending oracle/adaptive testing expert review
- Memory updated to reflect correct article status across series

## 2026-10-10

- Flex Risk Team round 3 interview prep — full-day study session
- Studied payment flow scenarios using POST/GET status patterns
- Practiced responding to AI-generated prompts on payment domain edge cases
- Reviewed and deepened understanding of payment test suite in Python/pytest

## 2026-10-11

- Flex Risk Team round 3 interview prep — continued study session
- Practiced crafting and responding to AI-generated prompts on payment domain
- Studied payment test suite patterns — happy path, retries, edge cases
- Focused on risky test scenarios: delinquency, idempotency failures, MAX_RETRIES_EXCEEDED

## 2026-10-14
- Flex Risk Team round 3 interview prep — mock session day 2
- Practiced 6 behavioral questions with STAR format answers
- Learned financial terms in plain English: disbursement, credit float, delinquency, ACH return, ledger, state machine
- Q3: speed vs thoroughness — Finix Friday release review story
- Q4: bug nobody else found — duplicate disbursement guard story
- Q5: pushing back on a requirement — fourth retry MAX_RETRIES_EXCEEDED story
- Q6: test that caught a real problem — ACH return after SUCCEEDED story
- Reviewed ACH return credit float scenario step by step
- Friday = Risk Team behavioral, Monday = AI Testing hands-on

## 2026-10-16
- Flex Risk Team round 3 behavioral interview — completed, went well
- Sent follow-up email with Article 6 (PHI Guardrails) and Article 11 (Untested Risks) links
- Completed AI Testing interview prompt practice session
- Monday = AI Testing hands-on exercise (next interview)

## 2026-10-17
- AI Testing interview prep — worked through AI prompt assignments
- Practice focus: writing and evaluating AI prompts for test generation scenarios
- Monday = AI Testing hands-on exercise interview

## 2026-10-18
- AI Testing hands-on interview prep — Sunday evening study session
- Reviewed framework components: DeepEval scoring, AiObserver, InputGuard, OutputGuard, ClaudeJudge
- DeepEval: quality gate at generation time — threshold 0.7, rejects low-scoring tests
- AiObserver: production monitor tracking cost, speed, and quality drift on every Claude API call
- InputGuard and OutputGuard: domain-agnostic guardrails — PHI scrubbing in healthcare, PCI scrubbing in fintech
- ClaudeJudge: uses Claude to evaluate quality of Claude-generated tests — not data protection
- Cohen's kappa confirmed not implemented in repo — honest answer: on roadmap, currently using DeepEval
- "AI wrote 20 tests and all pass — do you trust them?" practice answer: No. Passing is not the same as correct.
- Monday = AI Testing hands-on exercise (fourth and final Flex interview)

## 2026-10-20
- Flex AI Testing hands-on interview — fourth and final interview completed, went well
- Format: Codebyte Challenge / live coding assessment
- Task: implement Flex APIs in Python during the session
- Used Claude as AI co-pilot to identify and address errors in real time
- Demonstrated practical AI-assisted test engineering workflow under interview conditions

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
- Article 16 published on LinkedIn — Every Layer Passed. The Patient Still Couldn't Schedule Their Procedure.
- Final title agreed upon by both ChatGPT and Claude review
- Topic: healthcare patient journey oracle testing — all API layers pass but the patient-facing outcome fails
- Extends the customer journey oracle pattern from Article 15 into the healthcare domain
- 16 articles in this series

## 2026-10-22
- Flex split-rent tests wired into CI — new parallel job: Flex Split-Rent Tests (62 tests)
- SQL data quality tests wired into CI — new parallel job: SQL Data Quality Tests (15 tests)
- Total CI jobs: 17 parallel
- Total tests: 212 passed, 1 skipped
- README badges updated: tests-212, CI jobs-17
- README Test Coverage section updated with Flex and SQL suite entries

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
