"""
conftest.py
-----------
Pytest fixtures for the Insurance UI test suite.
Uses pytest-playwright built-in fixtures to avoid session conflicts.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import BrowserContext, Page

from projects.insurance.ui.pages.jsonplaceholder_page import JsonPlaceholderPage


@pytest.fixture(scope="function")
def insurance_browser_context(playwright) -> BrowserContext:  # type: ignore
    """Fresh browser context per test — uses pytest-playwright's playwright fixture."""
    browser = playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
    )
    yield context
    context.close()
    browser.close()


@pytest.fixture(scope="function")
def insurance_ui_page(insurance_browser_context: BrowserContext) -> Page:  # type: ignore
    """Fresh browser tab per test."""
    page = insurance_browser_context.new_page()
    yield page
    page.close()


@pytest.fixture(scope="function")
def jsonplaceholder_page(insurance_ui_page: Page) -> JsonPlaceholderPage:
    """Provide a JsonPlaceholderPage instance to UI tests."""
    return JsonPlaceholderPage(insurance_ui_page)
