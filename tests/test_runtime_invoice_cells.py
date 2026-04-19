from __future__ import annotations

from src.modules.runtime_invoice_cells import (
    invoice_barcode_cell_idx,
    looks_like_invoice_qty_unit_cell,
    looks_like_percent_text,
    split_invoice_qty_unit,
)


def test_looks_like_percent_text_accepts_percent_and_ocr_tail() -> None:
    assert looks_like_percent_text("20%")
    assert looks_like_percent_text("20...")


def test_split_invoice_qty_unit_parses_quantity_and_unit() -> None:
    assert split_invoice_qty_unit("2 \u0448\u0442") == (2, "\u0448\u0442")
    assert split_invoice_qty_unit("3 juit") == (3, "\u0448\u0442")


def test_looks_like_invoice_qty_unit_cell_rejects_long_noisy_unit() -> None:
    assert looks_like_invoice_qty_unit_cell("2 \u0448\u0442")
    assert not looks_like_invoice_qty_unit_cell("2 123456")


def test_invoice_barcode_cell_idx_prefers_exact_barcode_cell() -> None:
    assert invoice_barcode_cell_idx(["1", "item 4810123456789", "4810555555555"]) == 2
    assert invoice_barcode_cell_idx(["1", "item 4810123456789"]) == 1
