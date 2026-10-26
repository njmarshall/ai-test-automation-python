"""
jira_notifier.py
----------------
Phase 6 — JIRA auto-ticket integration for StalenessDetector / SelfHealingAgent.

When the self-healing agent applies a fix, this notifier creates (or updates)
a JIRA ticket so the deviation has a permanent, human-closeable audit trail.
This is a hard compliance requirement in HIPAA, PCI, and IEC 62304 environments:
  - The CI build passes, but the deviation must be reviewed by a human.
  - The JIRA ticket is the record that a human acknowledged the self-heal.
  - No automated process should close the ticket — only a human can.

Architecture
------------
  Pattern : Facade — hides JIRA REST API complexity behind a single `notify()` call
  SOLID   : SRP — this class does one job: translate a HealingResult into a ticket
            OCP — new notification channels (Slack, email) extend without changes here
            DIP — depends on a config dict, not on concrete env var reads

Credentials
-----------
Set these environment variables (or pass via JiraConfig):
  JIRA_BASE_URL   = https://your-org.atlassian.net
  JIRA_PROJECT    = SDET
  JIRA_EMAIL      = neil@example.com
  JIRA_API_TOKEN  = (Atlassian API token — not your password)

If any credential is missing, JiraNotifier runs in DRY_RUN mode:
  - It prints the ticket it would have created.
  - It returns a JiraTicketResult with dry_run=True.
  - No network call is made.
  This makes Phase 6 safe to run in CI without JIRA credentials.

Usage
-----
    from shared.jira.jira_notifier import JiraNotifier
    from shared.agent.self_healing_agent import HealingResult

    notifier = JiraNotifier()
    result   = notifier.notify(healing_result)

    if result.created:
        print(f"JIRA ticket: {result.ticket_key}  {result.ticket_url}")
    elif result.dry_run:
        print("DRY RUN — no ticket created (missing JIRA credentials)")
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from base64 import b64encode
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from shared.agent.self_healing_agent import HealingResult


# ------------------------------------------------------------------ #
#  Config                                                              #
# ------------------------------------------------------------------ #

@dataclass
class JiraConfig:
    """
    JIRA connection config.  Reads from env vars by default so
    secrets never appear in source code.
    """
    base_url:   str = field(default_factory=lambda: os.getenv("JIRA_BASE_URL", ""))
    project:    str = field(default_factory=lambda: os.getenv("JIRA_PROJECT", "SDET"))
    email:      str = field(default_factory=lambda: os.getenv("JIRA_EMAIL", ""))
    api_token:  str = field(default_factory=lambda: os.getenv("JIRA_API_TOKEN", ""))
    issue_type: str = "Bug"   # "Bug" maps to a standard JIRA issue type

    @property
    def is_configured(self) -> bool:
        """True only when all three required credentials are present."""
        return bool(self.base_url and self.email and self.api_token)

    @property
    def auth_header(self) -> str:
        """Basic-auth header value for Atlassian Cloud REST API v3."""
        token = b64encode(f"{self.email}:{self.api_token}".encode()).decode()
        return f"Basic {token}"


# ------------------------------------------------------------------ #
#  Ticket data                                                         #
# ------------------------------------------------------------------ #

@dataclass
class JiraTicketPayload:
    """
    All the information that goes into the JIRA ticket.
    Built from a HealingResult so the notifier has a clean boundary.
    """
    summary:       str
    description:   str
    test_path:     str
    fix_applied:   Optional[str]
    quality_score: Optional[float]
    timestamp:     str
    labels:        list[str] = field(default_factory=list)

    @classmethod
    def from_healing_result(cls, result: "HealingResult") -> "JiraTicketPayload":
        """Factory: build a payload from a HealingResult."""
        test_name   = result.test_path.split("/")[-1]
        now_utc     = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        score_str   = (
            f"{result.quality_score:.2f}" if result.quality_score is not None
            else "N/A"
        )

        summary = (
            f"[Self-Heal] Deviation detected and auto-fixed in {test_name}"
        )

        description = (
            f"h2. Self-Healing Deviation Report\n\n"
            f"*Detected:* {now_utc}\n"
            f"*Test file:* {result.test_path}\n"
            f"*Quality score:* {score_str} (threshold: 0.70)\n\n"
            f"h3. What was fixed\n\n"
            f"{result.fix_applied or 'No fix details recorded.'}\n\n"
            f"h3. Warnings\n\n"
            f"{chr(10).join(f'* {w}' for w in result.warnings) or 'None'}\n\n"
            f"h3. Action required\n\n"
            f"A human must review the auto-applied fix and close this ticket "
            f"to confirm the deviation is understood and accepted.\n\n"
            f"*Do not close this ticket via automation.*\n\n"
            f"h3. Compliance note\n\n"
            f"This ticket exists because the system self-healed without direct "
            f"human intervention. In HIPAA, PCI, and IEC 62304 environments this "
            f"constitutes a deviation from the validated test suite and requires "
            f"documented human review."
        )

        return cls(
            summary=summary,
            description=description,
            test_path=result.test_path,
            fix_applied=result.fix_applied,
            quality_score=result.quality_score,
            timestamp=now_utc,
            labels=["self-heal", "manual-review-required", "ai-test-automation"],
        )

    def to_jira_json(self, project_key: str, issue_type: str) -> dict:
        """Serialize to the JIRA REST API v3 create-issue body."""
        return {
            "fields": {
                "project":     {"key": project_key},
                "issuetype":   {"name": issue_type},
                "summary":     self.summary,
                "description": {
                    "version": 1,
                    "type":    "doc",
                    "content": [
                        {
                            "type":    "paragraph",
                            "content": [
                                {"type": "text", "text": self.description}
                            ],
                        }
                    ],
                },
                "labels": self.labels,
            }
        }


# ------------------------------------------------------------------ #
#  Result                                                              #
# ------------------------------------------------------------------ #

@dataclass
class JiraTicketResult:
    """Outcome of a notify() call."""
    created:    bool
    dry_run:    bool    = False
    ticket_key: Optional[str] = None
    ticket_url: Optional[str] = None
    error:      Optional[str] = None

    def __str__(self) -> str:
        if self.dry_run:
            return "JiraTicketResult(DRY RUN — no ticket created)"
        if self.created:
            return f"JiraTicketResult(created={self.ticket_key} url={self.ticket_url})"
        return f"JiraTicketResult(failed — {self.error})"


# ------------------------------------------------------------------ #
#  Notifier (Facade)                                                   #
# ------------------------------------------------------------------ #

class JiraNotifier:
    """
    Facade: translates a HealingResult into a JIRA ticket.

    Dry-run mode activates automatically when JIRA credentials are
    not configured — safe to run in CI without secrets.
    """

    def __init__(self, config: Optional[JiraConfig] = None) -> None:
        self._config = config or JiraConfig()

    # ------------------------------------------------------------------ #
    #  Public interface                                                    #
    # ------------------------------------------------------------------ #

    def notify(self, healing_result: "HealingResult") -> JiraTicketResult:
        """
        Create a JIRA ticket for a completed self-healing event.

        Parameters
        ----------
        healing_result : the HealingResult from SelfHealingAgent.heal()

        Returns
        -------
        JiraTicketResult — contains ticket key/URL or dry_run=True
        """
        payload = JiraTicketPayload.from_healing_result(healing_result)

        if not self._config.is_configured:
            self._print_dry_run(payload)
            return JiraTicketResult(created=False, dry_run=True)

        return self._post_ticket(payload)

    # ------------------------------------------------------------------ #
    #  Internal                                                            #
    # ------------------------------------------------------------------ #

    def _post_ticket(self, payload: JiraTicketPayload) -> JiraTicketResult:
        """POST to JIRA REST API v3 and return the result."""
        url  = f"{self._config.base_url.rstrip('/')}/rest/api/3/issue"
        body = json.dumps(
            payload.to_jira_json(self._config.project, self._config.issue_type)
        ).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": self._config.auth_header,
                "Content-Type":  "application/json",
                "Accept":        "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data       = json.loads(resp.read().decode())
                ticket_key = data.get("key", "")
                ticket_url = (
                    f"{self._config.base_url.rstrip('/')}/browse/{ticket_key}"
                )
                return JiraTicketResult(
                    created=True,
                    ticket_key=ticket_key,
                    ticket_url=ticket_url,
                )
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode(errors="replace")
            return JiraTicketResult(
                created=False,
                error=f"HTTP {exc.code}: {body_text[:200]}",
            )
        except Exception as exc:
            return JiraTicketResult(
                created=False,
                error=str(exc),
            )

    def _print_dry_run(self, payload: JiraTicketPayload) -> None:
        """Print what the ticket would look like in dry-run mode."""
        print("\n" + "="*60)
        print("JIRA NOTIFIER — DRY RUN (no credentials configured)")
        print("="*60)
        print(f"Would create: {payload.summary}")
        print(f"Labels      : {', '.join(payload.labels)}")
        print(f"Test path   : {payload.test_path}")
        print(f"Timestamp   : {payload.timestamp}")
        print("="*60 + "\n")
        print("To enable real JIRA tickets, set:")
        print("  JIRA_BASE_URL   = https://your-org.atlassian.net")
        print("  JIRA_PROJECT    = SDET")
        print("  JIRA_EMAIL      = your@email.com")
        print("  JIRA_API_TOKEN  = (Atlassian API token)")
        print("="*60 + "\n")
