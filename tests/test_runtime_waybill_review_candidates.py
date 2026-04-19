from __future__ import annotations

from types import SimpleNamespace

from src.modules.runtime_waybill_raw import _waybill_trim_window_before_next_barcode
from src.modules.runtime_waybill_raw_repair import repair_waybill_review_item_names_from_raw
from src.modules.runtime_waybill_items import extract_waybill_unit_token
from src.modules.runtime_waybill_review_candidates import (
    split_waybill_raw_cells,
    waybill_review_row_candidate_from_window,
    waybill_trim_window_to_row,
)
from src.modules.runtime_waybill_review_windows import waybill_significant_name_tokens


REVIEW = "\u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u043f\u043e\u043b\u0435"
UNIT = "\u0448\u0442"


def test_waybill_raw_repair_window_stops_before_next_item_code() -> None:
    trimmed = _waybill_trim_window_before_next_barcode(
        [
            "shade 40 ml 4606453061634 discount 10",
            "7/0 next product",
            "next product numeric tail sht 3 5,83 17,50 20% 3,50 21,00",
        ],
        {"name": "4/0 current product 4606453061634"},
    )

    assert trimmed == ["shade 40 ml 4606453061634 discount 10"]


def test_split_waybill_raw_cells_splits_pipe_separated_line() -> None:
    assert split_waybill_raw_cells(f"{UNIT} | 2 | 60,00 | 20%") == [UNIT, "2", "60,00", "20%"]


def test_extract_waybill_unit_token_normalizes_confusable_sht_variants() -> None:
    assert extract_waybill_unit_token("\u0428\u03a4") == UNIT
    assert extract_waybill_unit_token("\u0428T") == UNIT


def test_waybill_review_row_candidate_from_window_reads_compact_numeric_tail() -> None:
    row = waybill_review_row_candidate_from_window([f"{UNIT} 2 60,00 120,00 20% 20,00 140,00"], default_unit=UNIT)

    assert row is not None
    assert row["unit"] == UNIT
    assert row["quantity"] == 2
    assert row["cost_with_vat"] == 140


def test_waybill_review_row_candidate_from_window_reads_bare_vat_rate_without_percent() -> None:
    row = waybill_review_row_candidate_from_window(
        [f"1., Shaving gel NISHMAN 02 {UNIT} 1 11,50 11,50 20 2,30 13,80"],
        default_unit=UNIT,
    )

    assert row is not None
    assert row["unit"] == UNIT
    assert row["quantity"] == 1
    assert row["price"] == 11.5
    assert row["cost_with_vat"] == 13.8


def test_waybill_review_row_candidate_from_window_uses_single_post_rate_value_as_total() -> None:
    row = waybill_review_row_candidate_from_window([f"{UNIT} 2 0,01 0,02 20% 0,02"], default_unit=UNIT)

    assert row is not None
    assert row["quantity"] == 2
    assert row["price"] == 0.01
    assert row["cost"] == 0.02
    assert row["vat_amount"] == 0
    assert row["cost_with_vat"] == 0.02


def test_waybill_review_row_candidate_from_window_recovers_price_from_qty_and_cost() -> None:
    row = waybill_review_row_candidate_from_window([f"{UNIT} 30 5,00 180,00 20% 36,00 216,00"], default_unit=UNIT)

    assert row is not None
    assert row["quantity"] == 30
    assert row["price"] == 6
    assert row["cost"] == 180
    assert row["vat_amount"] == 36
    assert row["cost_with_vat"] == 216


def test_waybill_review_row_candidate_from_window_ignores_note_numbers_after_rate() -> None:
    row = waybill_review_row_candidate_from_window(
        [
            f"Набор ESTEL АЛЬФА {UNIT} 2 0,01 0,02 20% 0,02 "
            "цена отпускная (импортера) 31,67, скидка к отпускной цене % -99,97"
        ],
        default_unit=UNIT,
    )

    assert row is not None
    assert row["quantity"] == 2
    assert row["price"] == 0.01
    assert row["cost"] == 0.02
    assert row["vat_amount"] == 0
    assert row["cost_with_vat"] == 0.02


