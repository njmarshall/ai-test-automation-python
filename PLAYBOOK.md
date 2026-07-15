# 📖 Framework Playbook

> **Quick reference for contributors and interviewers.**
> For the full deep-dive, see the
> [ai-test-automation-playbook](https://github.com/njmarshall/playbook/blob/main/ai/ai-test-automation-playbook.md)
> in the playbook repo.

---

## At a Glance

| Item | Detail |
|------|--------|
| **Tests** | 90 passing across 4 domains |
| **Language** | Python 3.11+ |
| **HTTP Client** | httpx (sync + async) |
| **Models** | Pydantic v2 (CRTP pattern) |
| **Test Runner** | pytest |
| **UI Tests** | Playwright |
| **CI** | GitHub Actions (domain matrix) |
| **AI Co-Pilot** | Anthropic Claude (Chat + Code) |

---

## 5-Layer Architecture

```
Layer 5 — Fluent Assertions       framework/assertions/fluent_assert.py
Layer 4 — Factory                 domains/<domain>/factory/
Layer 3 — CRTP Pydantic Models    domains/<domain>/models/  +  framework/models/
Layer 2 — Facade (HTTP Client)    domains/<domain>/client/
Layer 1 — Singleton (Session)     framework/http/base_client.py
                                  framework/config/fhir_config.py
```

Each layer has one job. Tests call the Facade — never raw HTTP.

---

## Domain Map

| Domain | Tests | API | Key Pattern |
|--------|-------|-----|-------------|
| `healthcare_fhir` | ~35 | HAPI FHIR R4 | CRTP models · AsyncPoller · 202 pattern |
| `insurance` | ~20 | Internal mock | Claim lifecycle state machine |
| `fintech` | ~20 | Internal mock | Async 202 · `status_in` fix |
| `petstore` | ~15 | Swagger Petstore | Baseline CRUD · Fluent assertions |

---

## Run Tests

```bash
# All tests
pytest

# Single domain
pytest domains/healthcare_fhir/tests/ -v

# By marker
pytest -m "healthcare_fhir" -v

# With coverage
pytest --cov=framework --cov=domains --cov-report=html

# Playwright UI tests
pytest tests/ui/ --headed
```

---

## Add a New Domain — Checklist

```
□ mkdir -p domains/<name>/{models,client,factory,tests}
□ Add __init__.py files
□ Define model  → extends BaseResource["ModelName"]
□ Define client → uses BaseHttpClient.session()
□ Define factory → static builder methods with sensible defaults
□ Add conftest.py with session-scoped client + function-scoped factory
□ Write ≥5 tests: happy path, search, create, error case, edge case
□ Add marker to pytest.ini
□ Add domain to .github/workflows/ci.yml matrix
□ Update this file's domain count
```

Full walkthrough →
[Adding a New Domain](https://github.com/njmarshall/playbook/blob/main/ai/ai-test-automation-playbook.md#part-4--how-to-add-a-new-domain)

---

## Key Design Decisions

**Singleton** — `lru_cache(maxsize=1)` on config classmethod.
One TLS session per test run, not one per test.

**CRTP** — `Patient(BaseResource["Patient"])` gives type-safe
`from_dict()` returning the concrete type via `Self`.
No casting, no `Any`.

**AsyncPoller `status_in`** — Accepts a list of terminal states
(`["completed", "failed"]`), not a single string.
Derived from the Indeed ~30% flakiness fix.

**Claude as co-pilot** — Chat for architecture decisions,
Code for surgical test fixes. Architecture stays the engineer's.

---

## Interview: The 5 Talking Points

1. **Repo overview** — 90 tests, 4 domains, 5-layer AI co-pilot architecture
2. **Singleton** — `lru_cache` on classmethod, one session per run
3. **Async 202 fix** — `status_in` list, derived from Indeed flakiness story
4. **Claude dual-mode** — Chat for design, Code for targeted fixes
5. **StalenessDetector** — AST scan + LLM suggestion = agentic self-healing

Full talking points with scripts →
[Interview Section](https://github.com/njmarshall/playbook/blob/main/ai/ai-test-automation-playbook.md#part-7--interview-talking-points)

---

## Related

| Resource | Link |
|----------|------|
| Full playbook | [playbook/ai/ai-test-automation-playbook.md](https://github.com/njmarshall/playbook/blob/main/ai/ai-test-automation-playbook.md) |
| API resilience | [playbook/career/api-resilience-playbook.md](https://github.com/njmarshall/playbook/blob/main/career/api-resilience-playbook.md) |
| FHIR patterns | [playbook/fhir/04-fhir-in-testing.md](https://github.com/njmarshall/playbook/blob/main/fhir/04-fhir-in-testing.md) |
| Interview prep | [playbook/career/interview-prep.md](https://github.com/njmarshall/playbook/blob/main/career/interview-prep.md) |

---

*90 tests · 4 domains · 5 layers · 1 AI co-pilot*
