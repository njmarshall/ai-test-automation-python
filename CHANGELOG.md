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
