from shared.config.env_config import EnvConfig


class AuthHelper:
    """
    Builds auth headers — replaces AuthHelper.java.
    Supports Bearer token, API key, or no auth.
    """

    @staticmethod
    def build_headers() -> dict:
        headers = {"Content-Type": "application/json"}

        if EnvConfig.BEARER_TOKEN:
            headers["Authorization"] = f"Bearer {EnvConfig.BEARER_TOKEN}"
        elif EnvConfig.API_KEY:
            headers["api_key"] = EnvConfig.API_KEY

        return headers