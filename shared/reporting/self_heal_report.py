"""
self_heal_report.py
-------------------
Phase 6 reporting — aggregates HealingResult + JiraTicketResult into
a single printable summary for CI output and Allure attachment.

In a regulated environment (HIPAA, PCI, IEC 62304) every self-heal
needs two records:
  1. The Allure report — shows the deviation visually in the current run.
  2. The JIRA ticket   — permanent audit trail that survives the build.

This class owns the first one: it produces a Markdown summary that CI
can print to stdout, write to a file, or attach as an Allure artifact.

Pattern : Builder — chain .add_healing() calls, then call .build()
SOLID   : SRP — produces one output (the report); knows nothing about
                how the report is delivered
          OCP — new sections added via subclass or .add_section()

Usage
-----
    from shared.reporting.self_heal_report import SelfHealReport

    report = (
        SelfHealReport(run_id="ci-run-1234")
        .add_healing(healing_result, jira_result)
        .add_healing(healing_result2, jira_result2)
        .build()
    )

    print(report.to_markdown())
    report.save("self_heal_report.md")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from shared.agent.self_healing_agent import HealingResult
    from shared.jira.jira_notifier import JiraTicketResult


# ------------------------------------------------------------------ #
#  Report entry                                                        #
# ------------------------------------------------------------------ #

@dataclass
class HealingEntry:
    """One self-heal event in the report."""
    test_path:     str
    status:        str
    fix_applied:   Optional[str]
    quality_score: Optional[float]
    cost_usd:      float
    duration_ms:   float
    warnings:      list[str]
    jira_key:      Optional[str]
    jira_url:      Optional[str]
    jira_dry_run:  bool

    @classmethod
    def from_results(
        cls,
        healing: "HealingResult",
        jira:    "JiraTicketResult",
    ) -> "HealingEntry":
        return cls(
            test_path=healing.test_path,
            status=healing.status,
            fix_applied=healing.fix_applied,
            quality_score=healing.quality_score,
            cost_usd=healing.cost_usd,
            duration_ms=healing.duration_ms,
            warnings=list(healing.warnings),
            jira_key=jira.ticket_key,
            jira_url=jira.ticket_url,
            jira_dry_run=jira.dry_run,
        )

    def to_markdown_section(self, index: int) -> str:
        score_str = (
            f"{self.quality_score:.2f}" if self.quality_score is not None else "N/A"
        )
        jira_str = (
            f"[{self.jira_key}]({self.jira_url})"
            if self.jira_key and self.jira_url
            else ("DRY RUN — no ticket" if self.jira_dry_run else "Not created")
        )
        warnings_md = (
            "\n".join(f"  - {w}" for w in self.warnings)
            if self.warnings else "  None"
        )
        fix_preview = (self.fix_applied or "None")[:120]

        return (
            f"### Event {index}: `{self.test_path.split('/')[-1]}`\n\n"
            f"| Field | Value |\n"
            f"|-------|-------|\n"
            f"| Status | `{self.status}` |\n"
            f"| Quality score | {score_str} |\n"
            f"| Cost | ${self.cost_usd:.4f} |\n"
            f"| Duration | {self.duration_ms:.0f} ms |\n"
            f"| JIRA ticket | {jira_str} |\n"
            f"| Test file | `{self.test_path}` |\n\n"
            f"**Fix applied:**\n```\n{fix_preview}\n```\n\n"
            f"**Warnings:**\n{warnings_md}\n"
        )


# ------------------------------------------------------------------ #
#  Built report (immutable)                                            #
# ------------------------------------------------------------------ #

@dataclass
class BuiltReport:
    """Immutable output of SelfHealReport.build()."""
    run_id:        str
    generated_at:  str
    total_events:  int
    passed:        int
    rejected:      int
    jira_created:  int
    total_cost:    float
    entries:       list[HealingEntry]

    def to_markdown(self) -> str:
        sections = "\n".join(
            e.to_markdown_section(i + 1)
            for i, e in enumerate(self.entries)
        )
        status_icon = "GREEN" if self.rejected == 0 else "YELLOW"
        return (
            f"# Self-Heal Report\n\n"
            f"**Run ID:** `{self.run_id}`  \n"
            f"**Generated:** {self.generated_at}  \n"
            f"**Status:** {status_icon}\n\n"
            f"## Summary\n\n"
            f"| Metric | Value |\n"
            f"|--------|-------|\n"
            f"| Total events | {self.total_events} |\n"
            f"| Passed | {self.passed} |\n"
            f"| Rejected / Error | {self.rejected} |\n"
            f"| JIRA tickets created | {self.jira_created} |\n"
            f"| Total AI cost | ${self.total_cost:.4f} |\n\n"
            f"---\n\n"
            f"## Events\n\n"
            f"{sections}\n"
            f"---\n\n"
            f"> **Compliance note:** All PASS events above require human review "
            f"via the linked JIRA ticket before the deviation is considered resolved. "
            f"No automated process may close these tickets.\n"
        )

    def to_json(self) -> str:
        return json.dumps({
            "run_id":       self.run_id,
            "generated_at": self.generated_at,
            "summary": {
                "total_events": self.total_events,
                "passed":       self.passed,
                "rejected":     self.rejected,
                "jira_created": self.jira_created,
                "total_cost":   self.total_cost,
            },
            "events": [
                {
                    "test_path":     e.test_path,
                    "status":        e.status,
                    "quality_score": e.quality_score,
                    "cost_usd":      e.cost_usd,
                    "duration_ms":   e.duration_ms,
                    "jira_key":      e.jira_key,
                    "jira_url":      e.jira_url,
                    "jira_dry_run":  e.jira_dry_run,
                    "warnings":      e.warnings,
                }
                for e in self.entries
            ],
        }, indent=2)

    def save(self, path: str | Path, fmt: str = "md") -> Path:
        """
        Write the report to disk.

        Parameters
        ----------
        path : output file path
        fmt  : "md" (default) or "json"
        """
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        content = self.to_json() if fmt == "json" else self.to_markdown()
        out.write_text(content, encoding="utf-8")
        return out


# ------------------------------------------------------------------ #
#  Builder                                                             #
# ------------------------------------------------------------------ #

class SelfHealReport:
    """
    Builder: collect self-heal events, then call .build() to get
    an immutable BuiltReport ready to print or save.

    Example
    -------
        report = (
            SelfHealReport(run_id="ci-run-1234")
            .add_healing(result1, jira1)
            .add_healing(result2, jira2)
            .build()
        )
        print(report.to_markdown())
        report.save("reports/self_heal_report.md")
    """

    def __init__(self, run_id: str = "local") -> None:
        self._run_id  = run_id
        self._entries: list[HealingEntry] = []

    def add_healing(
        self,
        healing: "HealingResult",
        jira:    "JiraTicketResult",
    ) -> "SelfHealReport":
        """Add one self-heal event. Returns self for chaining."""
        self._entries.append(HealingEntry.from_results(healing, jira))
        return self

    def build(self) -> BuiltReport:
        """Finalise and return an immutable BuiltReport."""
        passed   = sum(1 for e in self._entries if e.status == "PASS")
        rejected = sum(1 for e in self._entries if e.status != "PASS")
        created  = sum(1 for e in self._entries if e.jira_key is not None)
        cost     = sum(e.cost_usd for e in self._entries)

        return BuiltReport(
            run_id=self._run_id,
            generated_at=datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            total_events=len(self._entries),
            passed=passed,
            rejected=rejected,
            jira_created=created,
            total_cost=cost,
            entries=list(self._entries),
        )
