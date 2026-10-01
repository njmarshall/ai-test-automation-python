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
