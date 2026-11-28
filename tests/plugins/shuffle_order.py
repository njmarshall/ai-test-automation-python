"""
shuffle_order.py
----------------
Opt-in pytest plugin that runs tests in a seeded random order.

    SHUFFLE_SEED=12345 pytest -p tests.plugins.shuffle_order ...

Why: a test that passes only after another test has run (shared state, a
server left running, a port still held) looks green in file order. A
shuffled order exposes it. On November 27, 2026 this found three flakes
in the payments and scheduling sandboxes (see CHANGELOG).

The seed is printed in the header, so any failing order can be replayed
exactly with the same SHUFFLE_SEED.
"""

from __future__ import annotations

import os
import random


def _seed():
    value = os.environ.get("SHUFFLE_SEED")
    return int(value) if value else None


def pytest_report_header(config):
    seed = _seed()
    return f"shuffle_order: SHUFFLE_SEED={seed}" if seed is not None else "shuffle_order: off (set SHUFFLE_SEED)"


def pytest_collection_modifyitems(session, config, items):
    seed = _seed()
    if seed is not None:
        random.Random(seed).shuffle(items)
