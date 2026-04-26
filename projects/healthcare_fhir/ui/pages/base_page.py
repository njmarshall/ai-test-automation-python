"""
base_page.py
------------
Page Object Model base class for all FHIR UI page objects.

Pattern : Template Method + Facade
          BasePage defines the shared navigation and interaction contract.
          Concrete pages (FhirExplorerPage, etc.) extend it with
          page-specific locators and actions.
SOLID   : SRP  — one class, one job: wrap Playwright page interactions
          OCP  — new pages extend BasePage without modifying it
          DIP  — UI tests depend on page objects, never raw Playwright

Java parallel
-------------
This is the Python equivalent of BasePage.java in your upgrade repo:
  upgrade/test/framework/ui/BasePage.java
Same philosophy — hide browser mechanics behind clean methods.
The key difference: no explicit WebDriverWait needed here.
Playwright auto-waits for elements to be visible and stable.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


class BasePage:
    """
    Abstract base for all FHIR UI page objects.

    Every concrete page receives a Playwright Page via constructor
    injection (DIP) — tests never instantiate Page directly.

    Auto-wait philosophy
    --------------------
    Playwright waits automatically for:
      - Element to be visible
      - Element to be enabled
      - Element to stop animating
    No explicit sleep() or wait_for_* needed in most cases.
    """

    # Default navigation timeout (ms) — overridable per page
    NAV_TIMEOUT  : int = 30_000
    # Default action timeout (ms)
    ACT_TIMEOUT  : int = 10_000

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------ #
    #  Navigation                                                          #
    # ------------------------------------------------------------------ #

    def navigate(self, url: str) -> None:
        """Navigate to a URL and wait for the page to load."""
        self._page.goto(url, timeout=self.NAV_TIMEOUT, wait_until="domcontentloaded")

    def get_title(self) -> str:
        """Return the current page title."""
        return self._page.title()

    def get_url(self) -> str:
        """Return the current page URL."""
        return self._page.url

    def wait_for_url(self, pattern: str) -> None:
        """Wait until the URL matches a pattern (string or regex)."""
        self._page.wait_for_url(pattern, timeout=self.NAV_TIMEOUT)

    # ------------------------------------------------------------------ #
    #  Element interactions                                                #
    # ------------------------------------------------------------------ #

    def click(self, selector: str) -> None:
        """Click an element by CSS selector."""
        self._page.locator(selector).click(timeout=self.ACT_TIMEOUT)

    def fill(self, selector: str, value: str) -> None:
        """Fill an input field by CSS selector."""
        self._page.locator(selector).fill(value, timeout=self.ACT_TIMEOUT)

    def get_text(self, selector: str) -> str:
        """Return the inner text of an element."""
        return self._page.locator(selector).inner_text()

    def is_visible(self, selector: str) -> bool:
        """Return True if the element is visible on the page."""
        return self._page.locator(selector).is_visible()

    def wait_for_selector(self, selector: str) -> None:
        """Wait for an element to appear in the DOM."""
        self._page.locator(selector).wait_for(
            state="visible",
            timeout=self.ACT_TIMEOUT,
        )

    # ------------------------------------------------------------------ #
    #  Screenshot helper (debug aid)                                       #
    # ------------------------------------------------------------------ #

    def screenshot(self, path: str) -> None:
        """Save a screenshot to the given path — useful for CI debugging."""
        self._page.screenshot(path=path, full_page=True)

    # ------------------------------------------------------------------ #
    #  Playwright expect — exposed for fluent assertions in tests          #
    # ------------------------------------------------------------------ #

    @property
    def expect(self):
        """Expose Playwright expect for use in tests via page object."""
        return expect
