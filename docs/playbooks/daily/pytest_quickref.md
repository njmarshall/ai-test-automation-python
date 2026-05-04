# pytest Quick Reference

> Fast-recall cheatsheet for Senior SDET / Automation Architects  
> Stack: `pytest` · Python 3.9+ · pytest-playwright · pytest-xdist · pytest-cov

---

## Table of Contents
- [Installation](#installation)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Writing Tests](#writing-tests)
- [Assertions](#assertions)
- [Fixtures](#fixtures)
- [conftest.py](#conftestpy)
- [Markers](#markers)
- [Parametrize](#parametrize)
- [Mocking](#mocking)
- [Plugins](#plugins)
- [Parallel Execution](#parallel-execution)
- [Coverage](#coverage)
- [CLI Commands](#cli-commands)
- [Gotchas](#gotchas)
- [Quick Reference Card](#quick-reference-card)

---

## Installation

```bash
pip install pytest
pip install pytest-playwright       # UI testing
pip install pytest-xdist            # parallel execution
pip install pytest-cov              # coverage
pip install pytest-mock             # mocker fixture
pip install pytest-html             # HTML reports
pip install pytest-rerunfailures    # retry flaky tests
```

---

## Project Structure

```
ai-test-automation-python/
├── projects/
│   └── healthcare_fhir/
│       └── api/
│           ├── tests/
│           │   ├── conftest.py         # shared fixtures
│           │   ├── test_patient.py
│           │   └── test_observation.py
│           └── pages/                  # POM (UI tests)
├── shared/
│   └── fixtures/
│       └── base_fixtures.py
├── pytest.ini                          # or pyproject.toml
└── conftest.py                         # root-level fixtures
```

> ✅ Test files must be named `test_*.py` or `*_test.py`.  
> ✅ Test functions must be named `test_*`.  
> ✅ Test classes must be named `Test*` (no `__init__`).

---

## Configuration

### `pytest.ini`

```ini
[pytest]
testpaths       = projects
python_files    = test_*.py
python_classes  = Test*
python_functions= test_*
addopts         =
    --strict-markers
    --tb=short
    -ra
markers =
    smoke: smoke tests
    regression: regression suite
    fhir: FHIR-specific tests
    slow: tests that take > 5s
```

### `pyproject.toml`

```toml
[tool.pytest.ini_options]
testpaths       = ["projects"]
addopts         = "--strict-markers --tb=short -ra"
markers         = [
    "smoke: smoke tests",
    "regression: regression suite",
    "fhir: FHIR-specific tests",
]
```

---

## Writing Tests

```python
# Simplest test
def test_addition():
    assert 1 + 1 == 2

# Test class (no __init__ needed)
class TestPatientAPI:
    def test_get_patient_returns_200(self, api_client):
        response = api_client.get("/Patient/123")
        assert response.status_code == 200

    def test_patient_has_name(self, api_client):
        response = api_client.get("/Patient/123")
        data = response.json()
        assert "name" in data

# Expected exception
import pytest

def test_invalid_id_raises():
    with pytest.raises(ValueError, match="Invalid patient ID"):
        get_patient(-1)

# Expected warning
def test_deprecated_method():
    with pytest.warns(DeprecationWarning):
        old_method()

# Skip a test
@pytest.mark.skip(reason="endpoint not deployed yet")
def test_not_ready():
    ...

# Skip conditionally
@pytest.mark.skipif(sys.platform == "win32", reason="Linux only")
def test_linux_only():
    ...

# Expected failure
@pytest.mark.xfail(reason="known bug PW-123")
def test_known_bug():
    assert broken_function() == "expected"
```

---

## Assertions

pytest rewrites `assert` statements for rich failure output — no need for a special assertion library.

```python
# Equality
assert result == expected
assert result != unexpected

# Membership
assert "name" in response.json()
assert item not in collection

# Type
assert isinstance(result, dict)
assert isinstance(patient_id, str)

# Numeric
assert response.status_code == 200
assert len(patients) > 0
assert 0.0 <= score <= 1.0

# String
assert "Jane" in response.text
assert response.text.startswith("Patient")

# Approximate float
assert result == pytest.approx(3.14, rel=1e-3)

# None
assert result is None
assert result is not None

# Exception message
with pytest.raises(ValueError) as exc_info:
    validate_id(-1)
assert "Invalid" in str(exc_info.value)
```

---

## Fixtures

Fixtures provide setup/teardown and dependency injection.

```python
import pytest
import httpx

# Function scope (default) — fresh per test
@pytest.fixture
def api_client():
    client = httpx.Client(base_url="https://hapi.fhir.org/baseR4")
    yield client
    client.close()    # teardown

# Session scope — once per test session
@pytest.fixture(scope="session")
def auth_token():
    return get_token(os.environ["TEST_USER"], os.environ["TEST_PASS"])

# Module scope — once per test file
@pytest.fixture(scope="module")
def db_connection():
    conn = create_connection()
    yield conn
    conn.close()

# Fixture with params
@pytest.fixture(params=["chromium", "firefox", "webkit"])
def browser_type(request):
    return request.param

# Fixture using another fixture
@pytest.fixture
def authenticated_client(api_client, auth_token):
    api_client.headers["Authorization"] = f"Bearer {auth_token}"
    return api_client

# Autouse — runs for every test in scope without explicit request
@pytest.fixture(autouse=True)
def reset_db():
    yield
    db.rollback()
```

### Fixture scopes summary

| Scope | Lifetime | Use for |
|---|---|---|
| `function` | Per test (default) | Isolated state |
| `class` | Per test class | Shared class setup |
| `module` | Per test file | DB connections |
| `package` | Per package | Expensive resources |
| `session` | Entire run | Auth tokens, browsers |

---

## conftest.py

`conftest.py` is auto-discovered — no imports needed. Place at the right level.

```python
# conftest.py (root level — available everywhere)
import pytest
import os
import httpx

@pytest.fixture(scope="session")
def base_url():
    return os.environ.get("BASE_URL", "https://hapi.fhir.org/baseR4")

@pytest.fixture(scope="session")
def api_client(base_url):
    client = httpx.Client(base_url=base_url, timeout=30.0)
    yield client
    client.close()

# conftest.py (project-level — available within that project)
@pytest.fixture
def sample_patient():
    return {
        "resourceType": "Patient",
        "name": [{"family": "Doe", "given": ["Jane"]}],
        "birthDate": "1990-01-15"
    }
```

---

## Markers

```python
# Register in pytest.ini first (with --strict-markers)
# [pytest]
# markers = smoke, regression, fhir, slow

import pytest

@pytest.mark.smoke
def test_health_check(api_client):
    response = api_client.get("/metadata")
    assert response.status_code == 200

@pytest.mark.fhir
@pytest.mark.regression
def test_create_patient(api_client, sample_patient):
    response = api_client.post("/Patient", json=sample_patient)
    assert response.status_code == 201

# Run by marker
# pytest -m smoke
# pytest -m "fhir and not slow"
# pytest -m "smoke or regression"
```

---

## Parametrize

```python
import pytest

# Simple parametrize
@pytest.mark.parametrize("patient_id,expected_status", [
    ("123",   200),
    ("VALID", 200),
    ("",      404),
    ("-1",    400),
])
def test_get_patient(api_client, patient_id, expected_status):
    response = api_client.get(f"/Patient/{patient_id}")
    assert response.status_code == expected_status

# Multiple parametrize decorators (combinatorial)
@pytest.mark.parametrize("resource", ["Patient", "Observation", "Condition"])
@pytest.mark.parametrize("format_", ["json", "xml"])
def test_resource_formats(api_client, resource, format_):
    response = api_client.get(f"/{resource}?_format={format_}")
    assert response.status_code == 200

# Parametrize with IDs for readable output
@pytest.mark.parametrize("role,expected_path", [
    pytest.param("admin",  "/admin",     id="admin-lands-on-admin"),
    pytest.param("user",   "/dashboard", id="user-lands-on-dashboard"),
    pytest.param("viewer", "/view",      id="viewer-lands-on-view"),
])
def test_role_redirect(page, role, expected_path):
    ...

# Indirect parametrize (passes param through a fixture)
@pytest.mark.parametrize("auth_token", ["admin", "editor"], indirect=True)
def test_with_role(api_client, auth_token):
    ...
```

---

## Mocking

```python
from unittest.mock import patch, MagicMock
import pytest

# patch as decorator
@patch("mymodule.requests.get")
def test_api_call(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"id": "123"}
    result = fetch_patient("123")
    assert result["id"] == "123"
    mock_get.assert_called_once_with("https://api.example.com/Patient/123")

# patch as context manager
def test_api_error():
    with patch("mymodule.requests.get") as mock_get:
        mock_get.side_effect = ConnectionError("Network down")
        with pytest.raises(ConnectionError):
            fetch_patient("123")

# pytest-mock mocker fixture (cleaner)
def test_with_mocker(mocker):
    mock_get = mocker.patch("mymodule.requests.get")
    mock_get.return_value.status_code = 200
    result = fetch_patient("123")
    assert result is not None

# Mock a class method
def test_mock_class(mocker):
    mocker.patch.object(PatientService, "get_by_id", return_value={"id": "123"})
    service = PatientService()
    assert service.get_by_id("123")["id"] == "123"

# Spy (call through + track calls)
def test_spy(mocker):
    spy = mocker.spy(PatientService, "get_by_id")
    service = PatientService()
    service.get_by_id("123")
    spy.assert_called_once_with("123")
```

---

## Plugins

| Plugin | Purpose | Install |
|---|---|---|
| `pytest-playwright` | Browser automation | `pip install pytest-playwright` |
| `pytest-xdist` | Parallel execution | `pip install pytest-xdist` |
| `pytest-cov` | Code coverage | `pip install pytest-cov` |
| `pytest-mock` | Mocker fixture | `pip install pytest-mock` |
| `pytest-html` | HTML report | `pip install pytest-html` |
| `pytest-rerunfailures` | Retry flaky tests | `pip install pytest-rerunfailures` |
| `pytest-randomly` | Randomize test order | `pip install pytest-randomly` |
| `pytest-timeout` | Per-test timeout | `pip install pytest-timeout` |
| `pytest-env` | Set env vars in ini | `pip install pytest-env` |
| `pytest-asyncio` | Async test support | `pip install pytest-asyncio` |

---

## Parallel Execution

```bash
# Install
pip install pytest-xdist

# Run with N workers
pytest -n 4
pytest -n auto                    # one worker per CPU core

# Run with load balancing
pytest -n 4 --dist=loadfile      # group by file (default)
pytest -n 4 --dist=loadscope     # group by scope
pytest -n 4 --dist=no            # disable (serial)

# Combine with markers
pytest -n 4 -m smoke
```

```python
# Mark a test as not safe for parallel
@pytest.mark.run_only_once        # custom marker
@pytest.mark.xdist_group("group1")  # force group onto same worker
def test_db_reset():
    ...
```

---

## Coverage

```bash
# Run with coverage
pytest --cov=projects --cov-report=term-missing
pytest --cov=projects --cov-report=html        # generates htmlcov/
pytest --cov=projects --cov-report=xml         # for CI badge / SonarQube

# Fail if coverage below threshold
pytest --cov=projects --cov-fail-under=80

# Combine with parallel
pytest -n 4 --cov=projects --cov-report=term-missing
```

```ini
# .coveragerc
[run]
source = projects
omit =
    */tests/*
    */conftest.py
    */__init__.py

[report]
show_missing = True
skip_covered = False
```

---

## CLI Commands

```bash
# Run all tests
pytest

# Run a specific file
pytest projects/healthcare_fhir/api/tests/test_patient.py

# Run a specific test
pytest tests/test_patient.py::test_get_patient_returns_200

# Run a specific class
pytest tests/test_patient.py::TestPatientAPI

# Filter by name substring
pytest -k "patient"
pytest -k "patient and not slow"

# Run by marker
pytest -m smoke
pytest -m "fhir and regression"

# Verbose output
pytest -v
pytest -vv                        # extra verbose

# Stop after first failure
pytest -x

# Stop after N failures
pytest --maxfail=3

# Show local variables on failure
pytest -l

# Show print() output (no capture)
pytest -s
pytest --capture=no

# Rerun failed tests only
pytest --lf                       # last failed
pytest --ff                       # failed first, then rest

# Retry flaky tests
pytest --reruns 3 --reruns-delay 1

# Dry run (collect only, no execution)
pytest --collect-only

# Output formats
pytest --tb=short                 # short traceback (default)
pytest --tb=long                  # full traceback
pytest --tb=line                  # one line per failure
pytest --tb=no                    # no traceback

# HTML report
pytest --html=reports/report.html --self-contained-html

# Duration report (slowest tests)
pytest --durations=10
```

---

## Gotchas

### Don't use `__init__.py` in test directories

```
# WRONG — breaks pytest discovery
tests/
├── __init__.py
└── test_patient.py

# RIGHT
tests/
└── test_patient.py
```

### Fixture scope mismatch

```python
# WRONG — session fixture requesting function-scoped fixture
@pytest.fixture(scope="session")
def api_client(sample_patient):    # sample_patient is function-scoped — ERROR
    ...

# RIGHT — match or widen scope
@pytest.fixture(scope="session")
def sample_patient():
    return {"resourceType": "Patient", ...}
```

### `yield` fixture teardown always runs

```python
@pytest.fixture
def temp_patient(api_client):
    response = api_client.post("/Patient", json=sample)
    patient_id = response.json()["id"]
    yield patient_id
    api_client.delete(f"/Patient/{patient_id}")   # always runs, even on failure
```

### Avoid mutable default fixture values

```python
# WRONG — list shared across tests
@pytest.fixture
def patient_list():
    return []     # same object reused if scope > function

# RIGHT
@pytest.fixture
def patient_list():
    return list()  # or scope="function" (default)
```

---

## Quick Reference Card

| Command | Purpose |
|---|---|
| `pytest -v` | Verbose output |
| `pytest -x` | Stop on first failure |
| `pytest -k "name"` | Filter by test name |
| `pytest -m smoke` | Run by marker |
| `pytest --lf` | Rerun last failed only |
| `pytest -s` | Show print output |
| `pytest -n 4` | Run 4 parallel workers |
| `pytest --collect-only` | Dry run — list tests |
| `pytest --durations=10` | Show 10 slowest tests |
| `pytest --cov=src` | Run with coverage |
| `pytest --tb=short` | Short tracebacks |
| `pytest --reruns 3` | Retry flaky tests |

---

*Part of the [ai-test-automation-python](https://github.com/njmarshall/ai-test-automation-python) daily playbooks*
