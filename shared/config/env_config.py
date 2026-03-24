import os
from dotenv import load_dotenv

load_dotenv()  # reads .env file — env vars always take priority

class EnvConfig:
    """
    Central config — replaces EnvConfig.java + BaseConfig.java.
    All settings driven by environment variables with sensible defaults.
    """
    BASE_URL: str             = os.getenv("BASE_URL", "https://petstore.swagger.io/v2")
    REQUEST_TIMEOUT_MS: int   = int(os.getenv("REQUEST_TIMEOUT_MS", "10000"))
    RESPONSE_TIME_SLA_MS: int = int(os.getenv("RESPONSE_TIME_SLA_MS", "3000"))
    MAX_RETRIES: int          = int(os.getenv("MAX_RETRIES", "2"))
    API_KEY: str              = os.getenv("API_KEY", "")
    BEARER_TOKEN: str         = os.getenv("BEARER_TOKEN", "")
    LOG_ALL_REQUESTS: bool    = os.getenv("LOG_ALL_REQUESTS", "false").lower() == "true"
    LLM_API_KEY: str          = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str            = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")