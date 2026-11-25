"""
test_ticket_retest_agent.py
---------------------------
Unit tests for the Ticket Retesting Agent.

The rules under test:
  - all passed            -> VERIFIED, comment only, never close
  - any failed or error   -> STILL_FAILING, reopen and comment
  - skipped or not found  -> INCONCLUSIVE, comment only (silence is not evidence)
  - the tracker has no close(), so the agent cannot close a ticket
  - failure messages are PHI scrubbed before they reach the ticket
"""

from __future__ import annotations

import textwrap

import pytest

from shared.agent.ticket_retest_agent import (
    DryRunTracker,
    PytestRunner,
    RetestRequest,
    TestOutcome,
    TicketRetestAgent,
    TicketTracker,
    Verdict,
)

pytestmark = pytest.mark.unit


class FakeRunner:
    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.asked = None

    def run(self, nodeids):
        self.asked = list(nodeids)
        return list(self.outcomes)


def _req(*nodeids, key="SDET-42", build="build-101"):
    return RetestRequest(ticket_key=key, test_nodeids=nodeids, build_id=build)


def _agent(outcomes):
    tracker = DryRunTracker()
    return TicketRetestAgent(FakeRunner(outcomes), tracker), tracker


class TestVerdicts:
    def test_all_passed_is_verified_and_only_comments(self):
        agent, tracker = _agent([TestOutcome("a::t1", "passed"), TestOutcome("a::t2", "passed")])
        report = agent.retest(_req("a::t1", "a::t2"))
        assert report.verdict is Verdict.VERIFIED
        assert [c[0] for c in tracker.calls] == ["comment"]
        assert "Ready for a human to review and close" in report.comment

    @pytest.mark.parametrize("bad", ["failed", "error"])
    def test_any_failure_reopens_and_comments(self, bad):
        agent, tracker = _agent([TestOutcome("a::t1", "passed"), TestOutcome("a::t2", bad, message="boom")])
        report = agent.retest(_req("a::t1", "a::t2"))
        assert report.verdict is Verdict.STILL_FAILING and report.reopened
        assert [c[0] for c in tracker.calls] == ["reopen", "comment"]
        assert "build-101" in tracker.calls[0][2]

    @pytest.mark.parametrize("silent", ["skipped", "not_found"])
    def test_skipped_or_missing_is_inconclusive_never_verified(self, silent):
        agent, tracker = _agent([TestOutcome("a::t1", "passed"), TestOutcome("a::t2", silent)])
        report = agent.retest(_req("a::t1", "a::t2"))
        assert report.verdict is Verdict.INCONCLUSIVE
        assert not report.reopened
        assert [c[0] for c in tracker.calls] == ["comment"]
        assert "not evidence of a fix" in report.comment

    def test_failure_beats_skip(self):
        assert TicketRetestAgent.decide([TestOutcome("x", "skipped"), TestOutcome("y", "failed")]) is Verdict.STILL_FAILING

    def test_ticket_with_no_linked_tests_is_inconclusive_and_runs_nothing(self):
        runner, tracker = FakeRunner([]), DryRunTracker()
        report = TicketRetestAgent(runner, tracker).retest(_req())
        assert report.verdict is Verdict.INCONCLUSIVE
        assert runner.asked is None
        assert "no tests were linked" in report.comment


class TestCannotClose:
    def test_tracker_interface_has_no_close(self):
        assert not hasattr(TicketTracker, "close")
        assert not hasattr(DryRunTracker(), "close")

    def test_agent_never_calls_anything_but_comment_and_reopen(self):
        class StrictTracker:
            def __init__(self):
                self.calls = []

            def comment(self, key, text):
                self.calls.append("comment")

            def reopen(self, key, reason):
                self.calls.append("reopen")

            def __getattr__(self, name):  # any other method, e.g. close or transition
                raise AssertionError(f"agent tried to call tracker.{name}")

        for outcome in ("passed", "failed", "skipped"):
            t = StrictTracker()
            TicketRetestAgent(FakeRunner([TestOutcome("a::t", outcome)]), t).retest(_req("a::t"))
            assert set(t.calls) <= {"comment", "reopen"}


class TestEvidence:
    def test_comment_lists_every_test_with_outcome_and_duration(self):
        agent, _ = _agent([TestOutcome("a::t1", "passed", 0.12), TestOutcome("a::t2", "failed", 0.5, "assert 1 == 2")])
        report = agent.retest(_req("a::t1", "a::t2"))
        assert "PASSED    a::t1 (0.12s)" in report.comment
        assert "FAILED    a::t2 (0.50s)" in report.comment
        assert "assert 1 == 2" in report.comment
        assert report.comment.rstrip().endswith("This agent never closes tickets.")

    def test_failure_message_is_phi_scrubbed_before_reaching_the_ticket(self):
        phi = "patient SSN 123-45-6789 not found"
        agent, tracker = _agent([TestOutcome("a::t", "failed", message=phi)])
        agent.retest(_req("a::t"))
        sent = tracker.calls[-1][2]
        assert "123-45-6789" not in sent

    def test_long_failure_message_is_truncated(self):
        agent, _ = _agent([TestOutcome("a::t", "failed", message="x" * 5000)])
        report = agent.retest(_req("a::t"))
        assert "x" * TicketRetestAgent.MAX_MESSAGE_CHARS in report.comment
        assert "x" * (TicketRetestAgent.MAX_MESSAGE_CHARS + 1) not in report.comment


class TestRealPytestRunner:
    """End to end: the real runner reruns real tests in a subprocess. Offline."""

    @pytest.fixture
    def suite(self, tmp_path):
        (tmp_path / "test_fixed_bug.py").write_text(textwrap.dedent("""
            import pytest

            class TestPayments:
                def test_refund_is_idempotent(self):
                    assert 2 + 2 == 4

                def test_still_broken(self):
                    assert 1 == 2, "refund charged twice"

            @pytest.mark.skip(reason="sandbox down")
            def test_skipped():
                pass
        """))
        return tmp_path

    def test_verified_when_the_fixed_test_passes(self, suite):
        tracker = DryRunTracker()
        report = TicketRetestAgent(PytestRunner(cwd=suite, timeout_s=60), tracker).retest(
            _req("test_fixed_bug.py::TestPayments::test_refund_is_idempotent"))
        assert report.verdict is Verdict.VERIFIED
        assert report.outcomes[0].outcome == "passed"

    def test_still_failing_reopens_with_the_real_assertion_message(self, suite):
        tracker = DryRunTracker()
        report = TicketRetestAgent(PytestRunner(cwd=suite, timeout_s=60), tracker).retest(
            _req("test_fixed_bug.py::TestPayments::test_refund_is_idempotent",
                 "test_fixed_bug.py::TestPayments::test_still_broken"))
        assert report.verdict is Verdict.STILL_FAILING and report.reopened
        assert "refund charged twice" in report.comment

    def test_skipped_and_renamed_tests_are_inconclusive(self, suite):
        report = TicketRetestAgent(PytestRunner(cwd=suite, timeout_s=60), DryRunTracker()).retest(
            _req("test_fixed_bug.py::test_skipped", "test_fixed_bug.py::TestPayments::test_renamed_away"))
        assert report.verdict is Verdict.INCONCLUSIVE
        assert [o.outcome for o in report.outcomes] == ["skipped", "not_found"]
