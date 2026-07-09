"""
test_coinbase_ui.py
-------------------
Phase 1 MVP: Coinbase public price page UI tests using Playwright.

What we're testing
------------------
The Coinbase public price page (https://www.coinbase.com/price)
shows live cryptocurrency prices. Tests verify the page loads
correctly and key crypto assets are displayed.

Architecture recap
------------------
  BasePage       (POM base)     ← Facade over raw Playwright
  CoinbasePage   (POM concrete) ← Coinbase UI locators + actions
  coinbase_page  (fixture)      ← injected via conftest.py (DIP)

Fintech context
---------------
UI testing a financial data page validates that:
- The platform is accessible and loading correctly
- Key assets (BTC, ETH) are displayed to users
- Page performance is within acceptable SLA
This mirrors real fintech QA work — validating that traders
and investors can see accurate, timely market data.
"""

from __future__ import annotations

import pytest

from projects.fintech.ui.pages.coinbase_page import CoinbasePage


@pytest.mark.fintech
@pytest.mark.ui
class TestCoinbaseUI:
    """
    Coinbase public price page UI tests — Phase 1 MVP.

    Three tests covering core UI validation:
      1. Price page loads — Coinbase is reachable via browser
      2. Bitcoin displayed — BTC visible on price page
      3. Ethereum displayed — ETH visible on price page
    """

    # ------------------------------------------------------------------ #
    #  Test 1 — Price page loads                                           #
    # ------------------------------------------------------------------ #

    def test_coinbase_price_page_loads(
        self, coinbase_page: CoinbasePage
    ) -> None:
        """
        Navigate to Coinbase price page and verify it loads correctly.

        This is the UI equivalent of a health check — confirms the
        Coinbase platform is reachable and serving pages correctly.

        Assertions
        ----------
        - URL contains 'coinbase.com'
        - Page title contains 'Coinbase' or 'price' or 'crypto'
        - Page loaded within 10s SLA
        """
        coinbase_page.navigate_to_prices()

        coinbase_page.assert_url_contains("coinbase.com")

        title = coinbase_page.get_page_title()
        assert any(
            keyword.lower() in title.lower()
            for keyword in ["Coinbase", "price", "crypto", "bitcoin"]
        ), f"Expected Coinbase-related title, got '{title}'."

        assert coinbase_page.is_coinbase_page(), (
            "Expected to be on a Coinbase page."
        )

    # ------------------------------------------------------------------ #
    #  Test 2 — Bitcoin visible                                            #
    # ------------------------------------------------------------------ #

    def test_bitcoin_displayed_on_price_page(
        self, coinbase_page: CoinbasePage
    ) -> None:
        """
        Verify Bitcoin (BTC) is displayed on the Coinbase price page.

        Bitcoin is the most traded cryptocurrency — its absence from
        the price page would indicate a critical UI failure.

        Assertions
        ----------
        - Page loads successfully
        - 'Bitcoin' or 'BTC' text visible on page
        """
        coinbase_page.navigate_to_prices()

        coinbase_page.assert_url_contains("coinbase.com")

        content = coinbase_page.get_page_content()
        assert "Bitcoin" in content or "BTC" in content, (
            "Expected 'Bitcoin' or 'BTC' to be visible on the price page."
        )

    # ------------------------------------------------------------------ #
    #  Test 3 — Ethereum visible                                           #
    # ------------------------------------------------------------------ #

    def test_ethereum_displayed_on_price_page(
        self, coinbase_page: CoinbasePage
    ) -> None:
        """
        Verify Ethereum (ETH) is displayed on the Coinbase price page.

        Ethereum is the second largest cryptocurrency by market cap.
        Its presence validates that the price page renders multiple
        assets correctly, not just Bitcoin.

        Assertions
        ----------
        - Page loads successfully
        - 'Ethereum' or 'ETH' text visible on page
        """
        coinbase_page.navigate_to_prices()

        coinbase_page.assert_url_contains("coinbase.com")

        content = coinbase_page.get_page_content()
        assert "Ethereum" in content or "ETH" in content, (
            "Expected 'Ethereum' or 'ETH' to be visible on the price page."
        )
