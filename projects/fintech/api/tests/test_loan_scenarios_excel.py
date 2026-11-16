"""
test_loan_scenarios_excel.py
-----------------------------
Data-driven loan calculation tests driven from a BA-owned Excel fixture.

Why Excel?
----------
Loan scenario data (amount, term, rate, expected payment) belongs to
the finance business analyst, not the engineer. The BA maintains the
sheet; the engineer writes the assertion logic. This pattern is common
in regulated financial institutions where test evidence must be
human-readable and auditable (SOX, Basel III).

The same assertion logic runs against every row in the sheet — adding
a new scenario requires only a new Excel row, not a code change.

Fixture
-------
projects/fintech/api/data/loan_scenarios.xlsx
  Columns: scenario_id, scenario_label, loan_amount, term_months,
           annual_rate_pct, expected_monthly_payment,
           expected_total_interest, notes

Design
------
  ExcelDataProvider  (Strategy) <- loads and normalises the sheet
  pytest.parametrize             <- drives one test per row
  Monthly payment formula        <- standard amortisation: M = P*r*(1+r)^n / ((1+r)^n - 1)
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

from shared.dataprovider.excel_data_provider import ExcelDataProvider

# Resolve fixture path relative to the repo root (cwd when pytest runs)
_FIXTURE = Path("projects/fintech/api/data/loan_scenarios.xlsx")

# Load once at collection time — parametrize needs the list at import
_SCENARIOS = ExcelDataProvider.load(_FIXTURE)


CENT = Decimal("0.01")


def _money(value) -> Decimal:
    """Convert a sheet cell to Decimal via str() so float noise never enters."""
    return Decimal(str(value))


def _monthly_payment(principal: Decimal, annual_rate_pct: Decimal, term_months: int) -> Decimal:
    """
    Standard amortisation formula, computed in Decimal and quantized to
    the cent with ROUND_HALF_UP (banker's rounding is NOT used for
    customer-facing payments).

        M = P * r * (1+r)^n / ((1+r)^n - 1)

    For zero-interest loans the formula collapses to P / n.
    """
    if annual_rate_pct == 0:
        return (principal / term_months).quantize(CENT, rounding=ROUND_HALF_UP)
    r = annual_rate_pct / Decimal(100) / Decimal(12)
    n = term_months
    growth = (1 + r) ** n
    m = principal * r * growth / (growth - 1)
    return m.quantize(CENT, rounding=ROUND_HALF_UP)


def _total_interest(monthly: Decimal, term_months: int, principal: Decimal, annual_rate_pct: Decimal) -> Decimal:
    if annual_rate_pct == 0:
        return Decimal("0.00")
    return (monthly * term_months - principal).quantize(CENT, rounding=ROUND_HALF_UP)


@pytest.mark.fintech
@pytest.mark.excel
@pytest.mark.unit
class TestLoanScenariosFromExcel:
    """
    Each test method runs once per row in loan_scenarios.xlsx.

    The BA owns the expected values; the engineer owns the assertion.
    Adding a new scenario is a spreadsheet edit, not a code change.
    """

    @pytest.mark.parametrize(
        "scenario",
        _SCENARIOS,
        ids=[s["scenario_id"] for s in _SCENARIOS],
    )
    def test_monthly_payment_matches_expected(self, scenario: dict) -> None:
        """
        Calculated monthly payment must equal the BA's expected value to
        the cent. Decimal arithmetic with an explicit ROUND_HALF_UP policy,
        so no float tolerance is needed or allowed.
        """
        calculated = _monthly_payment(
            principal=_money(scenario["loan_amount"]),
            annual_rate_pct=_money(scenario["annual_rate_pct"]),
            term_months=int(scenario["term_months"]),
        )
        expected = _money(scenario["expected_monthly_payment"]).quantize(CENT)

        assert calculated == expected, (
            f"[{scenario['scenario_id']}] {scenario['scenario_label']}: "
            f"calculated ${calculated:.2f} vs expected ${expected:.2f} "
            f"(loan ${scenario['loan_amount']}, "
            f"{scenario['term_months']} months @ {scenario['annual_rate_pct']}%)"
        )

    @pytest.mark.parametrize(
        "scenario",
        _SCENARIOS,
        ids=[s["scenario_id"] for s in _SCENARIOS],
    )
    def test_total_interest_matches_expected(self, scenario: dict) -> None:
        """
        Total interest over the loan term must equal the BA's expected
        value to the cent, derived from the quantized monthly payment.
        """
        monthly = _monthly_payment(
            principal=_money(scenario["loan_amount"]),
            annual_rate_pct=_money(scenario["annual_rate_pct"]),
            term_months=int(scenario["term_months"]),
        )
        calculated_interest = _total_interest(
            monthly=monthly,
            term_months=int(scenario["term_months"]),
            principal=_money(scenario["loan_amount"]),
            annual_rate_pct=_money(scenario["annual_rate_pct"]),
        )
        expected_interest = _money(scenario["expected_total_interest"]).quantize(CENT)

        assert calculated_interest == expected_interest, (
            f"[{scenario['scenario_id']}] {scenario['scenario_label']}: "
            f"total interest ${calculated_interest:.2f} vs expected ${expected_interest:.2f}"
        )

    @pytest.mark.parametrize(
        "scenario",
        _SCENARIOS,
        ids=[s["scenario_id"] for s in _SCENARIOS],
    )
    def test_scenario_has_required_columns(self, scenario: dict) -> None:
        """
        Each row must contain all required columns — guards against a BA
        accidentally deleting a column in the shared spreadsheet.
        """
        required = {
            "scenario_id", "scenario_label", "loan_amount",
            "term_months", "annual_rate_pct",
            "expected_monthly_payment", "expected_total_interest",
        }
        missing = required - scenario.keys()
        assert not missing, (
            f"Fixture row is missing required columns: {missing}. "
            f"Check loan_scenarios.xlsx for a column header change."
        )
