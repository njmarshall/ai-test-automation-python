"""
test_excel_data_provider.py
----------------------------
Unit tests for shared.dataprovider.ExcelDataProvider.

Tests cover:
  - happy-path load() with a real openpyxl workbook
  - blank-row skipping
  - sheet_index targeting
  - load_named() by sheet name
  - FileNotFoundError on missing path
  - ValueError on out-of-range sheet_index
  - KeyError on unknown sheet name
  - ValueError on empty sheet

Each test builds its own minimal in-memory workbook so this file has
zero filesystem dependencies and runs at true unit speed.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import openpyxl
import pytest

from shared.dataprovider.excel_data_provider import ExcelDataProvider

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_xlsx(rows: list[list], sheet_name: str = "Sheet1") -> Path:
    """
    Write rows to a temp .xlsx file and return its path.
    Caller is responsible for cleanup (use tmp_path fixture in pytest).
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    for row in rows:
        ws.append(row)
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = Path(f.name)
    wb.save(path)
    return path


# ---------------------------------------------------------------------------
# happy-path tests
# ---------------------------------------------------------------------------

class TestExcelDataProviderLoad:
    """Core load() behaviour."""

    def test_returns_list_of_dicts(self, tmp_path):
        path = tmp_path / "test.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["id", "name", "value"])
        ws.append([1, "alpha", 100])
        ws.append([2, "beta", 200])
        wb.save(path)

        result = ExcelDataProvider.load(path)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(row, dict) for row in result)

    def test_header_row_becomes_keys(self, tmp_path):
        path = tmp_path / "test.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["scenario_id", "loan_amount", "term_months"])
        ws.append(["LOAN-001", 10000, 36])
        wb.save(path)

        result = ExcelDataProvider.load(path)

        assert result[0].keys() == {"scenario_id", "loan_amount", "term_months"}

    def test_cell_values_are_correct(self, tmp_path):
        path = tmp_path / "test.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["id", "amount"])
        ws.append(["LOAN-001", 5000.0])
        wb.save(path)

        result = ExcelDataProvider.load(path)

        assert result[0]["id"] == "LOAN-001"
        assert result[0]["amount"] == 5000.0

    def test_blank_rows_are_skipped(self, tmp_path):
        path = tmp_path / "test.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["id", "value"])
        ws.append(["ROW-001", 1])
        ws.append([None, None])          # blank spacer row
        ws.append(["ROW-002", 2])
        wb.save(path)

        result = ExcelDataProvider.load(path)

        assert len(result) == 2
        assert result[0]["id"] == "ROW-001"
        assert result[1]["id"] == "ROW-002"

    def test_sheet_index_zero_is_default(self, tmp_path):
        path = tmp_path / "test.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "First"
        ws.append(["label"])
        ws.append(["first-sheet"])
        wb.create_sheet("Second")
        wb["Second"].append(["label"])
        wb["Second"].append(["second-sheet"])
        wb.save(path)

        result = ExcelDataProvider.load(path)

        assert result[0]["label"] == "first-sheet"

    def test_sheet_index_one_targets_second_sheet(self, tmp_path):
        path = tmp_path / "test.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "First"
        ws.append(["label"])
        ws.append(["first-sheet"])
        ws2 = wb.create_sheet("Second")
        ws2.append(["label"])
        ws2.append(["second-sheet"])
        wb.save(path)

        result = ExcelDataProvider.load(path, sheet_index=1)

        assert result[0]["label"] == "second-sheet"

    def test_header_whitespace_is_stripped(self, tmp_path):
        path = tmp_path / "test.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["  id  ", " name "])
        ws.append([1, "alpha"])
        wb.save(path)

        result = ExcelDataProvider.load(path)

        # keys must be stripped
        assert "id" in result[0]
        assert "name" in result[0]


# ---------------------------------------------------------------------------
# load_named() tests
# ---------------------------------------------------------------------------

class TestExcelDataProviderLoadNamed:
    """load_named() finds sheets by name."""

    def test_load_named_returns_correct_sheet(self, tmp_path):
        path = tmp_path / "test.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Fintech"
        ws.append(["scenario_id"])
        ws.append(["LOAN-001"])
        ws2 = wb.create_sheet("Healthcare")
        ws2.append(["scenario_id"])
        ws2.append(["AUTH-001"])
        wb.save(path)

        result = ExcelDataProvider.load_named(path, sheet_name="Healthcare")

        assert result[0]["scenario_id"] == "AUTH-001"

    def test_load_named_raises_key_error_for_unknown_sheet(self, tmp_path):
        path = tmp_path / "test.xlsx"
        wb = openpyxl.Workbook()
        wb.active.append(["col"])
        wb.save(path)

        with pytest.raises(KeyError, match="NoSuchSheet"):
            ExcelDataProvider.load_named(path, sheet_name="NoSuchSheet")


# ---------------------------------------------------------------------------
# error-path tests
# ---------------------------------------------------------------------------

class TestExcelDataProviderErrors:
    """Error cases raise the right exception types."""

    def test_missing_file_raises_file_not_found(self, tmp_path):
        missing = tmp_path / "does_not_exist.xlsx"
        with pytest.raises(FileNotFoundError, match="Excel fixture not found"):
            ExcelDataProvider.load(missing)

    def test_out_of_range_sheet_index_raises_value_error(self, tmp_path):
        path = tmp_path / "test.xlsx"
        wb = openpyxl.Workbook()
        wb.active.append(["col"])
        wb.save(path)

        with pytest.raises(ValueError, match="sheet_index"):
            ExcelDataProvider.load(path, sheet_index=99)

    def test_empty_sheet_raises_value_error(self, tmp_path):
        path = tmp_path / "test.xlsx"
        wb = openpyxl.Workbook()
        # Leave the sheet completely empty — no rows appended
        wb.save(path)

        with pytest.raises(ValueError, match="empty"):
            ExcelDataProvider.load(path)

    def test_missing_file_load_named_raises_file_not_found(self, tmp_path):
        missing = tmp_path / "ghost.xlsx"
        with pytest.raises(FileNotFoundError):
            ExcelDataProvider.load_named(missing, sheet_name="Sheet1")
