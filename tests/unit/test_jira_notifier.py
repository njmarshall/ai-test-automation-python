"""
test_jira_notifier.py
---------------------
Unit tests for Phase 6 — JiraNotifier and JiraTicketPayload.

These tests use no network and no JIRA credentials: they verify
the dry-run path, payload construction, and the agent integration
hook, all in isolation.
"""

from __future__ import annotations

import json
import unittest
from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from shared.jira.jira_notifier import (
    JiraConfig,
    JiraNotifier,
    JiraTicketPayload,
    JiraTicketResult,
)


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

def _make_healing_result(
    status: str = "PASS",
    test_path: str = "projects/healthcare_fhir/api/tests/test_patient.py",
    fix_applied: Optional[str] = "Updated status assertion from 422 to 201.",
    quality_score: Optional[float] = 0.85,
    warnings: Optional[list] = None,
) -> MagicMock:
    """Build a minimal HealingResult-like object for testing."""
    result = MagicMock()
    result.status        = status
    result.test_path     = test_path
    result.fix_applied   = fix_applied
    result.quality_score = quality_score
    result.warnings      = warnings if warnings is not None else []
    return result


# ------------------------------------------------------------------ #
#  JiraConfig                                                          #
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestJiraConfig(unittest.TestCase):

    def test_is_configured_true_when_all_credentials_present(self):
        config = JiraConfig(
            base_url="https://acme.atlassian.net",
            email="neil@acme.com",
            api_token="secret-token",
        )
        self.assertTrue(config.is_configured)

    def test_is_configured_false_when_base_url_missing(self):
        config = JiraConfig(base_url="", email="neil@acme.com", api_token="token")
        self.assertFalse(config.is_configured)

    def test_is_configured_false_when_email_missing(self):
        config = JiraConfig(base_url="https://acme.atlassian.net", email="", api_token="token")
        self.assertFalse(config.is_configured)

    def test_is_configured_false_when_api_token_missing(self):
        config = JiraConfig(base_url="https://acme.atlassian.net", email="neil@acme.com", api_token="")
        self.assertFalse(config.is_configured)

    def test_auth_header_is_basic_base64(self):
        config = JiraConfig(
            base_url="https://acme.atlassian.net",
            email="neil@acme.com",
            api_token="mytoken",
        )
        import base64
        expected = "Basic " + base64.b64encode(b"neil@acme.com:mytoken").decode()
        self.assertEqual(config.auth_header, expected)


# ------------------------------------------------------------------ #
#  JiraTicketPayload                                                   #
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestJiraTicketPayload(unittest.TestCase):

    def setUp(self):
        self.result = _make_healing_result()

    def test_from_healing_result_builds_summary(self):
        payload = JiraTicketPayload.from_healing_result(self.result)
        self.assertIn("Self-Heal", payload.summary)
        self.assertIn("test_patient.py", payload.summary)

    def test_from_healing_result_includes_fix_in_description(self):
        payload = JiraTicketPayload.from_healing_result(self.result)
        self.assertIn("Updated status assertion", payload.description)

    def test_from_healing_result_includes_quality_score(self):
        payload = JiraTicketPayload.from_healing_result(self.result)
        self.assertIn("0.85", payload.description)

    def test_from_healing_result_labels_include_required_tags(self):
        payload = JiraTicketPayload.from_healing_result(self.result)
        self.assertIn("self-heal", payload.labels)
        self.assertIn("manual-review-required", payload.labels)

    def test_from_healing_result_no_fix_applied(self):
        result = _make_healing_result(fix_applied=None)
        payload = JiraTicketPayload.from_healing_result(result)
        self.assertIn("No fix details recorded", payload.description)

    def test_from_healing_result_no_quality_score(self):
        result = _make_healing_result(quality_score=None)
        payload = JiraTicketPayload.from_healing_result(result)
        self.assertIn("N/A", payload.description)

    def test_to_jira_json_structure(self):
        payload = JiraTicketPayload.from_healing_result(self.result)
        body    = payload.to_jira_json(project_key="SDET", issue_type="Bug")
        self.assertIn("fields", body)
        fields = body["fields"]
        self.assertEqual(fields["project"]["key"], "SDET")
        self.assertEqual(fields["issuetype"]["name"], "Bug")
        self.assertEqual(fields["summary"], payload.summary)
        self.assertIn("labels", fields)


