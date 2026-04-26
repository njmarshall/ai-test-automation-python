"""
fhir_explorer_page.py
---------------------
Page Object Model for the HAPI FHIR web explorer UI.

Pattern : Page Object Model (POM) — extends BasePage
SOLID   : SRP — owns only HAPI FHIR UI locators and actions
          OCP — add new page sections (Encounter explorer, etc.)
                without modifying existing methods

Target UI
---------
HAPI FHIR public R4 sandbox: https://hapi.fhir.org
The explorer UI lets users:
  - Search for FHIR resources (Patient, Encounter, Observation)
  - View individual resource JSON
  - Navigate the FHIR capability statement
  - Browse server metadata

Locator strategy
----------------
Prefer role-based and text-based selectors over CSS/XPath.
Playwright auto-waits so no explicit waits are needed.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

from projects.healthcare_fhir.ui.pages.base_page import BasePage


class FhirExplorerPage(BasePage):
    """
    Page object for the HAPI FHIR R4 web explorer.

    Encapsulates all locators and actions for the HAPI FHIR UI.
    Tests call high-level methods like search_for_resource() —
    they never touch raw Playwright selectors directly.

    Usage
    -----
        explorer = FhirExplorerPage(page)
        explorer.navigate_to_home()
        explorer.search_for_resource("Patient")
    """

    # ------------------------------------------------------------------ #
    #  URLs                                                                #
    # ------------------------------------------------------------------ #

    BASE_URL         = "https://hapi.fhir.org"
    HOME_URL         = "https://hapi.fhir.org/baseR4"
    CAPABILITY_URL   = "https://hapi.fhir.org/baseR4/metadata?_pretty=true"

    # ------------------------------------------------------------------ #
    #  Locators (CSS / role / text)                                        #
    # ------------------------------------------------------------------ #

    # Navigation
    _NAV_SEARCH_INPUT  = "input[name='query'], input[type='search'], input[placeholder*='earch']"
    _NAV_LOGO          = "a.navbar-brand, .navbar-brand"

    # Resource type links in the capability statement
    _RESOURCE_TYPE_ROW = "table tbody tr"

    # JSON viewer
    _JSON_CONTENT      = "pre, code, .json-content, #json"

    # Server info banner
    _SERVER_BANNER     = ".jumbotron, .hero, h1, .server-title"

    # ------------------------------------------------------------------ #
    #  Navigation actions                                                  #
    # ------------------------------------------------------------------ #

    def navigate_to_home(self) -> None:
        """Navigate to the HAPI FHIR R4 base URL."""
        self.navigate(self.HOME_URL)

    def navigate_to_capability_statement(self) -> None:
        """Navigate directly to the FHIR capability statement."""
        self.navigate(self.CAPABILITY_URL)

    def navigate_to_patient_search(self) -> None:
        """Navigate to the Patient search page."""
        self.navigate(f"{self.HOME_URL}/Patient?_pretty=true&_count=5")

    def navigate_to_resource(self, resource_type: str, resource_id: str) -> None:
        """Navigate directly to a specific FHIR resource by type and id."""
        self.navigate(
            f"{self.HOME_URL}/{resource_type}/{resource_id}?_pretty=true"
        )

    # ------------------------------------------------------------------ #
    #  Page state queries                                                  #
    # ------------------------------------------------------------------ #

    def get_page_title(self) -> str:
        """Return the browser tab title."""
        return self._page.title()

    def is_fhir_page(self) -> bool:
        """Return True if the current page is a HAPI FHIR page."""
        return "hapi.fhir.org" in self._page.url

    def get_response_body_text(self) -> str:
        """
        Return the raw text content of the FHIR JSON response body.
        Works for both pretty-printed JSON pages and plain text responses.
        """
        try:
            return self._page.locator("pre").first.inner_text(timeout=8_000)
        except Exception:
            return self._page.content()

    def page_contains_text(self, text: str) -> bool:
        """Return True if the given text appears anywhere on the page."""
        return text in self._page.content()

    def get_resource_type_from_response(self) -> str:
        """
        Extract the resourceType value from a FHIR JSON response page.
        Returns empty string if not found.
        """
        body = self.get_response_body_text()
        import re
        match = re.search(r'"resourceType"\s*:\s*"([^"]+)"', body)
        return match.group(1) if match else ""

    def get_resource_id_from_response(self) -> str:
        """
        Extract the id value from a FHIR JSON response page.
        Returns empty string if not found.
        """
        body = self.get_response_body_text()
        import re
        match = re.search(r'"id"\s*:\s*"([^"]+)"', body)
        return match.group(1) if match else ""

    def get_bundle_total(self) -> int:
        """
        Extract the total count from a FHIR Bundle response.
        Returns -1 if not found.
        """
        body = self.get_response_body_text()
        import re
        match = re.search(r'"total"\s*:\s*(\d+)', body)
        return int(match.group(1)) if match else -1

    # ------------------------------------------------------------------ #
    #  Assertions (fluent — return self for chaining)                      #
    # ------------------------------------------------------------------ #

    def assert_title_contains(self, text: str) -> "FhirExplorerPage":
        """Assert the page title contains the given text."""
        assert text in self._page.title(), (
            f"Expected page title to contain '{text}', got '{self._page.title()}'."
        )
        return self

    def assert_url_contains(self, text: str) -> "FhirExplorerPage":
        """Assert the current URL contains the given text."""
        assert text in self._page.url, (
            f"Expected URL to contain '{text}', got '{self._page.url}'."
        )
        return self

    def assert_response_contains(self, text: str) -> "FhirExplorerPage":
        """Assert the FHIR JSON response body contains the given text."""
        body = self.get_response_body_text()
        assert text in body, (
            f"Expected response body to contain '{text}'.\n"
            f"Body preview: {body[:400]}"
        )
        return self

    def assert_resource_type(self, expected: str) -> "FhirExplorerPage":
        """Assert the resourceType in the response matches expected."""
        actual = self.get_resource_type_from_response()
        assert actual == expected, (
            f"Expected resourceType '{expected}', got '{actual}'."
        )
        return self
