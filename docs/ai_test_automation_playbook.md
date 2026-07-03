# AI Test Automation Playbook
## Neil Marshall — Senior SDET & AI Test Automation Architect

---

## 1. The Golden Rules

### Rule 1: Never let AI autonomously modify hand-crafted tests
- Claude Code should only touch `ai/generated/` files autonomously
- Hand-crafted tests (`test_patient.py`, `test_encounter.py`, etc.) = YOUR domain
- Always review AI changes to hand-crafted files line by line before committing

### Rule 2: Establish and protect your test count baseline
Before ANY Claude Code session:
```bash
pytest projects/ --co -q 2>&1 | tail -3
```
Write down the count. After Claude Code runs, verify it hasn't dropped.
A dropping count = tests deleted or skipped — always investigate why.

### Rule 3: Commit before Claude Code touches anything
```bash
git stash        # before Claude Code session
git stash pop    # if Claude Code makes things worse
```

### Rule 4: Use Claude Code for surgical fixes only
Always be explicit:
```
Fix ONLY the failing assertion on line X.
Do not modify any other lines.
Do not regenerate the file.
```

### Rule 5: Never delete a flaky test — document and skip
```python
@pytest.mark.skip(reason="HAPI sandbox search index too slow — verified manually")
def test_search_by_family_name(...):
```
Skipping with documentation > deleting > fighting forever

---

## 2. Flaky Test Management Strategy

### The 3-tier approach (learned from Indeed experience):

**Tier 1 — Fix it properly**
- Root cause is in YOUR code
- Fix the assertion or test logic
- No retry needed

**Tier 2 — Retry with delay**
- Root cause is external (sandbox timing, network latency)
- Use `@pytest.mark.flaky(reruns=3, reruns_delay=2)`
- Document WHY in the test docstring

**Tier 3 — Skip with documentation**
- Root cause is fundamental sandbox limitation
- Use `@pytest.mark.skip(reason="...")`
- Add to known issues list
- Verify manually periodically

### Flaky test indicators:
- Passes alone, fails in full suite → session-level conflict or timing
- Fails intermittently with same error → network/sandbox latency
- Count keeps changing → AI tool modifying files autonomously ⚠️

---

## 3. Claude Code Guardrails

### DO use Claude Code for:
- Running tests and reporting results
- Fixing specific assertion errors in AI-generated files
- Installing dependencies
- Git operations (add, commit, push)

### DO NOT use Claude Code for:
- Modifying hand-crafted test files autonomously
- Regenerating entire test files
- Making architectural decisions
- Changing test counts without your approval

### Safe Claude Code prompt template:
```
In [filename], line [N] is failing with [error].
Fix ONLY that line to handle [specific issue].
Do not modify any other lines.
After fixing, run pytest [specific test] -v to confirm it passes.
Show me the diff before applying.
```

### Unsafe Claude Code prompts (avoid):
```
❌ "Fix all failing tests"
❌ "Make the test suite pass"
❌ "Regenerate the test file"
❌ "Fix the HAPI sandbox issues"
```

---

## 4. HAPI Sandbox Known Quirks

| Behaviour | Expected | HAPI Actual | Fix |
|---|---|---|---|
| DELETE existing resource | 204 No Content | 200 + OperationOutcome | `status_in(200, 204)` |
| DELETE non-existent | 404 Not Found | 200 + OperationOutcome | `status_in(200, 404)` |
| Search Bundle total | Always present | Often omitted | Check `entry` instead |
| Create then search | Immediate | Delayed (index lag) | Skip or `reruns_delay=5` |
| Response time | < 1s | 2-5s variable | `within_sla(5000)` |

---

## 5. Pre-Commit Checklist

Before every `git commit`:
```bash
# 1. Check test count baseline
pytest projects/ --co -q 2>&1 | tail -3

# 2. Run full suite
pytest projects/ --tb=short 2>&1 | tail -5

# 3. Check what changed
git diff --name-only

# 4. Verify no hand-crafted tests were modified unexpectedly
git diff projects/healthcare_fhir/api/tests/
git diff projects/petstore/api/tests/
git diff projects/insurance/api/tests/

# 5. Only then commit
git add -A
git commit -m "meaningful message"
git push origin main
```

