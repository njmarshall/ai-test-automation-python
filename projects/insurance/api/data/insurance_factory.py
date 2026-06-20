"""
insurance_factory.py
--------------------
Factory that generates valid, randomised Insurance Policy payloads.

Pattern : Factory Method
SOLID   : SRP — one class, one job: produce test data
          OCP — extend with build_claim(), build_quote() without touching build_policy()
"""

from __future__ import annotations

import random
from typing import Optional

from faker import Faker

from projects.insurance.api.models.policy import Policy

_fake = Faker()

_POLICY_TYPES = [
    "Auto Insurance Policy",
    "Home Insurance Policy",
    "Life Insurance Policy",
    "Health Insurance Policy",
    "Travel Insurance Policy",
    "Business Insurance Policy",
]

_POLICY_DESCRIPTIONS = [
    "Comprehensive coverage for all standard risks and liabilities.",
    "Full protection plan with premium benefits and 24/7 support.",
    "Basic coverage plan with essential protection benefits.",
    "Extended coverage including natural disasters and accidents.",
    "Premium policy with zero deductible and full replacement value.",
]


class InsuranceFactory:
    """
    Generates randomised Insurance Policy test data.

    All methods are static — no state, no instantiation needed.

    Example
    -------
        payload = InsuranceFactory.build_policy_dict()
        # POST payload to /posts
    """

    @staticmethod
    def build_policy(user_id: Optional[int] = None) -> Policy:
        """Return a fully populated Policy model with randomised data."""
        return Policy(
            title=random.choice(_POLICY_TYPES),
            body=random.choice(_POLICY_DESCRIPTIONS),
            userId=user_id or random.randint(1, 10),
        )

    @staticmethod
    def build_policy_dict(user_id: Optional[int] = None) -> dict:
        """Return a dict ready to POST as a request body."""
        return InsuranceFactory.build_policy(user_id=user_id).to_dict()
