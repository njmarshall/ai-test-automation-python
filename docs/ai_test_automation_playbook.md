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
