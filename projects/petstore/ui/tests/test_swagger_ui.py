"""
test_swagger_ui.py
------------------
Phase 1 MVP: Swagger PetStore UI tests using Playwright.

What we're testing
------------------
The Swagger PetStore UI (https://petstore.swagger.io) is the official
interactive documentation for the PetStore REST API — the same API
tested in projects/petstore/api/tests/.

Architecture recap
------------------
  BasePage    (POM base)     ← Facade over raw Playwright
  SwaggerPage (POM concrete) ← Swagger UI locators + actions
  swagger_page (fixture)     ← injected via conftest.py (DIP)

PetStore context
----------------
UI testing the Swagger interface validates:
- The API documentation platform is accessible
- Key resource sections (pet, store) are visible
- The interface loads correctly for developer experience
This bridges our API tests with UI layer — same resources,
verified at both HTTP and browser levels.
"""

from __future__ import annotations

import pytest

from projects.petstore.ui.pages.swagger_page import SwaggerPage


@pytest.mark.petstore
@pytest.mark.ui
class TestSwaggerUI:
    """
    Swagger PetStore UI tests — Phase 1 MVP.

    Three tests covering core UI validation:
      1. Swagger UI loads — PetStore docs are reachable
      2. Pet resource visible — /pet section in documentation
      3. Store resource visible — /store section in documentation
    """

    # ------------------------------------------------------------------ #
    #  Test 1 — Swagger UI loads                                           #
    # ------------------------------------------------------------------ #

    def test_swagger_ui_loads(
        self, swagger_page: SwaggerPage
    ) -> None:
        """
        Navigate to Swagger PetStore UI and verify it loads correctly.

        Assertions
        ----------
        - URL contains 'petstore.swagger.io'
        - Page is a Swagger/PetStore page
        - Content loads successfully
        """
        swagger_page.navigate_to_swagger()

        swagger_page.assert_url_contains("petstore.swagger.io")

        assert swagger_page.is_swagger_page(), (
            "Expected to be on the Swagger PetStore page."
        )

        content = swagger_page.get_page_content()
        assert len(content) > 100, (
            "Expected Swagger UI to render meaningful content."
        )

    # ------------------------------------------------------------------ #
    #  Test 2 — Pet resource visible                                       #
    # ------------------------------------------------------------------ #

    def test_pet_resource_visible_in_swagger(
        self, swagger_page: SwaggerPage
    ) -> None:
        """
        Verify the /pet resource section is visible in Swagger UI.

        /pet is the primary resource in our PetStore API test suite.
        Its presence in the documentation confirms the Swagger UI
        is correctly rendering the API spec we test against.

        Assertions
        ----------
        - Swagger UI loads
        - 'pet' text visible in page content
        """
        swagger_page.navigate_to_swagger()
        swagger_page.assert_url_contains("petstore.swagger.io")

        content = swagger_page.get_page_content()
        assert "pet" in content.lower(), (
            "Expected 'pet' resource to be visible in Swagger UI."
        )

    # ------------------------------------------------------------------ #
    #  Test 3 — Store resource visible                                     #
    # ------------------------------------------------------------------ #

    def test_store_resource_visible_in_swagger(
        self, swagger_page: SwaggerPage
    ) -> None:
        """
        Verify the /store resource section is visible in Swagger UI.

        /store is the second resource in our PetStore API test suite
        (inventory, orders). Its presence validates that multiple
        resource sections render correctly in the documentation.

        Assertions
        ----------
        - Swagger UI loads
        - 'store' text visible in page content
        """
        swagger_page.navigate_to_swagger()
        swagger_page.assert_url_contains("petstore.swagger.io")
        swagger_page.wait_for_swagger_ui_render()

        content = swagger_page.get_page_content()
        assert "store" in content.lower(), (
            "Expected 'store' resource to be visible in Swagger UI."
        )
