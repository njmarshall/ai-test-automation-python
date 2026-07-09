"""
conftest.py
-----------
Pytest fixtures for the Fintech UI test suite.
Reuses the same browser fixture pattern as healthcare_fhir UI tests.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright

from projects.fintech.ui.pages.coinbase_page import CoinbasePage


@pytest.fixture(scope="session")
def fintech_browser_instance(playwright: Playwright) -> Browser:  # type: ignore
    """
    Launch Chromium once for the entire test session.

    Reuses pytest-playwright's session-scoped `playwright` fixture rather
    than calling sync_playwright() directly — Playwright's sync API only
    allows one driver loop per thread, so a second manual sync_playwright()
    call (e.g. from the healthcare_fhir UI conftest) would raise
    "using Playwright Sync API inside the asyncio loop" when both suites
    run in the same pytest session.
    """
    browser = playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    yield browser
    browser.close()


@pytest.fixture(scope="function")
def fintech_browser_context(fintech_browser_instance: Browser) -> BrowserContext:  # type: ignore
    """Fresh browser context per test."""
    context = fintech_browser_instance.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    )
    yield context
    context.close()


@pytest.fixture(scope="function")
def fintech_ui_page(fintech_browser_context: BrowserContext) -> Page:  # type: ignore
    """Fresh browser tab per test."""
    page = fintech_browser_context.new_page()
    yield page
    page.close()


@pytest.fixture(scope="function")
def coinbase_page(fintech_ui_page: Page) -> CoinbasePage:
    """Provide a CoinbasePage instance to UI tests."""
    return CoinbasePage(fintech_ui_page)
