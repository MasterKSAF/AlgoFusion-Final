from __future__ import annotations

from src.modules.runtime_invoice_units import looks_like_invoice_unit_cell, normalize_invoice_unit_v2


def test_normalize_invoice_unit_v2_handles_known_units_and_ocr_variants() -> None:
    assert normalize_invoice_unit_v2("juit") == "\u0448\u0442"
    assert normalize_invoice_unit_v2("ltr") == "\u043b"
    assert normalize_invoice_unit_v2("\u0443\u043f\u0430\u043a.") == "\u0443\u043f"
    assert normalize_invoice_unit_v2("upak") == "\u0443\u043f"


def test_looks_like_invoice_unit_cell_rejects_numeric_text() -> None:
    assert looks_like_invoice_unit_cell("\u0448\u0442")
    assert not looks_like_invoice_unit_cell("123456")
