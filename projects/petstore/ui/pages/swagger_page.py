"""
swagger_page.py
---------------
Page Object Model for the Swagger PetStore UI.

Pattern : Page Object Model (POM) — extends BasePage
SOLID   : SRP — owns only Swagger UI locators and actions
          OCP — add new page sections without modifying existing methods

Target UI
---------
Swagger PetStore UI: https://petstore.swagger.io
Official interactive documentation for the PetStore REST API.
Same API tested in projects/petstore/api/tests/.

Testing context
---------------
UI testing the Swagger interface validates:
- The API documentation is accessible to developers
- Key resource sections (pet, store, user) are visible
- The interactive docs load correctly for developer experience
"""

from __future__ import annotations

from playwright.sync_api import Page

from projects.healthcare_fhir.ui.pages.base_page import BasePage


class SwaggerPage(BasePage):
    """
    Page object for the Swagger PetStore UI.

    Usage
    -----
        page = SwaggerPage(page)
        page.navigate_to_swagger()
        page.assert_title_contains("Swagger")
    """

    # ------------------------------------------------------------------ #
    #  URLs                                                                #
    # ------------------------------------------------------------------ #

    SWAGGER_URL = "https://petstore.swagger.io"

    # ------------------------------------------------------------------ #
    #  Navigation                                                          #
    # ------------------------------------------------------------------ #

    def navigate_to_swagger(self) -> None:
        """Navigate to the Swagger PetStore UI."""
        self.navigate(self.SWAGGER_URL)

    def wait_for_swagger_ui_render(self) -> None:
        """
        Wait for Swagger UI's client-side JS to finish rendering.

        The initial HTML is just a shell — resource sections (pet,
        store, user) are injected dynamically after the spec loads.
        """
        self._page.wait_for_load_state("networkidle")

    # ------------------------------------------------------------------ #
    #  Page state queries                                                  #
    # ------------------------------------------------------------------ #

    def get_page_title(self) -> str:
        """Return the browser tab title."""
        return self._page.title()

    def is_swagger_page(self) -> bool:
        """Return True if the current page is the Swagger UI."""
        return "petstore.swagger.io" in self._page.url

    def get_page_content(self) -> str:
        """Return the full page content."""
        return self._page.content()

    def page_contains_text(self, text: str) -> bool:
        """Return True if the given text appears anywhere on the page."""
        return text.lower() in self._page.content().lower()

    # ------------------------------------------------------------------ #
    #  Assertions (fluent)                                                 #
    # ------------------------------------------------------------------ #

    def assert_title_contains(self, text: str) -> "SwaggerPage":
        """Assert the page title contains the given text."""
        title = self._page.title()
        assert text.lower() in title.lower(), (
            f"Expected title to contain '{text}', got '{title}'."
        )
        return self

    def assert_url_contains(self, text: str) -> "SwaggerPage":
        """Assert the current URL contains the given text."""
        assert text in self._page.url, (
            f"Expected URL to contain '{text}', got '{self._page.url}'."
        )
        return self

    def assert_page_contains(self, text: str) -> "SwaggerPage":
        """Assert the page content contains the given text."""
        content = self._page.content().lower()
        assert text.lower() in content, (
            f"Expected page to contain '{text}'."
        )
        return self