def test_waybill_trim_window_to_row_keeps_matching_tail() -> None:
    trimmed = waybill_trim_window_to_row(
        ["service line", "Mask Repair 4810123456789", "numeric tail"],
        {"name": "Mask Repair 4810123456789"},
    )

    assert trimmed == ["Mask Repair 4810123456789", "numeric tail"]


def test_waybill_trim_window_to_row_keeps_multiline_numeric_tail_before_barcode() -> None:
    trimmed = waybill_trim_window_to_row(
        [
            f"LUXE 9/56 color {UNIT} 1 8,57 8,57 20% 1,72 10,29",
            "4606453073750 \u0441\u0442\u0440\u0430\u043d\u0430 \u0432\u0432\u043e\u0437\u0430 \u0420\u041e\u0421\u0421\u0418\u042f \u0441\u043a\u0438\u0434\u043a\u0430 -26,47",
        ],
        {"name": "9/56 Product 4606453073750"},
    )

    assert trimmed == [
        f"LUXE 9/56 color {UNIT} 1 8,57 8,57 20% 1,72 10,29",
        "4606453073750 \u0441\u0442\u0440\u0430\u043d\u0430 \u0432\u0432\u043e\u0437\u0430 \u0420\u041e\u0421\u0421\u0418\u042f \u0441\u043a\u0438\u0434\u043a\u0430 -26,47",
    ]


def test_waybill_trim_window_to_row_keeps_numeric_tail_two_lines_before_barcode() -> None:
    trimmed = waybill_trim_window_to_row(
        [
            "anti yellow soothing gel estel",
            f"{UNIT} 1 10,87 10,87 20% 2,18 13,05 importer 12,50",
            "ANTI-YELLOW 80 ml discount -13",
            "4606453075976 \u0441\u0442\u0440\u0430\u043d\u0430 \u0432\u0432\u043e\u0437\u0430 \u0420\u041e\u0421\u0421\u0418\u042f",
        ],
        {"name": "Soothing gel ANTI-YELLOW 4606453075976"},
    )

    assert trimmed == [
        f"{UNIT} 1 10,87 10,87 20% 2,18 13,05 importer 12,50",
        "ANTI-YELLOW 80 ml discount -13",
        "4606453075976 \u0441\u0442\u0440\u0430\u043d\u0430 \u0432\u0432\u043e\u0437\u0430 \u0420\u041e\u0421\u0421\u0418\u042f",
    ]


def test_waybill_trim_window_to_row_keeps_numeric_tail_through_discount_bridge() -> None:
    trimmed = waybill_trim_window_to_row(
        [
            f"ANTI-YELLOW {UNIT} 1 15,83 15,83 20% 3,17 19,00 цена отпускная 15,83",
            "\u0441\u043a\u0438\u0434\u043a\u0430 \u043a \u043e\u0442\u043f\u0443\u0441\u043a\u043d\u043e\u0439 \u0446\u0435\u043d\u0435, %, 0",
            "4606453084282 \u0441\u0442\u0440\u0430\u043d\u0430 \u0432\u0432\u043e\u0437\u0430 \u0420\u041e\u0421\u0421\u0418\u042f",
        ],
        {"name": "ANTI-YELLOW 4606453084282"},
    )

    assert trimmed == [
        f"ANTI-YELLOW {UNIT} 1 15,83 15,83 20% 3,17 19,00 цена отпускная 15,83",
        "\u0441\u043a\u0438\u0434\u043a\u0430 \u043a \u043e\u0442\u043f\u0443\u0441\u043a\u043d\u043e\u0439 \u0446\u0435\u043d\u0435, %, 0",
        "4606453084282 \u0441\u0442\u0440\u0430\u043d\u0430 \u0432\u0432\u043e\u0437\u0430 \u0420\u041e\u0421\u0421\u0418\u042f",
    ]


