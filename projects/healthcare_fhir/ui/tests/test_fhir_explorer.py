"""
test_fhir_explorer.py
---------------------
Phase 4: HAPI FHIR UI tests using Playwright + Page Object Model.

What we're testing
------------------
The HAPI FHIR public R4 sandbox has a browser-accessible JSON API
explorer at https://hapi.fhir.org/baseR4. Tests navigate the UI,
issue FHIR queries via the browser, and assert on JSON responses —
bridging the API and UI test layers into one cohesive story.

Architecture recap
------------------
  BasePage          (POM base)      ← Facade over raw Playwright
  FhirExplorerPage  (POM concrete)  ← HAPI FHIR UI locators + actions
  fhir_explorer     (fixture)       ← injected via conftest.py (DIP)
  FhirClient        (API facade)    ← used in setup to create live resources

Java parallel
-------------
This mirrors LoadAppLoginUITest.java in upgrade repo but uses:
  Playwright instead of Selenium
  POM page objects instead of raw driver calls
  Role-based selectors instead of fragile XPath
  Auto-waiting instead of explicit WebDriverWait

HAPI sandbox notes
------------------
  - Base R4 URL redirects to Swagger UI (title = 'Swagger UI')
  - Search Bundle omits 'total' unless _summary=count is requested
  - Both are sandbox quirks — assertions adjusted accordingly
"""

from __future__ import annotations

import pytest

from projects.healthcare_fhir.api.client.fhir_client import FhirClient
from projects.healthcare_fhir.api.data.fhir_factory import FhirFactory
from projects.healthcare_fhir.ui.pages.fhir_explorer_page import FhirExplorerPage


@pytest.mark.healthcare
@pytest.mark.ui
class TestFhirExplorer:
    """
    HAPI FHIR UI tests — Phase 4 MVP.

    Three tests covering the core UI explorer flows:
      1. Home page loads — HAPI FHIR server reachable + CapabilityStatement served
      2. Patient resource renders — navigate to a live Patient JSON response
      3. Patient search renders — Bundle response with searchset type present
    """

    # ------------------------------------------------------------------ #
    #  Test 1 — Home page loads                                            #
    # ------------------------------------------------------------------ #

    def test_hapi_fhir_home_page_loads(
        self,
        fhir_explorer: FhirExplorerPage,
    ) -> None:
        """
        Navigate to the HAPI FHIR R4 base URL and verify the server is up.

        HAPI's base R4 URL now redirects to Swagger UI — the title
        assertion reflects the actual current behaviour of the sandbox.
        We also navigate to /metadata directly to verify the
        CapabilityStatement is served correctly.

        Assertions
        ----------
        - Home URL loads — title contains 'Swagger UI' (HAPI's current UI)
        - URL contains 'hapi.fhir.org'
        - Metadata endpoint returns CapabilityStatement resourceType
        """
        # Home page — HAPI now serves Swagger UI at base R4 URL
        fhir_explorer.navigate_to_home()

        fhir_explorer \
            .assert_title_contains("Swagger UI") \
            .assert_url_contains("hapi.fhir.org")

        # Navigate to metadata — verify CapabilityStatement is served
        fhir_explorer.navigate_to_capability_statement()

        fhir_explorer.assert_response_contains("resourceType")

        resource_type = fhir_explorer.get_resource_type_from_response()
        assert resource_type == "CapabilityStatement", (
            f"Expected metadata to return CapabilityStatement, "
            f"got '{resource_type}'."
        )

    # ------------------------------------------------------------------ #
    #  Test 2 — Patient resource renders in browser                       #
    # ------------------------------------------------------------------ #

    def test_patient_resource_renders_in_browser(
        self,
        fhir_explorer: FhirExplorerPage,
    ) -> None:
        """
        Create a Patient via API, then navigate to it in the browser
        and verify the JSON response renders correctly.

        This bridges Phase 1 API tests with Phase 4 UI tests —
        the same Patient resource is verified at both layers.

        Assertions
        ----------
        - Page loads at /Patient/{id}
        - resourceType in response is 'Patient'
        - Resource id in response matches what was created
        - Response contains 'name' field
        """
        # Arrange — create a live Patient via API
        client   = FhirClient()
        payload  = FhirFactory.build_patient_dict()
        response = client.create_patient(payload)
        assert response.status_code == 201, (
            f"API setup failed: {response.status_code}"
        )
        patient_id = response.json()["id"]

        try:
            # Act — navigate to the Patient resource in the browser
            fhir_explorer.navigate_to_resource("Patient", patient_id)

            # Assert — POM fluent assertions
            fhir_explorer \
                .assert_url_contains(patient_id) \
                .assert_response_contains("resourceType") \
                .assert_resource_type("Patient") \
                .assert_response_contains("name")

            # Verify id round-trips
            rendered_id = fhir_explorer.get_resource_id_from_response()
            assert rendered_id == patient_id, (
                f"Expected rendered Patient id '{patient_id}', "
                f"got '{rendered_id}'."
            )

        finally:
            # Teardown — always clean up the API resource
            client.delete_patient(patient_id)
            client.close()

    # ------------------------------------------------------------------ #
    #  Test 3 — Patient search renders Bundle in browser                  #
    # ------------------------------------------------------------------ #

    def test_patient_search_renders_bundle(
        self,
        fhir_explorer: FhirExplorerPage,
    ) -> None:
        """
        Navigate to the Patient search endpoint in the browser and
        verify a FHIR Bundle response is rendered correctly.

        Note: HAPI sandbox omits 'total' from Bundle responses unless
        _summary=count is explicitly requested. We assert on
        'searchset' type instead — which is always present.

        Assertions
        ----------
        - URL contains '/Patient'
        - resourceType in response is 'Bundle'
        - Bundle type is 'searchset'
        - Response contains 'entry' or 'link' field
        """
        fhir_explorer.navigate_to_patient_search()

        fhir_explorer \
            .assert_url_contains("Patient") \
            .assert_response_contains("resourceType") \
            .assert_resource_type("Bundle") \
            .assert_response_contains("searchset")

        # Verify bundle has either entries or navigation links
        body = fhir_explorer.get_response_body_text()
        assert "link" in body or "entry" in body, (
            "Expected Bundle to contain 'link' or 'entry' fields.\n"
            f"Body preview: {body[:400]}"
        )
