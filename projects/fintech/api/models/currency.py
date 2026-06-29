"""
currency.py
-----------
Fintech resource models for Coinbase market data.

Pattern : CRTP — Currency, ExchangeRate, SpotPrice extend FintechResource
SOLID   : OCP — extend with new resource types without modifying base
          SRP — each model owns only its own fields
"""

from __future__ import annotations

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T", bound="FintechResource")


class FintechResource(BaseModel, Generic[T]):
    """CRTP base for all Fintech resource models."""

    model_config = {"populate_by_name": True}

    def to_dict(self) -> dict:
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_response(cls, payload: dict) -> "FintechResource":
        return cls.model_validate(payload)


# ------------------------------------------------------------------ #
#  Currency resource                                                   #
# ------------------------------------------------------------------ #

class Currency(FintechResource["Currency"]):
    """
    Represents a supported currency on Coinbase.

    Maps to GET /currencies response item:
      id      → currency code (e.g. 'USD', 'BTC')
      name    → full name (e.g. 'US Dollar')
      min_size→ minimum transaction size
    """

    id:       Optional[str] = None
    name:     Optional[str] = None
    min_size: Optional[str] = Field(default=None, alias="min_size")

    @property
    def currency_code(self) -> str:
        return self.id or ""

    @property
    def display_name(self) -> str:
        return self.name or ""


# ------------------------------------------------------------------ #
#  ExchangeRate resource                                               #
# ------------------------------------------------------------------ #

class ExchangeRate(FintechResource["ExchangeRate"]):
    """
    Represents exchange rates for a base currency.

    Maps to GET /exchange-rates?currency={code} response data:
      currency → base currency code
      rates    → dict of currency code → rate
    """

    currency: Optional[str] = None
    rates:    Optional[dict] = None

    def get_rate(self, target: str) -> float:
        """Return the exchange rate for a target currency."""
        if self.rates and target in self.rates:
            return float(self.rates[target])
        return 0.0

    def has_rate(self, target: str) -> bool:
        """Return True if the target currency rate exists."""
        return bool(self.rates and target in self.rates)


# ------------------------------------------------------------------ #
#  SpotPrice resource                                                  #
# ------------------------------------------------------------------ #

class SpotPrice(FintechResource["SpotPrice"]):
    """
    Represents a spot price for a trading pair.

    Maps to GET /prices/{pair}/spot response data:
      base     → base currency (e.g. 'BTC')
      currency → quote currency (e.g. 'USD')
      amount   → spot price as string
    """

    base:     Optional[str] = None
    currency: Optional[str] = None
    amount:   Optional[str] = None

    @property
    def price(self) -> float:
        """Return the spot price as a float."""
        try:
            return float(self.amount or "0")
        except ValueError:
            return 0.0

    @property
    def trading_pair(self) -> str:
        """Return the trading pair string e.g. 'BTC-USD'."""
        return f"{self.base or ''}-{self.currency or ''}"
