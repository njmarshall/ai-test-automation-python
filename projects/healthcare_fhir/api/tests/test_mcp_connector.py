"""
test_mcp_connector.py
---------------------
Tests for the McpConnector — Slack, GitHub, Jira integration.

Tests run without real credentials — they verify the connector
handles missing configuration gracefully and returns clear
McpResult objects rather than raising exceptions.
"""

from __future__ import annotations

import pytest

from shared.mcp.mcp_connector import McpConnector, McpResult


class TestMcpConnector:
    """Tests for MCP connector scaffold."""

    def test_connector_initialises(self) -> None:
        """Connector initialises without credentials."""
        connector = McpConnector()
        assert connector is not None

    def test_from_env_returns_connector(self) -> None:
        """from_env() returns a connector even without env vars set."""
        connector = McpConnector.from_env()
        assert connector is not None

    def test_status_shows_not_configured(self) -> None:
        """Status shows not configured when no credentials provided."""
        connector = McpConnector()
        status = connector.status()

        assert status["slack"]  == "not configured"
        assert status["github"] == "not configured"
        assert status["jira"]   == "not configured"

    def test_status_shows_configured_when_credentials_set(self) -> None:
        """Status shows configured when credentials are provided."""
        connector = McpConnector(
            slack_webhook_url="https://hooks.slack.com/test",
            github_token="ghp_test",
            github_repo="njmarshall/ai-test-automation-python",
            jira_url="https://test.atlassian.net",
            jira_token="test_token",
            jira_project="QA",
        )
        status = connector.status()

        assert status["slack"]  == "configured"
        assert status["github"] == "configured"
        assert status["jira"]   == "configured"

    def test_slack_notify_fails_gracefully_without_webhook(self) -> None:
        """Slack notification returns McpResult with success=False when not configured."""
        connector = McpConnector()
        result = connector.notify_slack(
            test_path="projects/healthcare_fhir/api/tests/test_patient.py",
            classification="TEST_DEFECT",
            proposed_fix="Randomize patient identifier",
        )

        assert isinstance(result, McpResult)
        assert result.success is False
        assert "not configured" in result.message
        assert result.action == "slack_notify"

    def test_github_pr_fails_gracefully_without_token(self) -> None:
        """GitHub PR returns McpResult with success=False when not configured."""
        connector = McpConnector()
        result = connector.open_github_pr(
            branch_name="fix/patient-identifier",
            title="fix: randomize patient identifier",
            body="Healing ticket: QA-1234",
        )

        assert isinstance(result, McpResult)
        assert result.success is False
        assert "not configured" in result.message
        assert result.action == "github_pr"

    def test_jira_ticket_fails_gracefully_without_credentials(self) -> None:
        """Jira ticket returns McpResult with success=False when not configured."""
        connector = McpConnector()
        result = connector.create_jira_ticket(
            test_path="projects/healthcare_fhir/api/tests/test_patient.py",
            classification="TEST_DEFECT",
            summary="Healed test: Patient identifier collision",
            description="POST /Patient returned 412.",
        )

        assert isinstance(result, McpResult)
        assert result.success is False
        assert "not configured" in result.message
        assert result.action == "jira_ticket"

    def test_mcp_result_summary(self) -> None:
        """McpResult summary returns readable string."""
        result = McpResult(
            action="slack_notify",
            success=True,
            message="Approval request sent to Slack",
            url="https://hooks.slack.com/test",
        )
        summary = result.summary()
        assert "OK" in summary
        assert "slack_notify" in summary

    def test_mcp_result_failure_summary(self) -> None:
        """McpResult failure summary shows FAILED."""
        result = McpResult(
            action="jira_ticket",
            success=False,
            message="JIRA_URL not configured",
        )
        summary = result.summary()
        assert "FAILED" in summary
        assert "jira_ticket" in summary
