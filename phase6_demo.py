"""
phase6_demo.py
--------------
End-to-end demonstration of the Phase 6 self-healing audit loop.

What this shows
---------------
1. SelfHealingAgent.heal() runs on a synthetic failing test (no real
   Claude API call needed -- ANTHROPIC_API_KEY is not required).
2. JiraNotifier.notify() fires in dry-run mode when credentials are
   absent, printing the ticket payload to stdout instead of posting.
3. SelfHealReport builder aggregates every event from the CI run.
4. BuiltReport.to_markdown() prints the Allure-ready summary to stdout
   and saves it to reports/phase6_report.md.

Run locally
-----------
    python phase6_demo.py

Run in CI (no credentials needed)
----------------------------------
    ANTHROPIC_API_KEY=  python phase6_demo.py

Design patterns exercised
-------------------------
    Facade        -- JiraNotifier hides all JIRA REST API complexity
    Builder       -- SelfHealReport chains .add_healing() calls
    Value Object  -- BuiltReport is immutable after .build()
    Template Method -- SelfHealingAgent.heal() defines the repair skeleton

Compliance note
---------------
In HIPAA / PCI / IEC 62304 environments, every self-heal that reaches
PASS must produce a JIRA ticket so a human can review and close it.
This demo shows both the dry-run path (no credentials) and what the
real path would produce.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

# Ensure the repo root is on sys.path so shared/ imports resolve
# when the script is run from any directory.
REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))

from shared.agent.self_healing_agent import HealingResult, SelfHealingAgent
from shared.jira.jira_notifier import JiraTicketResult
from shared.reporting.self_heal_report import SelfHealReport

DIVIDER = "=" * 60


def section(title: str) -> None:
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


def run_heal_simulation(agent: SelfHealingAgent, label: str, status: str) -> HealingResult:
    """
    Return a synthetic HealingResult without making any real API call.
    Mocks _generate_fix and _request_approval so the full heal() skeleton
    runs and reaches the PASS or REJECTED branch.
    """
    fake_fix = (
        "def test_patient_create(fhir_client):\n"
        "    response = fhir_client.post('/Patient', json=PATIENT_PAYLOAD)\n"
        "    assert response.status_code in (200, 201)  # accept both\n"
    )

    if status == "PASS":
        with patch.object(agent, "_generate_fix", return_value=fake_fix), \
             patch.object(agent, "_request_approval", return_value=True), \
             patch.object(agent, "_read_test", return_value="# original test"):
            result = agent.heal(
                failing_test_path=f"projects/healthcare_fhir/api/tests/{label}.py",
                error_message="AssertionError: Expected status 201, got 200",
                spec_context="POST /Patient -- FHIR R4 Patient creation",
            )
    else:
        bad_fix = "# no test methods here -- malformed output"
        with patch.object(agent, "_generate_fix", return_value=bad_fix), \
             patch.object(agent, "_read_test", return_value="# original test"):
            result = agent.heal(
                failing_test_path=f"projects/healthcare_fhir/api/tests/{label}.py",
                error_message="AssertionError: Expected status 201, got 422",
                spec_context="POST /Patient -- FHIR R4 Patient creation",
            )

    return result


def main() -> None:
    print(f"\n{DIVIDER}")
    print("  Phase 6 -- Self-Healing Audit Loop Demo")
    print(f"{DIVIDER}")
    print("  SelfHealingAgent -> JiraNotifier (dry-run) -> SelfHealReport")
    print(f"{DIVIDER}")

    agent = SelfHealingAgent(require_approval=False)

    # Event 1: PASS
    section("Event 1 -- Heal attempt: PASS")
    result_pass = run_heal_simulation(agent, label="test_patient_create", status="PASS")
    print(result_pass.summary())
    jira_pass = JiraTicketResult(created=False, dry_run=True, ticket_key="SDET-DRY-001")
    print(f"\n  JiraNotifier result : dry_run={jira_pass.dry_run}, key={jira_pass.ticket_key}")

    # Event 2: REJECTED
    section("Event 2 -- Heal attempt: REJECTED (OutputGuard blocked it)")
    result_rejected = run_heal_simulation(agent, label="test_patient_update", status="REJECTED")
    print(result_rejected.summary())
    jira_rejected = JiraTicketResult(created=False, dry_run=False)
    print("\n  JiraNotifier result : not called (only fires on PASS)")

    # Event 3: second PASS
    section("Event 3 -- Heal attempt: PASS (second fix in this run)")
    result_pass2 = run_heal_simulation(agent, label="test_encounter_create", status="PASS")
    print(result_pass2.summary())
    jira_pass2 = JiraTicketResult(created=False, dry_run=True, ticket_key="SDET-DRY-002")
    print(f"\n  JiraNotifier result : dry_run={jira_pass2.dry_run}, key={jira_pass2.ticket_key}")

    # Build the aggregated report
    section("SelfHealReport -- aggregating all 3 events")
    report = (
        SelfHealReport(run_id="ci-demo-run-001")
        .add_healing(result_pass,     jira_pass)
        .add_healing(result_rejected, jira_rejected)
        .add_healing(result_pass2,    jira_pass2)
        .build()
    )

    # Print Markdown
    section("BuiltReport.to_markdown() -- Allure attachment preview")
    print(report.to_markdown())

    # Save to reports/
    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    md_path   = report.save(reports_dir / "phase6_report.md",   fmt="md")
    json_path = report.save(reports_dir / "phase6_report.json", fmt="json")

    section("Reports saved")
    print(f"  Markdown : {md_path}")
    print(f"  JSON     : {json_path}")
    print(f"\n  Open {md_path} to see the Allure-ready audit summary.\n")


if __name__ == "__main__":
    main()
