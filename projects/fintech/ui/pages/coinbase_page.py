"""
coinbase_page.py
----------------
Page Object Model for the Coinbase public price page.

Pattern : Page Object Model (POM) — extends BasePage
SOLID   : SRP — owns only Coinbase UI locators and actions
          OCP — add new page sections without modifying existing methods

Target UI
---------
Coinbase public price page: https://www.coinbase.com/price
Shows live cryptocurrency prices — no auth required.

Locator strategy
----------------
Prefer text-based and role-based selectors over fragile CSS/XPath.
Playwright auto-waits so no explicit waits needed.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from projects.healthcare_fhir.ui.pages.base_page import BasePage


class CoinbasePage(BasePage):
    """
    Page object for the Coinbase public price page.

    Encapsulates all locators and actions for the Coinbase UI.
    Tests call high-level methods — never raw Playwright selectors.

    Usage
    -----
        page = CoinbasePage(page)
        page.navigate_to_prices()
        page.assert_title_contains("Coinbase")
    """

    # ------------------------------------------------------------------ #
    #  URLs                                                                #
    # ------------------------------------------------------------------ #

    PRICES_URL = "https://www.coinbase.com/price"
    BASE_URL   = "https://www.coinbase.com"

    # ------------------------------------------------------------------ #
    #  Navigation                                                          #
    # ------------------------------------------------------------------ #

    def navigate_to_prices(self) -> None:
        """Navigate to the Coinbase crypto price page."""
        self.navigate(self.PRICES_URL)

    # ------------------------------------------------------------------ #
    #  Page state queries                                                  #
    # ------------------------------------------------------------------ #

    def get_page_title(self) -> str:
        """Return the browser tab title."""
        return self._page.title()

    def is_coinbase_page(self) -> bool:
        """Return True if the current page is a Coinbase page."""
        return "coinbase.com" in self._page.url

    def page_contains_text(self, text: str) -> bool:
        """Return True if the given text appears anywhere on the page."""
        return text.lower() in self._page.content().lower()

    def get_page_content(self) -> str:
        """Return the full page content as text."""
        return self._page.content()

    # ------------------------------------------------------------------ #
    #  Assertions (fluent)                                                 #
    # ------------------------------------------------------------------ #

    def assert_title_contains(self, text: str) -> "CoinbasePage":
        """Assert the page title contains the given text."""
        title = self._page.title()
        assert text.lower() in title.lower(), (
            f"Expected page title to contain '{text}', got '{title}'."
        )
        return self

    def assert_url_contains(self, text: str) -> "CoinbasePage":
        """Assert the current URL contains the given text."""
        assert text in self._page.url, (
            f"Expected URL to contain '{text}', got '{self._page.url}'."
        )
        return self

    def assert_page_contains(self, text: str) -> "CoinbasePage":
        """Assert the page content contains the given text."""
        content = self._page.content().lower()
        assert text.lower() in content, (
            f"Expected page to contain '{text}'."
        )
        return self

    def assert_crypto_name_visible(self, name: str) -> "CoinbasePage":
        """Assert a cryptocurrency name is visible on the page."""
        content = self._page.content()
        assert name in content, (
            f"Expected '{name}' to be visible on the Coinbase price page."
        )
        return self
