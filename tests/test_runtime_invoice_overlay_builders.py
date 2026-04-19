from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np

from src.modules.runtime_invoice_overlay_builders import build_invoice_items_overlay
from src.modules.runtime_types import PageWorkItem


def test_build_invoice_items_overlay_parses_single_table_row() -> None:
    blank = np.zeros((20, 20, 3), dtype=np.uint8)
    mask = np.zeros((20, 20), dtype=np.uint8)
    with tempfile.TemporaryDirectory() as tmp:
        roi_text_path = Path(tmp) / "roi_text.json"
        payload = {
            "regions": [
                {"kind": "table_cell", "bbox": [0, 0, 10, 10], "text": "Артикул"},
                {"kind": "table_cell", "bbox": [11, 0, 21, 10], "text": "Наименование"},
                {"kind": "table_cell", "bbox": [22, 0, 32, 10], "text": "Цена"},
                {"kind": "table_cell", "bbox": [33, 0, 43, 10], "text": "Сумма"},
                {"kind": "table_cell", "bbox": [44, 0, 54, 10], "text": "НДС"},
                {"kind": "table_cell", "bbox": [0, 20, 10, 30], "text": "1"},
                {"kind": "table_cell", "bbox": [11, 20, 21, 30], "text": "A10/16"},
                {"kind": "table_cell", "bbox": [22, 20, 32, 30], "text": "Shampoo"},
                {"kind": "table_cell", "bbox": [33, 20, 43, 30], "text": "4810123456789"},
                {"kind": "table_cell", "bbox": [44, 20, 54, 30], "text": "2"},
                {"kind": "table_cell", "bbox": [55, 20, 65, 30], "text": "шт"},
                {"kind": "table_cell", "bbox": [66, 20, 76, 30], "text": "60,00"},
                {"kind": "table_cell", "bbox": [77, 20, 87, 30], "text": "100,00"},
                {"kind": "table_cell", "bbox": [88, 20, 98, 30], "text": "20%"},
                {"kind": "table_cell", "bbox": [99, 20, 109, 30], "text": "20,00"},
                {"kind": "table_cell", "bbox": [110, 20, 120, 30], "text": "120,00"},
            ]
        }
        roi_text_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        item = PageWorkItem(
            page_id="p1",
            page_no=1,
            source_bgr=blank,
            clean_bgr=blank,
            no_lines_bgr=blank,
            mask=mask,
            mask_json_path=Path("missing-mask.json"),
            raw_ocr_json_path=Path("missing-ocr.json"),
            roi_text_path=roi_text_path,
        )

        items = build_invoice_items_overlay(item)

    assert len(items) == 1
    assert items[0]["article"] == "A10/16"
    assert items[0]["vat_rate"] == "20%"
