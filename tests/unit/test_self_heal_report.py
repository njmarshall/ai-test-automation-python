"""
test_self_heal_report.py
------------------------
Unit tests for Phase 6 SelfHealReport builder and BuiltReport output.
No network, no filesystem writes (except a tmp path test).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from shared.jira.jira_notifier import JiraTicketResult
from shared.reporting.self_heal_report import BuiltReport, HealingEntry, SelfHealReport


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

def _healing(status="PASS", path="projects/healthcare_fhir/api/tests/test_patient.py",
             fix="Fixed assertion.", score=0.85, cost=0.002, duration=310.0, warnings=None):
    r = MagicMock()
    r.status        = status
    r.test_path     = path
    r.fix_applied   = fix
    r.quality_score = score
    r.cost_usd      = cost
    r.duration_ms   = duration
    r.warnings      = warnings if warnings is not None else []
    return r

def _jira(created=True, key="SDET-42", url="https://acme.atlassian.net/browse/SDET-42",
          dry_run=False, error=None):
    return JiraTicketResult(created=created, ticket_key=key, ticket_url=url,
                            dry_run=dry_run, error=error)


# ------------------------------------------------------------------ #
#  HealingEntry                                                        #
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestHealingEntry(unittest.TestCase):

    def test_from_results_maps_fields(self):
        entry = HealingEntry.from_results(_healing(), _jira())
        self.assertEqual(entry.status, "PASS")
        self.assertEqual(entry.jira_key, "SDET-42")
        self.assertFalse(entry.jira_dry_run)

    def test_from_results_dry_run(self):
        entry = HealingEntry.from_results(_healing(), _jira(created=False, key=None, url=None, dry_run=True))
        self.assertTrue(entry.jira_dry_run)
        self.assertIsNone(entry.jira_key)

    def test_markdown_section_contains_status(self):
        entry = HealingEntry.from_results(_healing(), _jira())
        md = entry.to_markdown_section(1)
        self.assertIn("PASS", md)
        self.assertIn("SDET-42", md)
        self.assertIn("test_patient.py", md)

    def test_markdown_section_dry_run_label(self):
        entry = HealingEntry.from_results(_healing(), _jira(created=False, key=None, url=None, dry_run=True))
        md = entry.to_markdown_section(1)
        self.assertIn("DRY RUN", md)

    def test_markdown_section_no_quality_score(self):
        entry = HealingEntry.from_results(_healing(score=None), _jira())
        md = entry.to_markdown_section(1)
        self.assertIn("N/A", md)


# ------------------------------------------------------------------ #
#  SelfHealReport builder                                              #
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestSelfHealReportBuilder(unittest.TestCase):

    def test_empty_build(self):
        report = SelfHealReport(run_id="test-run").build()
        self.assertEqual(report.total_events, 0)
        self.assertEqual(report.passed, 0)
        self.assertEqual(report.total_cost, 0.0)

    def test_single_pass_event(self):
        report = SelfHealReport("run-1").add_healing(_healing(), _jira()).build()
        self.assertEqual(report.total_events, 1)
        self.assertEqual(report.passed, 1)
        self.assertEqual(report.rejected, 0)
        self.assertEqual(report.jira_created, 1)

    def test_rejected_event_counted(self):
        report = (
            SelfHealReport("run-1")
            .add_healing(_healing(status="REJECTED"), _jira(created=False, key=None, url=None))
            .build()
        )
        self.assertEqual(report.rejected, 1)
        self.assertEqual(report.passed, 0)
        self.assertEqual(report.jira_created, 0)

    def test_mixed_events(self):
        report = (
            SelfHealReport("run-1")
            .add_healing(_healing(status="PASS"), _jira())
            .add_healing(_healing(status="REJECTED"), _jira(created=False, key=None, url=None))
            .build()
        )
        self.assertEqual(report.total_events, 2)
        self.assertEqual(report.passed, 1)
        self.assertEqual(report.rejected, 1)

    def test_cost_accumulated(self):
        report = (
            SelfHealReport("run-1")
            .add_healing(_healing(cost=0.002), _jira())
            .add_healing(_healing(cost=0.003), _jira())
            .build()
        )
        self.assertAlmostEqual(report.total_cost, 0.005, places=6)

    def test_chaining_returns_self(self):
        builder = SelfHealReport("run-1")
        result  = builder.add_healing(_healing(), _jira())
        self.assertIs(result, builder)


# ------------------------------------------------------------------ #
#  BuiltReport output                                                  #
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestBuiltReportOutput(unittest.TestCase):

    def setUp(self):
        self.report = (
            SelfHealReport("ci-run-9999")
            .add_healing(_healing(warnings=["Review required."]), _jira())
            .build()
        )

    def test_to_markdown_contains_run_id(self):
        md = self.report.to_markdown()
        self.assertIn("ci-run-9999", md)

    def test_to_markdown_contains_compliance_note(self):
        md = self.report.to_markdown()
        self.assertIn("Compliance note", md)

    def test_to_markdown_contains_jira_link(self):
        md = self.report.to_markdown()
        self.assertIn("SDET-42", md)

    def test_to_json_is_valid_json(self):
        data = json.loads(self.report.to_json())
        self.assertIn("run_id", data)
        self.assertEqual(data["run_id"], "ci-run-9999")
        self.assertIn("summary", data)
        self.assertIn("events", data)
        self.assertEqual(len(data["events"]), 1)

    def test_to_json_event_fields(self):
        data   = json.loads(self.report.to_json())
        event  = data["events"][0]
        self.assertEqual(event["status"], "PASS")
        self.assertEqual(event["jira_key"], "SDET-42")
        self.assertAlmostEqual(event["quality_score"], 0.85)

    def test_save_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.md"
            self.report.save(out, fmt="md")
            self.assertTrue(out.exists())
            content = out.read_text()
            self.assertIn("ci-run-9999", content)

    def test_save_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.json"
            self.report.save(out, fmt="json")
            data = json.loads(out.read_text())
            self.assertEqual(data["run_id"], "ci-run-9999")

    def test_save_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nested" / "deep" / "report.md"
            self.report.save(out)
            self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
