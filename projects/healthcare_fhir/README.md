# Healthcare FHIR — API Test Suite

Phase 1 MVP: FHIR R4 Patient resource CRUD tests.

## Architecture

| Layer | File | Pattern |
|---|---|---|
| Config | `api/config/fhir_config.py` | Singleton |
| Client | `api/client/fhir_client.py` | Facade |
| Model | `api/models/patient.py` | CRTP + Pydantic |
| Factory | `api/data/fhir_factory.py` | Factory |
| Assertions | `api/assertions/fhir_validator.py` | Fluent |

## FHIR Server
Public HAPI R4 sandbox — runs out of the box, no credentials needed.
`https://hapi.fhir.org/baseR4`

## Running Tests
```bash
pytest projects/healthcare_fhir/api/tests/ -v
```

## Phase Roadmap
- Phase 1 ✅ — Patient CRUD (POST, GET, DELETE)
- Phase 2 🔜 — AI-powered test generation (Anthropic SDK)
- Phase 3 🔜 — Encounter + Observation resources
- Phase 4 🔜 — Playwright UI tests
