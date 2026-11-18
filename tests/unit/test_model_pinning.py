"""
test_model_pinning.py
---------------------
Guards the single-source-of-truth rule for Claude model strings.

If a model is hardcoded anywhere under shared/, a model retirement
means hunting through files and some calls silently keep the old
model. These tests fail the build the moment that happens.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SHARED = Path("shared")
_SOURCE_OF_TRUTH = _SHARED / "config" / "models.py"
_MODEL_LITERAL = re.compile(r"""["']claude-[a-z0-9][a-z0-9.\-]*["']""")


def _python_files():
    return sorted(p for p in _SHARED.rglob("*.py") if p != _SOURCE_OF_TRUTH)


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: str(p))
def test_no_hardcoded_model_string_outside_models_py(path: Path) -> None:
    hits = [
        f"{path}:{n}: {line.strip()}"
        for n, line in enumerate(path.read_text().splitlines(), start=1)
        if _MODEL_LITERAL.search(line)
    ]
    assert not hits, (
        "Hardcoded Claude model string found. Import GENERATOR_MODEL or "
        "JUDGE_MODEL from shared.config.models instead:\n" + "\n".join(hits)
    )


def test_env_config_and_models_agree() -> None:
    from shared.config.env_config import EnvConfig
    from shared.config.models import GENERATOR_MODEL

    assert EnvConfig.LLM_MODEL == GENERATOR_MODEL


def test_env_vars_override_both_roles(monkeypatch) -> None:
    import shared.config.models as models

    monkeypatch.setenv("LLM_MODEL", "claude-generator-under-test")
    monkeypatch.setenv("LLM_JUDGE_MODEL", "claude-judge-under-test")
    reloaded = importlib.reload(models)
    try:
        assert reloaded.GENERATOR_MODEL == "claude-generator-under-test"
        assert reloaded.JUDGE_MODEL == "claude-judge-under-test"
    finally:
        monkeypatch.delenv("LLM_MODEL")
        monkeypatch.delenv("LLM_JUDGE_MODEL")
        importlib.reload(models)


def test_pinned_defaults_are_exact_model_ids() -> None:
    import shared.config.models as models

    for value in (models._PINNED_GENERATOR, models._PINNED_JUDGE):
        assert value.startswith("claude-")
        assert "latest" not in value, "pin an exact model id, never an alias"
