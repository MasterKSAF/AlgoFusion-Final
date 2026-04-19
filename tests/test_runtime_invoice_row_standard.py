from __future__ import annotations

from src.modules.runtime_invoice_row_standard import parse_standard_invoice_region_nonempty


def test_parse_standard_invoice_region_nonempty_parses_full_numeric_row() -> None:
    row = parse_standard_invoice_region_nonempty(
        [
            "1",
            "A10/16",
            "Shampoo",
            "4810123456789",
            "2",
            "\u0448\u0442",
            "60,00",
            "100,00",
            "20%",
            "20,00",
            "120,00",
        ],
        fallback_line_number=7,
    )

    assert row is not None
    assert row["line_number"] == 1
    assert row["article"] == "A10/16"
    assert row["barcode"] == "4810123456789"
    assert row["quantity"] == 2
    assert row["unit"] == "\u0448\u0442"
    assert row["amount_no_disc_incl_vat"] == 120


def test_parse_standard_invoice_region_nonempty_rejects_nonmatching_shape() -> None:
    row = parse_standard_invoice_region_nonempty(
        ["1", "A10/16", "Shampoo", "oops", "2", "\u0448\u0442", "60,00", "100,00", "20%", "20,00", "120,00"],
        fallback_line_number=1,
    )

    assert row is None
