"""
ticket_retest_agent.py
----------------------
Ticket Retesting Agent: closes the loop after a bug is marked fixed.

The slow part of a bug's life is not finding it. It is the loop after
the fix: someone must rerun the failing tests on the new build, collect
evidence, and update the ticket. This agent does that loop, with one
hard limit.

    It may comment on a ticket and reopen it.
    It can never close a ticket. A human does that.

The limit is enforced by design, not by a flag: the TicketTracker
interface the agent receives has no close method at all.

Flow
----
    ticket marked fixed -> rerun its tests -> verdict -> evidence comment
        VERIFIED       every test passed      comment "ready for a human to close"
        STILL_FAILING  any test failed        reopen + comment with evidence
        INCONCLUSIVE   skipped or not found   comment "cannot verify", no reopen

INCONCLUSIVE is the fail-safe: a skipped or missing test is never
counted as a pass. Silence is not evidence.

Failure messages pass through InputGuard before they are written to a
ticket, so PHI from a request or response never lands in JIRA.

12-month plan: Phase E (started early). Pairs with JiraNotifier
(Phase 6), which opens the ticket this agent later retests.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Protocol, Sequence

from shared.guardrails.input_guard import InputGuard


class Verdict(Enum):
    VERIFIED = "verified"
    STILL_FAILING = "still_failing"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class RetestRequest:
    ticket_key: str
    test_nodeids: Sequence[str]
    build_id: str


@dataclass(frozen=True)
class TestOutcome:
    __test__ = False  # a data class, not a pytest test class
    nodeid: str
    outcome: str  # passed | failed | error | skipped | not_found
    duration_s: float = 0.0
    message: str = ""


@dataclass
class RetestReport:
    request: RetestRequest
    verdict: Verdict
    outcomes: List[TestOutcome]
    comment: str
    reopened: bool = False


class TestRunner(Protocol):
    __test__ = False

    def run(self, nodeids: Sequence[str]) -> List[TestOutcome]: ...


class TicketTracker(Protocol):
    """What the agent may do to a ticket. Deliberately no close()."""

    def comment(self, ticket_key: str, text: str) -> None: ...
    def reopen(self, ticket_key: str, reason: str) -> None: ...


class DryRunTracker:
    """Records what would be sent to JIRA. Used in CI and in tests."""

    def __init__(self) -> None:
        self.calls: List[tuple] = []

    def comment(self, ticket_key: str, text: str) -> None:
        self.calls.append(("comment", ticket_key, text))

    def reopen(self, ticket_key: str, reason: str) -> None:
        self.calls.append(("reopen", ticket_key, reason))


class PytestRunner:
    """Reruns the given node ids in a fresh pytest process and reads JUnit XML."""

    def __init__(self, cwd: str | Path = ".", timeout_s: int = 600) -> None:
        self.cwd = Path(cwd)
        self.timeout_s = timeout_s

    # pytest exit code 4: usage error, which includes "a node id was not found".
    # One missing id aborts the whole run, so fall back to one run per id.
    _USAGE_ERROR = 4

    def run(self, nodeids: Sequence[str]) -> List[TestOutcome]:
        code, found = self._run_once(nodeids)
        if code == self._USAGE_ERROR and len(nodeids) > 1:
            results = []
            for n in nodeids:
                _, one = self._run_once([n])
                results.append(one.get(n) or TestOutcome(n, "not_found"))
            return results
        # A requested test that never ran is reported, never silently dropped.
        return [found.get(n) or TestOutcome(n, "not_found") for n in nodeids]

    def _run_once(self, nodeids: Sequence[str]):
        with tempfile.TemporaryDirectory() as tmp:
            xml_path = Path(tmp) / "retest.xml"
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", *nodeids, "-q", "-p", "no:cacheprovider",
                 "-p", "no:randomly", "--reruns", "0", f"--junitxml={xml_path}"],
                cwd=self.cwd, capture_output=True, text=True, timeout=self.timeout_s,
            )
            found = self._parse(xml_path) if xml_path.exists() else _ResultIndex()
        return proc.returncode, found

    @staticmethod
    def _parse(xml_path: Path) -> dict:
        results = {}
        for tc in ET.parse(xml_path).iter("testcase"):
            module = tc.get("classname", "")
            name = tc.get("name", "")
            parts = module.split(".")
            # classname is "pkg.module.Class" or "pkg.module"; rebuild a node id suffix to match on
            key_tail = f"{parts[-1]}::{name}" if parts and parts[-1][:1].isupper() else name
            outcome, message = "passed", ""
            for child in tc:
                if child.tag in ("failure", "error"):
                    outcome, message = ("failed" if child.tag == "failure" else "error"), child.get("message", "")
                elif child.tag == "skipped":
                    outcome, message = "skipped", child.get("message", "")
            results[key_tail] = TestOutcome(key_tail, outcome, float(tc.get("time", 0) or 0), message)
        return _ResultIndex(results)


class _ResultIndex(dict):
    """Match a requested node id ('path::Class::test') to a JUnit result by its tail."""

    def get(self, nodeid, default=None):
        for tail, result in self.items():
            if nodeid.endswith("::" + tail):
                return TestOutcome(nodeid, result.outcome, result.duration_s, result.message)
        return default


class TicketRetestAgent:
    MAX_MESSAGE_CHARS = 300

    def __init__(self, runner: TestRunner, tracker: TicketTracker, guard: InputGuard | None = None) -> None:
        self.runner = runner
        self.tracker = tracker
        self.guard = guard or InputGuard()

    @staticmethod
    def decide(outcomes: Sequence[TestOutcome]) -> Verdict:
        if not outcomes:
            return Verdict.INCONCLUSIVE
        kinds = {o.outcome for o in outcomes}
        if kinds & {"failed", "error"}:
            return Verdict.STILL_FAILING
        if kinds == {"passed"}:
            return Verdict.VERIFIED
        return Verdict.INCONCLUSIVE

    def retest(self, request: RetestRequest) -> RetestReport:
        outcomes = self.runner.run(list(request.test_nodeids)) if request.test_nodeids else []
        verdict = self.decide(outcomes)
        comment = self._comment(request, verdict, outcomes)
        report = RetestReport(request, verdict, outcomes, comment)

        if verdict is Verdict.STILL_FAILING:
            self.tracker.reopen(request.ticket_key, f"Retest failed on build {request.build_id}")
            report.reopened = True
        self.tracker.comment(request.ticket_key, comment)
        return report

    def _comment(self, req: RetestRequest, verdict: Verdict, outcomes: Sequence[TestOutcome]) -> str:
        headline = {
            Verdict.VERIFIED: f"Retest PASSED on build {req.build_id}. Ready for a human to review and close.",
            Verdict.STILL_FAILING: f"Retest FAILED on build {req.build_id}. Ticket reopened.",
            Verdict.INCONCLUSIVE: (f"Retest INCONCLUSIVE on build {req.build_id}. A skipped or missing test "
                                   "is not evidence of a fix. A human must verify."),
        }[verdict]
        lines = [headline, "", "Evidence (automated retest, Ticket Retesting Agent):"]
        if not outcomes:
            lines.append("- no tests were linked to this ticket")
        for o in outcomes:
            line = f"- {o.outcome.upper():9} {o.nodeid} ({o.duration_s:.2f}s)"
            if o.message:
                msg = self.guard.scrub(o.message)[: self.MAX_MESSAGE_CHARS]
                line += f"\n    {msg}"
            lines.append(line)
        lines += ["", "This agent never closes tickets."]
        return "\n".join(lines)
