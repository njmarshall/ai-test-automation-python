# Playwright — Python Quick Reference

> Fast-recall cheatsheet for Senior SDET / Automation Architects  
> Stack: `playwright` · Python 3.9+ · pytest-playwright · sync & async API

---

## Table of Contents
- [Installation](#installation)
- [Core API — Sync](#core-api--sync)
- [Locators](#locators)
- [Assertions](#assertions)
- [Waiting Strategies](#waiting-strategies)
- [pytest-playwright](#pytest-playwright)
- [Page Object Model](#page-object-model)
- [Custom Fixtures](#custom-fixtures)
- [Auth & storageState](#auth--storagestate)
- [API Testing](#api-testing)
- [Network Mocking](#network-mocking)
- [Advanced Patterns](#advanced-patterns)
- [Async API](#async-api)
- [Gotchas](#gotchas)
- [CLI Commands](#cli-commands)

---

## Installation

```bash
pip install pytest-playwright
playwright install              # installs Chromium, Firefox, WebKit

# Or standalone (no pytest)
pip install playwright
python -m playwright install
```

### `pytest.ini` / `pyproject.toml`

```ini
# pytest.ini
[pytest]
addopts = --browser chromium --headed
base_url = http://localhost:3000
```

```toml
# pyproject.toml
[tool.pytest.ini_options]
addopts = "--browser chromium"
```

---

## Core API — Sync

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(base_url="https://example.com")
    page    = context.new_page()

    # Navigation
    page.goto("/login")
    page.goto("https://example.com", wait_until="networkidle")
    page.go_back()
    page.reload()

    # Actions
    page.get_by_role("button", name="Submit").click()
    page.get_by_label("Email").fill("user@example.com")
    page.get_by_label("Password").fill("s3cret")
    page.get_by_role("combobox").select_option("CA")
    page.get_by_label("Remember me").check()
    page.get_by_role("menuitem", name="Products").hover()
    page.locator("#source").drag_to(page.locator("#target"))

    browser.close()
```

---

## Locators

```python
# Preferred — semantic / a11y-based
page.get_by_role("button", name="Submit")
page.get_by_label("Email address")
page.get_by_placeholder("Search...")
page.get_by_text("Welcome back")
page.get_by_test_id("submit-btn")           # data-testid="submit-btn"

# CSS / XPath fallback
page.locator("css=.btn-primary")
page.locator("xpath=//button[@type='submit']")

# Chaining (scope to parent)
page.get_by_role("dialog").get_by_role("button", name="Confirm")

# nth (avoid if possible)
page.get_by_role("button", name="Edit").nth(0)

# Filter by text
page.get_by_role("listitem").filter(has_text="Jane Doe")
```

---

## Assertions

All `expect()` calls auto-wait/retry up to assertion timeout (default 5s).

```python
from playwright.sync_api import expect

# Page assertions
expect(page).to_have_url("/dashboard")
expect(page).to_have_title(re.compile("Dashboard"))

# Locator assertions
btn = page.get_by_role("button", name="Save")
expect(btn).to_be_visible()
expect(btn).to_be_enabled()
expect(btn).to_be_disabled()
expect(btn).to_have_text("Save changes")
expect(btn).to_have_attribute("aria-label", "Save")
expect(btn).to_have_count(1)

# Negative
expect(page.get_by_text("Error")).not_to_be_visible()

# Count
expect(page.get_by_role("listitem")).to_have_count(5)
```

---

## Waiting Strategies

> ⚠️ Avoid `page.wait_for_timeout()` — flakiness trap.

```python
# Auto-waiting — just use locator actions
page.get_by_role("button").click()                    # waits for actionable

# Wait for element state
page.get_by_text("Loading...").wait_for(state="hidden")
page.locator(".toast").wait_for(state="visible")

# Wait for URL after action
page.get_by_role("button", name="Login").click()
page.wait_for_url("**/dashboard")

# Wait for specific response
with page.expect_response(
    lambda r: "/api/user" in r.url and r.status == 200
) as resp_info:
    page.get_by_role("button", name="Load").click()
response = resp_info.value

# Wait for request
with page.expect_request(
    lambda r: "/api/save" in r.url and r.method == "POST"
) as req_info:
    page.get_by_role("button", name="Save").click()
body = req_info.value.post_data_json()
```

---

## pytest-playwright

`pytest-playwright` provides built-in fixtures: `playwright`, `browser`, `context`, `page`.

```python
# conftest.py — configure context options
import pytest

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "base_url": "https://staging.example.com",
        "record_video_dir": "build/videos/",
    }
```

```python
# test_login.py — use page fixture directly
from playwright.sync_api import Page, expect

def test_valid_login(page: Page):
    page.goto("/login")
    page.get_by_label("Email").fill("user@test.com")
    page.get_by_label("Password").fill("pass123")
    page.get_by_role("button", name="Log in").click()
    expect(page).to_have_url("/dashboard")
```

### Run options

```bash
pytest --browser chromium
pytest --browser firefox
pytest --browser webkit
pytest --headed                             # visible browser
pytest --slowmo 500                         # slow down 500ms
pytest -k "test_login"                      # filter by name
pytest --tracing on                         # always capture trace
pytest --screenshot only-on-failure
pytest --video retain-on-failure
```

---

## Page Object Model

```python
# pages/login_page.py
from playwright.sync_api import Page, Locator

class LoginPage:
    def __init__(self, page: Page) -> None:
        self.page          = page
        self.email_input   = page.get_by_label("Email")
        self.password_input = page.get_by_label("Password")
        self.submit_btn    = page.get_by_role("button", name="Log in")

    def goto(self) -> None:
        self.page.goto("/login")

    def login(self, email: str, password: str) -> None:
        self.email_input.fill(email)
        self.password_input.fill(password)
        self.submit_btn.click()
```

---

## Custom Fixtures

```python
# conftest.py
import pytest
import os
from playwright.sync_api import Page
from pages.login_page import LoginPage

@pytest.fixture
def login_page(page: Page) -> LoginPage:
    return LoginPage(page)

@pytest.fixture
def authenticated_page(page: Page) -> Page:
    """Log in and return a ready-to-use page."""
    page.goto("/login")
    page.get_by_label("Email").fill(os.environ["TEST_USER"])
    page.get_by_label("Password").fill(os.environ["TEST_PASS"])
    page.get_by_role("button", name="Log in").click()
    page.wait_for_url("**/dashboard")
    return page

# Usage in test:
def test_dashboard_loads(authenticated_page: Page):
    expect(authenticated_page.get_by_heading("Dashboard")).to_be_visible()
```

---

## Auth & storageState

```python
# scripts/save_auth.py — run once to produce auth.json
import os
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context()
    page    = context.new_page()

    page.goto(os.environ["BASE_URL"] + "/login")
    page.get_by_label("Email").fill(os.environ["TEST_USER"])
    page.get_by_label("Password").fill(os.environ["TEST_PASS"])
    page.get_by_role("button", name="Log in").click()
    page.wait_for_url("**/dashboard")

    context.storage_state(path="auth.json")
    browser.close()
```

```python
# conftest.py — reuse in all tests
@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "storage_state": "auth.json"}
```

### Multi-role pattern

```python
# conftest.py
@pytest.fixture(params=["admin", "editor", "viewer"])
def role_context(browser, request):
    context = browser.new_context(
        storage_state=f"auth/{request.param}.json"
    )
    yield context, request.param
    context.close()
```

---

## API Testing

```python
from playwright.sync_api import APIRequestContext, expect as api_expect

def test_get_patients(request: APIRequestContext):
    response = request.get("/api/patients")
    assert response.status == 200
    body = response.json()
    assert "data" in body

def test_create_patient(request: APIRequestContext):
    response = request.post("/api/patients", data={
        "name": "Jane Doe",
        "dob": "1990-01-15"
    })
    assert response.status == 201
```

### Hybrid API + UI test

```python
def test_patient_appears_in_ui(page: Page, request: APIRequestContext):
    # Seed via API
    resp = request.post("/api/patients", data={"name": "Test Patient"})
    patient_id = resp.json()["id"]

    # Assert in UI
    page.goto("/patients")
    expect(page.get_by_text("Test Patient")).to_be_visible()

    # Cleanup
    request.delete(f"/api/patients/{patient_id}")
```

---

## Network Mocking

```python
# Mock a 500 error
page.route("**/api/patients", lambda route: route.fulfill(
    status=500,
    content_type="application/json",
    body='{"error": "Internal Server Error"}'
))

# Abort (block analytics)
page.route("**/*.analytics.js", lambda route: route.abort())

# Intercept + modify real response
def modify_config(route):
    response = route.fetch()
    body = response.json()
    body["featureFlag"] = True
    route.fulfill(response=response, json=body)

page.route("**/api/config", modify_config)

# HAR replay
page.route_from_har("fixtures/api.har", not_found="fallback")
```

---

## Advanced Patterns

### Data-driven with `@pytest.mark.parametrize`

```python
import pytest
from playwright.sync_api import Page, expect

@pytest.mark.parametrize("email,password,expected", [
    ("admin@test.com",  "admin123",  "/admin"),
    ("user@test.com",   "user123",   "/dashboard"),
    ("viewer@test.com", "viewer123", "/view"),
])
def test_login_redirects(page: Page, email: str, password: str, expected: str):
    page.goto("/login")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Log in").click()
    expect(page).to_have_url(expected)
```

### Visual regression

```python
def test_dashboard_layout(page: Page, assert_snapshot):
    page.goto("/dashboard")
    assert_snapshot(page.screenshot(full_page=True), "dashboard.png")

# Or with built-in:
def test_dashboard_screenshot(page: Page):
    page.goto("/dashboard")
    page.screenshot(path="snapshots/dashboard.png", full_page=True)
    # Compare with pytest-image-diff or pixelmatch
```

### iFrames

```python
iframe = page.frame_locator("#sandbox-iframe")
iframe.get_by_role("button", name="Agree").click()
expect(iframe.get_by_text("Accepted")).to_be_visible()
```

### File upload / download

```python
# Upload
with page.expect_file_chooser() as fc_info:
    page.get_by_label("Upload file").click()
file_chooser = fc_info.value
file_chooser.set_files("tests/fixtures/sample.pdf")

# Download
with page.expect_download() as dl_info:
    page.get_by_role("link", name="Export CSV").click()
download = dl_info.value
download.save_as(f"build/downloads/{download.suggested_filename}")
```

### Mobile emulation

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    iphone = p.devices["iPhone 12"]
    context = p.webkit.launch().new_context(**iphone)
    page = context.new_page()
    page.goto("https://example.com")
```

```python
# pytest: conftest.py
@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, playwright):
    iphone = playwright.devices["iPhone 12"]
    return {**browser_context_args, **iphone}
```

### CI sharding with pytest-xdist

```bash
# Run 4 workers in parallel
pytest -n 4

# Or split manually by node id
pytest --shard-id=1 --num-shards=4     # needs pytest-shard plugin
```

---

## Async API

```python
import asyncio
from playwright.async_api import async_playwright, expect

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page    = await browser.new_page()

        await page.goto("https://example.com")
        await page.get_by_role("button", name="Submit").click()
        await expect(page).to_have_url("/success")

        await browser.close()

asyncio.run(main())
```

```python
# pytest-asyncio integration
import pytest
from playwright.async_api import Page, expect

@pytest.mark.asyncio
async def test_async_login(page: Page):
    await page.goto("/login")
    await page.get_by_label("Email").fill("user@test.com")
    await page.get_by_role("button", name="Log in").click()
    await expect(page).to_have_url("/dashboard")
```

---

## Gotchas

### Strict mode — multiple matches

```python
# Throws if 2+ buttons named 'Edit' exist
page.get_by_role("button", name="Edit").click()  # Error!

# Fix: scope to parent
page.get_by_role("row", name="Jane Doe") \
    .get_by_role("button", name="Edit") \
    .click()
```

### Sync vs async — don't mix

```python
# WRONG — mixing sync page in async test
async def test_bad(page):
    page.goto("/login")    # sync call in async context — deadlock

# RIGHT — use async page
async def test_good(page):
    await page.goto("/login")
```

### Use `with` or explicit close

```python
# WRONG — resource leak
playwright = sync_playwright().start()
browser = playwright.chromium.launch()
# ... forgot to close

# RIGHT
with sync_playwright() as p:
    browser = p.chromium.launch()
    # auto-closes on exit
```

### Debugging

```bash
# Open Playwright Inspector (headed + paused)
PWDEBUG=1 pytest test_login.py

# Record test via codegen
playwright codegen https://example.com

# Open trace viewer
playwright show-trace build/traces/test_login.zip

# Slow down for visual debugging
pytest --slowmo 1000
```

---

## CLI Commands

| Command | Purpose |
|---|---|
| `pytest` | Run all tests |
| `pytest -k "login"` | Filter by name |
| `pytest --browser firefox` | Single browser |
| `pytest --headed` | Visible browser |
| `pytest --tracing on` | Capture traces always |
| `pytest --update-snapshots` | Refresh visual baselines |
| `playwright install` | Install/update browsers |
| `playwright codegen <url>` | Record test by clicking |
| `playwright show-trace <file>` | Open trace viewer |
| `playwright screenshot <url> out.png` | Quick screenshot |

---

## Sync vs Async — Quick Comparison

| Feature | Sync API | Async API |
|---|---|---|
| Import | `playwright.sync_api` | `playwright.async_api` |
| Launch | `p.chromium.launch()` | `await p.chromium.launch()` |
| Navigate | `page.goto(url)` | `await page.goto(url)` |
| Click | `locator.click()` | `await locator.click()` |
| Best for | pytest, scripts | FastAPI, aiohttp, async frameworks |

---

*Part of the [ai-test-automation-python](https://github.com/njmarshall/ai-test-automation-python) portfolio*
