from __future__ import annotations

from src.modules.runtime_invoice_row_numeric_tail import build_invoice_numeric_tail_row


def test_build_invoice_numeric_tail_row_parses_discount_shape() -> None:
    row = build_invoice_numeric_tail_row(
        line_number=7,
        article="A10/16",
        description="Shampoo",
        barcode="4810123456789",
        quantity=2,
        unit="\u0448\u0442",
        before_rate=["60,00", "120,00", "5,00", "95,00"],
        vat_rate_text="20 %",
        after_rate=["19,00", "114,00"],
    )

    assert row is not None
    assert row["amount_no_disc_incl_vat"] == 120
    assert row["disc_amount"] == 5
    assert row["amount_with_disc_excl_vat"] == 95
    assert row["vat_rate"] == "20%"
    assert row["total_with_disc_incl_vat"] == 114


def test_build_invoice_numeric_tail_row_requires_min_numeric_tail() -> None:
    row = build_invoice_numeric_tail_row(
        line_number=1,
        article=None,
        description="Shampoo",
        barcode=None,
        quantity=2,
        unit="\u0448\u0442",
        before_rate=["60,00"],
        vat_rate_text="20%",
        after_rate=["20,00"],
    )

    assert row is None