---

## 6. Management Communication Template

When reporting to managers:

```
Test Suite Status — [Date]

Total collected : XX tests
Passing         : XX ✅
Skipped         : X  ⏭️  (documented reasons below)
Flaky (retried) : X  🔄 (external dependency issues)
Failed          : 0  ✅

Skipped tests:
- test_search_by_family_name: HAPI sandbox search index latency
  → Verified manually, passes in isolation

Trend: Week 1: 34 → Week 2: 37 → Week 3: 39 (upward trend ✅)

CI Status: All 4 jobs green ✅
```

---

## 7. Interview Talking Points

### On flaky tests:
> "At Indeed I reduced flaky test rates by categorising failures into 
> code bugs vs external dependency issues, applying targeted retry 
> strategies, and documenting known sandbox limitations. This gave 
> management a clear, honest picture of test health rather than 
> misleading pass/fail numbers."

### On AI-assisted testing:
> "I use Claude interactively for architecture decisions and design 
> patterns, and I use Claude Code for automated test fixing loops — 
> but always with guardrails. The AI suggests fixes; I review and 
> approve. This mirrors how I'd work with a junior engineer."

### On self-healing tests:
> "My StalenessDetector in the healthcare_fhir project automatically 
> flags tests that reference deprecated endpoints or fields before 
> they fail in CI — preventing false failures from reaching the team."

---

## 8. Current Test Suite Baseline (June 2026)

```
projects/
├── healthcare_fhir/api/tests/    4 hand-crafted Patient CRUD tests
├── healthcare_fhir/api/tests/    3 Encounter tests
├── healthcare_fhir/api/tests/    3 Observation tests  
├── healthcare_fhir/api/ai/       8 AI-generated Patient tests + 1 skipped
├── healthcare_fhir/ui/tests/     3 Playwright UI tests
├── petstore/api/tests/           11 PetStore API tests
└── insurance/api/tests/          5 Insurance Policy tests
─────────────────────────────────────────────────────
Total: 37 passed, 1 skipped | CI: 4 jobs green ✅
```

---

## 9. Phase Roadmap

| Phase | Status | Description |
|---|---|---|
| Phase 1 | ✅ | Patient CRUD — Singleton, Facade, CRTP, Factory, Fluent |
| Phase 2 | ✅ | AI test generation — Template Method, StalenessDetector |
| Phase 3 | ✅ | Encounter + Observation — LOINC vital signs, OCP |
| Phase 4 | ✅ | Playwright UI — POM, BasePage, FhirExplorerPage |
| Phase 5 | ✅ | GitHub Actions CI/CD — 4 jobs, green badges |
| Phase 6 | ⏳ | Insurance AI-generated tests |
| Phase 7 | ⏳ | Fintech capstone — leverage Finix background |

---

*Generated by Claude — Neil Marshall's AI Test Automation Playbook*

*Last reviewed: 2026-06-27*

---

## 10. Fintech Capstone — Design Decisions

### Why Coinbase public API (not Alpaca, Stripe, or Finix)

| Option | Verdict | Reason |
|---|---|---|
| Finix | Rejected for MVP | Requires production credentials — your actual employer's API |
| Alpaca | Rejected | Requires API key signup — adds friction |
| Stripe | Rejected | Test mode requires account creation |
| **Coinbase public API** | ✅ Selected | Zero auth, real financial data, runs out of the box |

### What this demonstrates to a hiring manager

Testing real market data (currencies, exchange rates, spot prices) shows:
- Understanding of fintech data structures (not just CRUD)
- Ability to test third-party financial APIs without environment setup friction
- SLA-conscious testing (`within_sla()`) — critical for trading/payment systems

### Connection to Finix background (interview talking point)

> "While my Coinbase market data tests target public endpoints, the testing 
> philosophy directly applies to my Finix experience — validating payment 
> processing accuracy, SLA compliance, and data integrity are universal 
> fintech QA principles regardless of the specific API."

