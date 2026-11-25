"""
test_input_guard_properties.py
------------------------------
Property-based tests for the PHI scrubber (InputGuard), using Hypothesis.

An example-based test checks the inputs we thought of. A property-based
test states a rule that must hold for every input, then lets Hypothesis
generate thousands of inputs, including ugly ones, to break it. When it
finds a failure, it shrinks it to the smallest example and the
@example decorator pins it as a permanent regression test.

Properties:
  1. No leak: an SSN placed anywhere in arbitrary text is always removed.
  2. No leak: an email address placed anywhere is always removed.
  3. Idempotent: scrubbing twice gives the same result as scrubbing once.
  4. Clean after scrub: is_safe() is true for anything scrub() returned.
  5. No false positives: text with no digits, no '@', and no trigger words
     comes back unchanged.
"""

from __future__ import annotations

import re

import pytest
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from shared.guardrails.input_guard import InputGuard

pytestmark = pytest.mark.unit

GUARD = InputGuard()
SETTINGS = settings(max_examples=400, deadline=None, suppress_health_check=[HealthCheck.too_slow])

SSN_SHAPE = re.compile(r"\d{3}-\d{2}-\d{4}")

ssns = st.builds(
    lambda a, b, c: f"{a:03d}-{b:02d}-{c:04d}",
    st.integers(1, 899), st.integers(1, 99), st.integers(1, 9999),
)
# Arbitrary surrounding text: letters, digits, punctuation, spaces, underscores.
around = st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), max_size=20)


# Policy, decided after Hypothesis found '001-01-0001' + '0' on its first run:
# an SSN shape touched by more digits is a different, longer number (not an SSN),
# but an SSN touched by letters, underscores or punctuation must always be scrubbed.
@SETTINGS
@given(before=around, ssn=ssns, after=around)
@example(before="", ssn="001-01-0001", after="A")      # found by Hypothesis: letter after SSN leaked
@example(before="ssn", ssn="123-45-6789", after="")    # same flaw, letter before
@example(before="id_", ssn="123-45-6789", after="")    # underscore is a word character too
def test_ssn_anywhere_in_text_is_removed(before, ssn, after):
    if before[-1:].isdigit() or after[:1].isdigit():
        return  # a longer digit run, out of scope by policy
    out = GUARD.scrub(before + ssn + after)
    assert ssn not in out, f"SSN leaked: {out!r}"


emails = st.from_regex(r"[a-z]{1,8}@[a-z]{1,8}\.(com|org|net)", fullmatch=True)


@SETTINGS
@given(before=around, email=emails, after=around)
def test_email_anywhere_in_text_is_removed(before, email, after):
    out = GUARD.scrub(before + " " + email + " " + after)
    assert email not in out, f"email leaked: {out!r}"


@SETTINGS
@given(text=st.text(max_size=80))
def test_scrub_is_idempotent(text):
    once = GUARD.scrub(text)
    assert GUARD.scrub(once) == once


@SETTINGS
@given(text=st.text(max_size=80))
def test_scrubbed_output_is_safe(text):
    assert GUARD.is_safe(GUARD.scrub(text))


TRIGGERS = ("patient", "mrn", "dob", "born", "date of birth")
plain = st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126, exclude_characters="@0123456789"), max_size=80)


@SETTINGS
@given(text=plain)
def test_text_without_phi_markers_is_unchanged(text):
    lowered = text.lower()
    if any(t in lowered for t in TRIGGERS):
        return
    assert GUARD.scrub(text) == text


phones = st.builds(lambda a, b, c: f"{a:03d}-{b:03d}-{c:04d}",
                   st.integers(200, 999), st.integers(200, 999), st.integers(0, 9999))


@SETTINGS
@given(before=around, phone=phones, after=around)
@example(before="tel", phone="415-555-0100", after="")  # letter before: leaked under \b
def test_phone_anywhere_in_text_is_removed(before, phone, after):
    if before[-1:].isdigit() or after[:1].isdigit():
        return  # a longer digit run, out of scope by policy
    out = GUARD.scrub(before + phone + after)
    assert phone not in out, f"phone leaked: {out!r}"
