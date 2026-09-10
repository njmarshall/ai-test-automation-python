"""
mcp_connector.py
----------------
MCP (Model Context Protocol) connector for SelfHealingAgent.

Real-world context
------------------
The SelfHealingAgent currently asks for terminal approval.
In production, engineers don't watch terminals — they watch Slack.

This connector bridges the SelfHealingAgent to:
  - Slack  — real-time approval notifications
  - GitHub — automatic PR creation after approval
  - Jira   — deviation ticket creation and CI/CD gate

Architecture
------------
  SelfHealingAgent → McpConnector → Slack (notify)
                                  → GitHub (open PR)
                                  → Jira (create ticket)

Pattern : Facade — McpConnector wraps all external integrations
SOLID   : OCP — add new connectors without modifying existing
          SRP — one connector, one job per method

Usage
-----
    connector = McpConnector(
        slack_webhook_url="https://hooks.slack.com/...",
        github_token="ghp_...",
        github_repo="njmarshall/ai-test-automation-python",
        jira_url="https://yourorg.atlassian.net",
        jira_token="...",
        jira_project="QA",
    )

    # Notify Slack when healing attempt needs approval
    connector.notify_slack(
        test_path="projects/healthcare_fhir/api/tests/test_patient.py",
        classification="TEST_DEFECT",
        proposed_fix="Randomize patient identifier per run",
        jira_ticket="QA-1234",
    )

    # Open GitHub PR after approval
    connector.open_github_pr(
        branch_name="fix/patient-identifier-collision",
        title="fix: randomize patient identifier to avoid 412 duplicates",
        body="Healing ticket: QA-1234",
    )

    # Create Jira deviation ticket
    connector.create_jira_ticket(
        test_path="projects/healthcare_fhir/api/tests/test_patient.py",
        classification="TEST_DEFECT",
        summary="Healed test: Patient identifier collision",
        description="POST /Patient returned 412 due to duplicate identifier.",
    )
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional


# ------------------------------------------------------------------ #
#  MCP Result                                                          #
# ------------------------------------------------------------------ #

@dataclass
class McpResult:
    """Result of an MCP connector action."""
    action:     str
    success:    bool
    message:    str
    url:        Optional[str] = None

    def summary(self) -> str:
        status = "OK" if self.success else "FAILED"
        return f"{status} | {self.action} | {self.message}"


# ------------------------------------------------------------------ #
#  MCP Connector                                                       #
# ------------------------------------------------------------------ #

class McpConnector:
    """
    Bridges SelfHealingAgent to Slack, GitHub, and Jira.

    All methods are safe to call even when credentials are not
    configured — they return a McpResult with success=False and
    a clear message rather than raising exceptions. This allows
    the SelfHealingAgent to run in environments without MCP
    credentials configured.

    Example
    -------
        connector = McpConnector.from_env()

        result = connector.notify_slack(
            test_path="projects/healthcare_fhir/...",
            classification="TEST_DEFECT",
            proposed_fix="Randomize patient identifier",
            jira_ticket="QA-1234",
        )
        print(result.summary())
        # OK | slack_notify | Message sent to #qa-alerts
    """

    def __init__(
        self,
        slack_webhook_url: Optional[str] = None,
        github_token:      Optional[str] = None,
        github_repo:       Optional[str] = None,
        jira_url:          Optional[str] = None,
        jira_token:        Optional[str] = None,
        jira_project:      Optional[str] = None,
    ) -> None:
        self._slack_webhook = slack_webhook_url
        self._github_token  = github_token
        self._github_repo   = github_repo
        self._jira_url      = jira_url
        self._jira_token    = jira_token
        self._jira_project  = jira_project

    @classmethod
    def from_env(cls) -> "McpConnector":
        """
        Create connector from environment variables.

        Required env vars:
          SLACK_WEBHOOK_URL
          GITHUB_TOKEN
          GITHUB_REPO (e.g. njmarshall/ai-test-automation-python)
          JIRA_URL
          JIRA_TOKEN
          JIRA_PROJECT
        """
        return cls(
            slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
            github_token=os.getenv("GITHUB_TOKEN"),
            github_repo=os.getenv("GITHUB_REPO"),
            jira_url=os.getenv("JIRA_URL"),
            jira_token=os.getenv("JIRA_TOKEN"),
            jira_project=os.getenv("JIRA_PROJECT"),
        )

    # ------------------------------------------------------------------ #
    #  Slack                                                               #
    # ------------------------------------------------------------------ #

    def notify_slack(
        self,
        test_path:      str,
        classification: str,
        proposed_fix:   str,
        jira_ticket:    Optional[str] = None,
        cost_usd:       float = 0.0,
    ) -> McpResult:
        """
        Send healing approval request to Slack.

        Posts a structured message to the configured webhook
        with the test path, classification, proposed fix,
        Jira ticket link, and cost.

        The engineer approves or rejects directly from Slack.
        The discussion is archived in the Slack thread.
        """
        if not self._slack_webhook:
            return McpResult(
                action="slack_notify",
                success=False,
                message="SLACK_WEBHOOK_URL not configured",
            )

        try:
            import httpx

            jira_line = f"Jira: {jira_ticket}" if jira_ticket else "Jira: not yet created"

            payload = {
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "SelfHealingAgent — Approval Required"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Test:*\n`{test_path}`"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Classification:*\n{classification}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Proposed fix:*\n{proposed_fix}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Cost:*\n${cost_usd:.4f}"
                            },
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{jira_line}\nReview and close the Jira ticket to release the CI/CD gate."
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Approve"},
                                "style": "primary",
                                "value": "approve"
                            },
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Reject"},
                                "style": "danger",
                                "value": "reject"
                            },
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Investigate"},
                                "value": "investigate"
                            }
                        ]
                    }
                ]
            }

            response = httpx.post(
                self._slack_webhook,
                json=payload,
                timeout=5.0,
            )

            if response.status_code == 200:
                return McpResult(
                    action="slack_notify",
                    success=True,
                    message="Approval request sent to Slack",
                )
            return McpResult(
                action="slack_notify",
                success=False,
                message=f"Slack returned {response.status_code}",
            )

        except Exception as e:
            return McpResult(
                action="slack_notify",
                success=False,
                message=f"Slack notification failed: {e}",
            )

    # ------------------------------------------------------------------ #
    #  GitHub                                                              #
    # ------------------------------------------------------------------ #

    def open_github_pr(
        self,
        branch_name: str,
        title:       str,
        body:        str,
        base_branch: str = "main",
    ) -> McpResult:
        """
        Open a GitHub pull request with the proposed fix.

        The PR is not merged automatically — it requires human
        review and approval before merging. This preserves the
        human-in-the-loop safety checkpoint.
        """
        if not self._github_token or not self._github_repo:
            return McpResult(
                action="github_pr",
                success=False,
                message="GITHUB_TOKEN or GITHUB_REPO not configured",
            )

        try:
            import httpx

            response = httpx.post(
                f"https://api.github.com/repos/{self._github_repo}/pulls",
                headers={
                    "Authorization": f"Bearer {self._github_token}",
                    "Accept": "application/vnd.github+json",
                },
                json={
                    "title": title,
                    "body":  body,
                    "head":  branch_name,
                    "base":  base_branch,
                },
                timeout=10.0,
            )

            if response.status_code == 201:
                pr_url = response.json().get("html_url", "")
                return McpResult(
                    action="github_pr",
                    success=True,
                    message=f"PR opened: {title}",
                    url=pr_url,
                )
            return McpResult(
                action="github_pr",
                success=False,
                message=f"GitHub returned {response.status_code}: {response.text[:200]}",
            )

        except Exception as e:
            return McpResult(
                action="github_pr",
                success=False,
                message=f"GitHub PR failed: {e}",
            )

    # ------------------------------------------------------------------ #
    #  Jira                                                                #
    # ------------------------------------------------------------------ #

    def create_jira_ticket(
        self,
        test_path:      str,
        classification: str,
        summary:        str,
        description:    str,
    ) -> McpResult:
        """
        Create a Jira deviation ticket for the healed test.

        The ticket blocks the CI/CD gate and the quarterly
        release plan. The version cannot ship until this
        ticket is closed and reviewed.

        The ticket requires:
        - Owner assignment
        - Impact assessment (test procedure, documentation, screenshots)
        - Manual retest confirmation
        - Final approval recorded in Jira
        """
        if not self._jira_url or not self._jira_token or not self._jira_project:
            return McpResult(
                action="jira_ticket",
                success=False,
                message="JIRA_URL, JIRA_TOKEN, or JIRA_PROJECT not configured",
            )

        try:
            import httpx
            import base64

            auth = base64.b64encode(
                f":{self._jira_token}".encode()
            ).decode()

            payload = {
                "fields": {
                    "project":     {"key": self._jira_project},
                    "summary":     f"[HEALED_WITH_DEVIATION] {summary}",
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {"type": "text", "text": description}
                                ]
                            },
                            {
                                "type": "paragraph",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": f"Test path: {test_path}\n"
                                                f"Classification: {classification}\n"
                                                f"Action required: Review deviation, "
                                                f"update documentation, confirm manual retest."
                                    }
                                ]
                            }
                        ]
                    },
                    "issuetype":   {"name": "Bug"},
                    "priority":    {"name": "Medium"},
                    "labels":      ["HEALED_WITH_DEVIATION", "self-healing-agent"],
                }
            }

            response = httpx.post(
                f"{self._jira_url}/rest/api/3/issue",
                headers={
                    "Authorization": f"Basic {auth}",
                    "Content-Type":  "application/json",
                },
                json=payload,
                timeout=10.0,
            )

            if response.status_code == 201:
                ticket_key = response.json().get("key", "")
                ticket_url = f"{self._jira_url}/browse/{ticket_key}"
                return McpResult(
                    action="jira_ticket",
                    success=True,
                    message=f"Deviation ticket created: {ticket_key}",
                    url=ticket_url,
                )
            return McpResult(
                action="jira_ticket",
                success=False,
                message=f"Jira returned {response.status_code}: {response.text[:200]}",
            )

        except Exception as e:
            return McpResult(
                action="jira_ticket",
                success=False,
                message=f"Jira ticket creation failed: {e}",
            )

    # ------------------------------------------------------------------ #
    #  Status                                                              #
    # ------------------------------------------------------------------ #

    def status(self) -> dict:
        """Return configuration status of all connectors."""
        return {
            "slack":  "configured" if self._slack_webhook else "not configured",
            "github": "configured" if self._github_token and self._github_repo else "not configured",
            "jira":   "configured" if self._jira_url and self._jira_token else "not configured",
        }
