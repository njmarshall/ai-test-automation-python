"""
insurance_client.py
-------------------
Facade over httpx for Insurance Policy API operations.

Pattern : Facade
SOLID   : DIP — tests depend on InsuranceClient, not httpx directly
          OCP  — add claim/quote methods without touching policy methods
"""

from __future__ import annotations

import httpx

from projects.insurance.api.config.insurance_config import InsuranceConfig


class InsuranceClient:
    """
    Facade that hides httpx complexity from test code.

    Tests call high-level methods like create_policy() and read_policy();
    they never construct URLs, set headers, or handle timeouts directly.
    """

    def __init__(self) -> None:
        cfg = InsuranceConfig()
        self._cfg      = cfg
        self._base_url = cfg.base_url
        self._session  = httpx.Client(
            headers={
                "Content-Type": "application/json",
                "Accept":        "application/json",
            },
            timeout=cfg.timeout_sec,
            follow_redirects=True,
        )

    # ------------------------------------------------------------------ #
    #  Policy operations                                                   #
    # ------------------------------------------------------------------ #

    def create_policy(self, payload: dict) -> httpx.Response:
        """POST /posts — create a new Policy resource."""
        return self._session.post(f"{self._base_url}/posts", json=payload)

    def read_policy(self, policy_id: int) -> httpx.Response:
        """GET /posts/{id} — retrieve an existing Policy resource."""
        return self._session.get(f"{self._base_url}/posts/{policy_id}")

    def update_policy(self, policy_id: int, payload: dict) -> httpx.Response:
        """PUT /posts/{id} — update an existing Policy resource."""
        return self._session.put(
            f"{self._base_url}/posts/{policy_id}", json=payload
        )

    def delete_policy(self, policy_id: int) -> httpx.Response:
        """DELETE /posts/{id} — remove a Policy resource."""
        return self._session.delete(f"{self._base_url}/posts/{policy_id}")

    def list_policies(self) -> httpx.Response:
        """GET /posts — list all Policy resources."""
        return self._session.get(f"{self._base_url}/posts")

    def list_policies_by_customer(self, user_id: int) -> httpx.Response:
        """GET /posts?userId={id} — list policies for a customer."""
        return self._session.get(
            f"{self._base_url}/posts",
            params={"userId": user_id},
        )

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    def close(self) -> None:
        """Close the underlying httpx session."""
        self._session.close()

    def __enter__(self) -> "InsuranceClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()
