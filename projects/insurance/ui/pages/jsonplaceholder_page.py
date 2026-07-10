"""
jsonplaceholder_page.py
-----------------------
Page Object Model for the JSONPlaceholder public API documentation page.

Pattern : Page Object Model (POM) — extends BasePage
SOLID   : SRP — owns only JSONPlaceholder UI locators and actions
          OCP — add new page sections without modifying existing methods

Target UI
---------
JSONPlaceholder: https://jsonplaceholder.typicode.com
Free fake REST API for testing — same backend used for Insurance API tests.
The website documents all available endpoints including /posts (our policies).

Insurance context
-----------------
Testing the JSONPlaceholder UI bridges our Insurance API tests with UI layer:
- Verifies the mock backend documentation is accessible
- Confirms /posts endpoint is documented (our Insurance Policy resource)
- Validates the developer experience of the API we're testing against
"""

from __future__ import annotations

from playwright.sync_api import Page

from projects.healthcare_fhir.ui.pages.base_page import BasePage


class JsonPlaceholderPage(BasePage):
    """
    Page object for the JSONPlaceholder public documentation page.

    Usage
    -----
        page = JsonPlaceholderPage(page)
        page.navigate_to_home()
        page.assert_title_contains("JSONPlaceholder")
    """

    # ------------------------------------------------------------------ #
    #  URLs                                                                #
    # ------------------------------------------------------------------ #

    HOME_URL  = "https://jsonplaceholder.typicode.com"
    POSTS_URL = "https://jsonplaceholder.typicode.com/posts"

    # ------------------------------------------------------------------ #
    #  Navigation                                                          #
    # ------------------------------------------------------------------ #

    def navigate_to_home(self) -> None:
        """Navigate to the JSONPlaceholder home page."""
        self.navigate(self.HOME_URL)

    def navigate_to_posts(self) -> None:
        """Navigate to the /posts endpoint directly in browser."""
        self.navigate(self.POSTS_URL)

    # ------------------------------------------------------------------ #
    #  Page state queries                                                  #
    # ------------------------------------------------------------------ #

    def get_page_title(self) -> str:
        """Return the browser tab title."""
        return self._page.title()

    def is_jsonplaceholder_page(self) -> bool:
        """Return True if the current page is JSONPlaceholder."""
        return "jsonplaceholder.typicode.com" in self._page.url

    def get_page_content(self) -> str:
        """Return the full page content."""
        return self._page.content()

    def page_contains_text(self, text: str) -> bool:
        """Return True if the given text appears anywhere on the page."""
        return text.lower() in self._page.content().lower()

    # ------------------------------------------------------------------ #
    #  Assertions (fluent)                                                 #
    # ------------------------------------------------------------------ #

    def assert_title_contains(self, text: str) -> "JsonPlaceholderPage":
        """Assert the page title contains the given text."""
        title = self._page.title()
        assert text.lower() in title.lower(), (
            f"Expected title to contain '{text}', got '{title}'."
        )
        return self

    def assert_url_contains(self, text: str) -> "JsonPlaceholderPage":
        """Assert the current URL contains the given text."""
        assert text in self._page.url, (
            f"Expected URL to contain '{text}', got '{self._page.url}'."
        )
        return self

    def assert_page_contains(self, text: str) -> "JsonPlaceholderPage":
        """Assert the page content contains the given text."""
        content = self._page.content().lower()
        assert text.lower() in content, (
            f"Expected page to contain '{text}'."
        )
        return self
