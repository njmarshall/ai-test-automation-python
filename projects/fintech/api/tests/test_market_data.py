"""
test_market_data.py
-------------------
Phase 1 MVP: Coinbase public market data API tests.

What we're testing
------------------
Coinbase public API (https://api.coinbase.com/v2) — no auth required.
Tests cover currency listings, exchange rates, and spot prices.

Clinical/Domain context
-----------------------
Financial market data APIs are the foundation of every fintech product:
  - Currency lists → onboarding, multi-currency support
  - Exchange rates → FX conversion, international payments
  - Spot prices    → trading, portfolio valuation, payment processing

This directly maps to Finix payment processing work — validating that
currency data, rates, and prices are accurate and within SLA is a
core fintech testing responsibility.

Architecture recap
------------------
  FintechConfig    (Singleton) ← loaded once
  FintechClient    (Facade)    ← injected via fixture
  Currency/ExchangeRate/SpotPrice (CRTP) ← typed models
  FintechValidator (Fluent)    ← chainable assertions
"""

from __future__ import annotations

import pytest

from projects.fintech.api.assertions.fintech_validator import FintechValidator
from projects.fintech.api.client.fintech_client import FintechClient
from projects.fintech.api.models.currency import Currency, ExchangeRate, SpotPrice


@pytest.mark.fintech
class TestCurrencies:
    """Tests for GET /currencies — list all supported currencies."""

    def test_get_currencies_returns_200(
        self, fintech_client: FintechClient
    ) -> None:
        """
        GET /currencies must return HTTP 200 with a non-empty list
        of supported currencies.

        Assertions
        ----------
        - HTTP 200 OK
        - Response contains 'data' field
        - Data is a non-empty list
        - Response within 5s SLA
        """
        response = fintech_client.get_currencies()

        (
            FintechValidator(response)
            .status(200)
            .has_data()
            .data_is_list()
            .data_list_is_not_empty()
            .within_sla(sla_ms=5000)
        )

    def test_currencies_list_contains_usd(
        self, fintech_client: FintechClient
    ) -> None:
        """
        USD must be present in the supported currencies list.

        Assertions
        ----------
        - HTTP 200 OK
        - USD currency exists in the list
        - CRTP model: currency_code and display_name non-empty
        """
        response = fintech_client.get_currencies()

        FintechValidator(response).status(200).has_data().data_is_list()

        currencies_data = response.json()["data"]
        usd = next((c for c in currencies_data if c.get("id") == "USD"), None)
        assert usd is not None, "Expected USD in supported currencies list."

        currency = Currency.from_response(usd)
        assert currency.currency_code == "USD"
        assert currency.display_name, "Expected non-empty display name for USD."

    def test_currencies_list_contains_eur(
        self, fintech_client: FintechClient
    ) -> None:
        """
        EUR must be present in the supported currencies list.

        Assertions
        ----------
        - EUR currency exists in the list
        - CRTP model: currency_code is 'EUR'
        """
        response = fintech_client.get_currencies()
        FintechValidator(response).status(200).has_data().data_is_list()

        currencies_data = response.json()["data"]
        eur = next((c for c in currencies_data if c.get("id") == "EUR"), None)
        assert eur is not None, "Expected EUR in supported currencies list."

        currency = Currency.from_response(eur)
        assert currency.currency_code == "EUR"


@pytest.mark.fintech
class TestExchangeRates:
    """Tests for GET /exchange-rates — get exchange rates."""

    def test_get_usd_exchange_rates_returns_200(
        self, fintech_client: FintechClient
    ) -> None:
        """
        GET /exchange-rates?currency=USD must return HTTP 200
        with exchange rate data.

        Assertions
        ----------
        - HTTP 200 OK
        - Response contains 'data' field
        - Data contains 'currency' and 'rates' fields
        - Response within 5s SLA
        """
        response = fintech_client.get_exchange_rates(currency="USD")

        (
            FintechValidator(response)
            .status(200)
            .has_data()
            .has_data_field("currency")
            .has_data_field("rates")
            .within_sla(sla_ms=5000)
        )

    def test_usd_exchange_rates_currency_matches_request(
        self, fintech_client: FintechClient
    ) -> None:
        """
        The currency field in the response must match the requested
        base currency (USD).

        Assertions
        ----------
        - data.currency equals 'USD'
        - CRTP model: has_rate for EUR and GBP
        """
        response = fintech_client.get_exchange_rates(currency="USD")

        (
            FintechValidator(response)
            .status(200)
            .data_field_equals("currency", "USD")
        )

        exchange_rate = ExchangeRate.from_response(response.json()["data"])
        assert exchange_rate.currency == "USD"
        assert exchange_rate.has_rate("EUR"), "Expected EUR rate in USD exchange rates."
        assert exchange_rate.has_rate("GBP"), "Expected GBP rate in USD exchange rates."

    def test_exchange_rate_values_are_positive(
        self, fintech_client: FintechClient
    ) -> None:
        """
        All exchange rate values must be positive numbers.

        Assertions
        ----------
        - EUR rate > 0
        - BTC rate > 0
        """
        response = fintech_client.get_exchange_rates(currency="USD")
        FintechValidator(response).status(200)

        exchange_rate = ExchangeRate.from_response(response.json()["data"])
        assert exchange_rate.get_rate("EUR") > 0, "Expected positive EUR rate."
        assert exchange_rate.get_rate("BTC") > 0, "Expected positive BTC rate."


@pytest.mark.fintech
class TestSpotPrices:
    """Tests for GET /prices/{pair}/spot — get spot prices."""

    def test_get_btc_usd_spot_price_returns_200(
        self, fintech_client: FintechClient
    ) -> None:
        """
        GET /prices/BTC-USD/spot must return HTTP 200 with
        a positive spot price.

        Assertions
        ----------
        - HTTP 200 OK
        - Response contains 'data' field
        - Data contains 'amount', 'base', 'currency'
        - Amount is a positive number
        - Response within 5s SLA
        """
        response = fintech_client.get_spot_price(pair="BTC-USD")

        (
            FintechValidator(response)
            .status(200)
            .has_data()
            .has_data_field("amount")
            .has_data_field("base")
            .has_data_field("currency")
            .data_amount_is_positive()
            .within_sla(sla_ms=5000)
        )

    def test_btc_usd_spot_price_fields_match_pair(
        self, fintech_client: FintechClient
    ) -> None:
        """
        The base and currency fields must match the requested pair.

        Assertions
        ----------
        - data.base equals 'BTC'
        - data.currency equals 'USD'
        - CRTP model: trading_pair is 'BTC-USD'
        - Price > 0
        """
        response = fintech_client.get_spot_price(pair="BTC-USD")

        (
            FintechValidator(response)
            .status(200)
            .data_field_equals("base", "BTC")
            .data_field_equals("currency", "USD")
        )

        spot = SpotPrice.from_response(response.json()["data"])
        assert spot.trading_pair == "BTC-USD"
        assert spot.price > 0, f"Expected positive BTC-USD price, got {spot.price}."

    def test_eth_usd_spot_price_returns_200(
        self, fintech_client: FintechClient
    ) -> None:
        """
        GET /prices/ETH-USD/spot must also return a valid price.
        Confirms the endpoint works for multiple trading pairs.

        Assertions
        ----------
        - HTTP 200 OK
        - Amount is positive
        - base equals 'ETH'
        """
        response = fintech_client.get_spot_price(pair="ETH-USD")

        (
            FintechValidator(response)
            .status(200)
            .has_data()
            .data_amount_is_positive()
            .data_field_equals("base", "ETH")
        )