# ------------------------------------------------------------------ #
#  JiraNotifier — dry-run path                                        #
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestJiraNotifierDryRun(unittest.TestCase):

    def setUp(self):
        # No credentials configured → dry-run
        self.notifier = JiraNotifier(config=JiraConfig(
            base_url="", email="", api_token=""
        ))
        self.result = _make_healing_result()

    def test_notify_returns_dry_run_result_when_no_credentials(self):
        ticket = self.notifier.notify(self.result)
        self.assertFalse(ticket.created)
        self.assertTrue(ticket.dry_run)
        self.assertIsNone(ticket.ticket_key)
        self.assertIsNone(ticket.ticket_url)

    def test_notify_dry_run_str_representation(self):
        ticket = self.notifier.notify(self.result)
        self.assertIn("DRY RUN", str(ticket))

    def test_notify_dry_run_makes_no_network_call(self):
        """Verify no urllib call is made in dry-run mode."""
        with patch("urllib.request.urlopen") as mock_open:
            self.notifier.notify(self.result)
            mock_open.assert_not_called()


# ------------------------------------------------------------------ #
#  JiraNotifier — live POST path (mocked)                             #
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestJiraNotifierLivePost(unittest.TestCase):

    def setUp(self):
        self.config = JiraConfig(
            base_url="https://acme.atlassian.net",
            project="SDET",
            email="neil@acme.com",
            api_token="secret",
        )
        self.notifier = JiraNotifier(config=self.config)
        self.result   = _make_healing_result()

    def test_notify_creates_ticket_on_200_response(self):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"key": "SDET-42"}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__  = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            ticket = self.notifier.notify(self.result)

        self.assertTrue(ticket.created)
        self.assertEqual(ticket.ticket_key, "SDET-42")
        self.assertEqual(ticket.ticket_url, "https://acme.atlassian.net/browse/SDET-42")

    def test_notify_returns_error_on_http_error(self):
        import urllib.error
        http_error = urllib.error.HTTPError(
            url="https://acme.atlassian.net/rest/api/3/issue",
            code=401,
            msg="Unauthorized",
            hdrs=MagicMock(),
            fp=MagicMock(read=lambda: b"Unauthorized"),
        )
        with patch("urllib.request.urlopen", side_effect=http_error):
            ticket = self.notifier.notify(self.result)

        self.assertFalse(ticket.created)
        self.assertIsNotNone(ticket.error)
        self.assertIn("401", ticket.error)

    def test_notify_returns_error_on_network_exception(self):
        with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("refused")):
            ticket = self.notifier.notify(self.result)

        self.assertFalse(ticket.created)
        self.assertIsNotNone(ticket.error)


# ------------------------------------------------------------------ #
#  SelfHealingAgent integration hook                                  #
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestSelfHealingAgentJiraHook(unittest.TestCase):
    """
    Verify that SelfHealingAgent.heal() calls JiraNotifier.notify()
    exactly once on a PASS result, and that the ticket key surfaces
    in the HealingResult warnings.
    """

    def test_jira_notify_called_on_pass(self):
        from shared.agent.self_healing_agent import SelfHealingAgent

        agent = SelfHealingAgent(require_approval=False)

        # Stub out every external dependency
        agent._input_guard.scrub_prompt    = lambda p: p
        agent._input_guard.is_safe         = lambda p: True
        agent._output_guard.validate       = lambda _: MagicMock(
            passed=True, failures=[], warnings=[]
        )
        agent._generate_fix                = lambda _: "def test_x(): assert True"

        mock_jira_result = JiraTicketResult(
            created=True, ticket_key="SDET-99",
            ticket_url="https://acme.atlassian.net/browse/SDET-99"
        )
        agent._jira.notify = MagicMock(return_value=mock_jira_result)

        healing = agent.heal(
            failing_test_path="projects/healthcare_fhir/api/tests/test_patient.py",
            error_message="AssertionError: Expected 200, got 404",
            spec_context="GET /Patient — FHIR R4",
        )

        agent._jira.notify.assert_called_once()
        self.assertEqual(healing.status, "PASS")
        self.assertTrue(
            any("SDET-99" in w for w in healing.warnings),
            f"Expected JIRA key in warnings, got: {healing.warnings}",
        )

    def test_jira_not_called_on_rejected(self):
        from shared.agent.self_healing_agent import SelfHealingAgent

        agent = SelfHealingAgent(require_approval=False)
        agent._input_guard.scrub_prompt = lambda p: p
        agent._input_guard.is_safe      = lambda p: True
        agent._output_guard.validate    = lambda _: MagicMock(
            passed=False, failures=["PHI detected"], warnings=[]
        )
        agent._generate_fix             = lambda _: "bad fix"
        agent._jira.notify              = MagicMock()

        healing = agent.heal(
            failing_test_path="projects/healthcare_fhir/api/tests/test_patient.py",
            error_message="Some error",
            spec_context="GET /Patient",
        )

        agent._jira.notify.assert_not_called()
        self.assertEqual(healing.status, "REJECTED")


if __name__ == "__main__":
    unittest.main()
