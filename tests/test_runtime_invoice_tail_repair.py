from __future__ import annotations

from src.modules.runtime_invoice_tail_repair import repair_invoice_shifted_tail_item


def test_repair_invoice_shifted_tail_item_restores_shifted_total_and_vat() -> None:
    repaired = repair_invoice_shifted_tail_item(
        {
            "vat_rate": "120,00",
            "disc_amount": "20,00",
            "amount_no_disc_incl_vat": "120,00",
            "amount_with_disc_excl_vat": "100,00",
            "vat_amount": None,
            "total_with_disc_incl_vat": None,
        }
    )

    assert repaired["vat_rate"] == "20%"
    assert repaired["disc_amount"] is None
    assert repaired["vat_amount"] == 20
    assert repaired["total_with_disc_incl_vat"] == 120