### Fintech-specific testing considerations

1. **Numeric precision** — financial amounts must never use floating point comparison without tolerance; `FintechValidator.data_amount_is_positive()` validates type safety first
2. **Real-time data volatility** — spot prices change constantly; tests assert structure and positivity, never exact values
3. **Multi-currency support** — `ExchangeRate.has_rate()` and `get_rate()` enable testing currency conversion logic without hardcoding rate values
4. **No mutation testing on public endpoints** — Coinbase public API is read-only; this is intentional for a portfolio (no risk of rate limiting or abuse)

### Fintech Phase Roadmap

| Phase | Status | Description |
|---|---|---|
| Phase 1 | ✅ | Market data — currencies, exchange rates, spot prices (9 tests) |
| Phase 2 | ⏳ | AI-generated fintech tests via Anthropic SDK |
| Phase 3 | ⏳ | Historical price data, multi-pair comparison |
| Phase 4 | ⏳ | Playwright UI — Coinbase public price charts |
| Phase 5 | ✅ | CI integration — fintech job added to GitHub Actions |

---

## 11. Interview Q&A — Practiced July 2026

### Q1 — Tell me about your ai-test-automation-python repo

**High-level answer:**
> "I built an AI-powered test automation framework as a co-pilot workflow
> between me and Claude. It covers 4 domains — healthcare FHIR, insurance,
> fintech, and PetStore — with 73 tests passing across API and UI layers.
> Each capstone follows the same layered architecture: Singleton config,
> Facade client, CRTP models, Factory test data, and Fluent assertions.
> The AI generates tests automatically from API specs, and a StalenessDetector
> flags tests that drift from the spec before they fail in CI."

---

### Q2 — Explain a design pattern you used

**Pattern: Singleton**
> "Singleton ensures one shared instance no matter how many times you
> instantiate the class. In test automation this is critical for the HTTP
> client — you don't want a new connection pool per test. In my FhirConfig
> and InsuranceConfig, environment variables are loaded exactly once across
> the entire test run — faster tests, consistent headers, no resource leaks."

---

### Q3 — Flaky test experience at Indeed

**STAR format:**
> "At Indeed we had async email delivery tests that intermittently failed —
> the service returned 200 (immediately processed) or 202 (queued).
> Both were valid responses. I updated assertions to accept status_in(200, 202),
> added retry with delay, and documented WHY both statuses are valid.
> Flaky rate dropped ~30% to near zero — my manager could trust the CI badge."

---

### Q4 — Claude Chat vs Claude Code

> "Claude Chat = architecture decisions and design pattern discussion.
> Claude Code = surgical fixes, running tests, fixing errors in terminal.
>
> Example: I used Claude Chat to design the CRTP base class FhirResource[T].
> When AI-generated tests had HAPI sandbox quirks, Claude Code fixed
> specific lines in 2 minutes vs 15 rounds of copy-pasting.
>
> Key guardrail: always tell Claude Code 'fix only this line, do not
> rewrite the file' — otherwise test counts drift."

---

### Q5 — Why healthtech? ⭐ STRONGEST ANSWER

> "My father was a family doctor — I grew up understanding how critical
> reliable health technology is for patients. Healthtech is rapidly growing
> and heavily relying on AI for quick solutions and health improvement.
> I'm building AI-powered test automation to support the health industry
> with stable, reliable products in the long run.
>
> My Deaf background also gives me a unique perspective on healthcare
> accessibility — I understand firsthand how critical reliable health
> technology is for patients who depend on it."

**Use this as your closing statement in every interview.**

---

### Quick Reference — Numbers to Remember

| Metric | Value |
|---|---|
| Total tests | 73 passed, 1 skipped |
| Domains | 4 (FHIR, Insurance, Fintech, PetStore) |
| AI-generated tests | 37 (10 FHIR + 12 Insurance + 15 Fintech) |
| Hand-crafted tests | 36 |
| CI jobs | 5 (all green) |
| Design patterns | Singleton, Facade, CRTP, Factory, Template Method, Fluent |

---

