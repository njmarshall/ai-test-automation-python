"""
insurance_config.py
-------------------
Singleton configuration loader for the Insurance API test framework.

Pattern : Singleton (thread-safe via __new__ + double-checked locking)
SOLID   : SRP — one class, one job: load and expose Insurance API settings

Target API
----------
JSONPlaceholder (https://jsonplaceholder.typicode.com) — free public REST API.
/posts endpoint used as insurance policy mock:
  id     → policy id
  title  → policy name
  body   → policy description
  userId → customer id
"""

from __future__ import annotations

import os
import threading


class InsuranceConfig:
    """
    Singleton that loads Insurance API connection settings.

    Usage
    -----
        cfg  = InsuranceConfig()
        cfg2 = InsuranceConfig()
        assert cfg is cfg2   # True — same instance

    Environment variables
    ---------------------
        INSURANCE_BASE_URL    Base URL (default: JSONPlaceholder)
        INSURANCE_TIMEOUT_SEC HTTP timeout in seconds (default: 15)
    """

    _instance: InsuranceConfig | None = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> InsuranceConfig:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._load()
                    cls._instance = instance
        return cls._instance

    def _load(self) -> None:
        self.base_url: str = os.getenv(
            "INSURANCE_BASE_URL",
            "https://jsonplaceholder.typicode.com",
        ).rstrip("/")

        self.timeout_sec: float = float(
            os.getenv("INSURANCE_TIMEOUT_SEC", "15")
        )

        self.policy_url: str = f"{self.base_url}/posts"

    @classmethod
    def reset(cls) -> None:
        """Test helper — destroys singleton so env overrides take effect."""
        with cls._lock:
            cls._instance = None

    def __repr__(self) -> str:
        return (
            f"InsuranceConfig(base_url={self.base_url!r}, "
            f"timeout_sec={self.timeout_sec})"
        )
