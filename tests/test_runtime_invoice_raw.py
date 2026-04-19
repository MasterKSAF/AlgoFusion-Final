from __future__ import annotations

from src.modules.runtime_invoice_raw import (
    build_invoice_raw_fallback_from_lines,
    parse_invoice_raw_item_block,
    repair_invoice_shifted_tail_item,
)


def test_parse_invoice_raw_item_block_parses_basic_tail() -> None:
    row = parse_invoice_raw_item_block(
        [
            "A10/16 Shampoo",
            "шт | 2 | 60,00 | 100,00 | 20% | 20,00 | 120,00",
        ],
        line_number=1,
    )

    assert row is not None
    assert row["line_number"] == 1
    assert row["article"] == "A10/16"
    assert row["description"] == "Shampoo"
    assert row["quantity"] == 2
    assert row["unit"] == "шт"
    assert row["vat_rate"] == "20%"
    assert row["total_with_disc_incl_vat"] == 120


def test_parse_invoice_raw_item_block_parses_compact_qty_unit_tail() -> None:
    row = parse_invoice_raw_item_block(
        [
            "1 | A.1321 | Shampoo | 4810123456789 | 2 шт | 0,01 | 0,02 | 20% | 0,02",
        ],
        line_number=1,
    )

    assert row is not None
    assert row["line_number"] == 1
    assert row["article"] == "A.1321"
    assert row["barcode"] == "4810123456789"
    assert row["quantity"] == 2
    assert row["unit"] == "шт"
    assert row["unit_price_incl_vat"] == 0.01
    assert row["amount_with_disc_excl_vat"] == 0.02
    assert row["vat_rate"] == "20%"
    assert row["vat_amount"] == 0
    assert row["total_with_disc_incl_vat"] == 0.02


def test_repair_invoice_shifted_tail_item_restores_totals() -> None:
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


def test_build_invoice_raw_fallback_from_lines_parses_minimal_invoice() -> None:
    payload = build_invoice_raw_fallback_from_lines(
        [
            "Счет № INV-77 от 01.02.2024",
            "Продавец: ООО Ромашка",
            "Артикул | Наименование | Цена | Сумма | НДС",
            "A10/16 Shampoo",
            "шт | 2 | 60,00 | 100,00 | 20% | 20,00 | 120,00",
            "Итого 100,00 20,00 120,00",
        ],
        page_role="single",
    )

    assert payload is not None
    assert payload["invoice_number"] == "INV-77"
    assert payload["invoice_date"] == "01.02.2024"
    assert payload["supplier"]["name"] == "ООО Ромашка"
    assert len(payload["items"]) == 1
    assert payload["items"][0]["article"] == "A10/16"
    assert payload["totals"]["vat_amount"] == 20
    assert payload["totals"]["total_with_disc_incl_vat"] == 120
