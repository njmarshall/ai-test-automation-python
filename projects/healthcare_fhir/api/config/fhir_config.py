"""
fhir_config.py
--------------
Singleton configuration loader for the Healthcare FHIR test framework.

Pattern : Singleton (thread-safe via __new__ + class-level guard)
SOLID   : SRP — one class, one job: load and expose FHIR settings
Design  : env vars take highest priority; sensible defaults for local dev

Public HAPI FHIR R4 sandbox used as the default base URL so the suite
runs out-of-the-box with no setup required.
"""

from __future__ import annotations

import os
import threading


class FhirConfig:
    """
    Singleton that loads FHIR connection settings from environment variables.

    Usage
    -----
        cfg = FhirConfig()           # first call — instantiates
        cfg2 = FhirConfig()          # subsequent calls — same instance
        assert cfg is cfg2           # True

    Environment variables
    ---------------------
        FHIR_BASE_URL       Base URL of the FHIR server  (default: HAPI public sandbox)
        FHIR_TIMEOUT_SEC    HTTP timeout in seconds       (default: 15)
        FHIR_BEARER_TOKEN   Optional OAuth bearer token  (default: empty — no auth)
        FHIR_API_KEY        Optional API key             (default: empty — no auth)
    """

    _instance: FhirConfig | None = None
    _lock: threading.Lock = threading.Lock()

    # ------------------------------------------------------------------ #
    #  Singleton enforcement                                               #
    # ------------------------------------------------------------------ #

    def __new__(cls) -> FhirConfig:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:          # double-checked locking
                    instance = super().__new__(cls)
                    instance._load()
                    cls._instance = instance
        return cls._instance

    # ------------------------------------------------------------------ #
    #  Internal loader — called exactly once                              #
    # ------------------------------------------------------------------ #

    def _load(self) -> None:
        self.base_url: str = os.getenv(
            "FHIR_BASE_URL",
            "https://hapi.fhir.org/baseR4",   # public HAPI R4 sandbox
        ).rstrip("/")

        self.timeout_sec: float = float(
            os.getenv("FHIR_TIMEOUT_SEC", "15")
        )

        self.bearer_token: str = os.getenv("FHIR_BEARER_TOKEN", "")
        self.api_key: str      = os.getenv("FHIR_API_KEY", "")

        # Derived: full Patient endpoint base
        self.patient_url: str = f"{self.base_url}/Patient"

    # ------------------------------------------------------------------ #
    #  Convenience                                                         #
    # ------------------------------------------------------------------ #

    @classmethod
    def reset(cls) -> None:
        """
        Test helper — destroys the singleton so env-var overrides take effect.
        Never call this in production code.
        """
        with cls._lock:
            cls._instance = None

    def __repr__(self) -> str:
        return (
            f"FhirConfig(base_url={self.base_url!r}, "
            f"timeout_sec={self.timeout_sec}, "
            f"auth={'bearer' if self.bearer_token else 'api_key' if self.api_key else 'none'})"
        )
