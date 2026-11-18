"""
models.py
---------
Single source of truth for every Claude model string in the framework.

Why this file exists
--------------------
Before this file, five modules hardcoded "claude-sonnet-4-6" and
EnvConfig defaulted to a different model ("claude-sonnet-4-20250514").
Two sources of truth that already disagreed. When a model is retired,
one line here changes, and the change is a documented re-baselining
event (see docs/Framework_Improvement_Plan_2027.docx, Phase A and B).

Two roles, kept separate on purpose
-----------------------------------
GENERATOR_MODEL : writes tests, fixes, and exploratory scenarios
JUDGE_MODEL     : scores generated output (ClaudeJudge / DeepEval)

Keeping them separate lets the judge be swapped and compared against
the old judge (Cohen's kappa) without changing what gets generated.
It also makes self-preference bias visible: if both roles use the same
model, the CHANGELOG should say so.

Override per environment
------------------------
    LLM_MODEL=claude-...        overrides GENERATOR_MODEL
    LLM_JUDGE_MODEL=claude-...  overrides JUDGE_MODEL

Rule (enforced by tests/unit/test_model_pinning.py)
---------------------------------------------------
No module under shared/ may hardcode a "claude-..." model string.
Read GENERATOR_MODEL or JUDGE_MODEL from here instead.
"""

from __future__ import annotations

import os

_PINNED_GENERATOR = "claude-sonnet-4-6"
_PINNED_JUDGE = "claude-sonnet-4-6"

GENERATOR_MODEL: str = os.getenv("LLM_MODEL", _PINNED_GENERATOR)
JUDGE_MODEL: str = os.getenv("LLM_JUDGE_MODEL", _PINNED_JUDGE)
