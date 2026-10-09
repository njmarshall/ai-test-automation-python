# Article 16 — Draft

**Title: I Built a Chartered Bank in Python. Here Is What the Tests Had to Prove.**

---

When I started preparing for a fintech interview, I did not study. I built.

I built a FastAPI mock of Flex's core banking API — the chartered bank that lets renters pay rent in two installments while guaranteeing landlords receive 100% of rent on the due date, no matter what.

Then I wrote 62 tests to prove it worked.

This is what I learned.

---

## The business problem nobody talks about in interviews

Most payment APIs look simple on the surface. POST /charge. Get 200. Done.

Flex is not that. Flex sits in the middle of a three-party transaction:

1. The renter, who wants to pay in two smaller installments across the month.
2. The landlord, who needs full rent on the first of the month, no exceptions.
3. Flex, acting as a chartered bank, absorbing the gap in between.

That gap is real money. If a renter pays installment 1 but not installment 2, Flex still pays the landlord in full. The bank takes on the credit risk.

Testing this correctly means testing that the bank's own accounting holds up under every failure scenario. That is a very different problem than testing a CRUD API.

---

## The state machine

Every rent plan has a lifecycle:

```
ACTIVE
  ↓ both installments SUCCEEDED → COMPLETED
  ↓ both installments permanently FAILED → DELINQUENT
  ↓ tenant cancels → CANCELLED
```

The word "permanently" is doing real work there.

Flex gives each installment three attempts. On the third failure, the installment is marked permanently FAILED. A fourth charge attempt does not try again. It returns MAX_RETRIES_EXCEEDED and stops.

The plan only goes DELINQUENT when both installments are permanently failed. If installment 1 fails three times but installment 2 succeeds, the plan is not delinquent. The landlord still gets paid. The bank absorbs the shortfall on installment 1 and records it as a credit float entry in the ledger.

I had to write tests for all of this. Not just the happy path — every edge of the state machine.

---

## The credit float ledger

This is the detail that most interviews never reach.

When Flex disburses to the landlord before an installment has been collected, that difference goes into the credit float ledger. It is not a bug. It is a design decision — the charter obligates Flex to pay landlords on time regardless.

A test that only checks whether the disbursement happened is incomplete. You also need to check whether the ledger entry exists and whether it is the correct amount.

My test suite verifies:

- Disbursement fires on the rent due date regardless of installment status.
- If installment 1 is still outstanding when disbursement fires, a credit float entry appears in the ledger.
- The float entry amount equals the disbursed amount minus what has been collected.
- A second disbursement call on the same plan returns an already-disbursed guard response, not a duplicate payment.

That last one is critical. Duplicate landlord payments are a compliance event. One test, one guard, zero tolerance.

---

## Idempotency — the rule that keeps the bank solvent

Every installment charge accepts an idempotency key. Send the same key twice and you get the same result back. No second charge. No double-debit.

This sounds simple. It is not.

The idempotency cache has to survive across retries. If a charge fails with a network timeout and the renter's app retries, the key has to block a second attempt — even if the first attempt never produced a result.

I wrote a test that:

1. Sends a charge with a given idempotency key.
2. Sends the exact same charge again, same key.
3. Asserts the response is identical.
4. Asserts the balance and retry count did not change.

Four assertions, one idempotency key, one test. That is what it takes to prove no double-charge.

---

## What 62 tests actually cover

The suite is spread across four files:

`test_plan_creation.py` (13 tests) — plan created correctly, installment amounts sum to exactly monthly rent, disbursement is scheduled, idempotency on plan creation.

`test_installment_charging.py` (20 tests) — happy path, idempotency under retry, all failure/retry transitions, delinquency triggered only when both installments fail.

`test_disbursement.py` (14 tests) — disbursement fires on due date, credit float entries appear when collection is outstanding, already-disbursed guard blocks duplicates.

`test_plan_summary.py` (15 tests) — full plan state across all status transitions, balance due calculation, float entries surfaced in summary, cancelled and delinquent edge cases.

---

## The split calculation

One business rule that looks trivial but will catch you out if you get it wrong:

Installment 1 = ceil(rent × 55%).
Installment 2 = rent minus installment 1.

The two installments always sum to exactly monthly rent. No rounding error. No fractional cent left on the table.

I tested this at $1,000, $1,500, $2,347, and $3,099 rent amounts. The last two are intentionally awkward numbers. Ceil arithmetic on $2,347 × 0.55 is not obvious. The tests are not there to verify math — they are there to catch a future developer who swaps ceil for round and silently breaks the guarantee.

---

## Why this matters for fintech interviews

Chartered bank split payments are not a niche pattern. Flex does it for rent. Splitit does it for retail. Afterpay does it for ecommerce. The underlying problem is always the same:

How do you collect from a consumer in installments while guaranteeing a merchant or landlord is paid in full on day one?

The answer requires a state machine, a credit float ledger, an idempotency cache, and a retry guard. Testing it requires verifying all four hold up under edge cases — not just when everything goes right.

If you can articulate that in an interview, you are not talking about your test suite anymore. You are talking about the bank's own accounting.

That is the level of depth that risk-critical fintech interviews are looking for.

---

## The repo

The full suite is live at: github.com/njmarshall/ai-test-automation-python under `projects/fintech/flex/`

269 tests total. 19 parallel CI jobs. All green.

---

*Neil Marshall is a Senior SDET and AI Test Automation Architect at Marshall Test Engineering. 15 articles in this series. Links in the comments.*
