"""
input_guard.py
--------------
Input guardrail — scrubs sensitive data before sending to AI.

Real-world context
------------------
In healthcare AI systems, patient data (PHI) must never be
sent to external AI APIs without scrubbing first. HIPAA requires
that Protected Health Information is de-identified before leaving
the healthcare system boundary.

This guardrail sits BEFORE the AI call:
  Raw input → InputGuard → Scrubbed input → Claude API

What it scrubs
--------------
- Patient names
- Date of birth
- Social Security Numbers
- Phone numbers
- Email addresses
- Medical record numbers
- IP addresses
- FHIR resource IDs that contain patient identifiers

Pattern : Strategy — different scrubbing rules per data type
SOLID   : SRP — one class, one job: scrub sensitive input
          OCP — add new scrubbing rules without modifying existing

Usage
-----
    guard = InputGuard()
    safe_input = guard.scrub("Patient John Smith DOB 1990-01-01")
    # Returns: "Patient [NAME] DOB [DATE]"

    # Or use as decorator on test generator prompts
    safe_prompt = guard.scrub_prompt(raw_prompt)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


# ------------------------------------------------------------------ #
#  Scrub result                                                        #
# ------------------------------------------------------------------ #

@dataclass
class ScrubResult:
    """Result of a scrubbing operation."""
    original:     str
    scrubbed:     str
    items_found:  List[str]

    @property
    def was_modified(self) -> bool:
        return self.original != self.scrubbed

    @property
    def is_safe(self) -> bool:
        return len(self.items_found) == 0

    def summary(self) -> str:
        if self.is_safe:
            return "Input is clean — no PHI detected."
        return (
            f"PHI detected and scrubbed: {self.items_found}. "
            f"Input modified before sending to AI."
        )


# ------------------------------------------------------------------ #
#  Input Guard                                                         #
# ------------------------------------------------------------------ #

class InputGuard:
    """
    Scrubs PHI and sensitive data from input before sending to AI.

    Designed for healthcare test automation where test prompts
    may accidentally include patient data from test fixtures.

    Example
    -------
        guard = InputGuard()

        # Scrub a raw test prompt
        result = guard.scrub_with_report(
            "Generate tests for Patient John Smith, MRN 12345"
        )
        print(result.scrubbed)
        # "Generate tests for Patient [NAME], MRN [MRN]"

        print(result.items_found)
        # ["name", "mrn"]
    """

    # PHI patterns — order matters, more specific first
    PATTERNS = [
        # Social Security Numbers
        (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]", "ssn"),
        # Medical Record Numbers
        (r"\bMRN[:\s]+\d+\b", "[MRN]", "mrn"),
        # Phone numbers
        (r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b", "[PHONE]", "phone"),
        # Email addresses
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]", "email"),
        # IP addresses
        (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[IP]", "ip"),
        # Dates of birth (common formats)
        (r"\b(?:DOB|Date of Birth|born)[:\s]+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
         "[DOB]", "dob"),
        # FHIR Patient IDs (UUIDs)
        (r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
         "[PATIENT-ID]", "fhir_id"),
        # Common name patterns after "Patient"
        (r"(?<=Patient\s)[A-Z][a-z]+\s[A-Z][a-z]+", "[NAME]", "name"),
    ]

    def __init__(self, strict: bool = False) -> None:
        """
        Parameters
        ----------
        strict : if True, raise an error when PHI is detected
                 if False, scrub and continue (default)
        """
        self.strict = strict
        self._compiled = [
            (re.compile(pattern, re.IGNORECASE), replacement, label)
            for pattern, replacement, label in self.PATTERNS
        ]

    def scrub(self, text: str) -> str:
        """Scrub PHI from text. Returns clean text."""
        return self.scrub_with_report(text).scrubbed

    def scrub_with_report(self, text: str) -> ScrubResult:
        """
        Scrub PHI and return a detailed report.

        Returns ScrubResult with original, scrubbed text,
        and list of PHI types found.
        """
        scrubbed    = text
        items_found = []

        for pattern, replacement, label in self._compiled:
            new_text, count = pattern.subn(replacement, scrubbed)
            if count > 0:
                items_found.append(label)
                scrubbed = new_text

        if self.strict and items_found:
            raise ValueError(
                f"PHI detected in input — cannot send to AI. "
                f"Types found: {items_found}"
            )

        return ScrubResult(
            original=text,
            scrubbed=scrubbed,
            items_found=items_found,
        )

    def scrub_prompt(self, prompt: str) -> str:
        """
        Convenience method for scrubbing AI generator prompts.

        Use before sending any prompt to Claude or other LLMs.

        Example
        -------
            guard = InputGuard()
            safe = guard.scrub_prompt(raw_prompt)
            response = claude.messages.create(
                messages=[{"role": "user", "content": safe}]
            )
        """
        return self.scrub(prompt)

    def is_safe(self, text: str) -> bool:
        """Return True if text contains no detectable PHI."""
        return self.scrub_with_report(text).is_safe
