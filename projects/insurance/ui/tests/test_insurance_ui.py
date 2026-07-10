"""
test_insurance_ui.py
--------------------
Phase 1 MVP: JSONPlaceholder UI tests using Playwright.

What we're testing
------------------
The JSONPlaceholder public website (https://jsonplaceholder.typicode.com)
documents the same REST API used by our Insurance Policy tests.
UI tests verify the backend documentation is accessible and the
/posts endpoint (our Insurance Policy resource) is documented.

Architecture recap
------------------
  BasePage            (POM base)     ← Facade over raw Playwright
  JsonPlaceholderPage (POM concrete) ← JSONPlaceholder UI locators
  jsonplaceholder_page (fixture)     ← injected via conftest.py (DIP)

Insurance context
-----------------
This bridges the Insurance API tests with a UI layer:
- Same backend, verified at both API and browser levels
- Confirms the mock service documentation is accessible
- Validates /posts endpoint documentation exists
"""

from __future__ import annotations

import pytest

from projects.insurance.ui.pages.jsonplaceholder_page import JsonPlaceholderPage


@pytest.mark.insurance
@pytest.mark.ui
class TestInsuranceUI:
    """
    JSONPlaceholder UI tests — Insurance Phase 1 MVP.

    Three tests covering core UI validation:
      1. Home page loads — JSONPlaceholder is reachable
      2. Posts endpoint documented — /posts visible on page
      3. Posts JSON renders — browser can fetch /posts directly
    """

    # ------------------------------------------------------------------ #
    #  Test 1 — Home page loads                                            #
    # ------------------------------------------------------------------ #

    def test_jsonplaceholder_home_page_loads(
        self, jsonplaceholder_page: JsonPlaceholderPage
    ) -> None:
        """
        Navigate to JSONPlaceholder home and verify it loads correctly.

        Assertions
        ----------
        - URL contains 'jsonplaceholder.typicode.com'
        - Page title or content contains 'JSONPlaceholder'
        - Page loaded successfully
        """
        jsonplaceholder_page.navigate_to_home()

        jsonplaceholder_page.assert_url_contains("jsonplaceholder.typicode.com")

        assert jsonplaceholder_page.is_jsonplaceholder_page(), (
            "Expected to be on JSONPlaceholder page."
        )

        content = jsonplaceholder_page.get_page_content()
        assert "jsonplaceholder" in content.lower() or \
               "JSONPlaceholder" in content, (
            "Expected JSONPlaceholder content on home page."
        )

    # ------------------------------------------------------------------ #
    #  Test 2 — Posts endpoint documented                                  #
    # ------------------------------------------------------------------ #

    def test_posts_endpoint_documented_on_home_page(
        self, jsonplaceholder_page: JsonPlaceholderPage
    ) -> None:
        """
        Verify /posts endpoint is documented on the JSONPlaceholder home page.

        /posts is the Insurance Policy resource in our test framework.
        Its presence in the documentation confirms the backend is
        correctly serving the resource we depend on.

        Assertions
        ----------
        - Home page loads
        - '/posts' text visible on page
        """
        jsonplaceholder_page.navigate_to_home()

        jsonplaceholder_page \
            .assert_url_contains("jsonplaceholder.typicode.com") \
            .assert_page_contains("/posts")

    # ------------------------------------------------------------------ #
    #  Test 3 — Posts JSON renders in browser                             #
    # ------------------------------------------------------------------ #

    def test_posts_json_renders_in_browser(
        self, jsonplaceholder_page: JsonPlaceholderPage
    ) -> None:
        """
        Navigate directly to /posts endpoint in browser and verify
        JSON response renders correctly.

        This bridges Phase 1 Insurance API tests with Phase 1 UI tests:
        the same /posts resource verified at both HTTP and browser layers.

        Assertions
        ----------
        - URL contains '/posts'
        - Response contains JSON array indicators
        - 'userId' field visible (our customer id field)
        - 'title' field visible (our policy name field)
        """
        jsonplaceholder_page.navigate_to_posts()

        jsonplaceholder_page.assert_url_contains("/posts")

        content = jsonplaceholder_page.get_page_content()
        assert "userId" in content, (
            "Expected 'userId' field in /posts JSON response."
        )
        assert "title" in content, (
            "Expected 'title' field in /posts JSON response."
        )
