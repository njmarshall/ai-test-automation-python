"""
conftest.py
-----------
Pytest fixtures for the PetStore UI test suite.
Uses pytest-playwright built-in fixtures to avoid session conflicts.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import BrowserContext, Page

from projects.petstore.ui.pages.swagger_page import SwaggerPage


@pytest.fixture(scope="function")
def petstore_browser_context(playwright) -> BrowserContext:  # type: ignore
    """Fresh browser context per test."""
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
def petstore_ui_page(petstore_browser_context: BrowserContext) -> Page:  # type: ignore
    """Fresh browser tab per test."""
    page = petstore_browser_context.new_page()
    yield page
    page.close()


@pytest.fixture(scope="function")
def swagger_page(petstore_ui_page: Page) -> SwaggerPage:
    """Provide a SwaggerPage instance to UI tests."""
    return SwaggerPage(petstore_ui_page)