def test_waybill_significant_name_tokens_keep_distinctive_suffix_terms() -> None:
    tokens = waybill_significant_name_tokens("Aqua gel for skin relief ESTEL ANTI-YELLOW 80 ml")

    assert "anti" in tokens
    assert "yellow" in tokens


def test_repair_waybill_review_item_names_from_raw_restores_multiline_name() -> None:
    page = SimpleNamespace(
        ocr_items=[
            {"text": "ACTIVATOR SENSATION DE", "bbox": [0, 0, 100, 8]},
            {"text": f"LUXE 1,5%, 1000 ml, {UNIT} 3 14,17 42,50 20% 8,50 51,00 цена отпускная 14,17", "bbox": [0, 12, 100, 20]},
            {"text": "4606453073590, \u0441\u0442\u0440\u0430\u043d\u0430 \u0432\u0432\u043e\u0437\u0430 \u0420\u041e\u0421\u0421\u0418\u042f \u0441\u043a\u0438\u0434\u043a\u0430 %, 0", "bbox": [0, 24, 100, 32]},
            {"text": "\u0420\u041e\u0421\u0421\u0418\u042f", "bbox": [0, 36, 100, 44]},
        ]
    )
    repaired = repair_waybill_review_item_names_from_raw(
        page,
        [
            {
                "name": REVIEW,
                "unit": UNIT,
                "quantity": 3,
                "price": 14.17,
                "cost": 42.5,
                "vat_rate": "20%",
                "vat_amount": 8.5,
                "cost_with_vat": 51,
            }
        ],
    )

    assert "4606453073590" in repaired[0]["name"]


def test_repair_waybill_review_item_names_from_raw_uses_numbered_item_block_fallback() -> None:
    page = SimpleNamespace(
        ocr_items=[
            {"text": f"1., Styling balm for beard {UNIT} 10 20,00 200,00 20 40,00 240,00", "bbox": [0, 0, 100, 8]},
            {"text": "NISHMAN Styling", "bbox": [0, 12, 100, 20]},
            {"text": "Balm 100 ml, Turkey", "bbox": [0, 24, 100, 32]},
            {"text": f"2., Next item {UNIT} 1 5,00 5,00 20 1,00 6,00", "bbox": [0, 36, 100, 44]},
        ]
    )
    repaired = repair_waybill_review_item_names_from_raw(
        page,
        [
            {
                "name": REVIEW,
                "unit": UNIT,
                "quantity": 10,
                "price": 20.0,
                "cost": 200.0,
                "vat_rate": "20%",
                "vat_amount": 40.0,
                "cost_with_vat": 240.0,
            }
        ],
    )

    assert "NISHMAN Styling Balm" in repaired[0]["name"]


def test_repair_waybill_review_item_names_from_raw_stops_after_country_tail() -> None:
    page = SimpleNamespace(
        ocr_items=[
            {"text": f"Крем после бритья NISHMAN 02 {UNIT} 2 14,00 28,00 20% 5,60 33,60", "bbox": [0, 0, 100, 8]},
            {"text": "Arctic Blue 200 мл /ТУРЦИЯ/", "bbox": [0, 12, 100, 20]},
            {"text": "Крем после бритья NISHMAN 05", "bbox": [0, 24, 100, 32]},
            {"text": f"{UNIT} 1 14,00 14,00 20% 2,80 16,80", "bbox": [0, 36, 100, 44]},
        ]
    )
    repaired = repair_waybill_review_item_names_from_raw(
        page,
        [
            {
                "name": REVIEW,
                "unit": UNIT,
                "quantity": 2,
                "price": 14.0,
                "cost": 28.0,
                "vat_rate": "20%",
                "vat_amount": 5.6,
                "cost_with_vat": 33.6,
            }
        ],
    )

    assert "Arctic Blue 200 мл /ТУРЦИЯ" in repaired[0]["name"]
    assert "NISHMAN 05" not in repaired[0]["name"]
