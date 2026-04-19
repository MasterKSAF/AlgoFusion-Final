from __future__ import annotations

from pathlib import Path

import numpy as np

from src.modules.runtime_segmentation import build_segments_v2, hard_signal_doc_type, select_structure_profile
from src.modules.runtime_types import PageWorkItem


def _make_item(page_no: int, *, page_doc_type: str, has_title: bool, has_footer: bool, role_hint: str) -> PageWorkItem:
    return PageWorkItem(
        page_id=f"Doc__p{page_no:04d}",
        page_no=page_no,
        source_bgr=np.zeros((10, 10, 3), dtype=np.uint8),
        clean_bgr=np.zeros((10, 10, 3), dtype=np.uint8),
        no_lines_bgr=np.zeros((10, 10, 3), dtype=np.uint8),
        mask=np.zeros((10, 10), dtype=np.uint8),
        mask_json_path=Path("mask.json"),
        raw_ocr_json_path=Path("ocr.json"),
        signals={
            "blank": False,
            "page_doc_type": page_doc_type,
            "has_title": has_title,
            "has_footer": has_footer,
            "continuation_like": False,
            "role_hint": role_hint,
            "layout_type": "table",
            "scores": {page_doc_type: 5},
        },
    )


def test_build_segments_v2_marks_first_and_last_pages() -> None:
    items = [
        _make_item(1, page_doc_type="waybill", has_title=True, has_footer=False, role_hint="first_candidate"),
        _make_item(2, page_doc_type="waybill", has_title=False, has_footer=True, role_hint="last_candidate"),
    ]

    segments = build_segments_v2(items)

    assert len(segments) == 1
    assert segments[0]["doc_type"] == "waybill"
    assert items[0].page_role == "first"
    assert items[1].page_role == "last"


def test_hard_signal_doc_type_detects_invoice_without_regex_errors() -> None:
    item = _make_item(1, page_doc_type="invoice", has_title=True, has_footer=False, role_hint="first_candidate")
    item.signals.update(
        {
            "page_document_type_text": "Счет",
            "top_text": "Счет № 15 от 12.03.2026",
            "full_text": "Поставщик ООО Тест Покупатель ООО Клиент Основание договор",
        }
    )

    assert hard_signal_doc_type(item) in {"invoice", "waybill"}


def test_select_structure_profile_for_waybill_pages() -> None:
    first_item = _make_item(1, page_doc_type="waybill", has_title=True, has_footer=False, role_hint="first_candidate")
    first_item.segment_doc_type = "waybill"
    first_item.page_role = "first"

    next_item = _make_item(2, page_doc_type="waybill", has_title=False, has_footer=True, role_hint="last_candidate")
    next_item.segment_doc_type = "waybill"
    next_item.page_role = "last"

    assert select_structure_profile(first_item) == "waybill_first_table"
    assert select_structure_profile(next_item) == "waybill_continuation_table"
