"""
excel_data_provider.py
----------------------
Reads BA-owned Excel fixtures and returns rows as plain dicts so
pytest.mark.parametrize can consume them without knowing anything
about the spreadsheet format.

Pattern : Strategy (the caller decides what sheet and columns to use)
SOLID   : SRP — one class, one job: translate a sheet into test data
          OCP — new domains add new fixture files; this reader never changes

Why Excel?
----------
Regulated environments (banking, healthcare) require human-readable,
auditable test evidence. Business analysts and compliance officers own
scenario data in spreadsheets — not in code. This reader bridges the
gap: the BA writes the data, the engineer writes the assertions, and
the same pytest parametrize mechanics drive both.

Usage
-----
    from shared.dataprovider.excel_data_provider import ExcelDataProvider

    rows = ExcelDataProvider.load("projects/fintech/api/data/loan_scenarios.xlsx")

    @pytest.mark.parametrize("scenario", ExcelDataProvider.load(FIXTURE))
    def test_monthly_payment(scenario):
        ...
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import openpyxl


class ExcelDataProvider:
    """
    Reads an Excel workbook (.xlsx) and returns its first sheet as a
    list of dicts — one dict per data row, keyed by the header row.

    Rules
    -----
    - Row 1 is always the header.
    - Rows where every cell is empty are skipped (blank spacer rows).
    - Cell values are returned as-is (str, int, float, datetime, None).
    - By default reads the first (index 0) sheet; pass sheet_index to
      target another.
    """

    @staticmethod
    def load(
        path: str | Path,
        *,
        sheet_index: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Load an Excel fixture file and return its rows as dicts.

        Parameters
        ----------
        path        : Path to the .xlsx file (absolute or relative to cwd).
        sheet_index : Zero-based index of the worksheet to read (default 0).

        Returns
        -------
        List of dicts. Each dict maps column header to cell value for one
        data row. Empty rows are excluded.

        Raises
        ------
        FileNotFoundError  : path does not exist.
        ValueError         : sheet_index is out of range, or the sheet has
                             no header row (completely empty).
        """
        resolved = Path(path).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Excel fixture not found: {resolved}")

        workbook = openpyxl.load_workbook(resolved, data_only=True)

        if sheet_index >= len(workbook.sheetnames):
            raise ValueError(
                f"sheet_index {sheet_index} out of range "
                f"(workbook has {len(workbook.sheetnames)} sheet(s))"
            )

        sheet = workbook.worksheets[sheet_index]
        rows  = list(sheet.iter_rows(values_only=True))

        if not rows:
            raise ValueError(f"Sheet '{sheet.title}' is empty: {resolved}")

        # Row 0 -> headers; normalise to stripped lowercase strings
        headers = [
            str(cell).strip() if cell is not None else f"col_{i}"
            for i, cell in enumerate(rows[0])
        ]

        result: list[dict[str, Any]] = []
        for raw_row in rows[1:]:
            if all(cell is None for cell in raw_row):
                continue
            result.append(dict(zip(headers, raw_row)))

        return result

    @staticmethod
    def load_named(
        path: str | Path,
        *,
        sheet_name: str,
    ) -> list[dict[str, Any]]:
        """
        Load a specific sheet by name instead of index.

        Parameters
        ----------
        path       : Path to the .xlsx file.
        sheet_name : Exact name of the worksheet (case-sensitive).

        Raises
        ------
        KeyError : sheet_name not found in workbook.
        """
        resolved = Path(path).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Excel fixture not found: {resolved}")

        workbook = openpyxl.load_workbook(resolved, data_only=True)

        if sheet_name not in workbook.sheetnames:
            raise KeyError(
                f"Sheet '{sheet_name}' not found. "
                f"Available sheets: {workbook.sheetnames}"
            )

        sheet_index = workbook.sheetnames.index(sheet_name)
        return ExcelDataProvider.load(path, sheet_index=sheet_index)
