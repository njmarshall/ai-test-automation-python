"""
test_flaky_registry.py
----------------------
Keeps tests/flaky_registry.json and the @pytest.mark.flaky markers in sync.

The rule: a retry is allowed only with accountability. Every flaky
marker needs a registry entry (owner, cause, exit plan, review date),
every entry must point to a real flaky test, and an entry whose
review date has passed fails the build until someone acts on it.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_REGISTRY = Path("tests/flaky_registry.json")
_SCAN_ROOTS = (Path("projects"), Path("tests"), Path("shared"))
_REQUIRED = {"nodeid", "quarantined", "owner", "status", "cause", "reason", "exit_plan", "reruns", "review_by"}
_CAUSES = {"external_dependency", "eventual_consistency", "llm_nondeterminism", "timing", "test_order"}
_STATUSES = {"quarantined", "skipped"}

_FLAKY = re.compile(r"^\s*@pytest\.mark\.flaky\(([^)]*)\)")
_DEF = re.compile(r"^\s*def (test_\w+)")
_RERUNS = re.compile(r"reruns\s*=\s*(\d+)")


def _entries() -> list[dict]:
    return json.loads(_REGISTRY.read_text())["entries"]


def _flaky_in_code() -> dict[str, int]:
    """Map 'path::test_name' to its reruns value for every flaky marker."""
    found: dict[str, int] = {}
    for root in _SCAN_ROOTS:
        for path in root.rglob("test_*.py"):
            if path.name == Path(__file__).name:
                continue
            pending = None
            for line in path.read_text().splitlines():
                m = _FLAKY.match(line)
                if m:
                    r = _RERUNS.search(m.group(1))
                    pending = int(r.group(1)) if r else 0
                    continue
                d = _DEF.match(line)
                if d and pending is not None:
                    found[f"{path.as_posix()}::{d.group(1)}"] = pending
                    pending = None
    return found


def _key(nodeid: str) -> str:
    """'path::Class::test' -> 'path::test' (markers are matched per function)."""
    parts = nodeid.split("::")
    return f"{parts[0]}::{parts[-1]}"


def test_every_flaky_marker_is_registered() -> None:
    registered = {_key(e["nodeid"]) for e in _entries()}
    missing = sorted(set(_flaky_in_code()) - registered)
    assert not missing, (
        "Flaky marker without a registry entry. Add owner, cause, reason, "
        f"exit_plan and review_by to {_REGISTRY}:\n  " + "\n  ".join(missing)
    )


def test_every_registry_entry_points_to_a_real_flaky_test() -> None:
    in_code = set(_flaky_in_code())
    stale = sorted(e["nodeid"] for e in _entries() if _key(e["nodeid"]) not in in_code)
    assert not stale, (
        "Registry entry with no matching flaky marker. If the test was fixed, "
        "remove its entry:\n  " + "\n  ".join(stale)
    )


def test_registry_reruns_match_the_marker() -> None:
    in_code = _flaky_in_code()
    wrong = [
        f"{e['nodeid']}: registry {e['reruns']}, marker {in_code[_key(e['nodeid'])]}"
        for e in _entries()
        if _key(e["nodeid"]) in in_code and in_code[_key(e["nodeid"])] != e["reruns"]
    ]
    assert not wrong, "Reruns differ between registry and marker:\n  " + "\n  ".join(wrong)


@pytest.mark.parametrize("entry", _entries(), ids=lambda e: _key(e["nodeid"]).split("::")[-1])
def test_entry_is_complete_and_valid(entry: dict) -> None:
    assert _REQUIRED <= entry.keys(), f"missing fields: {_REQUIRED - entry.keys()}"
    assert entry["cause"] in _CAUSES, f"unknown cause {entry['cause']!r}"
    assert entry["status"] in _STATUSES, f"unknown status {entry['status']!r}"
    assert entry["owner"].strip(), "every quarantined test needs an owner"
    assert entry["exit_plan"].strip(), "every quarantined test needs an exit plan"
    assert date.fromisoformat(entry["quarantined"]) <= date.fromisoformat(entry["review_by"])


@pytest.mark.parametrize("entry", _entries(), ids=lambda e: _key(e["nodeid"]).split("::")[-1])
def test_review_date_has_not_passed(entry: dict) -> None:
    assert date.today() <= date.fromisoformat(entry["review_by"]), (
        f"{entry['nodeid']} was due for review on {entry['review_by']}. Fix the "
        "test and remove the marker, or re-review and extend review_by."
    )
