from __future__ import annotations

from pathlib import Path

import numpy as np

from src.modules.runtime_invoice_vat_inference import infer_invoice_page_vat_rate
from src.modules.runtime_types import PageWorkItem


def test_infer_invoice_page_vat_rate_uses_repeated_ocr_rate_when_roi_is_missing() -> None:
    blank = np.zeros((10, 10, 3), dtype=np.uint8)
    mask = np.zeros((10, 10), dtype=np.uint8)
    item = PageWorkItem(
        page_id="p1",
        page_no=1,
        source_bgr=blank,
        clean_bgr=blank,
        no_lines_bgr=blank,
        mask=mask,
        mask_json_path=Path("missing-mask.json"),
        raw_ocr_json_path=Path("missing-ocr.json"),
        roi_text_path=Path("missing-roi.json"),
        ocr_items=[
            {"text": "VAT 20%", "bbox": [0, 0, 20, 10]},
            {"text": "Ставка 20%", "bbox": [0, 20, 30, 30]},
            {"text": "Льгота 10%", "bbox": [0, 40, 30, 50]},
        ],
    )

    assert infer_invoice_page_vat_rate(item) == "20%"
