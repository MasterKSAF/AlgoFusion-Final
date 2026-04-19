from __future__ import annotations

from src.modules.runtime_invoice_raw_detection import (
    looks_like_invoice_index_row,
    looks_like_invoice_table_header,
    normalize_invoice_unit,
)


def test_normalize_invoice_unit_handles_basic_units() -> None:
    assert normalize_invoice_unit("\u0448\u0442.") == "\u0448\u0442"
    assert normalize_invoice_unit("ltr") == "\u043b"


def test_looks_like_invoice_table_header_requires_multiple_markers() -> None:
    assert looks_like_invoice_table_header("\u0410\u0440\u0442\u0438\u043a\u0443\u043b \u0422\u043e\u0432\u0430\u0440 \u0426\u0435\u043d\u0430 \u0421\u0443\u043c\u043c\u0430 \u041d\u0414\u0421")
    assert not looks_like_invoice_table_header("\u0410\u0440\u0442\u0438\u043a\u0443\u043b")


def test_looks_like_invoice_index_row_rejects_total_lines() -> None:
    assert looks_like_invoice_index_row(["1", "2", "3", "4", "5", "6", "7", "8"])
    assert not looks_like_invoice_index_row(["1", "2", "3", "4", "5", "6", "7", "\u0418\u0442\u043e\u0433\u043e"])
