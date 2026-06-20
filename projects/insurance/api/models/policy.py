"""
policy.py
---------
Insurance Policy resource model.

Pattern : CRTP — Policy extends InsuranceResource["Policy"]
SOLID   : OCP — InsuranceResource base open for extension (Claim, Quote)
          SRP — owns only Policy-specific fields

Maps JSONPlaceholder /posts schema to Insurance domain:
  id     → policy id
  title  → policy name
  body   → policy description
  userId → customer id
"""

from __future__ import annotations

from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T", bound="InsuranceResource")


class InsuranceResource(BaseModel, Generic[T]):
    """CRTP base for all Insurance resource models."""

    id:      Optional[int] = None

    model_config = {"populate_by_name": True}

    def to_dict(self) -> dict:
        """Serialise to a dict, omitting None values."""
        return self.model_dump(by_alias=True, exclude_none=True)

    @classmethod
    def from_response(cls, payload: dict) -> "InsuranceResource":
        """Deserialise a raw API response dict into this resource type."""
        return cls.model_validate(payload)


class Policy(InsuranceResource["Policy"]):
    """
    Insurance Policy resource.

    CRTP pattern: Policy is both the generic type argument and
    the concrete implementor of InsuranceResource[Policy].

    Maps to JSONPlaceholder /posts endpoint:
      title  → policy name
      body   → policy description
      userId → customer id
    """

    title:   Optional[str] = None
    body:    Optional[str] = None
    user_id: Optional[int] = Field(default=None, alias="userId")

    @property
    def policy_name(self) -> str:
        """Return the policy name (title field)."""
        return self.title or ""

    @property
    def customer_id(self) -> int:
        """Return the customer id (userId field)."""
        return self.user_id or 0
