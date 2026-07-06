"""
fintech_client.py
-----------------
Facade over httpx for Coinbase public market data API operations.

Pattern : Facade
SOLID   : DIP — tests depend on FintechClient, not httpx directly
          OCP  — add new market data methods without touching existing ones
"""

from __future__ import annotations

import httpx

from projects.fintech.api.config.fintech_config import FintechConfig


class FintechClient:
    """
    Facade that hides httpx complexity from test code.

    Wraps Coinbase public API endpoints — no authentication required.
    """

    def __init__(self) -> None:
        cfg = FintechConfig()
        self._cfg      = cfg
        self._base_url = cfg.base_url
        self._session  = httpx.Client(
            headers={
                "Accept":     "application/json",
                "CB-VERSION": "2016-02-18",
            },
            timeout=cfg.timeout_sec,
            follow_redirects=True,
        )

    # ------------------------------------------------------------------ #
    #  Currency operations                                                 #
    # ------------------------------------------------------------------ #

    def get_currencies(self) -> httpx.Response:
        """GET /currencies — list all supported currencies."""
        return self._session.get(f"{self._base_url}/currencies")

    def get_exchange_rates(self, currency: str = "USD") -> httpx.Response:
        """GET /exchange-rates — get exchange rates for a base currency."""
        return self._session.get(
            f"{self._base_url}/exchange-rates",
            params={"currency": currency},
        )

    def get_spot_price(self, pair: str = "BTC-USD") -> httpx.Response:
        """GET /prices/{pair}/spot — get spot price for a trading pair."""
        return self._session.get(
            f"{self._base_url}/prices/{pair}/spot"
        )

    def get_buy_price(self, pair: str = "BTC-USD") -> httpx.Response:
        """GET /prices/{pair}/buy — get buy price for a trading pair."""
        return self._session.get(
            f"{self._base_url}/prices/{pair}/buy"
        )

    def get_sell_price(self, pair: str = "BTC-USD") -> httpx.Response:
        """GET /prices/{pair}/sell — get sell price for a trading pair."""
        return self._session.get(
            f"{self._base_url}/prices/{pair}/sell"
        )


    def get_server_time(self) -> httpx.Response:
        """GET /time — get Coinbase server time."""
        return self._session.get(f"{self._base_url}/time")

    def get_historic_prices(self, pair: str = "BTC-USD", period: str = "day") -> httpx.Response:
        """GET /prices/{pair}/historic — get historic prices for a trading pair."""
        return self._session.get(
            f"{self._base_url}/prices/{pair}/historic",
            params={"period": period},
        )

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    def close(self) -> None:
        """Close the underlying httpx session."""
        self._session.close()

    def __enter__(self) -> "FintechClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()
