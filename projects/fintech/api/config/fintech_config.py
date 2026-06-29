"""
fintech_config.py
-----------------
Singleton configuration loader for the Fintech API test framework.

Pattern : Singleton (thread-safe via __new__ + double-checked locking)
SOLID   : SRP — one class, one job: load and expose Fintech API settings

Target API
----------
Coinbase public API (https://api.coinbase.com/v2)
No authentication required for public market data endpoints:
  /currencies        — list all supported currencies
  /exchange-rates    — get exchange rates for a base currency
  /prices/{pair}/spot — get spot price for a trading pair
"""

from __future__ import annotations

import os
import threading


class FintechConfig:
    """
    Singleton that loads Fintech API connection settings.

    Usage
    -----
        cfg  = FintechConfig()
        cfg2 = FintechConfig()
        assert cfg is cfg2   # True — same instance
    """

    _instance: FintechConfig | None = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> FintechConfig:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._load()
                    cls._instance = instance
        return cls._instance

    def _load(self) -> None:
        self.base_url: str = os.getenv(
            "FINTECH_BASE_URL",
            "https://api.coinbase.com/v2",
        ).rstrip("/")

        self.timeout_sec: float = float(
            os.getenv("FINTECH_TIMEOUT_SEC", "15")
        )

        self.default_currency: str = os.getenv(
            "FINTECH_DEFAULT_CURRENCY", "USD"
        )

    @classmethod
    def reset(cls) -> None:
        """Test helper — destroys singleton so env overrides take effect."""
        with cls._lock:
            cls._instance = None

    def __repr__(self) -> str:
        return (
            f"FintechConfig(base_url={self.base_url!r}, "
            f"timeout_sec={self.timeout_sec}, "
            f"default_currency={self.default_currency!r})"
        )
