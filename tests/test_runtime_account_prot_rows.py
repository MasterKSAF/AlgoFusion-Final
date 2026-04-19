from __future__ import annotations

from src.modules.runtime_account_prot_rows import (
    group_regions_by_rows,
    make_row_region,
    merge_account_prot_item_row,
    normalize_account_prot_total_row,
    rewrite_account_prot_row_text_from_ocr,
)


def test_group_regions_by_rows_clusters_cells_by_y_coordinate() -> None:
    rows = group_regions_by_rows(
        [
            {"kind": "table_cell", "bbox": [20, 22, 30, 32], "text": "B"},
            {"kind": "table_cell", "bbox": [0, 0, 10, 10], "text": "A"},
            {"kind": "table_cell", "bbox": [0, 20, 10, 30], "text": "C"},
        ],
        tol=4,
    )

    assert [[cell["text"] for cell in row] for row in rows] == [["A"], ["C", "B"]]


def test_make_row_region_and_rewrite_account_prot_row_text_from_ocr() -> None:
    row = [
        {"kind": "table_cell", "bbox": [0, 0, 10, 10], "text": "Part"},
        {"kind": "table_cell", "bbox": [12, 0, 22, 10], "text": "Name"},
    ]
    region = make_row_region(row, kind="header_form_roi", prefix="auto", idx=1)
    assert region is not None
    assert region["bbox"] == [0, 0, 22, 10]

    rewritten = rewrite_account_prot_row_text_from_ocr(
        row,
        ocr_items=[
            {"bbox": [0, 0, 8, 9], "text": "Merged"},
            {"bbox": [9, 0, 20, 9], "text": "Text"},
        ],
    )
    assert rewritten[0]["text"] == "Merged Text"


def test_merge_account_prot_item_row_merges_leading_name_cells() -> None:
    row = [
        {"bbox": [0, 0, 10, 10], "text": "Item", "kind": "table_cell"},
        {"bbox": [11, 0, 25, 10], "text": "Name", "kind": "table_cell"},
        {"bbox": [26, 0, 35, 10], "text": "шт", "kind": "table_cell"},
        {"bbox": [36, 0, 45, 10], "text": "2", "kind": "table_cell"},
        {"bbox": [46, 0, 55, 10], "text": "x", "kind": "table_cell"},
        {"bbox": [56, 0, 65, 10], "text": "x", "kind": "table_cell"},
        {"bbox": [66, 0, 75, 10], "text": "x", "kind": "table_cell"},
        {"bbox": [76, 0, 85, 10], "text": "x", "kind": "table_cell"},
        {"bbox": [86, 0, 95, 10], "text": "x", "kind": "table_cell"},
        {"bbox": [96, 0, 105, 10], "text": "x", "kind": "table_cell"},
        {"bbox": [106, 0, 115, 10], "text": "x", "kind": "table_cell"},
    ]

    merged = merge_account_prot_item_row(row)
    assert len(merged) == 10
    assert merged[0]["text"] == "Item Name"


def test_normalize_account_prot_total_row_keeps_tail_values() -> None:
    row = [
        {"bbox": [0, 0, 10, 10], "text": "Итого", "kind": "table_cell"},
        {"bbox": [11, 0, 20, 10], "text": "", "kind": "table_cell"},
        {"bbox": [21, 0, 30, 10], "text": "1", "kind": "table_cell"},
        {"bbox": [31, 0, 40, 10], "text": "2", "kind": "table_cell"},
        {"bbox": [41, 0, 50, 10], "text": "3", "kind": "table_cell"},
        {"bbox": [51, 0, 60, 10], "text": "4", "kind": "table_cell"},
    ]

    normalized = normalize_account_prot_total_row(row)
    assert len(normalized) == 10
    assert [cell["text"] for cell in normalized][-4:] == ["1", "2", "3", "4"]
