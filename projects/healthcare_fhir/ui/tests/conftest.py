"""
conftest.py
-----------
Pytest fixtures for the Healthcare FHIR UI test suite.

Fixture design
--------------
  browser_context : session-scoped — one browser context for the entire run
  page            : function-scoped — fresh page per test (clean state)
  fhir_explorer   : function-scoped — FhirExplorerPage injected into tests

SOLID / Pattern notes
---------------------
  DIP  : tests receive FhirExplorerPage via fixture — never instantiate it
  POM  : fixtures are the only place page objects are constructed
  SRP  : each fixture has one job

Playwright integration
----------------------
pytest-playwright provides built-in fixtures:
  playwright  — Playwright instance
  browser     — Browser instance (Chromium by default)
  page        — Page instance (used by pytest-playwright natively)

We wrap these with our own fixtures to inject our page objects cleanly.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from projects.healthcare_fhir.ui.pages.fhir_explorer_page import FhirExplorerPage


# ------------------------------------------------------------------ #
#  Browser — session-scoped (launched once per test run)              #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="session")
def browser_instance():
    """
    Launch a Chromium browser once for the entire test session.
    Closed automatically after all UI tests complete.
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        yield browser
        browser.close()


# ------------------------------------------------------------------ #
#  Browser context — function-scoped (isolated per test)              #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="function")
def browser_context(browser_instance: Browser) -> BrowserContext:  # type: ignore
    """
    Create a fresh browser context (like incognito) per test.
    Ensures tests are fully isolated — cookies, storage, auth.
    Closed automatically after each test.
    """
    context = browser_instance.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
    )
    yield context
    context.close()


# ------------------------------------------------------------------ #
#  Page — function-scoped (fresh tab per test)                        #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="function")
def ui_page(browser_context: BrowserContext) -> Page:             # type: ignore
    """
    Open a fresh browser tab for each test.
    Named ui_page to avoid collision with pytest-playwright's 'page' fixture.
    """
    page = browser_context.new_page()
    yield page
    page.close()


# ------------------------------------------------------------------ #
#  FhirExplorerPage — the page object injected into UI tests          #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="function")
def fhir_explorer(ui_page: Page) -> FhirExplorerPage:
    """
    Provide a FhirExplorerPage instance to UI tests.

    Tests receive this fixture and call high-level page methods —
    they never touch raw Playwright directly (DIP).
    """
    return FhirExplorerPage(ui_page)
