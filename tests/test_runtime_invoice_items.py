from __future__ import annotations

from src.modules.runtime_invoice_items import (
    canonicalize_invoice_items,
    clean_invoice_description_value,
    extract_invoice_article_token,
    extract_invoice_lead_fields,
    invoice_barcode_cell_idx,
    parse_invoice_region_row,
    normalize_invoice_unit_v2,
)


def test_normalize_invoice_unit_v2_handles_ocr_variants() -> None:
    assert normalize_invoice_unit_v2("juit") == "\u0448\u0442"
    assert normalize_invoice_unit_v2("ltr") == "\u043b"
    assert normalize_invoice_unit_v2("\u0443\u043f\u0430\u043a.") == "\u0443\u043f"


def test_extract_invoice_article_token_supports_cyrillic_and_latin() -> None:
    assert extract_invoice_article_token("A 10/16") == "A10/16"
    assert extract_invoice_article_token("\u0410\u041110/16 \u0428\u0430\u043c\u043f\u0443\u043d\u044c") == "\u0410\u041110/16"


def test_clean_invoice_description_removes_leading_article() -> None:
    assert clean_invoice_description_value("A10/16 Shampoo", article="A10/16") == "Shampoo"


def test_invoice_barcode_cell_idx_prefers_exact_barcode_cell() -> None:
    assert invoice_barcode_cell_idx(["1", "item", "4810123456789", "20%"]) == 2


def test_extract_invoice_lead_fields_splits_line_article_description() -> None:
    line_number, article, description = extract_invoice_lead_fields(["7", "A10/16", "Shampoo"], 3)

    assert line_number == 7
    assert article == "A10/16"
    assert description == "Shampoo"


def test_canonicalize_invoice_items_normalizes_item_values() -> None:
    items = canonicalize_invoice_items(
        [
            {
                "line_number": 1,
                "article": " a10 / 16 ",
                "description": "A10/16 Shampoo",
                "unit": "juit",
                "vat_rate": "20 %",
            }
        ]
    )

    assert items[0]["article"] == "A10/16"
    assert items[0]["description"] == "Shampoo"
    assert items[0]["unit"] == "\u0448\u0442"
    assert items[0]["vat_rate"] == "20%"
def test_parse_invoice_region_row_standard_numeric_tail() -> None:
    row = parse_invoice_region_row(
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
        fallback_line_number=1,
    )

    assert row is not None
    assert row["line_number"] == 1
    assert row["barcode"] == "4810123456789"
    assert row["quantity"] == 2
    assert row["unit"] == "\u0448\u0442"
    assert row["vat_rate"] == "20%"


def test_parse_invoice_region_row_compact_qty_unit_tail() -> None:
    row = parse_invoice_region_row(
        [
            "1",
            "A.1321",
            "Shampoo",
            "4810123456789",
            "2 \u0448\u0442",
            "0,01",
            "0,02",
            "20%",
            "0,02",
        ],
        fallback_line_number=1,
    )

    assert row is not None
    assert row["line_number"] == 1
    assert row["barcode"] == "4810123456789"
    assert row["quantity"] == 2
    assert row["unit"] == "\u0448\u0442"
    assert row["unit_price_incl_vat"] == 0.01
    assert row["amount_no_disc_incl_vat"] == 0.02
    assert row["amount_with_disc_excl_vat"] == 0.02
    assert row["vat_rate"] == "20%"
    assert row["vat_amount"] == 0
    assert row["total_with_disc_incl_vat"] == 0.02
