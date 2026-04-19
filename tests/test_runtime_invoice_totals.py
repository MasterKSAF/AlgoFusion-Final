from __future__ import annotations

from src.modules.runtime_invoice_totals import summarize_invoice_item_totals


def test_summarize_invoice_item_totals_sums_present_numeric_fields() -> None:
    assert summarize_invoice_item_totals(
        [
            {
                "quantity": 2,
                "amount_with_disc_excl_vat": "100,00",
                "vat_amount": 20,
                "total_with_disc_incl_vat": 120,
            },
            {
                "quantity": 1,
                "amount_with_disc_excl_vat": "50,00",
                "vat_amount": 10,
                "total_with_disc_incl_vat": 60,
            },
        ]
    ) == {
        "total_quantity": 3,
        "subtotal_with_disc_excl_vat": 150,
        "vat_amount": 30,
        "total_with_disc_incl_vat": 180,
    }


def test_summarize_invoice_item_totals_omits_never_seen_fields() -> None:
    assert summarize_invoice_item_totals([{"quantity": None, "vat_amount": ""}]) == {}
