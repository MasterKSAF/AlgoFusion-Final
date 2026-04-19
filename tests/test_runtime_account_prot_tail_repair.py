from __future__ import annotations

from src.modules.runtime_account_prot_tail_repair import repair_shifted_account_prot_item


def test_repair_shifted_account_prot_item_restores_numeric_columns() -> None:
    repaired = repair_shifted_account_prot_item(
        {
            "unit": "ошибочныйтекст",
            "extra_charge": 12.5,
            "vat_rate": "20%",
            "vat_amount": 20,
            "total_incl_vat": 2.5,
            "total_excl_vat": 12.5,
        }
    )

    assert repaired["unit"] == "шт"
    assert repaired["free_unit_price_excl_vat"] == 12.5
    assert repaired["extra_charge"] is None
    assert repaired["unit_price_excl_vat"] == 12.5
    assert repaired["vat_rate"] == "20%"
    assert repaired["vat_amount"] == 2.5
    assert repaired["total_incl_vat"] == 15
